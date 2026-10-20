"""Move the air date in episode filenames to the end, in brackets.

    Show - s01e06 - 1998-07-12 - Title.mp4  ->  Show - s01e06 - Title [1998-07-12].mp4

Files that don't match the pattern (trailers, already-renamed episodes) are skipped.
Runs as a dry run unless --apply is given.
"""

import argparse
import re
from pathlib import Path

PATTERN = re.compile(
    r"^(?P<prefix>.+? - s\d+e\d+) - (?P<date>\d{4}-\d{2}-\d{2})\s*-\s*(?P<title>.+)$",
    re.IGNORECASE,
)


def new_name_for(path: Path) -> str | None:
    match = PATTERN.match(path.stem)
    if not match:
        return None
    return f"{match['prefix']} - {match['title']} [{match['date']}]{path.suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="folder containing the episodes")
    parser.add_argument("--apply", action="store_true", help="actually rename files (default is a dry run)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        parser.error(f"not a folder: {folder}")

    renamed = skipped = 0
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        new_name = new_name_for(path)
        if new_name is None:
            continue
        target = path.with_name(new_name)
        if target.exists():
            print(f"SKIP (target exists): {path.name}")
            skipped += 1
            continue
        print(f"{path.name}\n  -> {new_name}")
        if args.apply:
            path.rename(target)
        renamed += 1

    action = "Renamed" if args.apply else "Would rename"
    print(f"\n{action} {renamed} file(s); skipped {skipped}.")
    if not args.apply and renamed:
        print("Run again with --apply to rename.")


if __name__ == "__main__":
    main()
