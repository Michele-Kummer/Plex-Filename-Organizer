# Contributing

Thank you for helping with Plex-Filename-Organizer. This guide explains how to report a problem, how the work is organised, and how to make a change.

Everyone taking part is expected to follow the [code of conduct](CODE_OF_CONDUCT.md).

## Report a bug or ask for a feature

Use **[New issue](https://github.com/Michele-Kummer/Plex-Filename-Organizer/issues/new/choose)** and pick a form:

- **Bug:** something gives a wrong name, stops, or loses a file. Give the steps to reproduce it, what you expected and what happened.
- **User story:** something the tool should do. Write it as "As a TV series owner, I want …, so that …", with the acceptance criteria that would show it is done.

For a security problem, don't open an issue. Follow the [security policy](SECURITY.md) instead.

## How the work is organised

All work is tracked in [GitHub Issues](https://github.com/Michele-Kummer/Plex-Filename-Organizer/issues) and on the [project board](https://github.com/users/Michele-Kummer/projects/2).

- **Epics** group the work by area of the tool. Every user story and bug is a sub-issue of its epic, and each bug names the user story it affects.
- **Titles** start with the area, such as `Flatten:`, `Guide:` or `Movies:`.
- **Types:** stories have the **Feature** type and bugs the **Bug** type.
- **Labels** give the epic, the priority (`P1: Critical` to `P4: Low`), a bug's severity (`S1: Blocker` to `S4: Trivial`), who found a bug (`Found by: …`), and `In progress` while someone is working on it.
- The requirements were first gathered in [docs/user-stories-and-bugs.md](../docs/user-stories-and-bugs.md). It is kept as a record, and new work goes into issues.

## Set up

1. Install Python 3.10 or later. The scripts need nothing from pip.
2. Optional: [ExifTool](https://exiftool.org/) on `PATH`, so the scripts can read video lengths. The tests don't need it.
3. To try the plugin, raise `version` in `.claude-plugin/plugin.json` and run `/plugin update plex-filename-organizer@plex-filename-organizer`, then restart Claude Code.

## Run the tests

```
python -m unittest discover -s tests
```

The tests use temporary folders of small dummy files and fixed video lengths, so they never need real videos. In Claude Code, `/run-tests` runs them and explains any failures. Run them before every pull request.

## Rules for changes

These keep the scripts safe to run on a real Plex library:

- **Preview first.** Every script lists what it would do, and renames or moves files only with `--apply`.
- **Never delete, and never rename over a file.** Copies go aside into `_duplicates`, and a rename whose target exists is reported as `SKIP`.
- **Carry on past a locked file.** Use the shared `try_move` helper, which reports a file it cannot move as `FAILED` and goes on with the rest.
- **Add tests** for new and changed code, on dummy files.
- **Update the docs** that a change affects: the README, the [cheat sheet](../docs/project-cheatsheet.md), and the skills and commands Claude reads.
- **Write clearly:** proper casing in names, headings and output text, and no double spaces or stray dashes.

## Make a change

1. Pick an issue, or open one first, so the change is agreed before the work starts.
2. Create a branch from `main`.
3. Make the change, with its tests and docs, and run the tests.
4. Write commit messages as a short summary in the imperative ("Keep empty extras folders when flattening"), with more detail below it if needed.
5. Open a pull request. Write `Fixes #<issue number>` in its description, so merging it closes the issue and the project board moves it to Done.
