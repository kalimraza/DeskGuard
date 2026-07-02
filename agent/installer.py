# agent/installer.py — Install/remove the DeskGuard monitor Windows Service
# Run as Administrator:
#   python installer.py install
#   python installer.py remove
#   python installer.py status

import sys, os, subprocess, ctypes, time, winreg
import config

HELPER_REG_KEY  = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
HELPER_REG_NAME = "WinPerfMonHelper"
TASK_NAME       = "WinPerfMonHelper"


def _is_admin():
    try:    return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def _register_helper():
    """Add screenshot_helper.py to HKLM Run — starts with every user login."""
    python      = sys.executable
    helper_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "screenshot_helper.py"))
    cmd_value   = f'"{python}" "{helper_path}"'
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, HELPER_REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, HELPER_REG_NAME, 0, winreg.REG_SZ, cmd_value)
        winreg.CloseKey(key)
        print("  Screenshot helper registered in registry.")
    except Exception as e:
        print(f"  WARNING: Could not register helper: {e}")


def _unregister_helper():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, HELPER_REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, HELPER_REG_NAME)
        winreg.CloseKey(key)
        print("  Screenshot helper removed from registry.")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  WARNING: Could not remove helper key: {e}")


def _kill_helper():
    subprocess.run(["wmic", "process", "where",
                    "CommandLine like '%screenshot_helper%'", "delete"],
                   capture_output=True)
    _run(["schtasks", "/end", "/tn", TASK_NAME])


def _launch_helper_now():
    """Launch screenshot helper immediately in the interactive user session."""
    python      = sys.executable
    helper_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "screenshot_helper.py"))

    # Create scheduled task that runs at logon
    _run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"])
    _run(["schtasks", "/create",
          "/tn",  TASK_NAME,
          "/tr",  f'"{python}" "{helper_path}"',
          "/sc",  "onlogon",
          "/rl",  "limited",
          "/f"])

    # Run immediately in interactive session
    rc, out = _run(["schtasks", "/run", "/tn", TASK_NAME])
    if rc == 0:
        print("  Screenshot helper launched in user session.")
    else:
        print("  Screenshot helper scheduled for next login.")
        print("  Run start_helper.bat to start it now.")


def install():
    if not _is_admin():
        print("ERROR: Run as Administrator.")
        sys.exit(1)

    agent_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "agent.py"))
    python   = sys.executable

    print(f"Installing '{config.SERVICE_DISPLAY_NAME}'...")
    rc, out = _run([python, agent_py, "install"])
    if rc != 0:
        print(f"Install failed:\n{out}"); sys.exit(1)

    _run(["sc", "config",      config.SERVICE_NAME, "start=",  "auto"])
    _run(["sc", "failure",     config.SERVICE_NAME, "reset=",  "86400",
          "actions=", "restart/5000/restart/5000/restart/5000"])
    _run(["sc", "description", config.SERVICE_NAME, config.SERVICE_DESCRIPTION])

    _register_helper()
    _launch_helper_now()

    print("Starting service...")
    rc, out = _run(["sc", "start", config.SERVICE_NAME])
    if rc not in (0, 1056):
        print(f"Start warning: {out.strip()}")

    print(f"\nInstalled. Log: {config.LOG_FILE}")


def remove():
    if not _is_admin():
        print("ERROR: Run as Administrator.")
        sys.exit(1)

    print("Stopping service...")
    _run(["sc", "stop", config.SERVICE_NAME])
    time.sleep(3)

    print("Removing service...")
    agent_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "agent.py"))
    _run([sys.executable, agent_py, "remove"])

    print("Removing firewall rules...")
    try:
        from modules import firewall_block
        firewall_block.remove_all_firewall_blocks()
    except Exception as e:
        print(f"  Firewall cleanup: {e}")

    print("Cleaning hosts file...")
    try:
        from modules import website_blocker
        website_blocker.remove_blocklist()
    except Exception as e:
        print(f"  Hosts cleanup: {e}")

    _kill_helper()
    _unregister_helper()
    _run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"])

    print("Done. All traces removed.")


def status():
    rc, out = _run(["sc", "query", config.SERVICE_NAME])
    print(out if out else "Service not found.")
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, HELPER_REG_KEY, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, HELPER_REG_NAME)
        winreg.CloseKey(key)
        print(f"Screenshot helper: registered")
    except FileNotFoundError:
        print("Screenshot helper: NOT registered")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python installer.py [install | remove | status]")
        sys.exit(1)
    {"install": install, "remove": remove, "status": status}[sys.argv[1].lower()]()
