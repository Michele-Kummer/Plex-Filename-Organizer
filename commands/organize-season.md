---
description: Organize a ripped TV season for Plex - flatten disc folders, then rename from the episode guide
argument-hint: <season folder>
---

Organize this TV season folder for Plex: $ARGUMENTS

If no folder was given, ask for one.

1. List the folder at every depth.
2. If there are videos in subfolders (Disc 01, Disc 02, ...), follow the `tv-flatten-season` skill.
3. Follow the `tv-rename-episodes` skill to look up the episode guide and name the episodes and
   trailers.
4. If any episodes are still named `Show - sNNeNN - YYYY-MM-DD - Title`, follow the
   `tv-move-date-to-end` skill.

Show the preview of each step and wait for my OK before applying, unless I said to go ahead.
End with the final folder listing, the number of copies in `_duplicates`, and every assumption
you made (episode order, trailer order, characters dropped from titles).
