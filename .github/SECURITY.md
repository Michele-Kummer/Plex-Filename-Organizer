# Security policy

## Supported versions

Only the latest version on `main` is supported. It is the one `/plugin update plex-filename-organizer@plex-filename-organizer` installs. Fixes are not made to older versions.

## What counts as a security problem

Plex-Filename-Organizer runs on your own computer and works only on the folders you point it at. Its only network connections are to [TVmaze](https://www.tvmaze.com/), over HTTPS: `rename_episodes.py` downloads a season's episode guide, and `check_names.py` looks up the year a show started. They send only the show name and TVmaze's own number for the show. It runs ExifTool, if it is installed, to read video lengths.

Please report anything that could:

- rename, move or change a file outside the folder you gave it, or change any file during a preview (without `--apply`);
- lose a video, or rename one over another file;
- run a command or code taken from a file's name, a folder's name or an episode guide;
- send a file, or anything about your library other than the show name, anywhere.

A wrong name, a slow run or a script that stops with an error is a bug rather than a security problem. Please report those with the [Bug form](https://github.com/Michele-Kummer/Plex-Filename-Organizer/issues/new/choose).

## How to report one

Report it privately, so it can be fixed before anyone else learns of it:

1. Go to the repository's **Security** tab and choose **[Report a vulnerability](https://github.com/Michele-Kummer/Plex-Filename-Organizer/security/advisories/new)**.
2. Say what happens, the steps to reproduce it, and your version of Windows, Python and the scripts.

Please don't open a public issue, pull request or discussion about it.

## What happens next

- The report is read and answered as soon as possible.
- Once the problem is confirmed, it is fixed on `main` and a security advisory is published with the fix.
- You are credited in the advisory, unless you would rather not be.
