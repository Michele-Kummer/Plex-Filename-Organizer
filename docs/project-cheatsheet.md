# Project cheatsheet

## Organize a season by hand (PowerShell)

Run each step without `--apply` first, check the preview, then run it again with `--apply`.


```powershell
cd C:\Code\Plex-Filename-Organizer
$root  = "C:\Users\shell\Videos\TV Shows\Sex and the City (1998)\Season 04 (2001)"
python scripts\flatten_season.py $root              # preview
python scripts\flatten_season.py $root --apply      # move files, copies go to _duplicates
python scripts\rename_episodes.py $root             # preview, downloads the episode guide from TVmaze
python scripts\rename_episodes.py $root --apply     # rename
```
The episode guide is downloaded on every run, using the show name and year (`Sex and the City (1998)`)
and the season number in `$root`. To do another season, just change `$root`.

Check the preview:
- **Guide:** the first line says which show and season the titles came from. If it picked the wrong
  show, add `--year 1998` or `--show "Exact Name"`. To use your own guide instead, add `--guide file.json`.
- **Episode numbers:** episodes are numbered in disc order (Disc 01 first). Long videos left over
  once the guide runs out become bonus extras. If a bonus sits between episodes (e.g. a disc with one
  more long title than the others), add `--bonus "Disc 03 - title_t16.mkv"`.
- **Trailers:** short clips are named after the episodes in the same order. Open two or three to check.
  If there are more clips than episodes they are numbered instead. When the first ones are the episode
  trailers, add `--trailers-first`: those get episode names and the rest become `Other` extras.
- **Warnings:** an `ERROR` or `WARNING` line means the file count doesn't match the guide. Fix that before applying.

### 5. Old-style names only: move the date to the end

Only for seasons already named `Show - s01e06 - 1998-07-12 - Title`. Ripped seasons don't need it,
because step 4 already puts the date at the end.

```powershell
python scripts\move_date_to_end.py $root            # preview
python scripts\move_date_to_end.py $root --apply    # rename
```

### 6. Finish

```powershell
Get-ChildItem $root                       # check the result
Get-ChildItem "$root\_duplicates"         # copies kept from flattening
Remove-Item "$root\_duplicates" -Recurse  # optional: delete the copies once you're happy
```


## Or let Claude do it

In Claude Code, from any folder:

```
/organize-season C:\Users\shell\Videos\TV Shows\Sex and the City (1998)\Season 04 (2001)
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
