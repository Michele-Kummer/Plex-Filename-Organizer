# Plex-Filename-Organizer

Python scripts that tidy TV show folders for [Plex](https://www.plex.tv/). They turn raw disc rips
and inconsistent names into Plex-friendly names with the air date at the end:

```
Disc 01/title_t00.mkv                                   ->  Sex and the City - s03e01 - Where There's Smoke... [2000-06-04].mkv
Disc 01/title_t06.mkv                                   ->  Sex and the City - Where There's Smoke... - Trailer.mkv
Sex and the City - s01e06 - 1998-07-12 - Secret Sex.mp4 ->  Sex and the City - s01e06 - Secret Sex [1998-07-12].mp4
```

The scripts work for any show and season. Each one only previews changes until you add `--apply`,
never deletes a file and never renames over an existing one. You can run them yourself, or install
the Claude Code plugin and ask Claude to organize a season.

## Quick start with Claude Code

Install the plugin from GitHub:

```
/plugin install plex-filename-organizer --marketplace Michele-Kummer/Plex-Filename-Organizer
```

Or install it from a local copy of this repo:

```
/plugin marketplace add C:\Code\Plex-Filename-Organizer
/plugin install plex-filename-organizer@plex-filename-organizer
```

Then, from any folder:

```
/organize-season C:\Users\me\Videos\TV Shows\Sex and the City (1998)\Season 04 (2001)
```

See [Using it with Claude Code](#using-it-with-claude-code) for details.

## Requirements

- Python 3.10 or later.
- [ExifTool](https://exiftool.org/) on your `PATH` (optional, recommended). It reads video lengths,
  which separate episodes from short clips and spot repeated copies. Without it, the scripts go by
  file size.

## Expected folder layout

The scripts read the show and season from a Plex-style path:

```
TV Shows\
  Sex and the City (1998)\        <- show name, year optional
    Season 03 (2000)\             <- season number taken from "Season NN"
      Disc 01\title_t00.mkv ...   <- disc rips (flattened first)
```

## The scripts

Run them from the repo folder, e.g. `python scripts/flatten_season.py ...`. The first argument is
always the season folder.

### 1. `flatten_season.py`: move disc rips up into the season folder

```
python scripts/flatten_season.py "C:\...\Sex and the City (1998)\Season 03 (2000)"
python scripts/flatten_season.py "C:\...\Sex and the City (1998)\Season 03 (2000)" --apply
```

- Moves every video from the subfolders (`Disc 01`, `Disc 02`, ...) into the season folder and puts
  the subfolder name in front of the filename (`Disc 02 - title_t03.mkv`). Names stay unique and
  still sort in disc order.
- Discs often carry the same trailers. A file with the same extension, the same length and a size
  within 1 KB of a file already kept is checked further: samples of its video data are compared,
  because two different trailers can be almost the same size. Only a real copy goes to
  `_duplicates` in the season folder.
- Removes subfolders left empty. Folders whose names start with `_` are skipped.

| Option | Meaning |
|---|---|
| `--size-tolerance N` | Largest size difference in bytes for two files to count as copies (default 1024) |
| `--apply` | Move the files instead of only listing them |

### 2. `rename_episodes.py`: name episodes from the episode guide

```
python scripts/rename_episodes.py "C:\...\Sex and the City (1998)\Season 03 (2000)"
python scripts/rename_episodes.py "C:\...\Sex and the City (1998)\Season 03 (2000)" --apply
```

The episode titles and air dates are downloaded from [TVmaze](https://www.tvmaze.com), which is free
and needs no account. The show is looked up by the parent folder's name. When several shows share
that name, the year in brackets picks the right one. The first line of the output says which show
and season were used.

To use your own guide instead, pass `--guide season3.json`. The guide is a JSON list of the season's
episodes in order, for example copied from Google's episode guide, Wikipedia or TVDB:

```json
[
  {"episode": 1, "title": "Where There's Smoke...", "air_date": "2000-06-04"},
  {"episode": 2, "title": "Politically Erect",      "air_date": "2000-06-11"}
]
```

`air_date` can be left out. The name then has no date.

How files are matched:

- **Files that already have a tag like `s03e05`** are renamed to that episode's title and date.
- **Other videos** are taken in filename order, which after flattening is disc order. Videos at
  least 15 minutes long are numbered as the episodes still missing from the folder.
- **More long videos than episodes:** the ones left over once the guide runs out become bonus
  extras (`Season 6 Bonus 01 - Other`). If a bonus feature sits between the episodes, for example
  an extra long title on a middle disc, name it with `--bonus` so the episodes after it keep their
  numbers.
- **Short clips** become Plex trailers. When there is one clip per episode, clip N is named after
  episode N. Otherwise they are numbered (`Season 3 Extra 01 - Trailer`). When there are more clips
  than episodes and the first ones are the episode trailers, `--trailers-first` names those after
  the episodes and the rest `Season 3 Extra 01 - Other`.
- **Files already named as Plex extras** (`... - Trailer.mkv`, `- Featurette`, and similar) are
  left alone. The exception is clips the script numbered on an earlier run
  (`Season 3 Extra 01 - Trailer`), which are named again so a rerun can fix them.
- **Characters Windows does not allow** (`? " * < > | / \`) are removed, and a colon becomes " - ".

| Option | Meaning |
|---|---|
| `--guide FILE` | Episode guide JSON (default: download it from TVmaze) |
| `--year YYYY` | Year the show started, if the parent folder name has none |
| `--save-guide FILE` | Also save the downloaded guide as JSON |
| `--show NAME` | Show name, if the parent folder name is not right |
| `--season N` | Season number, if the folder name has none |
| `--min-minutes N` | Shortest length that counts as an episode (default 15) |
| `--first N` | Episode number for the first unnamed episode file |
| `--bonus FILE` | A long video that is a bonus feature, not an episode (repeat for more) |
| `--trailers-first` | More clips than episodes: name the first ones after the episodes, the rest `Other` |
| `--number-extras` | Number the short clips instead of naming them after episodes |
| `--extra-type TYPE` | Plex extra type for short clips (default `Trailer`) |
| `--apply` | Rename the files instead of only listing them |

Check the preview before applying. The script assumes the discs are in episode order and the clips
are in the same order as the episodes.

### 3. `move_date_to_end.py`: move the date to the end of the name

For seasons named `Show - s01e06 - 1998-07-12 - Title`:

```
python scripts/move_date_to_end.py "C:\...\Sex and the City (1998)\Season 01 (1998)"
python scripts/move_date_to_end.py "C:\...\Sex and the City (1998)\Season 01 (1998)" --apply
```

Files in any other format, such as trailers or files already renamed, are skipped.

## Typical workflow for a ripped season

1. `scripts/flatten_season.py` to bring the disc rips into the season folder.
2. `scripts/rename_episodes.py` to name the episodes and trailers from the downloaded guide.
3. Check `_duplicates`, then delete it when you're happy.
4. Refresh the library in Plex.

Run each step without `--apply` first.

## Using it with Claude Code

This repo is a [Claude Code](https://claude.com/claude-code) plugin, `plex-filename-organizer`. Once
it is installed (see [Quick start](#quick-start-with-claude-code)), it works from any folder. Claude
looks up the episode guide online, writes the JSON and runs the scripts.

**Command**, which you type:

| Command | What it does |
|---|---|
| `/organize-season <folder>` | The whole job: flatten, rename from the episode guide, move any dates to the end |

**Skills** are the individual steps. Claude uses them when your request matches, for example
"flatten C:\...\Season 04 (2001)", or you can type them as commands:

| Skill | What it does |
|---|---|
| `tv-flatten-season` | Runs `scripts/flatten_season.py` on a season folder |
| `tv-rename-episodes` | Looks up the season's episode guide and runs `scripts/rename_episodes.py` |
| `tv-move-date-to-end` | Runs `scripts/move_date_to_end.py` |

If another plugin uses the same name, use the full name, e.g.
`/plex-filename-organizer:organize-season`. Claude shows you the preview before it renames anything.

**Updating:** the installed plugin is a copy. After changing the repo, raise `version` in
`.claude-plugin/plugin.json` and run `/plugin update plex-filename-organizer@plex-filename-organizer`,
then restart Claude Code.

**Developing:** inside this repo, `/run-tests` (from `.claude/commands/`) runs the tests and explains
any failures.

## Tests

The tests use Python's built-in `unittest`, so there is nothing to install. They run on temporary
folders of small dummy files and use fixed video lengths in place of ExifTool:

```
python -m unittest discover -s tests
```

## Project layout

```
.claude-plugin/
  plugin.json               Plugin manifest: name, version, skills and commands
  marketplace.json          Lets this repo be added as a plugin marketplace
commands/                   Plugin slash commands
  organize-season.md          /organize-season: the whole workflow for one season
skills/                     Plugin skills, one step each
  tv-flatten-season/
  tv-rename-episodes/
  tv-move-date-to-end/
.claude/commands/           Commands for working on this repo only
  run-tests.md                /run-tests
scripts/                    The Python scripts
  flatten_season.py           Flatten disc subfolders and move copies to _duplicates
  rename_episodes.py          Rename episodes and trailers from an episode guide
  episode_guide.py            Download a season's episode guide from TVmaze
  move_date_to_end.py         Move YYYY-MM-DD from the middle of the name to the end
  plex_utils.py               Shared helpers: video lengths, safe filenames, show and season from the path
tests/                      Unit tests for the scripts and helpers
docs/                       Project notes
```
