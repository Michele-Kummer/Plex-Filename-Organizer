"""Check movie folders for names Plex will not read as intended, and put extras where Plex finds them.

Run through check_names.py --movies MOVIES_ROOT. Plex wants each movie in its own folder,
"Title (Year) {edition-Name}", with extras in type folders inside it:

    Movies/Double Jeopardy (1999)/Double Jeopardy (1999).mp4
    Movies/Double Jeopardy (1999)/Behind The Scenes/Behind The Scenes Featurette.mp4
    Movies/Double Jeopardy (1999)/Trailers/Trailer.mp4

Given MOVIES_ROOT itself, it checks the library. Given another folder (one that holds trailers and
bonus material in movie folders of their own, loose files and a _Trailers folder), it moves each
named extra into its movie's folder under MOVIES_ROOT. Either way it fixes:

  - Folder and movie file names: the year before the edition ("Title {edition-X} (2002)" ->
    "Title (2002) {edition-X}"), edition tags written "{edition-X}" ("{Edition-X}", "{editon-X}",
    "{edition - X}", a missing brace), typos and wrong years or titles listed in
    data/movie_corrections.json, an empty "()", double spaces, stray semicolons, "Ii" for "II".
  - Extras: the movie name is dropped from the file name and the file goes in its type folder
    (Trailers, Behind The Scenes, Deleted Scenes, Featurettes, Interviews, Shorts, Other), found
    from words in the name; anything else goes in Other. A trailer for another movie in the library
    goes to that movie. A bonus folder ("Title - Bonus (1987)") is merged into its movie folder.
  - Studio intros ("Universal Intro.mkv") go to _Intros as "Intro - Universal.mkv" when there is one.
  - The same extra twice ("Title - Trailer.mkv" and "Title - Trailer_12.mp4", or two files with
    the same video): the .mp4 is kept and the other copy goes to _duplicates.
  - Raw rips (MakeMKV names like A1_t01.mkv) shorter than --tiny-seconds (menus, logos) go to
    "_Tiny clips" to look over and delete.
  - Copy numbers added to dodge a name clash ("Bruce Almighty (2003)_1.mp4", "C4_t04_2.mkv") are
    removed. If the clean name is taken by the same video, the copy goes to _duplicates; by a
    different video, it is reported, never numbered again.

Reported but not changed: other raw rips and numbered generic names ("Special Features (3)"),
which need watching to name; movies with no year; extras whose movie has no folder under
MOVIES_ROOT; trailers for TV shows (moved to the show's Trailers/Season ## folder with --tv
when the name has a season, "The Golden Girls S5 - Trailer"). "Plex Versions" folders and folders
starting with "_" are skipped.
"""

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from check_names import KEYWORDS, MINOR, SEGMENT_SPLIT, plex_folder, tidy
from plex_utils import (EXTRA_FOLDERS, durations, is_video, safe_filename, same_content, season_trailer_path,
                        remove_if_empty, strip_collision_suffix, try_move)

CORRECTIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "movie_corrections.json"

YEAR_TAG = re.compile(r"\(\s*((?:19|20)\d{2})?\s*\)")  # "(2001)", or an empty "()"
HALF_YEAR = re.compile(r"(?<=\s)((?:19|20)\d{2})\)")  # "The Sweetest Thing 2002)"
# Edition tags as people type them: "{Edition-X}", "{editon-X}", "{edition - X}", "{edition-X" or "edition-X}".
EDITION = re.compile(r"\{\s*ed[a-z]*\s*-\s*([^{}]*?)\s*(?:\}|$)|(?<![{\w])edition\s*-\s*([^{}]*?)\s*\}", re.IGNORECASE)
YEAR_AFTER_EDITION = re.compile(r"(\{edition-[^}]*\})\s*(\((?:19|20)\d{2}\))")
RAW_RIP = re.compile(r".*_t\d{2,3}(?:_\d+)?", re.IGNORECASE)  # MakeMKV: "A1_t01", "title_t03", "Disc_t02"
NUMBERED_GENERIC = re.compile(r"(?:(?:special|bonus|extra)\s*features?|bonus|extras?)\s*\(?\d+\)?", re.IGNORECASE)
VERSION_MARK = re.compile(r"(?:\s*(?:(?:part|side|disc|cd|movie|version)\s*\d+|\d+|_\d+|\([^)]*\)|\{[^}]*\}|-))*",
                          re.IGNORECASE)  # what may follow the title in the movie's own file name
STUDIOS = (r"lions ?gate|universal|walt disney(?: home entertainment)?|disney|buena vista(?: home entertainment)?|"
           r"warner bros\.?|warner brothers|morgan creek|paramount|dreamworks|20th century fox|columbia|sony|mgm|"
           r"new line|miramax|pixar|touchstone")
STUDIO_INTRO = re.compile(rf"intro\W+(?P<a>{STUDIOS})|(?P<b>{STUDIOS})\W+intro", re.IGNORECASE)
TV_SEASON = re.compile(r"(.+?)\s+s(\d{1,2})", re.IGNORECASE)  # "The Golden Girls S5"
BONUS_FOLDER = re.compile(r"(.+?)\s*-\s*(?:bonus(?: disc| features)?|extras|special features)", re.IGNORECASE)
ROMAN = {"Ii": "II", "Iii": "III", "Iv": "IV", "Vii": "VII", "Viii": "VIII"}
SKIP_DIRS = {"plex versions"}

# Words that mark an extra and its Plex folder; anything else is Other.
MOVIE_KEYWORDS = KEYWORDS[:-1] + [
    (r"(?:animated )?shorts?|cartoons?", "Shorts"),
    (r"bloopers?|gag reels?|outtakes?", "Other"),
    KEYWORDS[-1],
]
ANY_KEYWORD = "|".join(pattern for pattern, _ in MOVIE_KEYWORDS)

# What kind of fix an action is, for the tally at the end.
TYPO = "typo fixed"
EDITION_FIX = "edition tag written {edition-...}"
YEAR_ORDER = "year moved before the edition"
CORRECTED = "title or year corrected (data/movie_corrections.json)"
EMPTY_YEAR = "empty () filled from the folder or removed"
MERGED = "bonus folder merged into its movie folder"
INTRO = "studio intro moved to _Intros"
DUPLICATE = "copy moved to _duplicates"
COLLISION = "copy number removed (_1)"
TINY = "short raw rip moved to _Tiny clips"
TV_TRAILER = "TV trailer moved to the show's Trailers/Season ## folder"
NAME_KINDS = [YEAR_ORDER, EDITION_FIX, TYPO, CORRECTED, EMPTY_YEAR, MINOR, MERGED]


@dataclass
class Corrections:
    words: dict[str, str] = field(default_factory=dict)  # misspelled word (lower case) -> right spelling
    movies: dict[str, tuple[str, int | None]] = field(default_factory=dict)  # title key -> (title, year)


def key(title: str) -> str:
    """Letters and digits only, for comparing titles: 'The Cat in the Hat' = 'Cat In The Hat'."""
    text = re.sub(r"^the\s+", "", title.lower().replace("&", "and"))
    return re.sub(r"[^a-z0-9]", "", text)


def fix_words(text: str, words: dict[str, str]) -> str:
    """Misspelled words fixed ('Rembering' -> 'Remembering') and 'Ii' -> 'II'."""
    def one(m: re.Match) -> str:
        word = m[0]
        if word in ROMAN:
            return ROMAN[word]
        right = words.get(word.lower())
        if right is None:
            return word
        return right.upper() if word.isupper() and len(word) > 1 else right
    return re.sub(r"[A-Za-z]+", one, text)


def tidy_name(text: str) -> str:
    """Single spaces, " - " between words, no stray semicolons or spaces before a period."""
    text = re.sub(r"\s*;\s*", " ", text)
    text = re.sub(r"\s+(?=[.,](?:\s|$))", "", text)  # "Dr . Seuss" -> "Dr. Seuss"
    return tidy(text, bracket_years=False)


def load_corrections(path: Path | None = None) -> Corrections:
    path = path or CORRECTIONS_FILE
    if not path.is_file():
        return Corrections()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    corrections = Corrections(words={k.lower(): v for k, v in data.get("words", {}).items()})
    for old, new in data.get("movies", {}).items():
        m = YEAR_TAG.search(new)
        title = new[:m.start()].strip() if m else new.strip()
        corrections.movies[key(fix_words(old, corrections.words))] = (title, int(m[1]) if m and m[1] else None)
    return corrections


@dataclass
class Fixed:
    name: str
    kinds: list[str]
    title: str
    year: int | None


def fix_name(name: str, corrections: Corrections, folder_year: int | None = None,
             folder_keys: tuple[str, ...] = ()) -> Fixed:
    """The name as Plex wants it, 'Title (Year) {edition-X} rest', and the kinds of fix.
    An empty '()' takes folder_year when the title is the folder's (one of folder_keys)."""
    kinds = []
    text = fix_words(name, corrections.words)
    if text != name:
        kinds.append(TYPO)
    new = EDITION.sub(lambda m: "{edition-" + (m[1] if m[1] is not None else m[2]).strip() + "}", text)
    if new != text:
        kinds.append(EDITION_FIX)
    text, new = new, YEAR_AFTER_EDITION.sub(r"\2 \1", new)
    if new != text:
        kinds.append(YEAR_ORDER)
    text, new = new, tidy_name(HALF_YEAR.sub(r"(\1)", new))
    if new != text:
        kinds.append(MINOR)
    text = new

    cut = re.search(r"\(\s*(?:(?:19|20)\d{2})?\s*\)|\{|\[", text)
    title, tail = (text[:cut.start()].rstrip(), text[cut.start():]) if cut else (text, "")
    year_tag = YEAR_TAG.match(tail)
    year = int(year_tag[1]) if year_tag and year_tag[1] else None
    after = tail[year_tag.end():] if year_tag else tail
    if (fix := corrections.movies.get(key(title))) and (fix[0].lower() != title.lower() or (fix[1] and fix[1] != year)):
        title, year = fix[0], fix[1] or year
        kinds.append(CORRECTED)
    if year_tag and not year_tag[1]:
        kinds.append(EMPTY_YEAR)
        if folder_year and key(title) in folder_keys:
            year = folder_year
    new = title + (f" ({year})" if year else "")
    if after:
        new += after if after[0] in " _" else " " + after
    new = safe_filename(tidy_name(new))
    return Fixed(new, list(dict.fromkeys(kinds)) if new != name else [], title, year)


def strip_title(stem: str, titles: list[str]) -> str:
    """The extra's own name, without the movie's name, year and edition in front:
    'The Wizard of Oz (1939) {edition-X}_The Making Of' -> 'The Making Of'."""
    for title in titles:
        words = re.findall(r"[a-z0-9]+", re.sub(r"^the\s+", "", title.lower()))
        if not words:
            continue
        pattern = (r"\W*(?:the\W+)?" + r"\W*".join(map(re.escape, words)) +
                   r"(?![a-z0-9])(?:\s*\(\s*(?:\d{4})?\s*\))?(?:\s*\{[^}]*\}?)?[\s_\-;:.,]*")
        if m := re.match(pattern, stem, re.IGNORECASE):
            return stem[m.end():]
    return stem


def classify(text: str) -> tuple[str, str]:
    """(Plex extras folder, title) for an extra named `text` (the movie name already dropped)."""
    segments = SEGMENT_SPLIT.split(text)
    for pattern, folder in MOVIE_KEYWORDS:
        for i, segment in enumerate(segments):
            if re.fullmatch(pattern, segment, re.IGNORECASE):  # "Trailer", "Deleted Scenes - Part 2"
                rest = " - ".join(segments[:i] + segments[i + 1:])
                if folder == "Other" and rest:  # "Bonus - Making Of": the specific word wins
                    folder = next((f for p, f in MOVIE_KEYWORDS if f != "Other"
                                   and re.search(rf"\b(?:{p})\b", rest, re.IGNORECASE)), folder)
                return folder, rest or segment[:1].upper() + segment[1:]
    for pattern, folder in MOVIE_KEYWORDS:
        if re.search(rf"\b(?:{pattern})\b", text, re.IGNORECASE):  # "Behind The Scenes Featurette"
            return folder, text
    return "Other", text


@dataclass
class Movie:
    path: Path
    title: str
    year: int | None

    @property
    def key(self) -> str:
        return key(self.title)


def index_movies(folder: Path, corrections: Corrections) -> list[Movie]:
    """The movie folders in `folder`, by their fixed title and year."""
    movies = []
    for d in sorted(folder.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and d.name.lower() not in SKIP_DIRS:
            fixed = fix_name(d.name, corrections)
            movies.append(Movie(d, fixed.title, fixed.year))
    return movies


def find_movie(movies: list[Movie], title: str, year: int | None, corrections: Corrections,
               contains: bool = False) -> Movie | None:
    """The movie titled `title`: the same title (and year, when more than one has it), or with a year,
    the one whose title ends with it ('Twilight (2008)' -> 'The Twilight Saga Twilight (2008)').
    With `contains`, also the one whose title the name contains ('Trailers from Into the Woods (2014)')."""
    if fix := corrections.movies.get(key(title)):
        title, year = fix[0], fix[1] or year
    k = key(title)
    if not k:
        return None
    same = [m for m in movies if m.key == k]
    if year and len([m for m in same if m.year == year]) == 1:
        return next(m for m in same if m.year == year)
    if len(same) == 1:
        return same[0]
    if year:
        near = [m for m in movies if m.year == year and len(m.key) >= 4
                and (m.key.endswith(k) or (contains and m.key in k))]
        if len(near) == 1:
            return near[0]
    return None


def match_name(stem: str, movies: list[Movie], corrections: Corrections) -> tuple[Movie | None, str]:
    """(movie, the extra's own name) for a loose file such as 'Trolls (2016) - Deleted Scenes' or
    'Happy Feet Trailer'. The movie is None when no movie folder fits."""
    text = strip_collision_suffix(stem)
    year_tag = YEAR_TAG.search(text)
    year = int(year_tag[1]) if year_tag and year_tag[1] else None
    if year_tag:
        text = text[:year_tag.start()] + text[year_tag.end():]
    text = tidy_name(fix_words(text, corrections.words))
    segments = SEGMENT_SPLIT.split(text)
    for n in range(len(segments), 0, -1):
        title, rest = " - ".join(segments[:n]), segments[n:]
        if movie := find_movie(movies, title, year, corrections):
            return movie, " - ".join(rest)
        if glued := re.fullmatch(rf"(.+?)\s+((?:{ANY_KEYWORD})\b.*)", title, re.IGNORECASE):  # "Happy Feet Trailer"
            if movie := find_movie(movies, glued[1], year, corrections):
                return movie, " - ".join([glued[2]] + rest)
    if year and (movie := find_movie(movies, text, year, corrections, contains=True)):  # "Multiple trailers from Into the Woods"
        return movie, text
    return None, text


def split_copies(files: list[Path]) -> tuple[list[Path], list[Path]]:
    """(files to keep, copies) among files with the same name once a copy number is removed
    ('X.mkv', 'X_12.mp4', 'X_13.mp4'). A copy is the same name in another format, or the same video
    data. The .mp4 is kept (the library's format), or else the largest."""
    groups: dict[str, list[Path]] = {}
    for f in files:
        groups.setdefault(strip_collision_suffix(f.stem).casefold(), []).append(f)
    keep, copies = [], []
    for group in groups.values():
        best = max(group, key=lambda f: (f.suffix.lower() == ".mp4", f.stat().st_size, -len(f.stem)))
        keep.append(best)
        for f in group:
            if f is best:
                continue
            if f.suffix.lower() != best.suffix.lower() or same_content(f, best):
                copies.append(f)
            else:
                keep.append(f)
    return sorted(keep), sorted(copies)


def studio_intro(text: str) -> str | None:
    """The studio for a studio logo clip ('Universal Intro', 'Intro - Lionsgate'), else None."""
    m = STUDIO_INTRO.fullmatch(text.strip())
    return (m["a"] or m["b"]) if m else None


class Planner:
    """Works out what to do with one folder (the movie library or a folder of extras)."""

    def __init__(self, folder: Path, root: Path, corrections: Corrections, tv_root: Path | None = None,
                 tiny_seconds: float = 10):
        self.folder, self.root, self.corrections = folder, root, corrections
        self.tv_root, self.tiny_seconds = tv_root, tiny_seconds
        self.library = os.path.normcase(str(folder.resolve())) == os.path.normcase(str(root.resolve()))
        self.movies = index_movies(root, corrections)
        self.local = self.movies if self.library else index_movies(folder, corrections)
        self.claimed: set[str] = set()
        self.actions: list[tuple[str, Path, Path | None, list[str] | str]] = []

    # -- output ---------------------------------------------------------------------------------
    def add(self, section: str, source: Path, target: Path | None, reason: list[str] | str) -> None:
        self.actions.append((section, source, target, reason))

    def free(self, target: Path, source: Path | None = None) -> Path:
        """`target`, or 'Name 2.ext', 'Name 3.ext', ... when another file has (or will have) that name."""
        n, path = 1, target  # a target holding the same video is no clash: the run sends the copy to _duplicates
        while (path.as_posix().lower() in self.claimed
               or (path.exists() and (source is None or path.resolve() != source.resolve())
                   and not (source and path.is_file() and same_content(source, path)))):
            n += 1
            path = target.with_name(f"{target.stem} {n}{target.suffix}")
        self.claimed.add(path.as_posix().lower())
        return path

    # -- planning -------------------------------------------------------------------------------
    def plan(self) -> list:
        for d in sorted(self.folder.iterdir()):
            if d.is_dir() and not d.name.startswith("_") and d.name.lower() not in SKIP_DIRS:
                self.plan_movie_folder(d)
        loose = [f for f in sorted(self.folder.iterdir()) if is_video(f)]
        trailers = self.folder / "_Trailers"
        if trailers.is_dir():
            loose += [f for f in sorted(trailers.iterdir()) if is_video(f)]
        if loose:
            self.plan_loose(loose)
        return self.actions

    def plan_movie_folder(self, d: Path) -> None:
        section = d.name
        fixed = fix_name(d.name, self.corrections)
        title, year, new_name, kinds = fixed.title, fixed.year, fixed.name, fixed.kinds
        if bonus := BONUS_FOLDER.fullmatch(title):  # "Dirty Dancing - Bonus (1987)"
            title = bonus[1]
            new_name = fix_name(title + new_name[len(fixed.title):], self.corrections).name
            kinds = [MERGED]
        home = d.with_name(new_name)
        merging = bonus is not None and home.is_dir() and home != d
        if new_name != d.name and not merging:
            self.add(section, d, home, kinds)
        if year is None:
            self.add(section, d, None, "no year in the name; Plex matches movies by title and year, add '(YYYY)'")
        if self.library:
            movie_dir = home
        else:
            found = find_movie(self.movies, title, year, self.corrections)
            movie_dir = found.path if found else None
            if not found:
                self.add(section, d, None, f"no movie folder for '{title}' in {self.root}; its extras stay here")

        titles = list(dict.fromkeys([fix_name(d.name, Corrections()).title, title]))
        keys = tuple(key(t) for t in titles)
        files = [f for f in sorted(d.iterdir()) if is_video(f)]
        main = [f for f in files if self.library and self.is_main(f, titles, year)]
        rips, generic, extras = [], [], []
        for f in files:
            stem = strip_collision_suffix(f.stem)
            if f in main:
                new = fix_name(stem, self.corrections, year, keys)
                if stem.lower() == d.name.lower() and new_name != d.name:  # named like the folder: keep it so
                    new = Fixed(new_name, kinds, title, year)
                if new.name != f.stem:
                    found = ([COLLISION] if stem != f.stem else []) + (new.kinds if new.name != stem else [])
                    self.rename(section, f, home / f"{new.name}{f.suffix}", found or [MINOR])
                continue
            if RAW_RIP.fullmatch(stem):
                rips.append(f)
                continue
            text = tidy_name(strip_title(fix_words(stem, self.corrections.words), titles))
            other_year = YEAR_TAG.search(stem)
            if (self.library and other_year and other_year[1] and year and int(other_year[1]) != year
                    and not re.search(rf"\b(?:{ANY_KEYWORD})\b", text, re.IGNORECASE)):
                self.add(section, f, None, f"another movie ({other_year[1]})? Give it its own folder")
                continue
            if not text:
                self.add(section, f, None, "looks like the movie itself, not an extra")
            elif NUMBERED_GENERIC.fullmatch(text):
                generic.append(f)
            else:
                extras.append((f, text))
        if self.library and files and not main and extras:
            self.add(section, d, None, "no file named after the movie; extras left as they are")
            extras = []

        keep, copies = split_copies([f for f, _ in extras])
        for f in copies:
            self.add(section, f, self.free(self.folder / "_duplicates" / d.name / f.name), [DUPLICATE])
        for f, text in extras:
            if f in keep:
                self.plan_extra(section, f, text, movie_dir, d)

        for sub in sorted(x for x in d.iterdir() if x.is_dir()):
            if sub.name.startswith("_") or sub.name.lower() in SKIP_DIRS:
                continue
            self.plan_extras_folder(section, sub, titles, movie_dir)

        self.plan_rips(section, rips, d, home if merging else None)
        if generic:
            self.add(section, d, None, f"{len(generic)} numbered generic name(s) like '{generic[0].name}'; "
                                       f"watch them, then name each one and put it in its type folder")
            if merging:
                for f in generic:
                    self.add(section, f, self.free(home / f.name, f), [MERGED])

    def is_main(self, f: Path, titles: list[str], year: int | None) -> bool:
        """True for the movie's own video (or one of its parts or versions), not an extra."""
        stem = strip_collision_suffix(f.stem)
        if RAW_RIP.fullmatch(stem):
            return False
        fixed = fix_name(stem, self.corrections)
        if year and fixed.year == year:
            return True
        stripped = strip_title(fix_words(stem, self.corrections.words), titles)
        return stripped != stem and VERSION_MARK.fullmatch(stripped) is not None

    def rename(self, section: str, f: Path, target: Path, kinds: list[str]) -> None:
        """Rename f to target. When the name is taken, an identical file makes f a copy for _duplicates;
        a different one needs a person (no number is added to dodge the clash)."""
        taken = target.as_posix().lower() in self.claimed
        if taken or (target.exists() and target.resolve() != f.resolve()):
            if not taken and target.is_file() and same_content(f, target):
                self.add(section, f, self.free(self.folder / "_duplicates" / f.relative_to(self.folder)), [DUPLICATE])
            else:
                self.add(section, f, None, f"would be named {target.name}, which another file has; "
                                           f"compare them and rename or delete one")
            return
        self.claimed.add(target.as_posix().lower())
        self.add(section, f, target, kinds)

    def plan_extra(self, section: str, f: Path, text: str, movie_dir: Path | None, d: Path) -> None:
        if studio := studio_intro(text):
            self.plan_intro(section, f, studio)
            return
        kind, title = classify(text)
        if kind == "Trailers":  # a trailer for another movie belongs with that movie
            name = re.sub(rf"\s*-?\s*\b(?:trailers?|teasers?|previews?|promos?)\b\s*(?:\d+)?\s*$", "", title,
                          flags=re.IGNORECASE)
            other = find_movie(self.movies, name, None, self.corrections) if name else None
            if other and other.path != movie_dir:
                self.add(section, f, self.free(other.path / "Trailers" / f"{safe_filename(title)}{f.suffix}"),
                         [f"trailer moved to {other.path.name}"])
                return
            mine = find_movie(self.local, name, None, self.corrections) if name and not self.library else None
            if mine and mine.path != d:
                self.add(section, f, None, f"trailer for {mine.path.name}, which has no folder in {self.root}")
                return
        if movie_dir is None:
            return
        target = movie_dir / kind / f"{safe_filename(title)}{f.suffix}"
        if target.as_posix().lower() != f.as_posix().lower():
            self.add(section, f, self.free(target, f), [f"extra moved to {kind}"])

    def plan_extras_folder(self, section: str, sub: Path, titles: list[str], movie_dir: Path | None) -> None:
        kind = plex_folder(sub.name)
        if kind is None:
            self.add(section, sub, None, "unknown folder")
            return
        generic = sub.name not in EXTRA_FOLDERS.values() and kind == "Other"  # "Special Features", "Bonus"
        for f in sorted(x for x in sub.iterdir() if is_video(x)):
            stem = strip_collision_suffix(f.stem)
            text = tidy_name(strip_title(fix_words(stem, self.corrections.words), titles)) or stem
            folder, title = classify(text) if generic else (kind, text)
            if movie_dir is None:
                continue
            target = movie_dir / folder / f"{safe_filename(title)}{f.suffix}"
            if target.as_posix().lower() != f.as_posix().lower():
                self.add(section, f, self.free(target, f), [f"extra moved to {folder}"] if folder != sub.name
                         or not self.library else [MINOR])

    def plan_intro(self, section: str, f: Path, studio: str) -> None:
        intros = self.folder / "_Intros"
        if not intros.is_dir():
            self.add(section, f, None, f"studio intro ({studio}); keep it with your other intros")
            return
        stem = f"Intro - {studio}"
        if any(x.stem.lower() == stem.lower() for x in intros.iterdir()):
            self.add(section, f, self.free(self.folder / "_duplicates" / "_Intros" / f"{stem}{f.suffix}"), [DUPLICATE])
        else:
            self.add(section, f, self.free(intros / f"{stem}{f.suffix}"), [INTRO])

    def plan_rips(self, section: str, rips: list[Path], d: Path, merge_into: Path | None) -> None:
        if not rips:
            return
        tiny = set()
        if self.tiny_seconds > 0:
            small = [f for f in rips if f.stat().st_size < 50_000_000]
            lengths = durations(small)
            tiny = {f for f in small if (lengths[f] is not None and lengths[f] < self.tiny_seconds)
                    or (lengths[f] is None and f.stat().st_size < 1_000_000)}
        name = lambda f: strip_collision_suffix(f.stem) + f.suffix  # "C4_t04_2.mkv" -> "C4_t04.mkv"
        for f in sorted(tiny):
            self.add(section, f, self.free(self.folder / "_Tiny clips" / d.name / name(f)), [TINY])
        rest = [f for f in rips if f not in tiny]
        for f in rest:
            if merge_into:  # "Bonus A1_t00.mkv": kept apart from the movie disc's own rips
                self.rename(section, f, merge_into / f"Bonus {name(f)}", [MERGED])
            elif name(f) != f.name:
                self.rename(section, f, f.with_name(name(f)), [COLLISION])
        if rest:
            sample = ", ".join(f.name for f in rest[:3]) + (", ..." if len(rest) > 3 else "")
            self.add(section, merge_into or d, None, f"{len(rest)} raw rip name(s) ({sample}); "
                                                     f"watch them, then name each one and put it in its type folder")

    def plan_loose(self, files: list[Path]) -> None:
        section = "Loose files and _Trailers"
        keep, copies = split_copies(files)
        for f in copies:
            self.add(section, f, self.free(self.folder / "_duplicates" / f.relative_to(self.folder)), [DUPLICATE])
        for f in keep:
            in_trailers = f.parent.name == "_Trailers"
            movie, text = match_name(f.stem, self.movies, self.corrections)
            if movie is None:
                self.plan_unmatched(section, f, text)
                continue
            if studio := studio_intro(text):
                self.plan_intro(section, f, studio)
                continue
            kind, title = classify(text) if text else ("Other", "")
            if in_trailers:
                kind = "Trailers"
            title = title or ("Trailer" if kind == "Trailers" else "Bonus")
            self.add(section, f, self.free(movie.path / kind / f"{safe_filename(title)}{f.suffix}", f),
                     [f"extra moved to {kind}"])

    def plan_unmatched(self, section: str, f: Path, text: str) -> None:
        first = SEGMENT_SPLIT.split(text)[0]
        if tv := TV_SEASON.fullmatch(first):  # "The Golden Girls S5 - Trailer"
            show, season = tv[1], int(tv[2])
            show_dir = self.tv_show(show)
            if show_dir:
                target = season_trailer_path(show_dir, season)
                self.add(section, f, self.free(target.with_name(target.name + f.suffix)), [TV_TRAILER])
            else:
                self.add(section, f, None, f"trailer for TV show '{show}' season {season}; put it in the show folder as "
                                           f"'Trailers/Season {season:02d}/Season {season} Trailer{f.suffix}'")
            return
        self.add(section, f, None, f"no movie folder for '{first}' in {self.root}"
                                   f" (if it is a TV show, put it in the show folder as 'Trailers/Season 01/Season 1 Trailer')")

    def tv_show(self, show: str) -> Path | None:
        if not self.tv_root or not self.tv_root.is_dir():
            return None
        found = [d for d in self.tv_root.iterdir()
                 if d.is_dir() and key(re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", d.name)) == key(show)]
        return found[0] if len(found) == 1 else None


def run(folder: Path, root: Path, apply: bool, corrections: Corrections | None = None,
        tv_root: Path | None = None, tiny_seconds: float = 10) -> None:
    corrections = corrections or load_corrections()
    planner = Planner(folder, root, corrections, tv_root, tiny_seconds)
    actions = planner.plan()

    def show(p: Path) -> str:
        try:
            return str(p.relative_to(folder))
        except ValueError:
            return str(p)

    renamed: dict[Path, Path] = {}
    kept: dict[str, tuple[Path, Path]] = {}  # section -> (new name, old name) of a folder rename skipped

    def remap(p: Path, section: str | None = None) -> Path:
        moves = list(renamed.items()) + ([kept[section]] if section in kept else [])
        for old, new in moves:
            if p == old or old in p.parents:
                return new / p.relative_to(old)
        return p

    fixes = reports = clashes = failed = 0
    kinds: Counter[str] = Counter()
    emptied: set[Path] = set()
    current = None
    for section, source, target, reason in actions:
        if section != current:
            print(f"\n== {section}")
            current = section
        if target is None:
            print(f"CHECK  {show(remap(source, section))}  ({reason})")
            reports += 1
            continue
        source, target = remap(source, section), remap(target, section)
        same = source.as_posix().lower() == target.as_posix().lower()
        if target.exists() and not same and source.is_file() and target.is_file() and same_content(source, target):
            target = folder / "_duplicates" / (source.relative_to(folder) if folder in source.parents else source.name)
            reason = [DUPLICATE]  # that extra is already there: this one is a copy
        if target.exists() and not same:
            print(f"SKIP   {show(source)}  (would overwrite {show(target)})")
            clashes += 1
            if source.is_dir():  # what this folder planned under its new name stays under the old one
                kept[section] = (target, source)
            continue
        verb = "RENAME" if source.parent == target.parent else "MOVE  "
        print(f"{verb} {show(source)}  ({'; '.join(reason)})\n    -> {show(target)}")
        is_dir = source.is_dir()
        if apply and (error := try_move(source, target)):
            print(f"FAILED {show(source)}  ({error})")
            failed += 1
            continue
        fixes += 1
        kinds.update(reason)
        if is_dir:
            renamed[source] = target
        if apply:
            emptied.add(source.parent)

    if apply:  # remove folders the moves left empty (e.g. a merged bonus folder, a "Special Features" folder)
        for d in sorted(emptied, key=lambda p: len(p.parts), reverse=True):
            d = remap(d)
            if d not in (folder, root):
                remove_if_empty(d)

    action = "Changed" if apply else "Would change"
    print(f"\n{action} {fixes}; {reports} to check by hand; {clashes} skipped (name taken).")
    if failed:
        print(f"{failed} could not be changed (FAILED lines above), usually because another program has the "
              f"file open (Plex, a player, Explorer's preview). Close it and run again.")
    if not apply and fixes:
        print("Run again with --apply to make the changes.")
    if kinds:
        print("\nBy kind of fix (a change can count under more than one):")
        for kind in NAME_KINDS + sorted(k for k in kinds if k not in NAME_KINDS):
            if kinds[kind]:
                print(f"  {kinds[kind]:5}  {kind}")
