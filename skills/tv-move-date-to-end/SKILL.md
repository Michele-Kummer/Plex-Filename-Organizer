---
name: tv-move-date-to-end
description: Move the air date in TV episode filenames to the end in brackets, "Show - s01e06 - 1998-07-12 - Title" -> "Show - s01e06 - Title [1998-07-12]". Use when the user asks to move the date to the end, put dates in brackets, or make a season's names match the rest of the library. Works for any show and season.
---

# Move the date to the end

```
Show - s01e06 - 1998-07-12 - Secret Sex.mp4  ->  Show - s01e06 - Secret Sex [1998-07-12].mp4
```

Only files named `<anything> - sNNeNN - YYYY-MM-DD - <title>` change. Trailers, extras and files
already in the new format are skipped. A file is never renamed over an existing one.

## Steps

1. Get the folder or folders from the request. To do a whole show, run once per season folder.
2. Dry run (`${CLAUDE_PLUGIN_ROOT}` is this plugin's folder):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/move_date_to_end.py" "<season folder>"
   ```
3. Show the user the planned renames. Apply with `--apply` (straight away if the user already
   asked for the rename), then report the count and anything skipped.
