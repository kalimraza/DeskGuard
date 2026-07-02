#!/usr/bin/env python3
# agent/viewer.py — DeskGuard Local DB Viewer
#
# python viewer.py                              <- today's summary
# python viewer.py dates                        <- list all dates with data
# python viewer.py summary  --date 2026-07-01
# python viewer.py activity --date 2026-07-01 [--limit 100]
# python viewer.py urls     --date 2026-07-01 [--limit 200]
# python viewer.py apps     --date 2026-07-01
# python viewer.py usb
# python viewer.py alerts   [--all]
# python viewer.py ack      --id 5
# python viewer.py keylog   --date 2026-07-01 [--decrypt]
# python viewer.py screens  --date 2026-07-01 --out-dir C:\IT\shots
# python viewer.py export   --date 2026-07-01 --out report.txt
# python viewer.py dbinfo

import argparse, base64, os, sqlite3, sys
from datetime import datetime, date, timezone

try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

RED="\033[91m"; YEL="\033[93m"; GRN="\033[92m"
CYN="\033[96m"; BOLD="\033[1m"; DIM="\033[2m"; RST="\033[0m"
SEV={"critical":RED,"high":YEL,"medium":CYN,"low":GRN}

DEFAULT_DB = os.path.join(
    os.environ.get("PROGRAMDATA","C:\\ProgramData"),
    "WinTelemetryHost","sys_perf.db"
)


def _conn(db_path):
    if not os.path.isfile(db_path):
        print(f"{RED}DB not found: {db_path}{RST}"); sys.exit(1)
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _table(rows, headers, colours=None):
    if not rows: print(f"  {DIM}(no records){RST}"); return
    rows = [list(r) for r in rows]
    w = [max(len(str(r[i])) for r in [headers]+rows) for i in range(len(headers))]
    fmt = "  "+"  ".join(f"{{:<{x}}}" for x in w)
    print(BOLD+fmt.format(*headers)+RST)
    print("  "+"  ".join("─"*x for x in w))
    for i, row in enumerate(rows):
        line = fmt.format(*[str(c) for c in row])
        col  = colours[i] if colours and i < len(colours) else ""
        print((col+line+RST) if col else line)


def _d(s):     return datetime.strptime(s,"%Y-%m-%d").date() if s else date.today()
def _range(d): return str(d), f"{d}~"
def _dur(s):
    s = int(s or 0)
    if s < 60:   return f"{s}s"
    if s < 3600: return f"{s//60}m {s%60}s"
    return f"{s//3600}h {(s%3600)//60}m"


def cmd_dates(c, args):
    print(f"\n{BOLD}Available Dates in Database{RST}\n")
    tables = [
        ("screenshots",     "captured_utc", "Screenshots"),
        ("activity_events", "start_utc",    "Activity   "),
        ("url_visits",      "visited_utc",  "URLs       "),
        ("app_violations",  "detected_utc", "Violations "),
        ("usb_events",      "detected_utc", "USB Events "),
        ("keylog_sessions", "start_utc",    "Keylog     "),
    ]
    all_dates = {}
    for table, col, label in tables:
        try:
            for row in c.execute(f"""
                SELECT substr({col},1,10) as d, COUNT(*) as n
                FROM {table} WHERE {col} IS NOT NULL GROUP BY d ORDER BY d DESC
            """).fetchall():
                all_dates.setdefault(row[0], {})[label] = row[1]
        except Exception:
            pass

    if not all_dates:
        print(f"  {DIM}No data yet. Wait 5 minutes after install then retry.{RST}\n")
        return

    for d in sorted(all_dates.keys(), reverse=True):
        is_today = (d == date.today().isoformat())
        mark = f"  {GRN}← today{RST}" if is_today else ""
        print(f"  {BOLD}{d}{RST}{mark}")
        for label, n in all_dates[d].items():
            bar = "#" * min(n // 3, 25)
            print(f"      {label}   {n:>5}   {CYN}{bar}{RST}")
        print()

    print(f"  View summary:    python viewer.py summary  --date YYYY-MM-DD")
    print(f"  Get screenshots: python viewer.py screens  --date YYYY-MM-DD --out-dir C:\\IT\\shots")
    print(f"  Full report:     python viewer.py export   --date YYYY-MM-DD --out report.txt\n")


def cmd_dbinfo(c, args):
    print(f"\n{BOLD}Database Info{RST}")
    tables = ["activity_events","url_visits","screenshots","app_violations",
              "usb_events","keylog_sessions","alerts"]
    rows = [[t, f"{c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:,}"] for t in tables]
    size = os.path.getsize(args.db) / (1024*1024)
    print(f"\n  File: {args.db}\n  Size: {size:.2f} MB\n")
    _table(rows, ["Table","Records"])
    first = c.execute("SELECT MIN(start_utc) FROM activity_events").fetchone()[0]
    last  = c.execute("SELECT MAX(start_utc) FROM activity_events").fetchone()[0]
    print(f"\n  Data range: {first or '-'}  →  {last or '-'}\n")


def cmd_summary(c, args):
    d = _d(args.date); s, e = _range(d)
    print(f"\n{BOLD}Daily Summary — {d}{RST}")

    rows = c.execute("SELECT start_utc,end_utc FROM activity_events WHERE start_utc BETWEEN ? AND ? AND idle=0",(s,e)).fetchall()
    total = sum(max((datetime.fromisoformat(r[1])-datetime.fromisoformat(r[0])).total_seconds(),0)
                for r in rows if r[0] and r[1])
    print(f"\n  Active time:    {_dur(total)}")

    apps = c.execute("""SELECT app, SUM(CAST((julianday(end_utc)-julianday(start_utc))*86400 AS INT)) s
        FROM activity_events WHERE start_utc BETWEEN ? AND ? AND idle=0
        GROUP BY app ORDER BY s DESC LIMIT 5""",(s,e)).fetchall()
    print(f"\n  Top apps:")
    for r in apps:
        bar = "█" * min(int((r[1] or 0)/max(total,1)*30),30)
        print(f"    {(r[0] or '?'):<28} {_dur(r[1]):<10} {GRN}{bar}{RST}")

    url_n  = c.execute("SELECT COUNT(*) FROM url_visits     WHERE visited_utc  BETWEEN ? AND ?",(s,e)).fetchone()[0]
    ss_n   = c.execute("SELECT COUNT(*) FROM screenshots    WHERE captured_utc BETWEEN ? AND ?",(s,e)).fetchone()[0]
    viol_n = c.execute("SELECT COUNT(*) FROM app_violations WHERE detected_utc BETWEEN ? AND ?",(s,e)).fetchone()[0]
    usb_n  = c.execute("SELECT COUNT(*) FROM usb_events     WHERE detected_utc BETWEEN ? AND ? AND whitelisted=0",(s,e)).fetchone()[0]
    alrt_n = c.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged=0").fetchone()[0]

    print(f"\n  URLs visited:   {url_n}")
    print(f"  Screenshots:    {ss_n}  (python viewer.py screens --date {d} --out-dir C:\\IT\\shots)")
    print(f"  App violations: {(RED if viol_n else GRN)+str(viol_n)+RST}")
    print(f"  USB intrusions: {(RED if usb_n  else GRN)+str(usb_n)+RST}")
    print(f"\n  {BOLD}Unacked alerts: {(RED if alrt_n else GRN)+str(alrt_n)+RST}\n")


def cmd_activity(c, args):
    d = _d(args.date); s, e = _range(d)
    rows = c.execute("SELECT start_utc,end_utc,app,window_title,idle FROM activity_events WHERE start_utc BETWEEN ? AND ? ORDER BY start_utc DESC LIMIT ?",(s,e,args.limit)).fetchall()
    data, cols = [], []
    for r in reversed(rows):
        try: secs=int((datetime.fromisoformat(r[1])-datetime.fromisoformat(r[0])).total_seconds())
        except: secs=0
        data.append([(r[0] or"-")[11:19], _dur(secs), r[2] or"-", (r[3] or"-")[:60], "IDLE"if r[4] else"active"])
        cols.append(DIM if r[4] else "")
    print(f"\n{BOLD}Activity — {d}{RST}")
    _table(data, ["Time(UTC)","Duration","App","Window Title","Status"], cols)


def cmd_urls(c, args):
    d = _d(args.date); s, e = _range(d)
    rows = c.execute("SELECT visited_utc,browser,url,title FROM url_visits WHERE visited_utc BETWEEN ? AND ? ORDER BY visited_utc DESC LIMIT ?",(s,e,args.limit)).fetchall()
    data = [[(r[0] or"-")[11:19], r[1] or"-", (r[2] or"-")[:80], (r[3] or"-")[:40]] for r in reversed(rows)]
    print(f"\n{BOLD}URLs — {d}{RST}")
    _table(data, ["Time(UTC)","Browser","URL","Title"])


def cmd_apps(c, args):
    d = _d(args.date); s, e = _range(d)
    rows = c.execute("""SELECT app, SUM(CAST((julianday(end_utc)-julianday(start_utc))*86400 AS INT)) s,
        COUNT(*) n FROM activity_events WHERE start_utc BETWEEN ? AND ? AND idle=0 AND app IS NOT NULL
        GROUP BY app ORDER BY s DESC LIMIT 30""",(s,e)).fetchall()
    print(f"\n{BOLD}App Usage — {d}{RST}")
    _table([[r[0],_dur(r[1]),r[2]] for r in rows], ["Application","Active Time","Sessions"])


def cmd_usb(c, args):
    rows = c.execute("SELECT detected_utc,drive_letter,device_serial,volume_serial,whitelisted,action,severity FROM usb_events ORDER BY detected_utc DESC LIMIT 100").fetchall()
    data, cols = [], []
    for r in rows:
        data.append([(r[0] or"-")[:16], r[1] or"-", r[2] or r[3] or"-",
                     "YES"if r[4] else"NO", r[5] or"none", r[6] or"-"])
        cols.append("" if r[4] else RED)
    print(f"\n{BOLD}USB Events{RST}")
    _table(data, ["Detected(UTC)","Drive","Serial","Whitelisted","Action","Severity"], cols)


def cmd_alerts(c, args):
    where = "" if args.all else "WHERE acknowledged=0"
    rows  = c.execute(f"SELECT id,severity,category,message,created_at,acknowledged FROM alerts {where} ORDER BY created_at DESC LIMIT 100").fetchall()
    print(f"\n{BOLD}{'All' if args.all else 'Unacknowledged'} Alerts{RST}")
    if not rows: print(f"  {GRN}No alerts.{RST}"); return
    for r in rows:
        col = SEV.get(r[1],""); ack = f" {DIM}[acked]{RST}" if r[5] else ""
        print(f"  [{BOLD}{r[0]}{RST}] {col}{(r[1] or'').upper():<8}{RST} {(r[2] or''):<16} {(r[4] or'')[:16]}{ack}")
        print(f"       {r[3]}")
    print(f"\n  Acknowledge: python viewer.py ack --id <ID>")


def cmd_ack(c_ro, args):
    db = c_ro.execute("PRAGMA database_list").fetchone()[2]
    c_ro.close()
    c = sqlite3.connect(db)
    c.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (args.id,))
    c.commit(); c.close()
    print(f"{GRN}Alert {args.id} acknowledged.{RST}")


def cmd_keylog(c, args):
    d = _d(args.date); s, e = _range(d)
    rows = c.execute("SELECT app,text_enc,start_utc,end_utc FROM keylog_sessions WHERE start_utc BETWEEN ? AND ? ORDER BY start_utc",(s,e)).fetchall()
    print(f"\n{BOLD}Keylog — {d}{RST}")
    if not rows: print(f"  {DIM}No sessions.{RST}"); return
    fernet = None
    if args.decrypt:
        key = os.environ.get("MONITOR_FERNET_KEY","").strip()
        if not key: print(f"{YEL}Set MONITOR_FERNET_KEY env var to decrypt.{RST}")
        else:
            try:
                from cryptography.fernet import Fernet
                fernet = Fernet(key.encode())
            except Exception as ex: print(f"{RED}Invalid key: {ex}{RST}")
    for r in rows:
        t = (r[2] or"-")[11:19]
        print(f"\n  [{t}] App: {BOLD}{r[0] or'?'}{RST}")
        enc = r[1] or ""
        if fernet and enc:
            try: print(f"  {CYN}{fernet.decrypt(base64.b64decode(enc)).decode(errors='replace')}{RST}")
            except: print(f"  {DIM}[decryption failed]{RST}")
        else: print(f"  {DIM}[encrypted — pass --decrypt to view]{RST}")


def cmd_screens(c, args):
    d = _d(args.date); s, e = _range(d)
    out_dir = args.out_dir or f"screenshots_{d}"
    os.makedirs(out_dir, exist_ok=True)
    rows = c.execute("SELECT filename,captured_utc,reason,image_data FROM screenshots WHERE captured_utc BETWEEN ? AND ? ORDER BY captured_utc",(s,e)).fetchall()
    if not rows: print(f"  {DIM}No screenshots for {d}.{RST}"); return
    saved = 0
    for r in rows:
        if not r[3]: continue
        fname = r[0] or f"ss_{r[1]}.jpg"
        out_path = os.path.join(out_dir, os.path.basename(fname))
        if os.path.exists(out_path):
            base, ext = os.path.splitext(out_path)
            out_path = f"{base}_{saved}{ext}"
        try:
            with open(out_path,"wb") as f: f.write(r[3])
            saved += 1
        except Exception as ex: print(f"  Error: {ex}")
    print(f"{GRN}Exported {saved} screenshots to: {out_dir}{RST}")


def cmd_export(c, args):
    d = _d(args.date); s, e = _range(d)
    out = args.out or f"report_{d}.txt"
    lines = [f"DeskGuard — Report — {d}", "="*60]
    rows = c.execute("SELECT start_utc,end_utc FROM activity_events WHERE start_utc BETWEEN ? AND ? AND idle=0",(s,e)).fetchall()
    total = sum(max((datetime.fromisoformat(r[1])-datetime.fromisoformat(r[0])).total_seconds(),0) for r in rows if r[0] and r[1])
    lines.append(f"\nActive Time: {_dur(total)}")
    urls = c.execute("SELECT visited_utc,browser,url FROM url_visits WHERE visited_utc BETWEEN ? AND ? ORDER BY visited_utc",(s,e)).fetchall()
    lines.append(f"\n\n--- URLs ({len(urls)}) ---")
    for r in urls: lines.append(f"  {(r[0] or'')[11:19]}  [{r[1]}]  {r[2]}")
    viols = c.execute("SELECT detected_utc,app_name,killed FROM app_violations WHERE detected_utc BETWEEN ? AND ?",(s,e)).fetchall()
    lines.append(f"\n\n--- App Violations ({len(viols)}) ---")
    for r in viols: lines.append(f"  {(r[0] or'')[11:19]}  {r[1]}  [{'KILLED'if r[2] else'DETECTED'}]")
    usbs = c.execute("SELECT detected_utc,drive_letter,device_serial,whitelisted,action FROM usb_events WHERE detected_utc BETWEEN ? AND ?",(s,e)).fetchall()
    lines.append(f"\n\n--- USB Events ({len(usbs)}) ---")
    for r in usbs: lines.append(f"  {(r[0] or'')[11:19]}  {r[1]}  {r[2] or'-'}  [{'OK'if r[3] else'UNAUTHORIZED'}]  {r[4]}")
    with open(out,"w",encoding="utf-8") as f: f.write("\n".join(lines))
    print(f"{GRN}Report saved: {out}{RST}")


def main():
    p = argparse.ArgumentParser(prog="viewer.py", description="DeskGuard — Local DB Viewer")
    p.add_argument("--db", default=DEFAULT_DB)
    sub = p.add_subparsers(dest="command")

    sub.add_parser("dates");  sub.add_parser("dbinfo")
    s=sub.add_parser("summary");  s.add_argument("--date")
    s=sub.add_parser("activity"); s.add_argument("--date"); s.add_argument("--limit",type=int,default=100)
    s=sub.add_parser("urls");     s.add_argument("--date"); s.add_argument("--limit",type=int,default=200)
    s=sub.add_parser("apps");     s.add_argument("--date")
    sub.add_parser("usb")
    s=sub.add_parser("alerts");   s.add_argument("--all",action="store_true")
    s=sub.add_parser("ack");      s.add_argument("--id",type=int,required=True)
    s=sub.add_parser("keylog");   s.add_argument("--date"); s.add_argument("--decrypt",action="store_true")
    s=sub.add_parser("screens");  s.add_argument("--date"); s.add_argument("--out-dir",dest="out_dir")
    s=sub.add_parser("export");   s.add_argument("--date"); s.add_argument("--out")

    args = p.parse_args()
    if not args.command:
        args.command = "summary"; args.date = None

    c = _conn(args.db)
    {"dates":cmd_dates,"dbinfo":cmd_dbinfo,"summary":cmd_summary,"activity":cmd_activity,
     "urls":cmd_urls,"apps":cmd_apps,"usb":cmd_usb,"alerts":cmd_alerts,"ack":cmd_ack,
     "keylog":cmd_keylog,"screens":cmd_screens,"export":cmd_export}[args.command](c, args)


if __name__ == "__main__":
    main()
