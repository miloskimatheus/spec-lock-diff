"""`python -m spec_lock_diff`, and the file the CI templates point at when the tool is installed."""

import sys

from spec_lock_diff.cli import main

if __name__ == "__main__":
    sys.exit(main())
