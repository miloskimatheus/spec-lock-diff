A macro added under macros/, carrying a config() of its own. G9 blocks the
protected path; G10 reads singular tests under tests/ and nothing else, so a
config in a macro is not a test born muted.
expect rules G9
expect absent G10
