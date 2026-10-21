"""Check TV folders for names Plex will not read as intended, and fix the ones that can be fixed.

Give it a season folder, a show folder (checks every season) or a library folder (checks every
show). For each season it looks for:

  - Extras named inline the old way, with a space after the hyphen ("Show - Title - Trailer.mkv")
    or by keyword ("Show - Trailer - Title.mkv", "Show - Tribute - Bonus.mkv",
    "Show - Deleted Scene 01.mkv"). They are moved into Plex extras folders:
        Show - Title - Behind The Scenes.mkv  ->  Behind The Scenes/Title.mkv
  - Trailers, which belong in the show's Trailers folder, in a folder for their season, named
    without the show (the folders already tell Plex which show and season):
        Season 01/Show - Title - Trailer.mkv, Season 01/Trailers/Title.mkv  ->  Trailers/Season 01/Title.mkv
        Season 01/Show - Trailer.mkv                                        ->  Trailers/Season 01/Season 1 Trailer.mkv
        Season 01/Show (1998) - S01 - Title-trailer.mkv (the old layout)    ->  Trailers/Season 01/Title.mkv
    Trailers already there that repeat the show name lose it ("Show - Title.mkv" -> "Title.mkv").
  - Extras folders with a name Plex does not know ("Extras", "Bonus Features").
    They are renamed, e.g. "Bonus Features" -> "Other".
  - Files in extras folders that repeat the show name ("Trailers/Show - Title.mkv" -> "Trailers/Title.mkv").
  - Episodes not in "Show (1998) - s##e## - Title [YYYY-MM-DD]" form: the name starts with the show
    folder's name, year included; the tag is padded to at least two digits and lower-cased
    (S2E3 -> s02e03; s01e101 and s01e04A are kept), any date moves to the end in brackets, and the
    parts are joined with " - ". A name that starts with something other than the show is reported.
  - Easter eggs ("Show - Eggs - Title") go to Other and keep "Eggs" in the name.
  - Hyphens between words written as anything other than " - " ("Eggs- Title", "Title -Part"),
    in every video name. Hyphens inside words ("Catch-38") are kept.

  - Copy numbers added to dodge a name clash ("Title_2.mkv", up to 5 digits; --collision-suffix
    for another style). When the clean name is taken by the same video, the copy goes to
    _duplicates; by a different one, it is skipped for a person to compare.

Date-based episodes ("Show - 2013-08-12 - Title") get the show's year too, from the show folder:
"Show (2012) - 2013-08-12 - Title", so Plex matches the right show. Reported but not changed:
videos it cannot place, more than one date in a name, mistyped dates, tags with no "e"
("s0121B"), and disc folders that still need flattening. Folders starting with "_" are skipped.

With --movies MOVIES_ROOT it checks movie folders instead (see movie_names.py): the movie library
itself when the folder is MOVIES_ROOT, or a separate folder of trailers and bonus material, whose
extras are moved into their movie's folder under MOVIES_ROOT.

Runs as a dry run unless --apply is given.
"""

import argparse
import functools
import os
import re
import urllib.parse
from collections import Counter
from pathlib import Path

from episode_guide import _get, pick_show
from plex_utils import (DEFAULT_COLLISION_SUFFIX, EXTRA_FOLDERS, is_plex_inline_extra, is_video, safe_filename,
                        same_content, season_trailer_path, set_collision_suffix, show_and_season_from_folder,
                        show_label, split_inline_extra, strip_collision_suffix, strip_show, try_move,
                        remove_if_empty)

# A season/episode tag, however it is written: s1e3, S01E03, s01 e03, s01e4A (split episode).
EPISODE_TAG = re.compile(r"(?<![a-z0-9])s(\d{1,3})\s*e(\d{1,4})([a-z]?)(?![a-z0-9])", re.IGNORECASE)
# A tag with no "e" ("s0121B") cannot be read.
ODD_TAG = re.compile(r"(?<![a-z0-9])s\d{3,}[a-z]?(?![a-z0-9])", re.IGNORECASE)
EASTER_EGG = re.compile(r"easter eggs?|eggs?", re.IGNORECASE)
DATE = re.compile(r"[\[(]?(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)[\])]?")
SPLIT_DATE = re.compile(r"(?<!\d)(\d{4})\s*-\s*(\d{2})\s*-\s*(\d{2})(?!\d)")  # "1993 -02-19"
# A year counts as the date when it is bracketed, even half-bracketed: "(1949)", "[1948]", "1945]".
YEAR = re.compile(r"[\[(]\s*((?:19|20)\d{2})\s*[\])]?|(?<![\d-])((?:19|20)\d{2})\s*[\])]")
# Plex also reads date-based episodes: "Show - 2013-08-12 - Title".
DATE_EPISODE = re.compile(r".+? - \d{4}-\d{2}-\d{2}( - .+)?")
DATE_START = re.compile(r"\d{4}-\d{2}-\d{2}(?!\d)")  # a date-based name once the show is taken off
SEASON_FOLDER = re.compile(r"(season\s*\d+|specials)\b.*", re.IGNORECASE)
DISC_FOLDER = re.compile(r"(disc|disk|dvd|bd)\s*\d+.*", re.IGNORECASE)

# Words that mark an extra, and the Plex folder each one belongs in.
KEYWORDS = [
    (r"deleted scenes?|deleted|alternate endings?", "Deleted Scenes"),
    (r"behind the scenes|making of", "Behind The Scenes"),
    (r"featurettes?", "Featurettes"),
    (r"interviews?", "Interviews"),
    (r"trailers?|promos?|previews?|teasers?", "Trailers"),
    (r"bonus|extras?|special features?", "Other"),
]
# Folder names people use for extras, by their letters only ("Bonus Features" -> "bonusfeatures").
FOLDER_ALIASES = {"extra": "Other", "extras": "Other", "bonus": "Other", "bonusfeatures": "Other",
                  "specialfeatures": "Other", "features": "Featurettes", "trailer": "Trailers",
                  "deleted": "Deleted Scenes", "deletedscene": "Deleted Scenes", "behindthescene": "Behind The Scenes",
                  "featurette": "Featurettes", "interview": "Interviews", "short": "Shorts"}
SEGMENT_SPLIT = re.compile(r"\s+-\s*|\s*-\s+")


def plex_folder(name: str) -> str | None:
    """The Plex extras folder a folder name stands for, or None."""
    key = re.sub(r"[^a-z]", "", name.lower())
    for folder in EXTRA_FOLDERS.values():
        if key == re.sub(r"[^a-z]", "", folder.lower()):
            return folder
    return FOLDER_ALIASES.get(key)


def tidy(text: str, bracket_years: bool = True) -> str:
    """Hyphens between words as " - ", single spaces, " - " before a date, years in [] not (),
    and no hyphen left dangling at either end. Hyphens inside words ("Catch-38", "1998-07-12") are kept."""
    text = re.sub(r"\s+-\s*|\s*-\s+", " - ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"(?<=[^\s\[(-])\s+(?=\d{4}-\d{2}-\d{2}(?!\d))", " - ", text)  # "Show 2016-09-17" -> "Show - 2016-09-17"
    if bracket_years:
        text = re.sub(r"\(\s*((?:19|20)\d{2})\s*\)", r"[\1]", text)  # "(2017)" -> "[2017]"
    text = re.sub(r"( - )+", " - ", text)
    return re.sub(r"^[\s-]+|[\s-]+$", "", text)


def normalize_episode(stem: str) -> tuple[str, list[str]]:
    """'Show - s01e06 - Title [YYYY-MM-DD]' for a name with a season/episode tag, and any problems
    that need a look by hand."""
    problems = []
    stem = SPLIT_DATE.sub(r"\1-\2-\3", stem)
    pattern = DATE
    dates = list(dict.fromkeys(m[1] for m in DATE.finditer(stem)))
    if not dates:  # no full date: a bracketed year is the date
        pattern = YEAR
        dates = list(dict.fromkeys(m[1] or m[2] for m in YEAR.finditer(stem)))
    if len(dates) > 1:
        problems.append(f"more than one date ({', '.join(dates)})")
    if not dates and (bad := re.search(r"(?<!\d)(?:19|20)\d{2}\s*-\s*\d+(?:\s*-\s*\d+)?", stem)):
        problems.append(f"'{bad[0]}' looks like a mistyped date")
    keep = pattern is DATE  # with an air date, a year such as "(2017)" is part of the title: keep it as is
    text = tidy(pattern.sub(" - ", stem) if len(dates) == 1 else stem, not keep)
    m = EPISODE_TAG.search(text)
    tag = f"s{int(m[1]):02d}e{int(m[2]):02d}{m[3]}"  # at least two digits each; longer numbers kept
    parts = [tidy(text[:m.start()], not keep), tag, tidy(text[m.end():], not keep)]
    new = " - ".join(part for part in parts if part)
    return new + (f" [{dates[0]}]" if len(dates) == 1 else ""), problems


# What kind of fix a rename is, for the tally at the end.
DATE_MOVED = "date or year moved to the end in []"
TAG_FORMAT = "season/episode written as s##e##"
MINOR = "minor formatting (spaces, hyphens, brackets)"
FOLDER_RENAMED = "extras folder renamed"
TRAILER_MOVED = "trailer moved to the show's Trailers/Season ## folder"
SHOW_PREFIX = "show name and year put at the start"
# A trailer in the old layout, in the season folder: "Show (1998) - S01 - Pilot-trailer", "Show (1998) - S01-trailer".
OLD_TRAILER = re.compile(r"(.*?)-trailer\d*", re.IGNORECASE)
COLLISION = "copy number removed (_1)"
DUPLICATE = "copy moved to _duplicates"
SEASON_PADDED = "season folder numbered 01, 02, ... (sorts in order)"
SEASON_YEAR = "year removed from season folder (it belongs on the show folder)"
SEASON_NUMBER = re.compile(r"season\s*(\d+)(.*)", re.IGNORECASE)
SHOW_YEAR = re.compile(r"\((?:19|20)\d{2}\)\s*$")


@functools.cache
def tvmaze_show(name: str, year: int | None) -> dict | None:
    """The show on TVmaze with exactly this name (and start year, if known), or None."""
    try:
        found = pick_show(_get("/search/shows?q=" + urllib.parse.quote(name)), name, year)
    except (OSError, ValueError):
        return None
    letters = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())  # "Show: The Series" = "Show The Series"
    return found if found and letters(found["name"]) == letters(name) else None


def suggest_year(show: str) -> str:
    """The year TVmaze says the show started, as a hint for the report, or "" if unknown."""
    return ((tvmaze_show(show, None) or {}).get("premiered") or "")[:4]


def season_folder_name(name: str) -> tuple[str, list[str]] | None:
    """('Season 01', kinds of fix) for 'Season 1 (2003)'; None when the name is already right or not a
    season. Plex wants the year on the show folder only: a year on a season folder can break matching."""
    m = SEASON_NUMBER.fullmatch(name)
    if not m:
        return None
    rest = tidy(re.sub(r"[\[(]\s*(?:19|20)\d{2}\s*[\])]", "", m[2]))
    new = f"Season {int(m[1]):02d}" + (f" {rest}" if rest else "")
    kinds = ([SEASON_PADDED] if f"{int(m[1]):02d}" != m[1] else []) + ([SEASON_YEAR] if rest != tidy(m[2]) else [])
    return (new, kinds or [MINOR]) if new != name else None
SEPARATOR_SLIP = re.compile(r"\s{2,}|\S-\s|\s-\S|^[\s-]|[\s-]$")


def episode_changes(stem: str, new: str) -> list[str]:
    """The kinds of fix that turn episode name `stem` into `new`."""
    kinds = []
    old_tag, new_tag = EPISODE_TAG.search(stem), EPISODE_TAG.search(new)
    if old_tag[0] != new_tag[0]:
        kinds.append(TAG_FORMAT)
    if date := re.search(r" \[([\d-]+)\]$", new):
        if not stem.endswith(f"[{date[1]}]"):
            at_end = re.search(rf"[\[(]?\s*{re.escape(date[1])}\s*[\])]?$", stem)
            kinds.append(MINOR if at_end else DATE_MOVED)  # "(1949)" at the end only needs brackets
    before, after = stem[:old_tag.start()], stem[old_tag.end():]
    if (SEPARATOR_SLIP.search(stem) or SPLIT_DATE.sub(r"\1-\2-\3", stem) != stem
            or (before and not before.endswith(" - ")) or (after and not after.startswith((" - ", " [")))
            or not kinds):
        kinds.append(MINOR)
    return list(dict.fromkeys(kinds))


def prefix_change(name: str, label: str) -> list[str]:
    """The kind of fix that puts `label` ('Show (1998)') at the start of episode name `name`, if any."""
    if name.startswith(f"{label} - "):
        return []
    return [MINOR] if name.lower().startswith(label.lower()) else [SHOW_PREFIX]


def classify_extra(stem: str, show: str) -> tuple[str, str] | None:
    """(extras folder, title) for a video named as an extra in a way Plex does not read, else None."""
    segments = SEGMENT_SPLIT.split(stem)
    if len(segments) > 1 and segments[0].lower() == show.lower():
        segments = segments[1:]
    if any(EASTER_EGG.fullmatch(segment) for segment in segments):  # "Eggs - Title" keeps "Eggs"
        return "Other", " - ".join(segments)
    if inline := split_inline_extra(stem, show):
        return inline
    for pattern, folder in KEYWORDS:
        for i, segment in enumerate(segments):
            if re.fullmatch(pattern, segment, re.IGNORECASE):  # "Trailer - Title", "Title - Bonus"
                title = " - ".join(segments[:i] + segments[i + 1:]) or show
                # "Bonus - Making Me featurette": a specific word in the title beats a general one.
                specific = next((f for p, f in KEYWORDS[:-1] if re.search(rf"\b({p})\b", title, re.IGNORECASE)),
                                None) if folder == "Other" else None
                return specific or folder, title
    title = " - ".join(segments)
    for pattern, folder in KEYWORDS:
        if re.search(rf"\b({pattern})\b", title, re.IGNORECASE):  # "Deleted Scene 01"
            return folder, title
    return None


def without_show(stem: str, show: str) -> str:
    """'Show - Title' -> 'Title'; other names unchanged."""
    prefix = show.lower() + " - "
    return stem[len(prefix):] if stem.lower().startswith(prefix) and len(stem) > len(prefix) else stem


def season_trailer(folder: Path, show: str, title: str, suffix: str) -> Path:
    """Where a trailer for season folder `folder` goes: 'Show (1998)/Trailers/Season 01/Title.mkv'.
    A trailer titled only after the show gets 'Season 1 Trailer'."""
    season = show_and_season_from_folder(folder)[1] or 0
    title = "" if title.lower() in (show.lower(), show_label(folder, show).lower()) else title
    target = season_trailer_path(folder.parent, season, title)
    return target.with_name(target.name + suffix)


def old_trailer_title(stem: str, show: str) -> str:
    """The title in an old-layout trailer name: 'Show (1998) - S01 - Pilot-trailer' -> 'Pilot',
    'Show (1998) - S01-trailer' -> ''."""
    text = strip_show(OLD_TRAILER.fullmatch(stem)[1], show)
    return tidy(re.sub(r"^s\d+(?![a-z0-9])\s*-?\s*", "", text, flags=re.IGNORECASE))


def show_trailers(folder: Path, show: str):
    """Yield (source, target, kinds of fix) for trailers already in the show's Trailers folder for the
    season of `folder` whose name or season folder is not right, e.g. 'Trailers/Season 1/Show - Pilot.mkv'."""
    season = show_and_season_from_folder(folder)[1]
    trailers = folder.parent / "Trailers"
    if season is None or not trailers.is_dir():
        return
    for d in sorted(trailers.iterdir()):
        m = SEASON_NUMBER.fullmatch(d.name)
        if not d.is_dir() or not m or int(m[1]) != season:
            continue
        for f in sorted(x for x in d.iterdir() if is_video(x)):
            name = strip_collision_suffix(f.stem)
            target = season_trailer(folder, show, tidy(strip_show(tidy(name), show)), f.suffix)
            if target.as_posix() != f.as_posix():
                tidied = target.parent != f.parent or target.name != f"{name}{f.suffix}"
                yield f, target, ([COLLISION] if name != f.stem else []) + ([MINOR] if tidied else [])


def check_season(folder: Path, show: str):
    """Yield (source, target, kinds of fix) for each rename, and (source, None, reason) for each
    thing to check by hand, in one season folder."""
    for p in sorted(folder.iterdir()):
        if p.is_dir():
            if p.name.startswith("_"):
                continue
            target_dir = plex_folder(p.name)
            if DISC_FOLDER.fullmatch(p.name):
                yield p, None, "disc folder; run flatten_season.py"
                continue
            if target_dir is None:
                yield p, None, "unknown folder"
                continue
            if target_dir == "Trailers":  # trailers belong in the show's Trailers/Season ## folder
                for f in sorted(x for x in p.iterdir() if is_video(x)):
                    name = strip_collision_suffix(f.stem)
                    inline = split_inline_extra(name, show)  # "Trailers/Title - Trailer" -> "Title"
                    title = tidy(without_show(tidy(inline[1] if inline and inline[0] == target_dir else name), show))
                    yield f, season_trailer(folder, show, title, f.suffix), [TRAILER_MOVED]
                continue
            if target_dir != p.name:
                yield p, folder / target_dir, [FOLDER_RENAMED]
            for f in sorted(x for x in p.iterdir() if is_video(x)):
                name = strip_collision_suffix(f.stem)
                inline = split_inline_extra(name, show)  # "Trailers/Title - Trailer" -> "Title"
                title = tidy(without_show(tidy(inline[1] if inline and inline[0] == target_dir else name), show))
                if title != f.stem:
                    yield (f, folder / target_dir / f"{safe_filename(title)}{f.suffix}",
                           ([COLLISION] if name != f.stem else []) + ([MINOR] if title != name else []))
            continue
        if not is_video(p):
            continue
        name = strip_collision_suffix(p.stem)  # "Show - s01e01 - Pilot_2" is "Show - s01e01 - Pilot"
        numbered = [COLLISION] if name != p.stem else []
        if OLD_TRAILER.fullmatch(name):  # "Show (1998) - S01 - Pilot-trailer" in the season folder
            yield p, season_trailer(folder, show, old_trailer_title(name, show), p.suffix), [TRAILER_MOVED]
            continue
        if is_plex_inline_extra(name):
            if numbered:
                yield p, folder / f"{name}{p.suffix}", numbered
            continue
        if EPISODE_TAG.search(name):
            label = show_label(folder, show)
            rest = strip_show(name, show)  # "Show (1998) - s01e01 - Pilot" -> "s01e01 - Pilot"
            new_rest, problems = normalize_episode(rest)
            new = f"{label} - {new_rest}" if EPISODE_TAG.match(new_rest) else new_rest
            if not EPISODE_TAG.match(new_rest):
                problems.append(f"does not start with the show name; it should start '{label} - '")
            target = folder / f"{new}{p.suffix}"
            if new != p.stem:
                yield p, target, list(dict.fromkeys(
                    numbered + prefix_change(name, label) + (episode_changes(rest, new_rest) if new_rest != rest else [])))
            for problem in problems:
                yield target, None, problem
            continue
        stem = tidy(name)
        if extra := classify_extra(stem, show):
            if extra[0] == "Trailers":
                yield p, season_trailer(folder, show, extra[1], p.suffix), [TRAILER_MOVED]
            else:
                yield p, folder / extra[0] / f"{safe_filename(extra[1])}{p.suffix}", [f"extra moved to {extra[0]}"]
            continue
        rest = tidy(strip_show(name, show))  # "Show - 2013-08-12 - Title" -> "2013-08-12 - Title"
        if DATE_START.match(rest) and not ODD_TAG.search(rest):
            # Date-based episode: the show's year goes on the show name so Plex can match the show.
            label = show_label(folder, show)
            stem = f"{label} - {rest}"
            if stem != p.stem:
                tidied = rest != strip_show(name, show)
                yield p, folder / f"{stem}{p.suffix}", list(dict.fromkeys(
                    numbered + prefix_change(name, label) + ([MINOR] if tidied else [])))
            continue
        target = folder / f"{stem}{p.suffix}"
        if stem != p.stem:
            yield p, target, numbered + ([MINOR] if stem != name else [])
        if ODD_TAG.search(stem):
            yield target, None, "season/episode not in s##e## form"
        elif not DATE_EPISODE.fullmatch(stem):
            yield target, None, "not an episode or a recognized extra"
        else:
            yield target, None, (f"does not start with the show name; it should start "
                                 f"'{show_label(folder, show)} - '")
    yield from show_trailers(folder, show)


def seasons_in(path: Path) -> list[Path]:
    """Season folders in a season, show or library folder."""
    if SEASON_FOLDER.fullmatch(path.name):
        return [path]
    children = sorted(d for d in path.iterdir() if d.is_dir() and not d.name.startswith("_"))
    seasons = [d for d in children if SEASON_FOLDER.fullmatch(d.name)]
    if seasons:
        return seasons
    return [s for d in children if not plex_folder(d.name)  # not a show's "Trailers/Season 01"
            for s in sorted(x for x in d.iterdir() if x.is_dir() and SEASON_FOLDER.fullmatch(x.name))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="season, show or library folder; with --movies, the movie library "
                                       "or a folder of trailers and bonus material")
    parser.add_argument("--show", help="show name (default: the season folder's parent, without the year)")
    parser.add_argument("--movies", metavar="MOVIES_ROOT",
                        help="check movies instead of TV: the movie library folder that holds one folder per movie")
    parser.add_argument("--tv", metavar="TV_ROOT", help="with --movies: the TV library, so a TV show's trailer "
                                                        "named with its season ('Show S5 - Trailer') moves there")
    parser.add_argument("--corrections", metavar="FILE",
                        help="with --movies: typos and release years to fix (default data/movie_corrections.json)")
    parser.add_argument("--tiny-seconds", type=float, default=10,
                        help="with --movies: raw rips shorter than this go to '_Tiny clips' (default 10; 0 = off)")
    parser.add_argument("--collision-suffix", metavar="REGEX", default=DEFAULT_COLLISION_SUFFIX,
                        help="how copies were numbered to dodge a name clash, removed from the end of names "
                             r"(default '_\d{1,5}', as in 'Title_2.mkv'; e.g. ' \(\d+\)' for 'Title (2).mkv'; "
                             "'' to keep them)")
    parser.add_argument("--apply", action="store_true", help="actually rename (default is a dry run)")
    args = parser.parse_args()
    set_collision_suffix(args.collision_suffix)

    root = Path(args.folder)
    if not root.is_dir():
        parser.error(f"not a folder: {root}")
    if args.movies:
        import movie_names  # imports this module, so loaded only when needed
        movies = Path(args.movies)
        if not movies.is_dir():
            parser.error(f"not a folder: {movies}")
        if args.corrections and not Path(args.corrections).is_file():
            parser.error(f"corrections file not found: {args.corrections}")
        corrections = movie_names.load_corrections(Path(args.corrections) if args.corrections else None)
        movie_names.run(root, movies, args.apply, corrections, Path(args.tv) if args.tv else None, args.tiny_seconds)
        return
    seasons = seasons_in(root)
    if not seasons:
        parser.error(f"no season folders found in {root}")

    fixes = reports = clashes = failed = 0
    kinds: Counter[str] = Counter()
    no_year = [show for show in dict.fromkeys(s.parent for s in seasons) if not SHOW_YEAR.search(show.name)]
    if no_year:
        print("== Show folders")
        for show in no_year:
            year = suggest_year(show.name)
            hint = f"TVmaze says it started in {year}: '{show.name} ({year})'" if year else "add '(YYYY)'"
            print(f"CHECK  {show.name}  (show folder has no year; {hint})")
        reports += len(no_year)
        print()

    for season in seasons:
        show = safe_filename(args.show or show_and_season_from_folder(season)[0] or "")
        rename = season_folder_name(season.name)
        findings = list(check_season(season, show))
        if not findings and not rename:
            continue
        print(f"== {season}")
        if rename:
            target = season.with_name(rename[0])
            if target.exists() and target.name.lower() != season.name.lower():
                print(f"SKIP   season folder  (would overwrite {target.name})")
                clashes += 1
            else:
                print(f"RENAME season folder  ({'; '.join(rename[1])})\n    -> {target.name}")
                error = try_move(season, target) if args.apply else None
                if error:
                    print(f"FAILED season folder  ({error})")
                    failed += 1
                else:
                    fixes += 1
                    kinds.update(rename[1])
                    if args.apply:
                        season = target
                        findings = list(check_season(season, show))
        rel = lambda path: Path(os.path.relpath(path, season))  # "..\Trailers\Season 01\Pilot.mkv" for a trailer
        renamed_dirs: dict[Path, Path] = {}
        taken = [t.as_posix().lower() for _, t, _ in findings if t]
        for source, target, reason in findings:
            if target is None:
                print(f"CHECK  {rel(source)}  ({reason})")
                reports += 1
                continue
            source = renamed_dirs.get(source.parent, source.parent) / source.name
            same = source.as_posix().lower() == target.as_posix().lower()
            if target.exists() and not same and source.is_file() and target.is_file() and same_content(source, target):
                target, reason = season / "_duplicates" / source.name, [DUPLICATE]  # already there: a copy
            if (target.exists() and not same) or taken.count(target.as_posix().lower()) > 1:
                print(f"SKIP   {rel(source)}  (would overwrite {rel(target)})")
                clashes += 1
                continue
            print(f"RENAME {rel(source)}  ({'; '.join(reason)})\n    -> {rel(target)}")
            if args.apply and (error := try_move(source, target)):
                print(f"FAILED {rel(source)}  ({error})")
                failed += 1
                continue
            fixes += 1
            kinds.update(reason)
            if args.apply and target.is_dir():
                renamed_dirs[source] = target
        if args.apply:  # e.g. a Trailers folder whose trailers moved to the show's Trailers folder
            for d in season.iterdir():
                if d.is_dir() and plex_folder(d.name):
                    remove_if_empty(d)
            trailers = season.parent / "Trailers"
            for d in trailers.iterdir() if trailers.is_dir() else []:  # "Trailers/Season 1" renamed "Season 01"
                if d.is_dir() and SEASON_NUMBER.fullmatch(d.name):
                    remove_if_empty(d)
        print()

    action = "Renamed" if args.apply else "Would rename"
    print(f"{action} {fixes}; {reports} to check by hand; {clashes} skipped (name taken).")
    if failed:
        print(f"{failed} could not be renamed (FAILED lines above), usually because another program has the "
              f"file open (Plex, a player, Explorer's preview). Close it and run again.")
    if not args.apply and fixes:
        print("Run again with --apply to rename.")
    if kinds:
        print("\nBy kind of fix (a rename can count under more than one):")
        order = [SHOW_PREFIX, DATE_MOVED, TAG_FORMAT, MINOR, COLLISION, DUPLICATE, SEASON_PADDED, SEASON_YEAR, FOLDER_RENAMED]
        for kind in order + sorted(k for k in kinds if k not in order):
            if kinds[kind]:
                print(f"  {kinds[kind]:5}  {kind}")


if __name__ == "__main__":
    main()
