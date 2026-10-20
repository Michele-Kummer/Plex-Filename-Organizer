"""Shared test helpers: temporary season folders and running a script's main()."""

import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


class SeasonTestCase(unittest.TestCase):
    """Gives each test a fresh 'Test Show (2001)/Season 02 (2002)' folder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.season = self.tmp / "Test Show (2001)" / "Season 02 (2002)"
        self.season.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, relative: str, size: int = 10) -> Path:
        path = self.season / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        return path

    def names(self, folder: Path | None = None) -> list[str]:
        return sorted(p.name for p in (folder or self.season).iterdir())

    def run_main(self, module, *args: str, lengths: dict[str, float] | None = None) -> str:
        """Run module.main() with argv, faking video lengths by filename. Returns stdout."""
        lengths = lengths or {}

        def fake_durations(paths):
            return {p: lengths.get(p.name) for p in paths}

        out = io.StringIO()
        argv = [module.__name__, *args]
        patches = [mock.patch.object(sys, "argv", argv)]
        if hasattr(module, "durations"):
            patches.append(mock.patch.object(module, "durations", fake_durations))
        with redirect_stdout(out):
            for p in patches:
                p.start()
            try:
                module.main()
            finally:
                for p in patches:
                    p.stop()
        return out.getvalue()
