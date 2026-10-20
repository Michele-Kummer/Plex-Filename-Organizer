---
name: tv-rename-episodes
description: Rename the videos in a TV season folder for Plex using that season's episode guide (titles and air dates looked up online), e.g. "Show - s03e01 - Title [2000-06-04].mkv", and name short clips as trailers. Use when the user asks to rename a season's files from the episode guide, Google, Wikipedia or TVDB, or to name disc rips like title_t00.mkv. Works for any show and season.
---

# Rename a season from its episode guide

Result format (date in brackets at the end, same as the rest of the library):

```
<Show> - s<SS>e<EE> - <Title> [<YYYY-MM-DD>].<ext>
Trailers/<Episode title>.<ext>     (inside the season folder)
```

## Steps

1. **Work out the show and season.** Take them from the request, or from a Plex-style path
   such as `...\Sex and the City (1998)\Season 03`, where the show is the parent folder
   without the year and the season is the number in the folder name. If unsure, ask.

2. **Flatten first if needed.** If the videos are in subfolders (Disc 01, Disc 02, ...), run the
   `tv-flatten-season` skill first. Disc rips reuse names like `title_t00.mkv` on every disc,
   and flattening also moves repeated clips to `_duplicates` before they are named.

3. **Get the episode guide.** The script downloads it from TVmaze when `--guide` is left out,
   using the show folder's name and year and the season number. Its first output line names the
   show and season it used. Check that they are right, and add `--year` or `--show` if not.

4. **Only if TVmaze fails or is wrong:** search for `<Show> season <N> episodes` (the Wikipedia
   season page or "List of <Show> episodes"). Write the guide as JSON in your scratchpad
   directory (not in the repo), in episode order, and pass it with `--guide`:
   ```json
   [{"episode": 1, "title": "Where There's Smoke...", "air_date": "2000-06-04"}]
   ```
   Keep titles exactly as published. The script removes characters Windows does not allow
   (`? " : * < > | / \`) and turns a colon into " - ".

5. **Check the files.** Count the long videos (episodes) and short ones (clips) and check
   durations with `exiftool -T -FileName -Duration <folder>`. The episode files should match
   the episodes missing from the folder. If there are fewer, stop and tell the user (missing
   episode, a double-length episode). If there are more, the extras are bonus features: look
   for one sitting between the episodes (a disc with one more long title than the others, an
   out-of-sequence title number such as `t16` after `t03`) and pass it with `--bonus "<file>"`.

6. **Dry run** (`${CLAUDE_PLUGIN_ROOT}` is this plugin's folder):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/rename_episodes.py" "<season folder>"
   ```
   How the script decides:
   - Files with an `sNNeNN` tag are renamed to the guide's title and date for that episode.
   - Other videos are taken in filename (disc) order. Those at least `--min-minutes` long
     (default 15) become the missing episodes in order. Use `--first N` if the first file is
     not the first missing episode. Long videos left over once the guide runs out become
     `Other/Season N Bonus NN`, and so do files passed with `--bonus`.
   - Extras go in Plex extras folders inside the season folder (`Trailers`, `Behind The Scenes`,
     `Deleted Scenes`, `Featurettes`, `Interviews`, `Scenes`, `Shorts`, `Other`). Never name an
     extra `Show - Title - Trailer.mkv`: Plex does not recognize a space after the hyphen.
   - Short clips: when there is one per episode, clip N becomes `Trailers/<episode title>`.
     Otherwise they are numbered. `--number-extras` forces numbering, and `--extra-type` picks
     another folder. When there are more clips than episodes, list them in disc order with
     durations: if the first ones are one trailer per episode (similar lengths, followed by
     different clips), ask the user and use `--trailers-first`, which puts the rest in `Other`.
     Clips the script numbered earlier are renamed again on a rerun.
   - Files in extras folders and names in Plex's own format (`... - Scene 16-deleted.mkv`) are
     left alone. Old-style `... - Trailer.mkv` names are moved into the matching folder;
     `--extras-only` does only that.
   - `--show` and `--season` override what the script reads from the folder path.

7. **Show the user the plan** and point out assumptions: that disc order is episode order,
   that clips are named in episode order, and which characters were dropped. Unless the user
   asked you to go ahead, wait for their OK.

8. **Apply** with `--apply`, list the folder and report what changed.
