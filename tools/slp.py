#!/usr/bin/env python3
"""slp, vendored: `python tools/slp.py check | gate | compare`.

The tool is the package beside this file, tools/spec_lock_diff/, which is also
what `pip install spec-lock-diff` installs. This file exists so that the
spelling every document uses keeps working, and so a copied tools/ folder needs
no install: it puts its own directory first on the path and hands over.
"""

import pathlib
import sys


def run() -> int:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from spec_lock_diff.cli import main

    return main()


if __name__ == "__main__":
    sys.exit(run())
