#!/usr/bin/env bash
# Spec-Lock-Diff, Rule 5: one step at a time. Copy to the root of your dbt
# project and commit only through it:
#
#   tcr.sh "what this step changed"
#
# It runs check, gate and the unit tests, in that order. All green: the working
# tree is committed with your message. Anything red: the working tree goes back
# to the last commit and a strike is counted. A green step resets the count;
# the fifth strike in a row stops with exit 3 and a sentence that says to ask a
# human. `dbt build` is not here on purpose: a build scans the sample window,
# and this loop runs many times. It runs once, in CI, at Stage D.
#
# The unit tests read no table - check rule T3 refuses one that leaves an input
# unmocked - so the loop costs nothing in the warehouse however often it runs.
set -u
message=${1:?usage: tcr.sh "commit message"}
# YOU: the branch this pull request targets, if it is not main.
base=${SLP_BASE:-main}
# YOU: add --marts-path <dir> to both slp commands below if your marts are not
# in models/marts/, with the same values the CI workflow uses.
strikes="$(git rev-parse --git-dir)/slp-tcr-strikes"
if python tools/slp.py check \
    && python tools/slp.py gate --base "$base" \
    && dbt test --select test_type:unit; then
  git add -A && git commit -q -m "$message" && rm -f "$strikes"
  echo "tcr: green, committed $(git rev-parse --short HEAD)"
else
  git checkout -q -- . && git clean -qfd
  count=$(( $(cat "$strikes" 2>/dev/null || echo 0) + 1 ))
  echo "$count" > "$strikes"
  echo "tcr: red, reverted to $(git rev-parse --short HEAD) (strike $count of 5)" >&2
  if [ "$count" -ge 5 ]; then
    echo "tcr: five reverts in a row; stop and ask a human (Rule 5)" >&2
    exit 3
  fi
  exit 1
fi
