# Plex-Filename-Organizer

Python scripts that tidy TV show folders for [Plex](https://www.plex.tv/). They turn raw disc rips
and inconsistent names into Plex-friendly names with the air date at the end:

```
Disc 01/title_t00.mkv                                   ->  Sex and the City (1998) - s03e01 - Where There's Smoke... [2000-06-04].mkv
Disc 01/title_t06.mkv                                   ->  ../Trailers/Season 03/Where There's Smoke....mkv
Sex and the City - s01e06 - 1998-07-12 - Secret Sex.mp4 ->  Sex and the City (1998) - s01e06 - Secret Sex [1998-07-12].mp4
```

Every episode name starts with the show and its year. Trailers go in the show's `Trailers` folder,
in a folder for their season, named without the show (the folders already say which show and
season it is):

```
TV Shows/
  Sex and the City (1998)/
    Trailers/
      Season 03/
        Season 3 Trailer.mp4
        Where There's Smoke....mkv
    Season 03/
      Sex and the City (1998) - s03e01 - Where There's Smoke... [2000-06-04].mkv
      Other/Gag Reel.mkv
```

`check_names.py --movies` does the same for movie folders, and moves trailers and bonus material
kept in a separate folder into each movie's folder (see [Movies](#movies)).

The scripts work for any show and season. Each one only previews changes until you add `--apply`,
never deletes a file and never renames over an existing one. A file it cannot rename (open in
Plex, a player or Explorer's preview pane) is reported as `FAILED` and the run carries on with the
rest; close the program and run it again to pick those up. You can run them yourself, or install
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
/organize-season C:\Users\me\Videos\TV Shows\Sex and the City (1998)\Season 04
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
    Season 03\                    <- season number taken from "Season NN" (no year)
      Disc 01\title_t00.mkv ...   <- disc rips (flattened first)
```

## The scripts

Run them from the repo folder, e.g. `python scripts/flatten_season.py ...`. The first argument is
always the season folder.

### 1. `flatten_season.py`: move disc rips up into the season folder

```
python scripts/flatten_season.py "C:\...\Sex and the City (1998)\Season 03"
python scripts/flatten_season.py "C:\...\Sex and the City (1998)\Season 03" --apply
```

- Moves every video from the subfolders (`Disc 01`, `Disc 02`, ...) into the season folder and puts
  the subfolder name in front of the filename (`Disc 02 - title_t03.mkv`). Names stay unique and
  still sort in disc order.
- Discs often carry the same trailers. A file with the same extension, the same length and a size
  within 1 KB of a file already kept is checked further: samples of its video data are compared,
  because two different trailers can be almost the same size. Only a real copy goes to
  `_duplicates` in the season folder.
- Removes subfolders left empty. Folders whose names start with `_` and Plex extras folders
  (`Trailers`, `Deleted Scenes`, ...) are skipped.

| Option | Meaning |
|---|---|
| `--size-tolerance N` | Largest size difference in bytes for two files to count as copies (default 1024) |
| `--apply` | Move the files instead of only listing them |

### 2. `rename_episodes.py`: name episodes from the episode guide

```
python scripts/rename_episodes.py "C:\...\Sex and the City (1998)\Season 03"
python scripts/rename_episodes.py "C:\...\Sex and the City (1998)\Season 03" --apply
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

- **Episode names** start with the show folder's name, year included:
  `Show (1998) - s03e05 - Title [date]`.
- **Files that already have a tag like `s03e05`** are renamed to that episode's title and date.
- **Other videos** are taken in filename order, which after flattening is disc order. Videos at
  least 15 minutes long are numbered as the episodes still missing from the folder.
- **Trailers go in the show's `Trailers` folder**, in a folder for the season:
  `Show (1998)/Trailers/Season 03/Title.mkv`, or `.../Season 03/Season 3 Trailer.mkv` when there is no
  title. The name leaves out the show, since the folders already give it.
- **Other extras go in Plex extras folders** inside the season folder: `Behind The Scenes`,
  `Deleted Scenes`, `Featurettes`, `Interviews`, `Scenes`, `Shorts` and `Other`. Plex reads the
  type from the folder and shows the file name as the title.
- **More long videos than episodes:** the ones left over once the guide runs out become bonus
  extras (`Other/Season 6 Bonus 01`). If a bonus feature sits between the episodes, for example
  an extra long title on a middle disc, name it with `--bonus` so the episodes after it keep their
  numbers.
- **Short clips** become trailers. When there is one clip per episode, clip N is named after
  episode N (`Trailers/Season 03/Pilot.mkv`). Otherwise they are numbered
  (`Trailers/Season 03/Season 3 Trailer 01.mkv`).
  When there are more clips than episodes and the first ones are the episode trailers,
  `--trailers-first` names those after the episodes and the rest `Other/Season 3 Extra 01`.
- **Files in extras folders, and names in Plex's own format** (`... - Scene 16-deleted.mkv`, the type
  right after the hyphen) are left alone. Clips the script numbered on an earlier run are named
  again, so a rerun can fix them.
- **Old-style extras** named `Show - Title - Trailer.mkv` (space after the hyphen, which Plex does
  not recognize) are moved to `Trailers/Season 03/Title.mkv`, or into the matching
  folder for other types (`Show - Title - Featurette.mkv` -> `Featurettes/Title.mkv`). `--extras-only` does
  just that, leaving episodes and other videos alone and needing no guide.
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
| `--extras-only` | Only move old-style extras into extras folders; leave everything else |
| `--number-extras` | Number the short clips instead of naming them after episodes |
| `--extra-type TYPE` | Plex extra type for short clips, which picks their folder (default `Trailer`) |
| `--apply` | Rename the files instead of only listing them |

Check the preview before applying. The script assumes the discs are in episode order and the clips
are in the same order as the episodes.

### 3. `move_date_to_end.py`: move the date to the end of the name

For seasons named `Show - s01e06 - 1998-07-12 - Title`:

```
python scripts/move_date_to_end.py "C:\...\Sex and the City (1998)\Season 01"
python scripts/move_date_to_end.py "C:\...\Sex and the City (1998)\Season 01" --apply
```

Files in any other format, such as trailers or files already renamed, are skipped.

### 4. `check_names.py`: find and fix names Plex won't read as intended

Run it any time, on one season, a whole show or the whole library:

```
python scripts/check_names.py "C:\Users\shell\Videos\TV Shows"
python scripts/check_names.py "C:\Users\shell\Videos\TV Shows" --apply
```

It fixes:

| Found | Becomes |
|---|---|
| `Show - Title - Trailer.mkv` (space after the hyphen, which Plex ignores), `Season 01/Trailers/Title.mkv` | `Show (1998)/Trailers/Season 01/Title.mkv` |
| `Show - Trailer.mkv` | `Show (1998)/Trailers/Season 01/Season 1 Trailer.mkv` |
| `Show (1998) - S01 - Title-trailer.mkv` in the season folder (this tool's old layout) | `Show (1998)/Trailers/Season 01/Title.mkv` |
| `Trailers/Season 1/Show - Title.mkv` | `Trailers/Season 01/Title.mkv` |
| `Show - Title - Bonus.mkv` | `Other/Title.mkv` |
| `Show - Eggs - Title.mkv` (Easter eggs keep the word) | `Other/Eggs - Title.mkv` |
| `Show - Deleted Scene 01.mkv`, `Show - The Making of X.mkv` | `Deleted Scenes/…`, `Behind The Scenes/…` |
| Folders named `Extras`, `Bonus Features`, ... | The Plex folder name (`Other`, ...) |
| `Featurettes/Show - Title.mkv` | `Featurettes/Title.mkv` |
| `Show - s01e01 - Pilot`, `s01e01 - Pilot` | `Show (1998) - s01e01 - Pilot` |
| `Show - 2013-08-12 - Title`, `2013-08-12 - Title` (date-based) | `Show (1998) - 2013-08-12 - Title` |
| `Show - s01e06 - 1998-07-12 - Title`, `Show s01e06 -Title` | `Show (1998) - s01e06 - Title [1998-07-12]`, `Show (1998) - s01e06 - Title` |
| `Show - S2E3 - Title (1949)`, `Show - s01e01 - Title 1945]` | `Show (1998) - s02e03 - Title [1949]`, `Show (1998) - s01e01 - Title [1945]` |
| `Show - s2e214 - Title`, `Show - s1e4A - Title` | `Show (1998) - s02e214 - Title`, `Show (1998) - s01e04A - Title` |
| `Show - s01e01 - Pilot [1998-06-07]_2.mkv` (a copy number added to dodge a name clash) | `Show (1998) - s01e01 - Pilot [1998-06-07].mkv` |
| `Eggs- Pre-marital sex`, `Title -Part`, `Title -` | `Eggs - Pre-marital sex`, `Title - Part`, `Title` |

Every episode with a season/episode tag ends up as `Show (1998) - s##e## - Title [date]`: the show
folder's name and year first (a name that starts with some other show is reported), the tag
lower-case and padded to at least two digits (longer numbers and a split-episode letter are kept),
any date (a full `YYYY-MM-DD`, or a bracketed year when there
is none) at the end in brackets, and the parts joined with ` - `. When an episode has an air date,
another year in its title (a collection's `(2017)`) is kept as written. Otherwise years in
parentheses become brackets: `Paw Patrol 2016-09-17 - Title (2017)` becomes
`Paw Patrol (2013) - 2016-09-17 - Title [2017]`.

Date-based episodes (`Show - 2013-08-12 - Title`) also get the show's original year, taken from the
show folder, so Plex can look the show up: in `Paw Patrol (2013)`, `Paw Patrol - 2016-09-17 - Title`
becomes `Paw Patrol (2013) - 2016-09-17 - Title`. The year is when the show started, not the
episode's air date. Hyphens between words become
` - ` in every video name; hyphens inside words (`Catch-38`) stay.

It only reports (`CHECK`) what needs a person: videos it can't place, disc folders that still
need flattening, unknown folders, more than one date in a name, mistyped dates and tags with no
`e` (`s0121B`), and episodes whose name starts with some other show. Names in Plex's own extras
format (`...-deleted.mkv`) and folders starting with `_` are fine and left alone. It never renames over an existing file (`SKIP`).

Copy numbers are what was added to a name to dodge a clash: `_` and up to 5 digits by default
(`Title_2.mkv`, `Title_12345.mkv`). If your tools number copies another way, pass the pattern as a
regular expression, e.g. `--collision-suffix " \(\d+\)"` for `Title (2).mkv`, or `""` to keep them.
When the clean name already belongs to a file with the same video, the numbered copy goes to
`_duplicates`; when it belongs to a different video, both are left for you to compare.

Season folders are named `Season 01`, `Season 02`, ...: two digits so they sort in order, and no
year (`Season 1 (2003)` becomes `Season 01`). The year belongs on the show folder only; Plex
forum users report that a year on season folders can make Plex mismatch the show. Show folders
without a year, `Dinosaurs` instead of `Dinosaurs (1991)`, are reported with the year TVmaze gives
as a hint; add the year yourself, since the scripts read it to tell shows with the same name apart.

Each `RENAME` line says what kind of fix it is, and the run ends with a count of each kind:

```
By kind of fix (a rename can count under more than one):
     40  show name and year put at the start
     52  date or year moved to the end in []
      4  season/episode written as s##e##
     23  minor formatting (spaces, hyphens, brackets)
      1  extras folder renamed
     21  extra moved to Other
      2  trailer moved to the show's Trailers/Season ## folder
```

### Movies

`check_names.py --movies MOVIES_ROOT` checks movie folders instead. Run it on the movie library
first, then on a separate folder of trailers and bonus material, if you keep one:

```
python scripts/check_names.py "C:\Users\shell\Videos\Movies" --movies "C:\Users\shell\Videos\Movies"
python scripts/check_names.py "E:\Trailers or Bonus" --movies "C:\Users\shell\Videos\Movies" --tv "C:\Users\shell\Videos\TV Shows"
```

Plex wants each movie in its own folder named `Title (Year) {edition-Name}`, extras in type
folders inside it. It fixes:

| Found | Becomes |
|---|---|
| `American Pie 2 {edition-Collector's Edition} (2002)` | `American Pie 2 (2001) {edition-Collector's Edition}` |
| `{edition - Unreated}`, `{editon-Unrated}`, `{Edition-Special Edition}`, `{edition-X` | `{edition-Unrated}`, `{edition-Unrated}`, `{edition-Special Edition}`, `{edition-X}` |
| `Castaway ()`, `Matrix Reloaded (2003)`, `Finding Nemo (2001)` | `Cast Away (2000)`, `The Matrix Reloaded (2003)`, `Finding Nemo (2003)` |
| `Ariel's Beginning  (2008)`, `Rags to Riches; The Making`, `Young Guns Ii` | single space, no semicolon, `Young Guns II` |
| `The Wizard of Oz (1939) {edition-X}_The Making Of.mkv` | `Behind The Scenes/The Making Of.mkv` |
| `Double Jeopardy - Behind The Scenes Featurette.mp4` (loose) | `Double Jeopardy (1999)/Behind The Scenes/...` |
| `_Trailers/Trolls - Trailer (2016).mkv` | `Trolls (2016)/Trailers/Trailer.mkv` |
| `Happy Feet Trailer.mp4` in another movie's folder | `Happy Feet (2006)/Trailers/...`, or reported if that folder is missing |
| `Dirty Dancing - Bonus (1987)` | merged into `Dirty Dancing (1987)` |
| `Universal Intro.mkv`, `Intro Lionsgate.mkv` | `_Intros/Intro - Universal.mkv`, ... |
| `X - Trailer.mkv` and `X - Trailer_12.mp4`, or two files with the same video | the `.mp4` is kept, the other copy goes to `_duplicates` |
| `Bruce Almighty (2003)_1.mp4`, `C4_t04_2.mkv` | `Bruce Almighty (2003).mp4`, `C4_t04.mkv` (reported if that name holds a different video) |
| Raw rips (`A1_t01.mkv`) shorter than 10 seconds | `_Tiny clips/` to look over and delete |

Each folder's movie file is renamed along with it. Extras are typed by words in their names
(trailer, deleted, behind the scenes / making of, featurette, interview, short, bloopers, bonus);
anything else goes in `Other`. In the library, a `Special Features` or `Bonus` folder is sorted
into type folders the same way.

Titles and years it cannot work out from the name alone, such as a DVD year where the release
year belongs, are listed in `data/movie_corrections.json`; add to it as you find more. Plex matches
movies by title and release year, so check a new entry against Plex's match before adding it.

It only reports what needs a person: raw rips (MakeMKV names like `A1_t01.mkv`) and numbered
generic names (`Special Features (3)`) that need watching to name, movies with no year, extras
whose movie has no folder in the library, other movies sharing a folder, and trailers for TV
shows. With `--tv`, a TV trailer named with its season (`The Golden Girls S5 - Trailer.mkv`) moves
into the show's trailers as `The Golden Girls (1985)/Trailers/Season 05/Season 5 Trailer.mkv`. Moves between drives copy, then
delete the original. `--tiny-seconds 0` keeps short rips where they are.

## Typical workflow for a ripped season

1. `scripts/flatten_season.py` to bring the disc rips into the season folder.
2. `scripts/rename_episodes.py` to name the episodes and trailers from the downloaded guide.
3. Check `_duplicates`, then delete it when you're happy.
4. `scripts/check_names.py` on the show to catch anything left over.
5. Refresh the library in Plex.

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
"flatten C:\...\Season 04", or you can type them as commands:

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
  check_names.py              Find and fix names Plex won't read as intended (extras, episode format)
  movie_names.py              The movie checks behind check_names.py --movies
  plex_utils.py               Shared helpers: video lengths, safe filenames, show and season from the path
data/                       Data the scripts read
  movie_corrections.json      Typos and release years for movie names
tests/                      Unit tests for the scripts and helpers
docs/                       Project notes
```
