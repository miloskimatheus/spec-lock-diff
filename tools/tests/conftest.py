"""Helpers every test uses. They run slp.py as a subprocess, exactly like CI does,
so what is tested is the real entry point and not an internal function."""

import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1]
SLP = TOOLS / "slp.py"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def run_slp(args, cwd):
    """Run slp.py with args in cwd. Returns (exit code, stdout, stderr)."""
    done = subprocess.run([sys.executable, str(SLP)] + list(args), cwd=str(cwd),
                          capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr
