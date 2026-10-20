"""Check TV folders for names Plex will not read as intended, and fix the ones that can be fixed.

Give it a season folder, a show folder (checks every season) or a library folder (checks every
show). For each season it looks for:

  - Extras named inline the old way, with a space after the hyphen ("Show - Title - Trailer.mkv")
    or by keyword ("Show - Trailer - Title.mkv", "Show - Tribute - Bonus.mkv",
    "Show - Deleted Scene 01.mkv"). They are moved into Plex extras folders:
        Show - Title - Trailer.mkv  ->  Trailers/Title.mkv
  - Extras folders with a name Plex does not know ("Extras", "Bonus Features", "trailer").
    They are renamed, e.g. "Bonus Features" -> "Other".
  - Files in extras folders that repeat the show name ("Trailers/Show - Title.mkv" -> "Trailers/Title.mkv").
  - Episodes not in "Show - s##e## - Title [YYYY-MM-DD]" form: the tag is padded to at least two
    digits and lower-cased (S2E3 -> s02e03; s01e101 and s01e04A are kept), any date moves to the
    end in brackets, and the parts are joined with " - ".
  - Easter eggs ("Show - Eggs - Title") go to Other and keep "Eggs" in the name.
  - Hyphens between words written as anything other than " - " ("Eggs- Title", "Title -Part"),
    in every video name. Hyphens inside words ("Catch-38") are kept.

Date-based episodes ("Show - 2013-08-12 - Title") are fine for Plex. Reported but not changed:
videos it cannot place, more than one date in a name, mistyped dates, tags with no "e"
("s0121B"), and disc folders that still need flattening. Folders starting with "_" are skipped.

Runs as a dry run unless --apply is given.
"""

import argparse
import functools
import re
import urllib.parse
from collections import Counter
from pathlib import Path

from episode_guide import _get, pick_show
from plex_utils import (EXTRA_FOLDERS, is_plex_inline_extra, is_video, safe_filename, show_and_season_from_folder,
                        split_inline_extra)

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
            if target_dir != p.name:
                yield p, folder / target_dir, [FOLDER_RENAMED]
            for f in sorted(x for x in p.iterdir() if is_video(x)):
                inline = split_inline_extra(f.stem, show)  # "Trailers/Title - Trailer" -> "Title"
                title = tidy(without_show(tidy(inline[1] if inline and inline[0] == target_dir else f.stem), show))
                if title != f.stem:
                    yield f, folder / target_dir / f"{safe_filename(title)}{f.suffix}", [MINOR]
            continue
        if not is_video(p) or is_plex_inline_extra(p.stem):
            continue
        if EPISODE_TAG.search(p.stem):
            new, problems = normalize_episode(p.stem)
            target = folder / f"{new}{p.suffix}"
            if new != p.stem:
                yield p, target, episode_changes(p.stem, new)
            for problem in problems:
                yield target, None, problem
            continue
        stem = tidy(p.stem)
        if extra := classify_extra(stem, show):
            yield p, folder / extra[0] / f"{safe_filename(extra[1])}{p.suffix}", [f"extra moved to {extra[0]}"]
            continue
        target = folder / f"{stem}{p.suffix}"
        if stem != p.stem:
            yield p, target, [MINOR]
        if ODD_TAG.search(stem):
            yield target, None, "season/episode not in s##e## form"
        elif not DATE_EPISODE.fullmatch(stem):
            yield target, None, "not an episode or a recognized extra"


def seasons_in(path: Path) -> list[Path]:
    """Season folders in a season, show or library folder."""
    if SEASON_FOLDER.fullmatch(path.name):
        return [path]
    children = sorted(d for d in path.iterdir() if d.is_dir() and not d.name.startswith("_"))
    seasons = [d for d in children if SEASON_FOLDER.fullmatch(d.name)]
    if seasons:
        return seasons
    return [s for d in children for s in sorted(x for x in d.iterdir() if x.is_dir() and SEASON_FOLDER.fullmatch(x.name))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="season, show or library folder")
    parser.add_argument("--show", help="show name (default: the season folder's parent, without the year)")
    parser.add_argument("--apply", action="store_true", help="actually rename (default is a dry run)")
    args = parser.parse_args()

    root = Path(args.folder)
    if not root.is_dir():
        parser.error(f"not a folder: {root}")
    seasons = seasons_in(root)
    if not seasons:
        parser.error(f"no season folders found in {root}")

    fixes = reports = clashes = 0
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
                fixes += 1
                kinds.update(rename[1])
                if args.apply:
                    season.rename(target)
                    season = target
                    findings = list(check_season(season, show))
        renamed_dirs: dict[Path, Path] = {}
        taken = [t.as_posix().lower() for _, t, _ in findings if t]
        for source, target, reason in findings:
            if target is None:
                print(f"CHECK  {source.relative_to(season)}  ({reason})")
                reports += 1
                continue
            source = renamed_dirs.get(source.parent, source.parent) / source.name
            same = source.as_posix().lower() == target.as_posix().lower()
            if (target.exists() and not same) or taken.count(target.as_posix().lower()) > 1:
                print(f"SKIP   {source.relative_to(season)}  (would overwrite {target.relative_to(season)})")
                clashes += 1
                continue
            print(f"RENAME {source.relative_to(season)}  ({'; '.join(reason)})\n    -> {target.relative_to(season)}")
            fixes += 1
            kinds.update(reason)
            if args.apply:
                target.parent.mkdir(exist_ok=True)
                source.rename(target)
                if target.is_dir():
                    renamed_dirs[source] = target
        print()

    action = "Renamed" if args.apply else "Would rename"
    print(f"{action} {fixes}; {reports} to check by hand; {clashes} skipped (name taken).")
    if not args.apply and fixes:
        print("Run again with --apply to rename.")
    if kinds:
        print("\nBy kind of fix (a rename can count under more than one):")
        order = [DATE_MOVED, TAG_FORMAT, MINOR, SEASON_PADDED, SEASON_YEAR, FOLDER_RENAMED]
        for kind in order + sorted(k for k in kinds if k not in order):
            if kinds[kind]:
                print(f"  {kinds[kind]:5}  {kind}")


if __name__ == "__main__":
    main()
