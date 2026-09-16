#!/usr/bin/env bash
# test && commit || revert, for this repository: the suite under coverage, then
# tools/tests/crap.py. Green commits the working tree; red puts it back.
#
#   tools/tests/tcr.sh "type(scope): what changed"
#
# It needs pytest and coverage (pip install -e ".[dev]"). A revert discards every
# change since the last commit, new files included: that is the point, so keep
# the step small. Files git ignores are left alone.
set -u
message=${1:?usage: tools/tests/tcr.sh "commit message"}
cd "$(git rev-parse --show-toplevel)" || exit 2
export COVERAGE_FILE="${TMPDIR:-/tmp}/slp-tcr.coverage"
if coverage run --branch --include='tools/slp.py' -m pytest tools/tests -q -p no:cacheprovider \
    && python tools/tests/crap.py; then
  git add -A && git commit -q -m "$message" && echo "tcr: committed $(git rev-parse --short HEAD)"
else
  git checkout -q -- . && git clean -qfd
  echo "tcr: red, reverted to $(git rev-parse --short HEAD)" >&2
  exit 1
fi
