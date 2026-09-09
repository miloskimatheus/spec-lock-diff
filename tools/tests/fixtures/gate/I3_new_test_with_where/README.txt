A test the branch adds with a where. Nothing was weakened - it has no earlier
self - and it still asserts nothing about the rows it skips, so this is shown
and not blocked.
expect exit 0
expect rules I3
expect count 1
