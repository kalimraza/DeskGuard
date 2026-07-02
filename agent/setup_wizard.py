#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# DeskGuard — Setup Wizard
# Run via SETUP.bat (handles admin elevation automatically)
# ─────────────────────────────────────────────────────────────────────────────

import os, sys, subprocess, socket, time, re, ctypes, shutil

# ── Terminal colours ──────────────────────────────────────────────────────────
try:
    ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

R="\033[91m"; Y="\033[93m"; G="\033[92m"; C="\033[96m"
B="\033[94m"; BOLD="\033[1m"; DIM="\033[2m"; RST="\033[0m"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load product identity from config
sys.path.insert(0, SCRIPT_DIR)
try:
    from config import PRODUCT_NAME, PRODUCT_VERSION, VENDOR_NAME
except ImportError:
    PRODUCT_NAME = "DeskGuard"
    PRODUCT_VERSION = "1.0.0"
    VENDOR_NAME = "Your Company" 


def clear():
    os.system("cls")


def header(step: int, total: int, title: str):
    clear()
    print(f"\n{BOLD}{B}{'═'*60}{RST}")
    print(f"  {BOLD}{PRODUCT_NAME} v{PRODUCT_VERSION} — Setup Wizard{RST}")
    print(f"  Step {step} of {total}: {C}{title}{RST}")
    print(f"{BOLD}{B}{'═'*60}{RST}\n")


def ok(msg):    print(f"  {G}✓{RST}  {msg}")
def warn(msg):  print(f"  {Y}⚠{RST}  {msg}")
def err(msg):   print(f"  {R}✗{RST}  {msg}")
def info(msg):  print(f"  {C}→{RST}  {msg}")
def step(msg):  print(f"\n  {BOLD}{msg}{RST}")


def ask(prompt, default="", required=True):
    """Ask user for input with optional default."""
    if default:
        display = f"{prompt} [{DIM}{default}{RST}]: "
    else:
        display = f"{prompt}: "
    while True:
        val = input(f"  {display}").strip()
        if not val and default:
            return default
        if not val and required:
            print(f"  {R}This field is required.{RST}")
            continue
        return val or default


def ask_choice(prompt, choices: list, default=None):
    """Ask user to pick from a numbered list."""
    print(f"\n  {BOLD}{prompt}{RST}")
    for i, c in enumerate(choices, 1):
        marker = f" {G}(default){RST}" if c == default else ""
        print(f"    {BOLD}{i}{RST}. {c}{marker}")
    while True:
        val = input(f"\n  Choose [1-{len(choices)}]: ").strip()
        if not val and default:
            return default
        try:
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"  {R}Please enter a number between 1 and {len(choices)}.{RST}")


def ask_yn(prompt, default="y") -> bool:
    opts = "Y/n" if default == "y" else "y/N"
    val = input(f"  {prompt} [{opts}]: ").strip().lower()
    if not val:
        return default == "y"
    return val.startswith("y")


def run_cmd(cmd: list, capture=True) -> tuple:
    r = subprocess.run(cmd, capture_output=capture, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def is_admin() -> bool:
    try:    return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False


# ── Step 1: Welcome ───────────────────────────────────────────────────────────

def step_welcome():
    header(1, 6, "Welcome")
    print(f"""
  This wizard will install the DeskGuard on this
  machine. It will:

    {G}✓{RST}  Install all required Python packages
    {G}✓{RST}  Configure monitoring settings for this machine
    {G}✓{RST}  Install the monitoring service (runs silently on startup)
    {G}✓{RST}  Set up screenshot capture
    {G}✓{RST}  Apply website and application blocking rules

  {Y}This tool is for use on company-owned devices only.{RST}
  {Y}Employees must have signed the IT Acceptable Use Policy.{RST}
""")

    if not is_admin():
        err("Not running as Administrator. Please restart via SETUP.bat")
        input("\n  Press Enter to exit...")
        sys.exit(1)
    ok("Running as Administrator")

    if not ask_yn("\n  Ready to begin installation?", "y"):
        print("\n  Installation cancelled.\n")
        sys.exit(0)


# ── Step 2: Python & Dependencies ─────────────────────────────────────────────

def step_dependencies():
    header(2, 6, "Installing Dependencies")

    step("Checking Python version...")
    rc, out = run_cmd([sys.executable, "--version"])
    if rc == 0:
        ok(f"Python: {out}")
    else:
        err("Python not found")
        sys.exit(1)

    step("Installing required packages...")
    req_file = os.path.join(SCRIPT_DIR, "requirements.txt")

    packages = [
        ("pywin32",      "Windows service support"),
        ("psutil",       "Process monitoring"),
        ("mss",          "Screen capture"),
        ("Pillow",       "Image processing"),
        ("pynput",       "Keyboard logging"),
        ("WMI",          "USB detection"),
        ("requests",     "Server communication"),
        ("cryptography", "Data encryption"),
    ]

    for pkg, desc in packages:
        print(f"  {DIM}Installing {pkg} ({desc})...{RST}", end="", flush=True)
        rc, out = run_cmd([sys.executable, "-m", "pip", "install", pkg,
                           "--quiet", "--no-warn-script-location"])
        if rc == 0:
            print(f"\r  {G}✓{RST}  {pkg:<16} {DIM}{desc}{RST}          ")
        else:
            print(f"\r  {R}✗{RST}  {pkg} — FAILED")
            warn(f"Error: {out[:100]}")

    # pywin32 post-install
    step("Running pywin32 post-install...")
    try:
        import win32serviceutil
        ok("pywin32 already configured")
    except ImportError:
        scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
        postinstall  = os.path.join(scripts_dir, "pywin32_postinstall.py")
        if os.path.isfile(postinstall):
            run_cmd([sys.executable, postinstall, "-install"])
            ok("pywin32 post-install completed")
        else:
            warn("pywin32 post-install script not found — may need manual fix")


# ── Step 3: Machine Configuration ─────────────────────────────────────────────

def step_configure() -> dict:
    header(3, 6, "Machine Configuration")

    detected_name = socket.gethostname()
    print(f"  Detected machine name: {BOLD}{detected_name}{RST}\n")

    cfg = {}

    # Machine name
    cfg["MACHINE_NAME"] = ask("Machine name (press Enter to use detected)", detected_name)

    # Mode
    print()
    mode = ask_choice(
        "Select monitoring mode:",
        [
            "local  — store data on this machine only (no server needed)",
            "hybrid — store locally AND upload to server every hour",
        ],
        default="local  — store data on this machine only (no server needed)"
    )
    cfg["MODE"] = "local" if mode.startswith("local") else "hybrid"

    # Server settings (only if hybrid)
    if cfg["MODE"] == "hybrid":
        print()
        cfg["SERVER_URL"] = ask("Server URL (e.g. https://monitor.yourdomain.com)")
        cfg["API_KEY"]    = ask("API Key (generated by: python cli.py addmachine)")
    else:
        cfg["SERVER_URL"] = "https://monitor.yourdomain.com"
        cfg["API_KEY"]    = "NOT_USED_IN_LOCAL_MODE"

    # Screenshot interval
    print()
    interval = ask_choice(
        "Screenshot capture interval:",
        ["60 seconds", "120 seconds", "180 seconds (default)", "300 seconds"],
        default="180 seconds (default)"
    )
    cfg["SCREENSHOT_INTERVAL"] = int(interval.split()[0])

    # USB mode
    print()
    usb_mode = ask_choice(
        "USB drive policy:",
        ["alert — log USB connections only (default)", "block — eject unauthorized drives immediately"],
        default="alert — log USB connections only (default)"
    )
    cfg["USB_BLOCK_MODE"] = "alert" if usb_mode.startswith("alert") else "block"

    # Website blocker
    print()
    cfg["WEBSITE_BLOCKER_ENABLED"] = ask_yn(
        "Enable hosts file blocking? (blocks sites via Windows hosts file)", "n"
    )

    # Keylogger
    print()
    cfg["KEYLOG_ENABLED"] = ask_yn("Enable keystroke logging?", "y")

    print(f"\n  {G}Configuration complete.{RST}")
    return cfg


# ── Step 4: Write Config File ─────────────────────────────────────────────────

def step_write_config(cfg: dict):
    header(4, 6, "Writing Configuration")

    config_path = os.path.join(SCRIPT_DIR, "config.py")

    # Read existing config
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace values
    replacements = {
        r'^MODE\s*=\s*.+$':
            f'MODE = "{cfg["MODE"]}"',
        r'^SERVER_URL\s*=\s*.+$':
            f'SERVER_URL = "{cfg["SERVER_URL"]}"',
        r'^API_KEY\s*=\s*.+$':
            f'API_KEY    = "{cfg["API_KEY"]}"',
        r'^MACHINE_NAME\s*=\s*.+$':
            f'MACHINE_NAME = "{cfg["MACHINE_NAME"]}"  # overridden by setup wizard',
        r'^SCREENSHOT_INTERVAL\s*=\s*.+$':
            f'SCREENSHOT_INTERVAL  = {cfg["SCREENSHOT_INTERVAL"]}',
        r'^USB_BLOCK_MODE\s*=\s*.+$':
            f'USB_BLOCK_MODE        = "{cfg["USB_BLOCK_MODE"]}"',
        r'^WEBSITE_BLOCKER_ENABLED\s*=\s*.+$':
            f'WEBSITE_BLOCKER_ENABLED = {cfg["WEBSITE_BLOCKER_ENABLED"]}',
        r'^KEYLOG_ENABLED\s*=\s*.+$':
            f'KEYLOG_ENABLED     = {cfg["KEYLOG_ENABLED"]}',
    }

    for pattern, replacement in replacements.items():
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)

    ok(f"config.py updated")

    # Show summary
    print(f"""
  {BOLD}Configuration Summary:{RST}
    Machine name   : {BOLD}{cfg["MACHINE_NAME"]}{RST}
    Mode           : {BOLD}{cfg["MODE"]}{RST}
    Server URL     : {cfg["SERVER_URL"]}
    Screenshots    : every {cfg["SCREENSHOT_INTERVAL"]} seconds
    USB policy     : {cfg["USB_BLOCK_MODE"]}
    Hosts blocking : {cfg["WEBSITE_BLOCKER_ENABLED"]}
    Keylogger      : {cfg["KEYLOG_ENABLED"]}
""")


# ── Step 5: Install Service ───────────────────────────────────────────────────

def step_install_service():
    header(5, 6, "Installing Windows Service")

    # Check if already installed
    rc, out = run_cmd(["sc", "query", "WinTelemetryHost"])
    if rc == 0 and "RUNNING" in out:
        warn("Service is already installed and running.")
        if ask_yn("  Reinstall (stop, remove, and reinstall)?", "y"):
            step("Stopping existing service...")
            run_cmd(["sc", "stop", "WinTelemetryHost"])
            time.sleep(3)
            run_cmd([sys.executable, os.path.join(SCRIPT_DIR, "agent.py"), "remove"])
            ok("Existing service removed")
        else:
            ok("Keeping existing installation")
            return

    step("Installing service...")
    agent_py = os.path.join(SCRIPT_DIR, "agent.py")
    rc, out = run_cmd([sys.executable, agent_py, "install"])
    if rc != 0:
        err(f"Service install failed: {out[:200]}")
        input("\n  Press Enter to exit...")
        sys.exit(1)
    ok("Service installed")

    step("Configuring auto-start and recovery...")
    run_cmd(["sc", "config",  "WinTelemetryHost", "start=", "auto"])
    run_cmd(["sc", "failure", "WinTelemetryHost", "reset=", "86400",
             "actions=", "restart/5000/restart/5000/restart/5000"])
    ok("Auto-start and recovery configured")

    step("Registering screenshot helper (starts at every login)...")
    try:
        import winreg
        python      = sys.executable
        helper_path = os.path.join(SCRIPT_DIR, "screenshot_helper.py")
        cmd_value   = f'"{python}" "{helper_path}"'
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "WinPerfMonHelper", 0, winreg.REG_SZ, cmd_value)
        winreg.CloseKey(key)
        ok("Screenshot helper registered in registry")
    except Exception as e:
        warn(f"Registry registration failed: {e}")

    step("Creating screenshot helper scheduled task...")
    python      = sys.executable
    helper_path = os.path.join(SCRIPT_DIR, "screenshot_helper.py")
    run_cmd(["schtasks", "/delete", "/tn", "WinPerfMonHelper", "/f"])
    rc, out = run_cmd([
        "schtasks", "/create",
        "/tn",  "WinPerfMonHelper",
        "/tr",  f'"{python}" "{helper_path}"',
        "/sc",  "onlogon",
        "/rl",  "limited",
        "/f"
    ])
    if rc == 0:
        ok("Screenshot task created")
    else:
        warn(f"Task creation note: {out[:100]}")

    step("Starting service...")
    rc, out = run_cmd(["sc", "start", "WinTelemetryHost"])
    if rc in (0, 1056):
        time.sleep(2)
        ok("Service started")
    else:
        warn(f"Service start: {out[:100]}")

    step("Launching screenshot helper now...")
    rc, out = run_cmd(["schtasks", "/run", "/tn", "WinPerfMonHelper"])
    if rc == 0:
        ok("Screenshot helper launched")
    else:
        warn("Helper will start at next login. Run start_helper.bat if needed.")

    step("Applying firewall rules...")
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from modules import firewall_block
        firewall_block.apply_firewall_blocks()
        firewall_block.block_whatsapp_specifically()
        ok("Firewall rules applied")
    except Exception as e:
        warn(f"Firewall module: {e}")


# ── Step 6: Verify & Complete ─────────────────────────────────────────────────

def step_verify():
    header(6, 6, "Verification & Complete")

    print(f"  {BOLD}Running checks...{RST}\n")
    all_ok = True

    # Service running
    rc, out = run_cmd(["sc", "query", "WinTelemetryHost"])
    if "RUNNING" in out:
        ok("Service is running")
    else:
        err("Service is NOT running")
        all_ok = False

    # Log file exists
    log_path = os.path.join(
        os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
        "WinTelemetryHost", "svc.log"
    )
    time.sleep(2)
    if os.path.isfile(log_path):
        ok(f"Log file created: {log_path}")
        # Show last few lines
        with open(log_path, "r", errors="ignore") as f:
            lines = f.readlines()
        if lines:
            print(f"\n  {DIM}Last log entries:{RST}")
            for line in lines[-5:]:
                print(f"  {DIM}{line.rstrip()}{RST}")
    else:
        warn("Log file not yet created (service may still be starting)")

    # DB file
    db_path = os.path.join(
        os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
        "WinTelemetryHost", "sys_perf.db"
    )
    if os.path.isfile(db_path):
        ok(f"Database created: {db_path}")
    else:
        info("Database will be created on first flush (within 5 minutes)")

    # Firewall rules
    rc, out = run_cmd(["netsh", "advfirewall", "firewall", "show",
                        "rule", "name=all", "dir=out"])
    count = out.count("DSKG_BLOCK_")
    if count > 0:
        ok(f"Firewall: {count} block rules active")
    else:
        warn("No firewall rules found")

    # Helper running
    rc, out = run_cmd(["tasklist"])
    if "pythonw" in out.lower():
        ok("Screenshot helper is running")
    else:
        info("Screenshot helper will start at next login")

    print()
    if all_ok:
        print(f"""
  {G}{BOLD}{'═'*56}{RST}
  {G}{BOLD}  Installation Complete!{RST}
  {G}{BOLD}{'═'*56}{RST}

  The monitoring system is now active on this machine.

  {BOLD}Quick commands (from this folder):{RST}
    check.bat                         ← check status anytime
    viewlogs.bat                      ← view logs
    python viewer.py dates            ← see what data is recorded
    python viewer.py summary          ← today's summary
    python viewer.py screens --date {time.strftime('%Y-%m-%d')} --out-dir C:\\IT\\shots

  {BOLD}Data location:{RST}
    {DIM}%PROGRAMDATA%\\WinTelemetryHost\\sys_perf.db{RST}
""")
    else:
        print(f"""
  {Y}{BOLD}Installation completed with warnings.{RST}
  Run check.bat to diagnose any issues.
""")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        step_welcome()
        step_dependencies()
        cfg = step_configure()
        step_write_config(cfg)
        step_install_service()
        step_verify()
    except KeyboardInterrupt:
        print(f"\n\n  {Y}Setup cancelled.{RST}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n  {R}Unexpected error: {e}{RST}")
        import traceback
        traceback.print_exc()

    input("\n  Press Enter to exit...")


if __name__ == "__main__":
    main()
