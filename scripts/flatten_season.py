"""Flatten a season folder: move videos out of subfolders (e.g. "Disc 01") into the season folder.

Each moved file gets its subfolder name as a prefix so names stay unique and keep their
disc order:   Disc 02/title_t03.mkv  ->  Disc 02 - title_t03.mkv

Repeated copies (same extension, same duration, size within --size-tolerance bytes and the same
video data) are kept once; the other copies go to a "_duplicates" folder inside the season
folder. Nothing is deleted. Subfolders left empty are removed. Plex extras folders (Trailers,
Other, Deleted Scenes, ...) and folders starting with "_" are left as they are.

Runs as a dry run unless --apply is given.
"""

import argparse
from pathlib import Path

from plex_utils import durations, is_extras_folder, is_video, same_content

DUPLICATES_DIR = "_duplicates"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="season folder to flatten")
    parser.add_argument("--size-tolerance", type=int, default=1024,
                        help="max size difference in bytes for two files to count as copies (default 1024)")
    parser.add_argument("--apply", action="store_true", help="actually move files (default is a dry run)")
    args = parser.parse_args()

    root = Path(args.folder)
    if not root.is_dir():
        parser.error(f"not a folder: {root}")

    def skipped(p: Path) -> bool:
        """In a "_" folder or a Plex extras folder (Trailers, Other, ...), which stay as they are."""
        return any(part.startswith("_") or is_extras_folder(part) for part in p.relative_to(root).parts[:-1])

    nested = sorted(p for p in root.rglob("*") if is_video(p) and p.parent != root and not skipped(p))
    if not nested:
        print("No videos in subfolders; nothing to flatten.")
        return

    lengths = durations(nested)
    kept: list[Path] = []
    moves: list[tuple[Path, Path, bool]] = []  # (source, target, is_duplicate)
    for path in nested:
        prefix = " - ".join(path.relative_to(root).parts[:-1])
        new_name = f"{prefix} - {path.name}"
        original = next((k for k in kept if k.suffix.lower() == path.suffix.lower()
                         and lengths[k] == lengths[path]
                         and abs(k.stat().st_size - path.stat().st_size) <= args.size_tolerance
                         and same_content(k, path)), None)
        if original:
            moves.append((path, root / DUPLICATES_DIR / new_name, True))
        else:
            kept.append(path)
            moves.append((path, root / new_name, False))

    clashes = [t for _, t, _ in moves if t.exists()]
    if clashes:
        for t in clashes:
            print(f"ERROR target already exists: {t}")
        raise SystemExit(1)

    dupes = sum(d for _, _, d in moves)
    for src, target, dup in moves:
        print(f"{src.relative_to(root)}  ->  {target.relative_to(root)}")
        if args.apply:
            target.parent.mkdir(exist_ok=True)
            src.rename(target)

    removed = []
    if args.apply:
        for d in sorted((p for p in root.rglob("*") if p.is_dir() and p.name != DUPLICATES_DIR),
                        key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
                removed.append(d.name)

    action = "Moved" if args.apply else "Would move"
    print(f"\n{action} {len(moves) - dupes} file(s) to the season folder and {dupes} copy(ies) to {DUPLICATES_DIR}.")
    if removed:
        print(f"Removed empty folders: {', '.join(removed)}")
    leftovers = [p for p in root.rglob("*") if p.is_file() and p.parent != root and not skipped(p)]
    if args.apply and leftovers:
        print("Non-video files left in subfolders:", *[f"  {p.relative_to(root)}" for p in leftovers], sep="\n")
    if not args.apply:
        print("Run again with --apply to move.")


if __name__ == "__main__":
    main()
