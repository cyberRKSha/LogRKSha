# fix_dump.py
import re

print("Starting conversion from SQLite to PostgreSQL dialect...")

# Read the original SQLite dump
with open('dump.sql', 'r') as f:
    dump_content = f.read()

# Perform a series of replacements to fix incompatibilities
# 1. Replace SQLite's AUTOINCREMENT with PostgreSQL's SERIAL
dump_content = re.sub(r'INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY', dump_content)
# 2. Replace SQLite's BLOB with PostgreSQL's BYTEA for binary data
dump_content = re.sub(r'BLOB', 'BYTEA', dump_content)
# 3. Remove all lines related to the SQLite-only "sqlite_sequence" table
dump_content = re.sub(r'(?m)^.*sqlite_sequence.*;?$', '', dump_content)
# 4. Remove SQLite's PRAGMA statements and transaction commands
dump_content = re.sub(r'(?m)^PRAGMA.*', '', dump_content)
dump_content = re.sub(r'BEGIN TRANSACTION;', '', dump_content)
dump_content = re.sub(r'COMMIT;', '', dump_content)
# 5. Remove any leftover empty lines
dump_content = re.sub(r'(?m)^\s*\n', '', dump_content)

# Write the corrected content to a new file
with open('dump_postgres.sql', 'w') as f:
    f.write(dump_content)

print("✅ Conversion complete. New file created: dump_postgres.sql")
