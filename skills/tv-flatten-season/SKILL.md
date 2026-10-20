---
name: tv-flatten-season
description: Flatten a TV season folder for Plex by moving videos out of subfolders (Disc 01, Disc 02, ...) into the season folder and moving repeated copies to _duplicates. Use when the user asks to flatten a season, move disc rips up to the root or season folder, or clean up disc folders. Run it before tv-rename-episodes when the season is still in disc folders.
---

# Flatten a season folder

Moves every video in the subfolders of a season folder up into the season folder. Each moved
file gets its subfolder name as a prefix (`Disc 02/title_t03.mkv` -> `Disc 02 - title_t03.mkv`),
so names stay unique and filename order still matches disc order.

DVD and Blu-ray rips often repeat the same short clips (trailers, previews) on every disc. A file
with the same extension, the same duration, a size within 1 KB and the same video data (sampled
at several points) as a file already kept counts as a copy and goes to `_duplicates` in the
season folder. **Nothing is deleted.** Subfolders left
empty are removed. Folders whose names start with `_` and Plex extras folders (`Trailers`,
`Deleted Scenes`, `Featurettes`, `Other`, ...) are never touched.

## Steps

1. Get the season folder from the user's request. If it is missing or ambiguous, ask.
2. List the folder at every depth so you know what is there (counts per subfolder, any
   non-video files).
3. Dry run (`${CLAUDE_PLUGIN_ROOT}` is this plugin's folder):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/flatten_season.py" "<season folder>"
   ```
4. Check the plan: the number of copies should make sense. For example, the same 18 clips on
   each of 3 discs gives 36 copies. If real episodes are flagged as copies, run again with a
   smaller `--size-tolerance`.
5. Apply with `--apply`, then list the folder and report: files moved, copies in `_duplicates`,
   folders removed, and any non-video files left in subfolders (these stay put; ask the user
   what to do with them).

ExifTool (on PATH) supplies durations. Without it, copies are matched by size alone.

If the user asks to rename the episodes as well, continue with the `tv-rename-episodes` skill.
