fct_a's unit test now expects the cancelled row it was written to exclude, and
fct_b holds a unit test of the same name. The inventory keyed unit tests by
name alone, so whichever file sorted later overwrote the other and the change
vanished: gate said "OK (no changes)".
expect count 1
