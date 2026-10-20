"""Rename the videos in a season folder from an episode guide.

    Show - s03e01 - Where There's Smoke... [2000-06-04].mkv
    Trailers/Where There's Smoke....mkv

The guide is a JSON list, one entry per episode, in episode order:
    [{"episode": 1, "title": "Where There's Smoke...", "air_date": "2000-06-04"}, ...]
("air_date" may be omitted or null.) Without --guide, the guide is downloaded from TVmaze using
the show name and year from the show folder ("Show (1998)") and the season number.

Files already carrying an sNNeNN tag are renamed to the guide's title and date for that episode.
Other videos (e.g. disc rips such as "Disc 01 - title_t00.mkv") are taken in filename order:
long ones become the episodes that are still missing, short ones become extras. When there is
one short clip per episode, clip N is named after episode N; otherwise they are numbered.
Extras go in Plex extras folders inside the season folder (Trailers, Other, ...). Old-style extras
named inline ("Show - Title - Trailer.mkv") are moved into the matching folder.

Runs as a dry run unless --apply is given.
"""

import argparse
import json
import re
from pathlib import Path

from episode_guide import fetch_guide
from plex_utils import (durations, extra_folder, is_plex_inline_extra, is_video, safe_filename,
                        show_and_season_from_folder, show_year_from_folder, split_inline_extra)

EPISODE_TAG = re.compile(r"\bs(\d{1,2})e(\d{1,3})\b", re.IGNORECASE)


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def fmt_length(seconds: float | None) -> str:
    return "?" if seconds is None else f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def load_guide(parser, args, show: str, season: int, folder: Path) -> dict[int, dict]:
    """The episode guide from --guide, or downloaded from TVmaze, keyed by episode number."""
    if args.guide:
        guide_path = Path(args.guide)
        if not guide_path.is_file():
            parser.error(f"episode guide not found: {guide_path}\n"
                         f"Leave out --guide to download it, or create it (see the JSON format in --help).")
        entries = guide_path.read_text(encoding="utf-8-sig")
        source = str(guide_path)
    else:
        try:
            label, downloaded = fetch_guide(show, season, args.year or show_year_from_folder(folder))
        except (OSError, LookupError, ValueError) as error:
            parser.error(f"could not download the episode guide: {error}\nPass --guide FILE instead.")
        entries = json.dumps(downloaded, ensure_ascii=False, indent=1)
        source = f"TVmaze, {label} season {season}"
        if args.save_guide:
            Path(args.save_guide).write_text(entries, encoding="utf-8")
    try:
        guide = {int(e["episode"]): e for e in json.loads(entries)}
    except (ValueError, KeyError, TypeError) as error:
        parser.error(f"could not read the episode guide {source}: {error}\n"
                     f'Each entry needs "episode" and "title", e.g. '
                     f'{{"episode": 1, "title": "Pilot", "air_date": "2000-01-01"}}')
    if not guide:
        parser.error("the guide is empty")
    print(f"Episode guide: {source}, {len(guide)} episode(s)\n")
    return guide


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="season folder (flatten disc subfolders first)")
    parser.add_argument("--guide", help="episode guide JSON file (default: download it from TVmaze)")
    parser.add_argument("--year", type=int, help="year the show started, to pick the right show on TVmaze "
                                                 "(default: from the show folder name)")
    parser.add_argument("--save-guide", help="also write the downloaded guide to this JSON file")
    parser.add_argument("--show", help="show name (default: parent folder name without the year)")
    parser.add_argument("--season", type=int, help="season number (default: from the folder name)")
    parser.add_argument("--min-minutes", type=float, default=15,
                        help="unnamed videos at least this long are episodes (default 15)")
    parser.add_argument("--first", type=int, help="episode number for the first unnamed episode file "
                                                   "(default: the first episode not already in the folder)")
    parser.add_argument("--bonus", action="append", default=[], metavar="FILE",
                        help="file name of a long video that is a bonus feature, not an episode; repeatable")
    parser.add_argument("--extra-type", default="Trailer", help="Plex extra type for short clips (default Trailer)")
    parser.add_argument("--trailers-first", action="store_true",
                        help="when there are more short clips than episodes, name the first ones after the "
                             "episodes and the rest as Other extras")
    parser.add_argument("--number-extras", action="store_true",
                        help="number short clips instead of naming them after episodes")
    parser.add_argument("--extras-only", action="store_true",
                        help="only move old-style extras (\"Show - Title - Trailer.mkv\") into extras folders; "
                             "leave episodes and other videos as they are (no guide needed)")
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

    guide = {} if args.extras_only else load_guide(parser, args, show, season, folder)

    def episode_name(n: int, ext: str) -> str:
        entry = guide[n]
        date = f" [{entry['air_date']}]" if entry.get("air_date") else ""
        return f"{safe_filename(show)} - s{season:02d}e{n:02d} - {safe_filename(entry['title'])}{date}{ext}"

    show_name = safe_filename(show)
    try:
        clip_dir = extra_folder(args.extra_type)
    except KeyError:
        parser.error(f"unknown --extra-type {args.extra_type}")
    plan: list[tuple[Path, str, str]] = []  # (source, new path relative to the season folder, note)

    # Clips this script numbered on an earlier run are renamed again, so a rerun can fix them.
    numbered = re.compile(rf"Season {season} Extra \d+", re.IGNORECASE)
    old_numbered = re.compile(rf"{re.escape(show_name)} - Season {season} Extra \d+ - "
                              rf"{re.escape(args.extra_type)}", re.IGNORECASE)
    videos = []
    for p in (p for p in folder.iterdir() if is_video(p) and not is_plex_inline_extra(p.stem)):
        inline = None if EPISODE_TAG.search(p.stem) or old_numbered.fullmatch(p.stem) \
            else split_inline_extra(p.stem, show_name)
        if inline:
            plan.append((p, f"{inline[0]}/{safe_filename(inline[1])}{p.suffix}", "extra"))
        elif not args.extras_only:
            videos.append(p)
    if (folder / clip_dir).is_dir() and not args.extras_only:
        videos += [p for p in (folder / clip_dir).iterdir() if is_video(p) and numbered.fullmatch(p.stem)]
    videos.sort(key=natural_key)

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

    marked = {name.lower() for name in args.bonus}
    unknown = marked - {p.name.lower() for p in untagged}
    if unknown:
        parser.error(f"--bonus file(s) not found among the unnamed videos: {', '.join(sorted(unknown))}")
    is_marked = lambda p: p.name.lower() in marked
    episodes = [p for p in untagged if is_long(p) and not is_marked(p)]
    extras = [p for p in untagged if not is_long(p) and not is_marked(p)]

    missing = [n for n in sorted(guide) if n not in tagged]
    if args.first is not None:
        missing = [n for n in missing if n >= args.first]
    leftover = episodes[len(missing):]
    episodes = episodes[:len(missing)]
    bonus = sorted([p for p in untagged if is_marked(p)] + leftover, key=natural_key)
    if leftover:
        print(f"WARNING {len(episodes) + len(leftover)} episode file(s) but only {len(missing)} episode(s) left "
              f"in the guide; the last {len(leftover)} become bonus extras. If a bonus file sits between "
              f"the episodes, name it with --bonus.\n")
    if episodes and len(episodes) < len(missing) and args.first is None:
        print(f"WARNING {len(episodes)} episode file(s) for {len(missing)} missing episode(s); "
              f"numbering from s{season:02d}e{missing[0]:02d}. Use --first if that is wrong.\n")
    for p, n in zip(episodes, missing):
        plan.append((p, episode_name(n, p.suffix), fmt_length(lengths[p])))
    for i, p in enumerate(bonus, start=1):
        plan.append((p, f"Other/Season {season} Bonus {i:02d}{p.suffix}", fmt_length(lengths[p])))

    by_episode = not args.number_extras and (len(extras) == len(guide)
                                             or (args.trailers_first and len(extras) > len(guide)))
    for i, p in enumerate(extras, start=1):
        if by_episode and i <= len(guide):
            target = f"{clip_dir}/{safe_filename(guide[sorted(guide)[i - 1]]['title'])}"
        elif by_episode:
            target = f"Other/Season {season} Extra {i - len(guide):02d}"
        else:
            target = f"{clip_dir}/Season {season} Extra {i:02d}"
        plan.append((p, target + p.suffix, fmt_length(lengths[p])))

    changes = [(p, name, note) for p, name, note in plan if p.relative_to(folder).as_posix() != name]
    targets = [name.lower() for _, name, _ in plan]
    clashes = {n for n in targets if targets.count(n) > 1}
    clashes |= {name.lower() for p, name, _ in changes if (folder / name).exists()
                and (folder / name).resolve() != p.resolve()}
    if clashes:
        for name in sorted(clashes):
            print(f"ERROR more than one file would be named: {name}")
        raise SystemExit(1)

    for p, name, note in changes:
        print(f"{p.relative_to(folder)}  ({note})\n  -> {Path(name)}")
        if args.apply:
            (folder / name).parent.mkdir(exist_ok=True)
            p.rename(folder / name)

    if extras and by_episode:
        print("\nNOTE short clips were named after episodes in filename order; spot-check a few.")
    if extras and not by_episode and not args.number_extras:
        print(f"\nNOTE {len(extras)} short clip(s) for {len(guide)} episode(s), so they were numbered."
              + (" If the first ones are the episode trailers, add --trailers-first." if len(extras) > len(guide) else ""))
    unmatched = [n for n in missing[len(episodes):]]
    if unmatched:
        print(f"Episodes with no file: {', '.join(f's{season:02d}e{n:02d}' for n in unmatched)}")
    action = "Renamed" if args.apply else "Would rename"
    print(f"\n{action} {len(changes)} file(s); {len(plan) - len(changes)} already correct.")
    if not args.apply and changes:
        print("Run again with --apply to rename.")


if __name__ == "__main__":
    main()
