# Project cheatsheet

## Organize a season by hand (PowerShell)

Run each step without `--apply` first, check the preview, then run it again with `--apply`.

### 1. Set up

```powershell
cd C:\Code\Plex-Filename-Organizer
$root  = "C:\Users\shell\Videos\TV Shows\Sex and the City (1998)\Season 04 (2001)"
$guide = "$env:TEMP\guide.json"
python scripts\flatten_season.py $root              # preview
python scripts\flatten_season.py $root --apply      # move files, copies go to _duplicates
notepad $guide
python scripts\rename_episodes.py $root --guide $guide              # preview
python scripts\rename_episodes.py $root --guide $guide --apply      # rename
```
Check the preview:
- **Episode numbers:** episodes are numbered in disc order (Disc 01 first).
- **Trailers:** short clips are named after the episodes in the same order. Open two or three to check.
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
