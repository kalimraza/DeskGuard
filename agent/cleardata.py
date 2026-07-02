# agent/cleardata.py — wipe all data from local DB
import sqlite3, os, sys

db = os.path.join(os.environ.get("PROGRAMDATA","C:\\ProgramData"),
                  "WinTelemetryHost", "sys_perf.db")

if not os.path.isfile(db):
    print(f"DB not found: {db}")
    input("Press Enter to exit..."); sys.exit(1)

print(f"\nDatabase: {db}")
print(f"Size before: {os.path.getsize(db)/1024/1024:.2f} MB\n")

confirm = input("Delete ALL recorded data permanently? Type YES to confirm: ")
if confirm.strip().upper() != "YES":
    print("Cancelled."); input("Press Enter..."); sys.exit(0)

tables = ["activity_events","url_visits","screenshots","app_violations",
          "usb_events","keylog_sessions","alerts","meta"]

c = sqlite3.connect(db)
for table in tables:
    try:
        count = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        c.execute(f"DELETE FROM {table}")
        print(f"  Cleared {count:>6} rows from {table}")
    except Exception:
        pass

c.commit(); c.close()

# VACUUM outside transaction
c = sqlite3.connect(db, isolation_level=None)
c.execute("VACUUM")
c.close()

print(f"\nSize after: {os.path.getsize(db)/1024/1024:.2f} MB")
print("Done.")
input("Press Enter to exit...")
