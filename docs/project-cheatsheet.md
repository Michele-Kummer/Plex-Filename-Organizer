# Project cheatsheet

Run each step without `--apply` first, check the preview, then run it again with `--apply`.

## Full cleanup, in order

```powershell
cd C:\Code\Plex-Filename-Organizer
$tv     = "C:\Users\shell\Videos\TV Shows"
$movies = "C:\Users\shell\Videos\Movies"
$bonus  = "E:\Trailers or Bonus"

# 1. Each newly ripped TV season (repeat per season)
$root = "$tv\Sex and the City (1998)\Season 04"
python scripts\flatten_season.py $root
python scripts\flatten_season.py $root --apply
python scripts\rename_episodes.py $root
python scripts\rename_episodes.py $root --apply
python scripts\move_date_to_end.py $root            # only old "Show - s01e06 - 1998-07-12 - Title" names
python scripts\move_date_to_end.py $root --apply

# 2. Whole TV library: extras, season trailers, copy numbers (_2)
python scripts\check_names.py $tv
python scripts\check_names.py $tv --apply

# 3. Movie library before the bonus folder, so extras land in the fixed folder names
python scripts\check_names.py $movies --movies $movies
python scripts\check_names.py $movies --movies $movies --apply

# 4. Bonus folder: extras into their movie folders (E: to C: copies, so it is slow)
python scripts\check_names.py $bonus --movies $movies --tv $tv
python scripts\check_names.py $bonus --movies $movies --tv $tv --apply

# 5. Review what was set aside, then delete it
Get-ChildItem "$bonus\_duplicates", "$bonus\_Tiny clips", "$movies\_duplicates", "$movies\_Tiny clips" -Recurse -ErrorAction SilentlyContinue
Remove-Item "$bonus\_duplicates", "$bonus\_Tiny clips", "$movies\_duplicates", "$movies\_Tiny clips" -Recurse -ErrorAction SilentlyContinue
Get-ChildItem $tv -Directory -Recurse -Filter _duplicates | Remove-Item -Recurse

# 6. Run 2-4 again without --apply: only CHECK lines (raw rips, generic names) should be left
```

Then refresh the TV and movie libraries in Plex. The sections below explain each step.


```powershell
cd C:\Code\Plex-Filename-Organizer
$root  = "C:\Users\shell\Videos\TV Shows\Sex and the City (1998)\Season 04"
python scripts\flatten_season.py $root              # preview
python scripts\flatten_season.py $root --apply      # move files, copies go to _duplicates
python scripts\rename_episodes.py $root             # preview, downloads the episode guide from TVmaze
python scripts\rename_episodes.py $root --apply     # rename
```


Check the preview:
- **Guide:** the first line says which show and season the titles came from. If it picked the wrong
  show, add `--year 1998` or `--show "Exact Name"`. To use your own guide instead, add `--guide file.json`.
- **Episode numbers:** episodes are numbered in disc order (Disc 01 first). Long videos left over
  once the guide runs out become bonus extras. If a bonus sits between episodes (e.g. a disc with one
  more long title than the others), add `--bonus "Disc 03 - title_t16.mkv"`.
- **Episodes** are named `Show (1998) - s04e01 - Title [date]`: show and year first.
- **Trailers:** short clips go in the show's `Trailers\Season 04\` folder, named after the episodes
  in the same order (`Trailers\Season 04\<episode>.mkv`), without the show name. Open two or
  three to check. If there are more clips than episodes they are numbered instead. When the first ones
  are the episode trailers, add `--trailers-first`: those get episode names and the rest go in `Other\`.
- **Other extras** (deleted scenes, featurettes, ...) go in Plex's folders inside the season folder:
  `Behind The Scenes`, `Deleted Scenes`, `Featurettes`, `Interviews`, `Scenes`, `Shorts`, `Other`.
  `check_names.py` moves trailers from a season's own `Trailers\` folder, and old
  `Show (1998) - S04 - Title-trailer` names, to the show's `Trailers\Season 04\`.
  To move old `Show - Title - Trailer.mkv` names into them without touching episodes, run
  `python scripts\rename_episodes.py $root --extras-only --apply`.
- **Warnings:** an `ERROR` or `WARNING` line means the file count doesn't match the guide. Fix that before applying.

### 5. Old-style names only: move the date to the end

Only for seasons already named `Show - s01e06 - 1998-07-12 - Title`. Ripped seasons don't need it,
because step 4 already puts the date at the end.

```powershell
python scripts\move_date_to_end.py $root            # preview
python scripts\move_date_to_end.py $root --apply    # rename
```

### Check names any time

On a season, a show or the whole library. `RENAME` lines are fixed with `--apply`; `CHECK` lines
need a look by hand. It also removes copy numbers (`Title_2.mkv` -> `Title.mkv`); a copy of a file
that is already there goes to `_duplicates`, and a `SKIP` means the two files differ: compare them.

```powershell
python scripts\check_names.py "C:\Users\shell\Videos\TV Shows"            # report
python scripts\check_names.py "C:\Users\shell\Videos\TV Shows" --apply    # fix
```

### Movies

Fix the movie library first, then move the trailers and bonus material into it. Same rule: preview,
then `--apply`.

```powershell
$movies = "C:\Users\shell\Videos\Movies"
python scripts\check_names.py $movies --movies $movies                     # preview library fixes
python scripts\check_names.py $movies --movies $movies --apply             # rename folders and movie files
python scripts\check_names.py "E:\Trailers or Bonus" --movies $movies --tv "C:\Users\shell\Videos\TV Shows"            # preview
python scripts\check_names.py "E:\Trailers or Bonus" --movies $movies --tv "C:\Users\shell\Videos\TV Shows" --apply    # move extras
```

- Release years and retitles (`Castaway` -> `Cast Away (2000)`) come from `data\movie_corrections.json`.
  Add a line there when Plex matches a movie wrongly.
- `CHECK` lines for raw rips (`A1_t01.mkv`) and `Special Features (3)` names: watch them, rename
  each one and put it in its type folder (`Featurettes`, `Deleted Scenes`, `Behind The Scenes`, ...).
- Look through `_Tiny clips` (rips under 10 seconds: menus, logos) and `_duplicates`, then delete them.
- Moving from E: to C: copies each file, so the bonus run takes a while.

### 6. Finish

```powershell
Get-ChildItem $root                       # check the result
Get-ChildItem "$root\_duplicates"         # copies kept from flattening
Remove-Item "$root\_duplicates" -Recurse  # optional: delete the copies once you're happy
```


## Or let Claude do it

In Claude Code, from any folder:

```
/organize-season C:\Users\shell\Videos\TV Shows\Sex and the City (1998)\Season 04
```

Claude looks up the episode guide, runs steps 2–5 and shows each preview before changing anything.

## Tests

```powershell
python -m unittest discover -s tests
```

## Updating the plugin

The installed plugin is a copy taken when you install. After you change the repo:

1. Raise `version` in `.claude-plugin\plugin.json`.
2. Run `/plugin update plex-filename-organizer@plex-filename-organizer`.
3. Restart Claude Code.
