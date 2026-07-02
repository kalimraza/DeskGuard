#!/usr/bin/env python3
# server/cli.py — DeskGuard Server CLI
#
# MACHINES:
#   python cli.py machines
#   python cli.py addmachine --name DESKTOP-ABC --notes "John Smith"
#
# CONFIG (remote control):
#   python cli.py config show                           # default config
#   python cli.py config show --machine DESKTOP-ABC    # machine config
#   python cli.py config set  --machine DESKTOP-ABC --key SCREENSHOT_INTERVAL --value 60
#   python cli.py config set  --machine __default__  --key USB_BLOCK_MODE --value block
#   python cli.py config set  --machine DESKTOP-ABC --key KEYLOG_ENABLED --value false
#   python cli.py config set  --machine DESKTOP-ABC --key UPLOAD_EVERY --value 1800
#   python cli.py config reset --machine DESKTOP-ABC   # back to default
#   python cli.py blocklist add    facebook.com         # add to default blocklist
#   python cli.py blocklist remove facebook.com
#   python cli.py blocklist add    --machine DESKTOP-ABC gambling.com
#   python cli.py blacklist add    whatsapp.exe
#   python cli.py blacklist remove whatsapp.exe
#   python cli.py blacklist add    --machine DESKTOP-ABC spotify.exe
#
# DATA:
#   python cli.py summary   --machine DESKTOP-ABC [--date 2026-07-01]
#   python cli.py activity  --machine DESKTOP-ABC [--date 2026-07-01]
#   python cli.py urls      --machine DESKTOP-ABC [--date 2026-07-01]
#   python cli.py alerts    [--severity critical]
#   python cli.py ack       --alert-id 5
#   python cli.py violations [--machine DESKTOP-ABC]
#   python cli.py usb        [--machine DESKTOP-ABC]
#   python cli.py screens   --machine DESKTOP-ABC --date 2026-07-01 --out-dir ./shots

import argparse, os, sys, json, secrets
from datetime import datetime, date

from sqlalchemy import func
from sqlalchemy.orm import Session

import config, database
from database import (Machine, MachineConfig, ActivityEvent, UrlVisit, Screenshot,
                      AppViolation, UsbEvent, KeylogSession, Alert, SessionLocal, init_db)

RED="\033[91m"; YEL="\033[93m"; GRN="\033[92m"; CYN="\033[96m"
BOLD="\033[1m"; DIM="\033[2m"; RST="\033[0m"
SEV={" critical":RED,"high":YEL,"medium":CYN,"low":GRN}

def _table(rows, headers, colours=None):
    if not rows: print(f"  {DIM}(no records){RST}"); return
    rows=[list(r) for r in rows]
    w=[max(len(str(r[i])) for r in [headers]+rows) for i in range(len(headers))]
    fmt="  "+"  ".join(f"{{:<{x}}}" for x in w)
    print(BOLD+fmt.format(*headers)+RST)
    print("  "+"  ".join("─"*x for x in w))
    for i,row in enumerate(rows):
        line=fmt.format(*[str(c) for c in row])
        col=colours[i] if colours and i<len(colours) else ""
        print((col+line+RST) if col else line)

def _d(s): return datetime.strptime(s,"%Y-%m-%d").date() if s else date.today()
def _range(d): return f"{d}",f"{d}~"
def _dur(s):
    s=int(s or 0)
    if s<60: return f"{s}s"
    if s<3600: return f"{s//60}m {s%60}s"
    return f"{s//3600}h {(s%3600)//60}m"


# ── Machine commands ──────────────────────────────────────────────────────────

def cmd_machines(db, args):
    ms=db.query(Machine).order_by(Machine.last_seen.desc()).all()
    _table([[m.name,"✓"if m.active else"✗",
             m.last_seen.strftime("%Y-%m-%d %H:%M")if m.last_seen else"-",
             m.notes[:40]] for m in ms],
           ["Name","Active","Last Seen (UTC)","Notes"])


def cmd_addmachine(db, args):
    name=args.name.strip()
    if db.query(Machine).filter_by(name=name).first():
        print(f"ERROR: Machine '{name}' already exists."); return
    api_key=secrets.token_urlsafe(32)
    db.add(Machine(name=name,api_key=api_key,notes=args.notes or ""))
    db.commit()
    print(f"\n{GRN}Machine '{name}' created.{RST}")
    print(f"API Key: {BOLD}{api_key}{RST}")
    print(f"\nSet this in agent/config.py → API_KEY before deploying.\n")


# ── Config commands ───────────────────────────────────────────────────────────

def _get_row(db, machine):
    return db.query(MachineConfig).filter_by(machine=machine).first()

def _bump_version(db, machine):
    row=_get_row(db,machine)
    if row: row.version+=1; row.updated_at=datetime.utcnow()

def _effective(db, machine):
    default=_get_row(db,"__default__")
    mrow=_get_row(db,machine)
    merged=json.loads(default.config_json) if default else {}
    version=default.version if default else 1
    if mrow:
        merged.update(json.loads(mrow.config_json))
        version=max(version,mrow.version)
    merged["version"]=version
    return merged


def cmd_config_show(db, args):
    machine = args.machine or "__default__"
    cfg = _effective(db, machine)
    print(f"\n{BOLD}Config — {machine} (version {cfg.get('version',1)}){RST}\n")
    for k, v in cfg.items():
        if k == "version": continue
        if isinstance(v, list):
            print(f"  {BOLD}{k}{RST}  ({len(v)} entries)")
            for item in v:
                print(f"      {item}")
        else:
            print(f"  {BOLD}{k}{RST}  =  {v}")
    print()


def cmd_config_set(db, args):
    machine = args.machine or "__default__"
    key     = args.key.upper()
    raw     = args.value

    # Parse value type
    if raw.lower() == "true":     val = True
    elif raw.lower() == "false":  val = False
    elif raw.startswith("["):
        try: val = json.loads(raw)
        except: print(f"Invalid JSON list: {raw}"); return
    else:
        try: val = int(raw)
        except ValueError:
            try: val = float(raw)
            except ValueError: val = raw

    row = _get_row(db, machine)
    if row:
        cfg = json.loads(row.config_json)
        cfg[key] = val
        row.config_json = json.dumps(cfg)
        row.version += 1
        row.updated_at = datetime.utcnow()
    else:
        db.add(MachineConfig(machine=machine,
                             config_json=json.dumps({key: val}), version=1))
    db.commit()
    print(f"{GRN}Set {key} = {val} on '{machine}'. Agents will pick up within 15 min.{RST}")


def cmd_config_reset(db, args):
    machine = args.machine
    row = _get_row(db, machine)
    if row: db.delete(row); db.commit()
    print(f"{GRN}Config for '{machine}' reset to default.{RST}")


def _list_op(db, machine, list_key, item, action):
    """Add or remove an item from a list config key."""
    row = _get_row(db, machine)
    if row:
        cfg = json.loads(row.config_json)
    else:
        # Start from effective config
        cfg = _effective(db, machine)

    lst = cfg.get(list_key, [])
    item_lower = item.lower()

    if action == "add":
        if item_lower not in [x.lower() for x in lst]:
            lst.append(item)
            print(f"{GRN}Added '{item}' to {list_key} on '{machine}'.{RST}")
        else:
            print(f"'{item}' already in {list_key}.")
    else:  # remove
        before = len(lst)
        lst = [x for x in lst if x.lower() != item_lower]
        if len(lst) < before:
            print(f"{GRN}Removed '{item}' from {list_key} on '{machine}'.{RST}")
        else:
            print(f"'{item}' not found in {list_key}.")

    cfg[list_key] = lst
    if row:
        row.config_json = json.dumps(cfg)
        row.version += 1
        row.updated_at = datetime.utcnow()
    else:
        db.add(MachineConfig(machine=machine, config_json=json.dumps(cfg), version=1))
    db.commit()
    print(f"  Agents will pick up change within 15 min.")


def cmd_blocklist(db, args):
    machine = args.machine or "__default__"
    if args.bl_action == "show":
        cfg = _effective(db, machine)
        lst = cfg.get("WEBSITE_BLOCKLIST", [])
        print(f"\n{BOLD}Website Blocklist — {machine} ({len(lst)} domains){RST}\n")
        for d in sorted(lst): print(f"  {d}")
    else:
        _list_op(db, machine, "WEBSITE_BLOCKLIST", args.domain, args.bl_action)


def cmd_blacklist(db, args):
    machine = args.machine or "__default__"
    if args.bl_action == "show":
        cfg = _effective(db, machine)
        lst = cfg.get("APP_BLACKLIST", [])
        print(f"\n{BOLD}App Blacklist — {machine} ({len(lst)} apps){RST}\n")
        for a in sorted(lst): print(f"  {a}")
    else:
        _list_op(db, machine, "APP_BLACKLIST", args.app, args.bl_action)


# ── Data commands ─────────────────────────────────────────────────────────────

def cmd_summary(db, args):
    d=_d(args.date); s,e=_range(d); m=args.machine
    print(f"\n{BOLD}Summary — {m} — {d}{RST}")
    rows=db.execute(f"SELECT start_utc,end_utc FROM activity_events WHERE machine='{m}' AND start_utc BETWEEN '{s}' AND '{e}' AND idle=0").fetchall()
    total=sum(max((datetime.fromisoformat(r[1])-datetime.fromisoformat(r[0])).total_seconds(),0) for r in rows if r[0] and r[1])
    print(f"\n  Active time:    {_dur(total)}")
    url_n=db.query(func.count(UrlVisit.id)).filter(UrlVisit.machine==m,UrlVisit.visited_utc.between(s,e)).scalar()
    ss_n =db.query(func.count(Screenshot.id)).filter(Screenshot.machine==m,Screenshot.captured_utc.between(s,e)).scalar()
    vn   =db.query(func.count(AppViolation.id)).filter(AppViolation.machine==m,AppViolation.detected_utc.between(s,e)).scalar()
    un   =db.query(func.count(UsbEvent.id)).filter(UsbEvent.machine==m,UsbEvent.detected_utc.between(s,e),UsbEvent.whitelisted==False).scalar()
    print(f"  URLs:           {url_n}")
    print(f"  Screenshots:    {ss_n}")
    print(f"  App violations: {(RED if vn else GRN)+str(vn)+RST}")
    print(f"  USB intrusions: {(RED if un else GRN)+str(un)+RST}\n")


def cmd_activity(db, args):
    d=_d(args.date); s,e=_range(d); m=args.machine
    rows=db.query(ActivityEvent).filter(ActivityEvent.machine==m,ActivityEvent.start_utc.between(s,e)).order_by(ActivityEvent.start_utc.desc()).limit(args.limit).all()
    data=[]
    for r in reversed(rows):
        try: secs=int((r.end_utc-r.start_utc).total_seconds())
        except: secs=0
        data.append([str(r.start_utc)[11:19],_dur(secs),r.app or"-",(r.window_title or"-")[:55],"IDLE"if r.idle else"active"])
    print(f"\n{BOLD}Activity — {m} — {d}{RST}")
    _table(data,["Time(UTC)","Duration","App","Window Title","Status"])


def cmd_urls(db, args):
    d=_d(args.date); s,e=_range(d); m=args.machine
    rows=db.query(UrlVisit).filter(UrlVisit.machine==m,UrlVisit.visited_utc.between(s,e)).order_by(UrlVisit.visited_utc.desc()).limit(args.limit).all()
    data=[[str(r.visited_utc)[11:19],r.browser or"-",(r.url or"-")[:80],(r.title or"-")[:35]] for r in reversed(rows)]
    print(f"\n{BOLD}URLs — {m} — {d}{RST}")
    _table(data,["Time(UTC)","Browser","URL","Title"])


def cmd_alerts(db, args):
    q=db.query(Alert).filter_by(acknowledged=False)
    if args.severity: q=q.filter_by(severity=args.severity)
    rows=q.order_by(Alert.created_at.desc()).limit(100).all()
    print(f"\n{BOLD}Unacknowledged Alerts{RST}")
    if not rows: print(f"  {GRN}No alerts.{RST}"); return
    for a in rows:
        col=SEV.get(a.severity,"")
        print(f"  [{BOLD}{a.id}{RST}] {col}{(a.severity or'').upper():<8}{RST} {a.machine:<20} {str(a.created_at)[:16]}")
        print(f"       {a.message}")


def cmd_ack(db, args):
    a=db.query(Alert).get(args.alert_id)
    if not a: print("Alert not found."); return
    a.acknowledged=True; db.commit()
    print(f"{GRN}Alert {args.alert_id} acknowledged.{RST}")


def cmd_violations(db, args):
    q=db.query(AppViolation)
    if args.machine: q=q.filter_by(machine=args.machine)
    rows=q.order_by(AppViolation.detected_utc.desc()).limit(100).all()
    _table([[r.machine,r.app_name or"-",r.username or"-","YES"if r.killed else"NO",
             str(r.detected_utc)[:16],r.severity] for r in rows],
           ["Machine","App","User","Killed","Detected","Severity"])


def cmd_usb(db, args):
    q=db.query(UsbEvent)
    if args.machine: q=q.filter_by(machine=args.machine)
    rows=q.order_by(UsbEvent.detected_utc.desc()).limit(100).all()
    _table([[r.machine,r.drive_letter or"-",r.device_serial or"-",
             "YES"if r.whitelisted else f"{RED}NO{RST}",r.action or"-",str(r.detected_utc)[:16]] for r in rows],
           ["Machine","Drive","Serial","Whitelisted","Action","Detected"])


def cmd_screens(db, args):
    d=_d(args.date); s,e=_range(d); m=args.machine
    out_dir=args.out_dir or f"screenshots_{m}_{d}"
    os.makedirs(out_dir,exist_ok=True)
    rows=db.query(Screenshot).filter(Screenshot.machine==m,Screenshot.captured_utc.between(s,e)).order_by(Screenshot.captured_utc).all()
    if not rows: print(f"  {DIM}No screenshots.{RST}"); return
    saved=0
    for r in rows:
        if config.SCREENSHOT_STORAGE=="disk":
            print(f"  File: {r.filename}")
        elif r.image_data:
            fname=r.filename or f"ss_{r.captured_utc}.jpg"
            out_path=os.path.join(out_dir,os.path.basename(fname))
            if os.path.exists(out_path):
                base,ext=os.path.splitext(out_path); out_path=f"{base}_{saved}{ext}"
            with open(out_path,"wb") as f: f.write(r.image_data)
            saved+=1
    if config.SCREENSHOT_STORAGE!="disk":
        print(f"{GRN}Exported {saved} screenshots to: {out_dir}{RST}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    init_db()
    db=SessionLocal()
    p=argparse.ArgumentParser(prog="cli.py")
    sub=p.add_subparsers(dest="command")

    sub.add_parser("machines")
    s=sub.add_parser("addmachine"); s.add_argument("--name",required=True); s.add_argument("--notes",default="")

    # Config
    cs=sub.add_parser("config"); css=cs.add_subparsers(dest="config_cmd")
    s=css.add_parser("show");  s.add_argument("--machine",default="__default__")
    s=css.add_parser("set");   s.add_argument("--machine",default="__default__"); s.add_argument("--key",required=True); s.add_argument("--value",required=True)
    s=css.add_parser("reset"); s.add_argument("--machine",required=True)

    # Blocklist
    bl=sub.add_parser("blocklist"); bl.add_argument("bl_action",choices=["add","remove","show"]); bl.add_argument("domain",nargs="?"); bl.add_argument("--machine")
    # Blacklist
    bk=sub.add_parser("blacklist"); bk.add_argument("bl_action",choices=["add","remove","show"]); bk.add_argument("app",nargs="?"); bk.add_argument("--machine")

    # Data
    s=sub.add_parser("summary");    s.add_argument("--machine",required=True); s.add_argument("--date")
    s=sub.add_parser("activity");   s.add_argument("--machine",required=True); s.add_argument("--date"); s.add_argument("--limit",type=int,default=100)
    s=sub.add_parser("urls");       s.add_argument("--machine",required=True); s.add_argument("--date"); s.add_argument("--limit",type=int,default=200)
    s=sub.add_parser("alerts");     s.add_argument("--severity")
    s=sub.add_parser("ack");        s.add_argument("--alert-id",type=int,dest="alert_id",required=True)
    s=sub.add_parser("violations"); s.add_argument("--machine")
    s=sub.add_parser("usb");        s.add_argument("--machine")
    s=sub.add_parser("screens");    s.add_argument("--machine",required=True); s.add_argument("--date"); s.add_argument("--out-dir",dest="out_dir")

    args=p.parse_args()
    if not args.command: p.print_help(); return

    if args.command=="config":
        {"show":cmd_config_show,"set":cmd_config_set,"reset":cmd_config_reset}[args.config_cmd](db,args)
    else:
        {"machines":cmd_machines,"addmachine":cmd_addmachine,
         "blocklist":cmd_blocklist,"blacklist":cmd_blacklist,
         "summary":cmd_summary,"activity":cmd_activity,"urls":cmd_urls,
         "alerts":cmd_alerts,"ack":cmd_ack,"violations":cmd_violations,
         "usb":cmd_usb,"screens":cmd_screens}[args.command](db,args)
    db.close()

if __name__=="__main__": main()
