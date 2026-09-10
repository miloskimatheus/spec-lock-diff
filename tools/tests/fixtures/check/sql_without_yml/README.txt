models/marts/ holds two .sql files and the yml declares only one of them.
The other has no spec, no primary key and no test, and until S4 existed every
rule here passed it in silence.
expect rules S4
expect count 1
