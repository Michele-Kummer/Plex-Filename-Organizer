"""Helpers shared by the Plex filename scripts."""

import re
import shutil
import subprocess
from pathlib import Path

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".m2ts", ".webm"}

# Plex local-extras suffixes, e.g. "Show - Title - Trailer.mkv".
EXTRA_SUFFIXES = ("trailer", "behindthescenes", "deleted", "featurette", "interview",
                  "scene", "short", "other", "behind the scenes")

# Plex extras folders inside a season folder, by extra type, e.g. "Season 03/Trailers/Pilot.mkv".
EXTRA_FOLDERS = {"trailer": "Trailers", "behindthescenes": "Behind The Scenes", "deleted": "Deleted Scenes",
                 "featurette": "Featurettes", "interview": "Interviews", "scene": "Scenes",
                 "short": "Shorts", "other": "Other"}

_INLINE_EXTRA = re.compile(r"(.*?)\s*-\s*(trailer|behind ?the ?scenes|deleted|featurette|interview|scene|short|other)",
                           re.IGNORECASE)

# Plex's own inline extra names: the type straight after a hyphen, "Pilot - Scene 16-deleted.mkv".
_PLEX_INLINE_EXTRA = re.compile(r".*\S-(trailer|behindthescenes|deleted|featurette|interview|scene|short|other)\d*",
                                re.IGNORECASE)

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


def safe_filename(text: str) -> str:
    """Drop characters Windows does not allow in filenames ("Part: Two" -> "Part - Two")."""
    text = re.sub(r"\s*:\s*", " - ", text)
    return re.sub(r"\s+", " ", _INVALID_CHARS.sub("", text)).strip() or "Untitled"


def is_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def is_extra(path: Path) -> bool:
    stem = path.stem.lower()
    return any(stem.endswith("-" + s) or stem.endswith(" - " + s) for s in EXTRA_SUFFIXES)


def extra_folder(kind: str) -> str:
    """Plex extras folder for an extra type: "Trailer" -> "Trailers". Raises KeyError if unknown."""
    return EXTRA_FOLDERS[kind.lower().replace(" ", "")]


def is_extras_folder(name: str) -> bool:
    return name.lower() in {f.lower() for f in EXTRA_FOLDERS.values()}


def is_plex_inline_extra(stem: str) -> bool:
    """True for names Plex already reads as extras, e.g. "Show - s06e20 - Title - Ending 1-deleted"."""
    return bool(_PLEX_INLINE_EXTRA.fullmatch(stem))


def split_inline_extra(stem: str, show: str) -> tuple[str, str] | None:
    """(extras folder, title) for an old-style name like "Show - Pilot - Trailer", else None."""
    m = _INLINE_EXTRA.fullmatch(stem)
    if not m:
        return None
    title = m.group(1)
    if title.lower().startswith(show.lower() + " - "):
        title = title[len(show) + 3:]
    return extra_folder(m.group(2)), title.strip() or "Untitled"


def _parse_duration(text: str) -> float | None:
    text = text.strip()
    if m := re.fullmatch(r"(\d+):(\d{2}):(\d{2})", text):
        h, mi, s = map(int, m.groups())
        return h * 3600 + mi * 60 + s
    if m := re.fullmatch(r"([\d.]+) s", text):
        return float(m.group(1))
    return None


def durations(paths: list[Path]) -> dict[Path, float | None]:
    """Duration in seconds for each file, read with ExifTool. None when unavailable."""
    result: dict[Path, float | None] = {p: None for p in paths}
    exiftool = shutil.which("exiftool")
    if not exiftool or not paths:
        return result
    args = [exiftool, "-q", "-fast", "-T", "-charset", "filename=utf8", "-Duration"]
    proc = subprocess.run(args + [str(p) for p in paths], capture_output=True, text=True, encoding="utf-8")
    lines = proc.stdout.splitlines()
    if len(lines) == len(paths):
        for path, line in zip(paths, lines):
            result[path] = _parse_duration(line)
    return result


def same_content(a: Path, b: Path, probe: int = 4096, slack: int = 65536) -> bool:
    """True when two files hold the same video data.

    Copies of a title on different discs differ by a few header bytes, which shifts the data, so
    blocks from several points in `a` are looked for near the same position in `b`.
    """
    size_a, size_b = a.stat().st_size, b.stat().st_size
    margin = abs(size_a - size_b) + slack
    with a.open("rb") as fa, b.open("rb") as fb:
        for fraction in (0.2, 0.4, 0.6, 0.8):
            offset = int(size_a * fraction)
            fa.seek(offset)
            block = fa.read(probe)
            start = max(0, offset - margin)
            fb.seek(start)
            if block not in fb.read(offset - start + probe + margin):
                return False
    return True


def show_and_season_from_folder(folder: Path) -> tuple[str | None, int | None]:
    """Guess the show and season from a Plex-style path like 'Show (1998)/Season 03'."""
    season = None
    if m := re.search(r"season\s*(\d+)", folder.name, re.IGNORECASE):
        season = int(m.group(1))
    show = re.sub(r"\s*\(\d{4}\)\s*$", "", folder.parent.name).strip() or None
    return show, season


def show_year_from_folder(folder: Path) -> int | None:
    """The year in the show folder's name, e.g. 1998 for 'Sex and the City (1998)/Season 03'."""
    m = re.search(r"\((\d{4})\)\s*$", folder.parent.name)
    return int(m.group(1)) if m else None
