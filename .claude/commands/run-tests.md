---
description: Run the Plex-Filename-Organizer test suite and explain any failures
---

From the repository root, run:

```
python -m unittest discover -s tests
```

If every test passes, report the count. If any fail, show each failing test with its error,
work out whether the script or the test is wrong, and propose a fix. Don't change any files
without asking.
