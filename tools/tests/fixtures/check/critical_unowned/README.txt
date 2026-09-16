A critical model under models/marts/finance/, and CODEOWNERS owns only
models/marts/sales/. Its sql and its yml would merge on the Author's approval
alone; the Partner the framework asks for is nobody.
expect rules S5
expect count 2
expect line BLOCK\tmodels/marts/finance/fct_invoices.sql\tfct_invoices\tcritical model, and no line of CODEOWNERS owns models/marts/finance/fct_invoices.sql; a Partner approves a critical model, and CODEOWNERS is what enforces it (README §3 Stage E)\t[S5]
