# The import workers should follow the following pattern:
1. Use copy from input stream into staging table.
2. Use SQL only where possible to reimport the row into the final table in one step. Do not loop through the import rows in Python.
3. Prefer removing the rows for the recalculated period from the table being imported, and importing them again, rather than upserting them. 