"""Rename the videos in a season folder from an episode guide.

    Show - s03e01 - Where There's Smoke... [2000-06-04].mkv
    Show - Where There's Smoke... - Trailer.mkv

The guide is a JSON list, one entry per episode, in episode order:
    [{"episode": 1, "title": "Where There's Smoke...", "air_date": "2000-06-04"}, ...]
("air_date" may be omitted or null.)

Files already carrying an sNNeNN tag are renamed to the guide's title and date for that episode.
Other videos (e.g. disc rips such as "Disc 01 - title_t00.mkv") are taken in filename order:
long ones become the episodes that are still missing, short ones become extras. When there is
one short clip per episode, clip N is named after episode N; otherwise they are numbered.
Files already named as Plex extras ("... - Trailer.mkv") are left alone.

Runs as a dry run unless --apply is given.
"""

import argparse
import json
import re
from pathlib import Path

from plex_utils import durations, is_extra, is_video, safe_filename, show_and_season_from_folder

EPISODE_TAG = re.compile(r"\bs(\d{1,2})e(\d{1,3})\b", re.IGNORECASE)


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def fmt_length(seconds: float | None) -> str:
    return "?" if seconds is None else f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="season folder (flatten disc subfolders first)")
    parser.add_argument("--guide", required=True, help="episode guide JSON file")
    parser.add_argument("--show", help="show name (default: parent folder name without the year)")
    parser.add_argument("--season", type=int, help="season number (default: from the folder name)")
    parser.add_argument("--min-minutes", type=float, default=15,
                        help="unnamed videos at least this long are episodes (default 15)")
    parser.add_argument("--first", type=int, help="episode number for the first unnamed episode file "
                                                   "(default: the first episode not already in the folder)")
    parser.add_argument("--extra-type", default="Trailer", help="Plex extra type for short clips (default Trailer)")
    parser.add_argument("--number-extras", action="store_true",
                        help="number short clips instead of naming them after episodes")
    parser.add_argument("--apply", action="store_true", help="actually rename files (default is a dry run)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        parser.error(f"not a folder: {folder}")
    guess_show, guess_season = show_and_season_from_folder(folder)
    show = args.show or guess_show
    season = args.season or guess_season
    if not show or not season:
        parser.error("could not tell the show or season from the folder name; pass --show and --season")

    guide_path = Path(args.guide)
    if not guide_path.is_file():
        parser.error(f"episode guide not found: {guide_path}\n"
                     f"Create it first (see the JSON format in --help).")
    try:
        guide = {int(e["episode"]): e for e in json.loads(guide_path.read_text(encoding="utf-8-sig"))}
    except (ValueError, KeyError, TypeError) as error:
        parser.error(f"could not read the episode guide {guide_path}: {error}\n"
                     f'Each entry needs "episode" and "title", e.g. '
                     f'{{"episode": 1, "title": "Pilot", "air_date": "2000-01-01"}}')
    if not guide:
        parser.error("the guide is empty")

    def episode_name(n: int, ext: str) -> str:
        entry = guide[n]
        date = f" [{entry['air_date']}]" if entry.get("air_date") else ""
        return f"{safe_filename(show)} - s{season:02d}e{n:02d} - {safe_filename(entry['title'])}{date}{ext}"

    videos = sorted((p for p in folder.iterdir() if is_video(p) and not is_extra(p)), key=natural_key)
    plan: list[tuple[Path, str, str]] = []  # (source, new name, note)

    tagged, untagged = {}, []
    for p in videos:
        m = EPISODE_TAG.search(p.stem)
        if m and int(m.group(1)) == season and int(m.group(2)) in guide:
            tagged[int(m.group(2))] = p
            plan.append((p, episode_name(int(m.group(2)), p.suffix), "already tagged"))
        else:
            untagged.append(p)

    lengths = durations(untagged)
    largest = max((p.stat().st_size for p in untagged), default=0)

    def is_long(p: Path) -> bool:
        if lengths[p] is not None:
            return lengths[p] >= args.min_minutes * 60
        return p.stat().st_size >= largest * 0.25

    episodes = [p for p in untagged if is_long(p)]
    extras = [p for p in untagged if not is_long(p)]

    missing = [n for n in sorted(guide) if n not in tagged]
    if args.first is not None:
        missing = [n for n in missing if n >= args.first]
    if len(episodes) > len(missing):
        raise SystemExit(f"ERROR {len(episodes)} unnamed episode file(s) but only {len(missing)} "
                         f"episode(s) left in the guide. Check --min-minutes, --first or the guide.")
    if episodes and len(episodes) < len(missing) and args.first is None:
        print(f"WARNING {len(episodes)} episode file(s) for {len(missing)} missing episode(s); "
              f"numbering from s{season:02d}e{missing[0]:02d}. Use --first if that is wrong.\n")
    for p, n in zip(episodes, missing):
        plan.append((p, episode_name(n, p.suffix), fmt_length(lengths[p])))

    by_episode = len(extras) == len(guide) and not args.number_extras
    for i, p in enumerate(extras, start=1):
        label = safe_filename(guide[sorted(guide)[i - 1]]["title"]) if by_episode else f"Season {season} Extra {i:02d}"
        plan.append((p, f"{safe_filename(show)} - {label} - {args.extra_type}{p.suffix}", fmt_length(lengths[p])))

    changes = [(p, name, note) for p, name, note in plan if p.name != name]
    targets = [name.lower() for _, name, _ in plan]
    clashes = {n for n in targets if targets.count(n) > 1}
    clashes |= {name.lower() for p, name, _ in changes if (folder / name).exists()
                and (folder / name).resolve() != p.resolve()}
    if clashes:
        for name in sorted(clashes):
            print(f"ERROR more than one file would be named: {name}")
        raise SystemExit(1)

    for p, name, note in changes:
        print(f"{p.name}  ({note})\n  -> {name}")
        if args.apply:
            p.rename(folder / name)

    if extras and by_episode:
        print("\nNOTE short clips were named after episodes in filename order; spot-check a few.")
    if extras and not by_episode and not args.number_extras:
        print(f"\nNOTE {len(extras)} short clip(s) for {len(guide)} episode(s), so they were numbered.")
    unmatched = [n for n in missing[len(episodes):]]
    if unmatched:
        print(f"Episodes with no file: {', '.join(f's{season:02d}e{n:02d}' for n in unmatched)}")
    action = "Renamed" if args.apply else "Would rename"
    print(f"\n{action} {len(changes)} file(s); {len(plan) - len(changes)} already correct.")
    if not args.apply and changes:
        print("Run again with --apply to rename.")


if __name__ == "__main__":
    main()
