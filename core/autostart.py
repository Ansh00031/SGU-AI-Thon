"""Windows persistent auto-start and startup task manager with single-instance enforcement and logging."""

import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_VALUE_NAME = "AutonomousOSDebugAgent"


def get_startup_folder() -> Path:
    """Return the Windows User Startup folder path."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def is_autostart_enabled() -> Tuple[bool, str]:
    """Check if the agent is registered to run automatically on PC startup.

    Returns:
        Tuple[bool, str]: (is_enabled, details_or_method)
    """
    if platform.system() != "Windows":
        return False, "Auto-start is only supported on Windows."

    # 1. Check Startup Folder Launcher (Primary)
    startup_bat = get_startup_folder() / "OS_Debug_Agent_Startup.bat"
    if startup_bat.exists():
        return True, f"Startup Folder Launcher ({startup_bat.name})"

    # 2. Check Registry Run Key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, AUTOSTART_VALUE_NAME)
            if val:
                return True, f"Windows Registry Run Key ({AUTOSTART_VALUE_NAME})"
    except Exception:
        pass

    return False, "Not registered for startup."


def enable_autostart(mode: str = "health_check") -> Tuple[bool, str]:
    """Register a single, clean startup launcher with persistent logging and visible window retention.

    Returns:
        Tuple[bool, str]: (success, status_message)
    """
    if platform.system() != "Windows":
        return False, "Auto-start is only supported on Windows operating systems."

    try:
        # First clean up any duplicate registry entries to prevent multiple popups
        disable_autostart()

        agent_dir = Path(__file__).resolve().parent.parent
        agent_py = agent_dir / "agent.py"
        python_exe = sys.executable
        backups_dir = agent_dir / ".backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        log_file = backups_dir / "startup_log.txt"

        # Create a single, high-visibility launcher in the Startup Folder
        startup_dir = get_startup_folder()
        startup_dir.mkdir(parents=True, exist_ok=True)
        startup_bat = startup_dir / "OS_Debug_Agent_Startup.bat"

        bat_content = f"""@echo off
cls
color 0B
echo ===============================================================================
echo     AUTONOMOUS OS DEBUGGING AGENT - SYSTEM STARTUP HEALTH MONITOR
echo ===============================================================================
echo [INFO] Timestamp: %DATE% %TIME%
echo [INFO] Session Log: {log_file}
echo.

cd /d "{agent_dir}"

REM Log execution to persistent file
echo [STARTUP_RUN] %DATE% %TIME% >> "{log_file}"

REM Run startup-monitor (shows problem faced, solution statement, and live health)
"{python_exe}" "{agent_py}" startup-monitor
echo.
echo ===============================================================================
echo [STATUS] Startup health scan complete. The agent is active and monitoring.
echo To run diagnostics on a specific error: python agent.py diagnose [ERROR_CODE]
echo ===============================================================================
echo.
pause
"""
        startup_bat.write_text(bat_content, encoding="utf-8")

        return True, f"Auto-start enabled! Created clean single startup launcher: {startup_bat.name}"

    except Exception as ex:
        return False, f"Failed to enable auto-start: {str(ex)}"


def disable_autostart() -> Tuple[bool, str]:
    """Unregister and remove all startup launchers and duplicate registry entries."""
    if platform.system() != "Windows":
        return False, "Auto-start is only supported on Windows."

    removed_items = []
    try:
        # 1. Clean Registry Run Key
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, AUTOSTART_VALUE_NAME)
                removed_items.append("Registry Run Key")
        except FileNotFoundError:
            pass

        # 2. Clean RunOnce Key if left over
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, "OSDebugAgentResume")
                removed_items.append("RunOnce Key")
        except FileNotFoundError:
            pass

        # 3. Clean Startup Folder Launcher
        startup_bat = get_startup_folder() / "OS_Debug_Agent_Startup.bat"
        if startup_bat.exists():
            startup_bat.unlink()
            removed_items.append(f"Startup file ({startup_bat.name})")

        if removed_items:
            return True, f"Successfully cleaned startup triggers (Removed: {', '.join(removed_items)})."
        else:
            return True, "Auto-start was already disabled."

    except Exception as ex:
        return False, f"Failed to disable auto-start: {str(ex)}"


def read_startup_log() -> str:
    """Read contents of the startup execution log."""
    agent_dir = Path(__file__).resolve().parent.parent
    log_file = agent_dir / ".backups" / "startup_log.txt"
    if log_file.exists():
        return log_file.read_text(encoding="utf-8")
    return "No startup logs recorded yet."
