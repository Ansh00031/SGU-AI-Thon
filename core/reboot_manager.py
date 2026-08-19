"""Post-reboot session persistence and Windows RunOnce lifecycle manager."""

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

RUNONCE_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
RUNONCE_VALUE_NAME = "OSDebugAgentResume"


def is_reboot_pending() -> bool:
    """Check whether Windows has a pending reboot scheduled by OS updates or component servicing."""
    if platform.system() != "Windows":
        return False

    try:
        import winreg

        # 1. Check Windows Update RebootRequired
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
            ):
                return True
        except FileNotFoundError:
            pass

        # 2. Check CBS RebootPending
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
            ):
                return True
        except FileNotFoundError:
            pass

        # 3. Check Session Manager PendingFileRenameOperations
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager",
            ) as key:
                val, _ = winreg.QueryValueEx(key, "PendingFileRenameOperations")
                if val:
                    return True
        except FileNotFoundError:
            pass

    except Exception:
        pass

    return False


def register_reboot_hook(session_id: str, verify_cmd: str) -> Tuple[bool, str]:
    """Register a Windows RunOnce startup entry so the agent automatically resumes and verifies after reboot.

    Args:
        session_id: The active session ID to verify post-reboot.
        verify_cmd: Verification command to run on wakeup.

    Returns:
        Tuple[bool, str]: (success, message_or_error)
    """
    if platform.system() != "Windows":
        return False, "Reboot persistence is currently only supported on Windows."

    try:
        import winreg

        agent_py = Path(__file__).resolve().parent.parent / "agent.py"
        python_exe = sys.executable

        # Build resume command line
        # Use quotes around paths to handle spaces in user directories
        resume_cmd = f'"{python_exe}" "{agent_py}" resume {session_id}'

        # Write to HKCU RunOnce
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUNONCE_REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, RUNONCE_VALUE_NAME, 0, winreg.REG_SZ, resume_cmd)

        # Record resume state file in session directory
        from core.snapshot import get_backups_dir
        session_dir = get_backups_dir() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        resume_state = {
            "session_id": session_id,
            "verify_command": verify_cmd,
            "registered_at": json.dumps(os.environ.get("USERNAME", "")),
            "command_line": resume_cmd,
            "status": "AWAITING_REBOOT",
        }
        (session_dir / "resume_state.json").write_text(json.dumps(resume_state, indent=2), encoding="utf-8")

        return True, f"Successfully registered RunOnce startup hook: {RUNONCE_VALUE_NAME}"

    except Exception as ex:
        return False, f"Failed to register RunOnce hook: {str(ex)}"


def unregister_reboot_hook() -> bool:
    """Remove the RunOnce registry key upon successful session resume."""
    if platform.system() != "Windows":
        return False

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUNONCE_REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            try:
                winreg.DeleteValue(key, RUNONCE_VALUE_NAME)
                return True
            except FileNotFoundError:
                return True
    except Exception:
        return False


def get_resume_state(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve resume state payload for a session."""
    from core.snapshot import get_backups_dir

    state_file = get_backups_dir() / session_id / "resume_state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None
