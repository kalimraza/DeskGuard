# fixdates.py — run once to fix screenshot timestamps in the DB
# Usage: python fixdates.py

import sqlite3, os, re

db = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                  "WinTelemetryHost", "sys_perf.db")

if not os.path.isfile(db):
    print(f"DB not found: {db}")
    input("Press Enter to exit...")
    exit(1)

c = sqlite3.connect(db)

rows = c.execute(
    "SELECT id, captured_utc FROM screenshots WHERE captured_utc NOT LIKE '____-__-__%'"
).fetchall()

print(f"Found {len(rows)} screenshots with bad date format.")

fixed = 0
for row_id, ts in rows:
    # Convert 20260701T180756Z  →  2026-07-01T18:07:56
    m = re.match(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", str(ts or ""))
    if m:
        new_ts = f"{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:{m[6]}"
        c.execute("UPDATE screenshots SET captured_utc=? WHERE id=?", (new_ts, row_id))
        fixed += 1

c.commit()
c.close()
print(f"Fixed {fixed} records. Done.")
input("Press Enter to exit...")
