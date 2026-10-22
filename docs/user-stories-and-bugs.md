# User stories and bugs

This document records the requirements for **Plex-Filename-Organizer** as user stories grouped into epics, followed by every known bug, open and resolved, and who found each one. It is meant as a worked example of how requirements were gathered and bugs identified for this project. Add to it as the project changes.

**How it was made (2026-10-22)**

- **User stories:** written with Claude Code (Claude Opus 5.5) by reading the scripts, docs, tests and git history. Each story's acceptance criteria describe how the project behaves today.
- **Open bugs:** found by Claude while writing the stories. Each one was reproduced on synthetic files.
- **Resolved bugs:** taken from the git history. Michele Kummer, the project's author, confirmed finding BUG-02, BUG-03, BUG-04 and BUG-07. Who found the others is still to be confirmed.

**Status** on each story is *Done* when every criterion holds, or *Partly done* when some do not, with the gap named.

Each epic below can be expanded and collapsed.

**Who the stories are for**

- **TV series owner:** someone who rips TV seasons from disc (or collects episodes from elsewhere) and wants Plex to match every episode, trailer and extra.
- **Movie owner:** the same person, in stories about the movie library.
- **Video owner:** the same person, in stories that apply to both TV series and movies.
- **Maintainer:** whoever changes or tests the scripts.

Each bug says what it **Affects**: episodes, extras, movies, or something else (setup, docs).

## At a glance

| | Count |
|---|---|
| Epics | 8 |
| User stories | 31 (29 Done, 2 Partly done) |
| Bugs | 9 (2 open, 7 resolved) |

| Bugs found by | Open | Resolved | Total |
|---|---|---|---|
| Michele Kummer | 0 | 4 | 4 |
| Claude | 2 | 0 | 2 |
| Automated tests | 0 | 0 | 0 |
| To confirm | 0 | 3 | 3 |

---

## Part 1 — User stories

<details>
<summary><strong>Epic 1 — Setup</strong> (US-01 to US-02)</summary>

Install the scripts or the plugin and know what they need.

#### US-01 Install the plugin
As a TV series owner, I want to install the Claude Code plugin with one command, so that I can organize a season from any folder.

- `/plugin install plex-filename-organizer --marketplace Michele-Kummer/Plex-Filename-Organizer` installs it from GitHub. A local copy can be added with `/plugin marketplace add`.
- After a change to the repo, raising `version` in `.claude-plugin/plugin.json` and running `/plugin update` picks it up.

**Status:** Done

#### US-02 Work without extra tools
As a video owner, I want the scripts to run with only Python installed, so that setup is quick.

- Requires Python 3.10 or later and nothing from pip.
- ExifTool on `PATH` is optional. Without it, video lengths are unknown and the scripts go by file size and order.

**Status:** Done

</details>

<details>
<summary><strong>Epic 2 — Safe changes</strong> (US-03 to US-06)</summary>

Every script must be safe to run on a real library.

#### US-03 Preview before anything changes
As a video owner, I want every script to list what it would do and change nothing until I say so, so that I can check the plan first.

- Every script is a dry run unless `--apply` is given, and the dry run ends with a line saying how to apply.

**Status:** Done

#### US-04 Never lose a file
As a video owner, I want files set aside rather than deleted, and never renamed over another file, so that a mistake can always be undone.

- Copies go to `_duplicates`, and movie rips under 10 seconds go to `_Tiny clips`. Deleting them is left to the user.
- A rename whose target already exists is reported as `SKIP` (or, in `flatten_season.py`, stops the run before anything moves).
- A copy number is only removed (`Title_2.mkv` to `Title.mkv`) when the clean name is free or holds the same video. When it holds a different video, both are left to compare.

**Status:** Done

#### US-05 Carry on past a locked file
As a video owner, I want a file that is open in Plex, a player or Explorer's preview pane reported and skipped, so that one locked file does not stop the run.

- `try_move` reports the file as `FAILED` with the reason, leaves it where it was and goes on with the rest.
- The summary says how many failed and to close the program and run again.

**Status:** Done

#### US-06 Move between drives
As a video owner, I want extras on another drive (`E:\Trailers or Bonus`) moved into my library on `C:`, so that I don't have to copy them by hand.

- A move to another drive copies the file and then removes the original.
- If the original is locked after copying, the new copy is removed, so the file is not left in two places.

**Status:** Done

</details>

<details>
<summary><strong>Epic 3 — Flatten disc rips</strong> (US-07 to US-09)</summary>

Bring ripped videos up out of their disc folders.

#### US-07 Move disc rips into the season folder
As a TV series owner, I want every video in `Disc 01`, `Disc 02`, ... moved into the season folder, so that the rename step can see them all.

- Each moved file gets its folder name in front (`Disc 02 - title_t03.mkv`), so names stay unique and sort in disc order.
- Folders left empty are removed. Non-video files left behind are listed.

**Status:** Done

#### US-08 Set aside repeated copies
As a TV series owner, I want the trailers repeated on every disc kept once, so that I don't end up with several copies of each.

- A file counts as a copy only when it has the same extension, the same length, a size within 1 KB (`--size-tolerance`) and the same video data at sampled points as a file already kept.
- Copies go to `_duplicates` in the season folder.

**Status:** Done

#### US-09 Leave extras and holding folders alone
As a TV series owner, I want Plex extras folders (`Trailers`, `Other`, ...) and folders starting with `_` left as they are, so that flattening does not undo earlier work.

- Videos in those folders are not moved, and the folders are kept.

**Status:** Partly done. Empty extras folders and empty `_` folders are still removed (BUG-08).

</details>

<details>
<summary><strong>Epic 4 — Name episodes from the guide</strong> (US-10 to US-17)</summary>

Give every episode and clip the name Plex expects.

#### US-10 Download the episode guide
As a TV series owner, I want the season's titles and air dates looked up for me, so that I don't have to type a guide.

- With no `--guide`, the guide is downloaded from TVmaze. The show name, year and season come from the folder path (`Show (1998)\Season 03`).
- `--year` picks the right show when several share a name, `--show` and `--season` override the folder, and `--save-guide` keeps a copy.
- The first line of output says which show and season were used.
- A show folder may carry a Plex ID tag (`Show (1998) {tvdb-76648}`).

**Status:** Partly done. A show folder with a Plex ID tag is not understood (BUG-09).

#### US-11 Use my own guide
As a TV series owner, I want to pass my own guide file, so that I can name seasons TVmaze gets wrong.

- `--guide FILE` reads a JSON list of `episode`, `title` and optional `air_date`. Files saved by Notepad (with a byte order mark) are accepted.
- A missing or invalid guide gives a clear error.

**Status:** Done

#### US-12 Name episodes the Plex way
As a TV series owner, I want episodes named `Show (1998) - s03e01 - Title [2000-06-04].mkv`, so that Plex matches them and the date sorts last.

- The show folder's name and year come first. Files that already have an `s03e05` tag get that episode's title and date.
- Characters Windows does not allow are removed, and a colon becomes ` - `.
- With no air date, the name has no date.

**Status:** Done

#### US-13 Number untagged rips in disc order
As a TV series owner, I want untagged rips numbered as the missing episodes in disc order, so that a freshly flattened season gets named in one go.

- Videos at least 15 minutes long (`--min-minutes`) are episodes, taken in filename order. `--first` sets the first episode number.
- Long videos left once the guide runs out become `Other/Season N Bonus NN`. `--bonus FILE` marks a bonus that sits between episodes, so later episodes keep their numbers.
- A count that does not match the guide gives an `ERROR` or `WARNING` line.

**Status:** Done

#### US-14 Put trailers in the show's Trailers folder
As a TV series owner, I want short clips filed as trailers by season, so that Plex shows them with the show.

- Clips go in `Show (1998)/Trailers/Season 03/`, named after the episodes when there is one per episode, else numbered (`Season 3 Trailer 01`). `--number-extras` always numbers them.
- The names leave out the show, since the folders say it.
- With more clips than episodes, `--trailers-first` names the first ones after the episodes and puts the rest in `Other`.

**Status:** Done

#### US-15 Put other extras in Plex extras folders
As a TV series owner, I want deleted scenes, featurettes and the like in Plex's folders, so that Plex reads their type.

- Extras go in `Behind The Scenes`, `Deleted Scenes`, `Featurettes`, `Interviews`, `Scenes`, `Shorts` or `Other` inside the season folder. `--extra-type` picks the type for short clips.
- Old-style names (`Show - Title - Trailer.mkv`) are moved into the matching folder. `--extras-only` does only that and needs no guide.
- Names already in Plex's own format (`... - Scene 16-deleted.mkv`) and files in extras folders are left alone.

**Status:** Done

#### US-16 Run it again safely
As a TV series owner, I want a second run to fix what the first got wrong, so that I can correct options and rerun.

- Clips the script numbered on an earlier run are named again.
- Files already correct are counted as correct, not renamed.

**Status:** Done

#### US-17 Move the date to the end
As a TV series owner, I want older names like `Show - s01e06 - 1998-07-12 - Title` turned into `Show - s01e06 - Title [1998-07-12]`, so that they match the rest of the library.

- `move_date_to_end.py` handles a date followed by ` - Title` or `-Title`.
- Files in any other format are skipped.

**Status:** Done

</details>

<details>
<summary><strong>Epic 5 — Check names across the TV library</strong> (US-18 to US-22)</summary>

Find and fix names Plex won't read as intended, on a season, a show or the whole library.

#### US-18 Fix episode names
As a TV series owner, I want every episode name made consistent, so that Plex matches them all.

- Names become `Show (1998) - s##e## - Title [date]`: show and year first, tag lower case and padded to two digits (longer numbers and split-episode letters kept), the date at the end in brackets, parts joined with ` - `.
- Date-based episodes become `Show (1998) - 2013-08-12 - Title`.
- Years in parentheses become brackets, unless the episode has an air date.
- Hyphens between words get a space on each side; hyphens inside words (`Catch-38`) stay.

**Status:** Done

#### US-19 Fix extras and trailers
As a TV series owner, I want extras named the old way, or by keyword, moved into Plex's folders, so that Plex shows them as extras.

- Keywords include Trailer, Bonus, Deleted Scene, Making of and Eggs. Easter eggs keep "Eggs" in the name.
- Folders such as `Extras` or `Bonus Features` get Plex's names, and the show name is removed from files inside them.
- Trailers in a season's own `Trailers` folder, or in the old `Show (1998) - S01 - Title-trailer` layout, move to the show's `Trailers/Season ##`.

**Status:** Done

#### US-20 Fix season folders
As a TV series owner, I want season folders named `Season 01`, so that they sort in order and Plex does not mismatch the show.

- Season folders get two digits and no year (`Season 1 (2003)` becomes `Season 01`).
- Show folders with no year are reported, with TVmaze's start year as a hint.

**Status:** Done

#### US-21 Remove copy numbers
As a video owner, I want numbers added to dodge a name clash removed, so that `Title_2.mkv` becomes `Title.mkv`.

- The default pattern is `_` and up to 5 digits. In `check_names.py`, `--collision-suffix` sets another pattern, or `""` turns it off.
- `movie_names.py` removes the default pattern from movie extras and rips too.
- A copy of a file already holding the clean name goes to `_duplicates`. A different video is left, with a `SKIP`.

**Status:** Done

#### US-22 Know what needs a person
As a TV series owner, I want what the script can't fix listed separately, so that I know what to look at by hand.

- `CHECK` lines list unplaceable videos, disc folders still to flatten, unknown folders, more than one date, mistyped dates, tags with no `e` and episodes starting with another show's name.
- Each `RENAME` line names its kind of fix, and the run ends with a count of each kind.

**Status:** Done

</details>

<details>
<summary><strong>Epic 6 — Movies</strong> (US-23 to US-27)</summary>

Give every movie and its extras the layout Plex expects: `Title (Year) {edition-Name}`.

#### US-23 Fix movie folder names
As a movie owner, I want each movie folder named `Title (Year) {edition-Name}`, so that Plex matches the right release.

- Edition tags are corrected (`{editon-Unrated}`, `{edition - Unreated}`, a missing `}`) and moved after the year.
- Double spaces, semicolons and Roman numeral casing (`Young Guns Ii`) are fixed.
- The movie file inside is renamed with its folder.

**Status:** Done

#### US-24 Correct titles and years
As a movie owner, I want known typos and release years corrected, so that Plex does not match a DVD year or a misspelled title.

- Corrections come from `data/movie_corrections.json` (`Castaway ()` to `Cast Away (2000)`), which the user can add to.
- Movies with no year are reported.

**Status:** Done

#### US-25 Put extras in their movie's folder
As a movie owner, I want trailers and bonus material, loose or in a separate folder, moved into each movie's folder by type, so that Plex shows them with the movie.

- Extras are typed by words in their names (trailer, deleted, behind the scenes or making of, featurette, interview, short, bloopers, bonus); anything else goes in `Other`.
- `- Bonus` folders are merged into the movie's folder, and `Special Features` folders are sorted into type folders.
- Extras whose movie has no folder are reported.

**Status:** Done

#### US-26 Set aside studio intros, copies and tiny rips
As a movie owner, I want studio intros, repeated copies and menu rips out of the way, so that only real extras remain.

- Studio intros go to `_Intros` as `Intro - Universal.mkv`.
- Of two copies, the `.mp4` is kept and the other goes to `_duplicates`.
- Raw rips shorter than 10 seconds (`--tiny-seconds`, `0` to keep them) go to `_Tiny clips`.
- Raw rips and numbered generic names that need watching are reported.

**Status:** Done

#### US-27 Send TV trailers to their show
As a TV series owner, I want TV trailers found among movie extras moved to the show, so that they don't sit in the wrong library.

- With `--tv`, a trailer named with its season (`The Golden Girls S5 - Trailer.mkv`) moves to `The Golden Girls (1985)/Trailers/Season 05/Season 5 Trailer.mkv`.
- Without `--tv`, TV trailers are reported.

**Status:** Done

</details>

<details>
<summary><strong>Epic 7 — Claude Code plugin</strong> (US-28 to US-29)</summary>

Let Claude run the workflow.

#### US-28 Organize a season with one command
As a TV series owner, I want to type one command for a whole season, so that I don't have to remember the steps.

- `/organize-season <folder>` flattens, renames from the guide and moves any dates to the end, showing each preview before applying.

**Status:** Done

#### US-29 Ask for one step in plain words
As a TV series owner, I want to ask for a single step ("flatten Season 04"), so that I can run just what I need.

- The skills `tv-flatten-season`, `tv-rename-episodes` and `tv-move-date-to-end` match plain requests and can also be typed as commands.

**Status:** Done

</details>

<details>
<summary><strong>Epic 8 — Maintenance</strong> (US-30 to US-31)</summary>

Keep the project easy to change safely.

#### US-30 Run the tests with nothing to install
As a maintainer, I want unit tests that need nothing but Python, so that anyone can run them.

- `python -m unittest discover -s tests` runs 115 tests on temporary folders of dummy files, with fixed video lengths in place of ExifTool.
- `/run-tests` runs them and explains any failures.

**Status:** Done

#### US-31 Keep the docs current
As a maintainer, I want the README, cheat sheet, skills and this file updated with each change, so that the docs match the scripts.

- Each feature commit so far updated the README, cheat sheet and skills.

**Status:** Done

</details>

---

## Part 2 — Bugs

Severity: **High** means files are lost or the scripts can't be used. **Medium** means a wrong result, or a step that fails or stops. **Low** means a cosmetic problem, or one with a workaround.

<details>
<summary><strong>Open bugs</strong> (2, both found by Claude on 2026-10-22)</summary>

Each was reproduced on synthetic files, except where noted.

#### BUG-08 Flattening removes empty extras and holding folders
**Severity:** Low · **Found by:** Claude · **Affects:** folders · **Where:** [flatten_season.py](../scripts/flatten_season.py) `main`

The docstring and README say Plex extras folders and folders starting with `_` are left as they are. Their videos are, but the empty-folder pass looks at every folder except `_duplicates`.

**Steps to reproduce**
1. Make `Season 01` with `Disc 01\a.mkv`, an empty `Featurettes` folder and an empty `_keep` folder.
2. Run `flatten_season.py` on it with `--apply`.

**Expected:** Only `Disc 01` is removed.
**Actual:** `Removed empty folders: Disc 01, Featurettes, _keep`.

#### BUG-09 Show folders with a Plex ID tag are not understood
**Severity:** Medium · **Found by:** Claude · **Affects:** episodes and trailers · **Where:** `show_and_season_from_folder`, `show_year_from_folder` in [plex_utils.py](../scripts/plex_utils.py)

Plex allows an ID tag on show folders, such as `Sex and the City (1998) {tvdb-76648}`. Both helpers only strip or read a year at the very end of the name.

**Steps to reproduce:** call the helpers on `TV\Sex and the City (1998) {tvdb-76648}\Season 03`.
**Expected:** show `Sex and the City`, year `1998`.
**Actual:** show `Sex and the City (1998) {tvdb-76648}`, year `None`. `rename_episodes.py` would search TVmaze for the whole string with no year to pick by, and episode names would start with the ID tag.

</details>

<details>
<summary><strong>Resolved bugs</strong> (7, 4 found by Michele Kummer, 3 still to be confirmed)</summary>

The list is oldest first. **Fixed in** gives the commit.

| ID | Bug | Affects | Severity | Found by | Fixed in |
|---|---|---|---|---|---|
| BUG-01 | Two different trailers set aside as copies | Extras | Medium | To confirm | `c918004` |
| BUG-02 | Renaming stopped when there were more long videos than episodes | Episodes | Medium | Michele Kummer | `c918004` |
| BUG-03 | Clips numbered on an earlier run were not renamed on a rerun | Extras | Low | Michele Kummer | `c918004` |
| BUG-04 | Plex did not recognize extras named `Show - Title - Trailer.mkv` | Extras | Medium | Michele Kummer | `db3374f` |
| BUG-05 | Flattening moved videos out of Plex extras folders | Extras | Medium | To confirm | `db3374f` |
| BUG-06 | A date followed by `-Title` with no space was not moved | Episodes | Low | To confirm | `db3374f` |
| BUG-07 | A locked file or a move to another drive stopped the run | All files | Medium | Michele Kummer | `9fb5d92` |

#### BUG-01 Two different trailers set aside as copies
**Found by:** to confirm · **Affects:** extras (trailers) · **Fixed in:** `c918004`

`flatten_season.py` treated files with the same length and a size within 1 KB as copies. Two different trailers of the same length can be only a few hundred bytes apart, so one was moved to `_duplicates`.
**Fix:** Samples of the video data are also compared (`same_content`) before a file counts as a copy.

#### BUG-02 Renaming stopped when there were more long videos than episodes
**Found by:** Michele Kummer · **Affects:** episodes · **Fixed in:** `c918004`

Discs with a bonus feature as long as an episode left more long videos than the guide had episodes, and `rename_episodes.py` stopped with an error.
**Fix:** Long videos left once the guide runs out become `Season N Bonus NN` extras, and `--bonus FILE` marks a bonus that sits between episodes.

#### BUG-03 Clips numbered on an earlier run were not renamed on a rerun
**Found by:** Michele Kummer · **Affects:** extras · **Fixed in:** `c918004`

Clips already named `Season N Extra NN - Trailer` were treated as finished, so rerunning with different options could not fix them.
**Fix:** Names the script gave on an earlier run are recognized and named again.

#### BUG-04 Plex did not recognize extras named `Show - Title - Trailer.mkv`
**Found by:** Michele Kummer · **Affects:** extras · **Fixed in:** `db3374f`

Plex's inline extras need the type straight after the hyphen (`Title-trailer`), so the space the scripts wrote made Plex treat extras as unknown videos.
**Fix:** Extras go in Plex's type folders instead, old-style names are moved into them, and the new `check_names.py` finds any left.

#### BUG-05 Flattening moved videos out of Plex extras folders
**Found by:** to confirm · **Affects:** extras · **Fixed in:** `db3374f`

Once extras lived in folders such as `Trailers` and `Other`, `flatten_season.py` would have moved them back up into the season folder as `Trailers - Title.mkv`.
**Fix:** Plex extras folders are skipped.

#### BUG-06 A date followed by `-Title` with no space was not moved
**Found by:** to confirm · **Affects:** episodes · **Fixed in:** `db3374f`

`move_date_to_end.py` expected ` - ` after the date, so `Show - s01e06 - 1998-07-12 -Title` was skipped.
**Fix:** The space after the hyphen is optional.

#### BUG-07 A locked file or a move to another drive stopped the run
**Found by:** Michele Kummer · **Affects:** all files · **Fixed in:** `9fb5d92`

A file open in Plex, a player or Explorer's preview pane could not be renamed, which stopped the script part way. Renaming onto another drive was not possible at all.
**Fix:** The shared `try_move` helper copies across drives, reports a locked file as `FAILED` and carries on with the rest.

</details>
