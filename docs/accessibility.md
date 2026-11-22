# Accessibility statement

Plex-Filename-Organizer should be usable by everyone who keeps a Plex library, including people who use a screen reader, a keyboard only, or high-contrast or magnified displays. This statement says how accessible it is today, where it falls short, and how to report a problem.

It covers the Python scripts, the Claude Code plugin and this repository's documentation. It was written on 2026-11-22.

## How accessible it is

**The scripts and the plugin**

- Everything is done by typing. Nothing needs a mouse.
- All output is plain text with no colour, so a screen reader can read it in the terminal and nothing depends on colour.
- Each line that reports on a file starts with a word that says what happened, such as `RENAME`, `SKIP`, `FAILED` or `CHECK`, followed by the file.
- A preview ends with a line saying how to make the changes.
- With the plugin, you can ask for each step in plain English, and Claude shows each preview before anything is renamed.

**The documentation**

- The README and the documents use headings in order, lists and tables, so they can be navigated by heading with a screen reader.
- The examples of names and folders are text in code blocks, not pictures.

## Known limits

- The scripts have not been tested with a screen reader or other assistive technology, and have not been audited against a standard.
- The examples show long file names side by side, which can be hard to follow when read aloud or magnified.
- A whole library produces a lot of output. To review it, send it to a file, for example `... > run.txt`, and read the counts at the end first.

## Report a problem

If something is hard or impossible to use with the way you work, please open an issue with the **[Bug form](https://github.com/Michele-Kummer/Plex-Filename-Organizer/issues/new/choose)**. Say "accessibility" under **Affects**, and describe what you were trying to do, what assistive technology you use, if any, and what happened. Issues about accessibility get the `accessibility` label.
