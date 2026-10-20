"""Helpers shared by the Plex filename scripts."""

import re
import shutil
import subprocess
from pathlib import Path

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".m2ts", ".webm"}

# Plex local-extras suffixes, e.g. "Show - Title - Trailer.mkv".
EXTRA_SUFFIXES = ("trailer", "behindthescenes", "deleted", "featurette", "interview",
                  "scene", "short", "other", "behind the scenes")

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


def show_and_season_from_folder(folder: Path) -> tuple[str | None, int | None]:
    """Guess the show and season from a Plex-style path like 'Show (1998)/Season 03 (2000)'."""
    season = None
    if m := re.search(r"season\s*(\d+)", folder.name, re.IGNORECASE):
        season = int(m.group(1))
    show = re.sub(r"\s*\(\d{4}\)\s*$", "", folder.parent.name).strip() or None
    return show, season
