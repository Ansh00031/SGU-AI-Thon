"""System state snapshot, session tracking, and rollback engine."""

import datetime
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.system_paths import find_powershell_executable, get_system_env

BACKUPS_DIR = Path(__file__).resolve().parent.parent / ".backups"


def get_backups_dir() -> Path:
    """Ensure and return the backups directory path."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUPS_DIR


def generate_session_id(error_code: str) -> str:
    """Generate a unique timestamped session identifier."""
    clean_code = error_code.replace("0x", "").replace(":", "_").replace(" ", "_")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"session_{timestamp}_{clean_code}"


def create_pre_fix_snapshot(
    session_id: str,
    error_code: str,
    proposal: Dict[str, Any],
    rollback_script: str,
    system_context: Dict[str, Any],
) -> Path:
    """Capture pre-fix system configuration, backup scripts, and metadata.

    Args:
        session_id: Unique session ID.
        error_code: Target error code.
        proposal: The approved remediation proposal.
        rollback_script: The inverse PowerShell script to undo the fix.
        system_context: Gathered OS metadata and diagnostics.

    Returns:
        Path: Path to the created session backup directory.
    """
    session_dir = get_backups_dir() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save fix script
    fix_path = session_dir / "fix.ps1"
    fix_path.write_text(proposal.get("script_content", ""), encoding="utf-8")

    # 2. Save rollback script
    rollback_path = session_dir / "rollback.ps1"
    rollback_path.write_text(rollback_script, encoding="utf-8")

    # 3. Save comprehensive session metadata
    metadata = {
        "session_id": session_id,
        "error_code": error_code,
        "created_at": datetime.datetime.now().isoformat(),
        "fix_title": proposal.get("title", "Remediation Fix"),
        "fix_summary": proposal.get("summary", ""),
        "verification_command": proposal.get("verification_command", ""),
        "os_info": system_context.get("os_info", {}),
        "status": "APPLIED",
        "rollback_executed": False,
    }

    meta_path = session_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return session_dir


def update_session_status(session_id: str, status: str, rollback_executed: bool = False) -> None:
    """Update execution status in session metadata."""
    session_dir = get_backups_dir() / session_id
    meta_path = session_dir / "metadata.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            data["status"] = status
            if rollback_executed:
                data["rollback_executed"] = True
                data["rolled_back_at"] = datetime.datetime.now().isoformat()
            meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass


def list_sessions() -> List[Dict[str, Any]]:
    """Retrieve all historical remediation sessions ordered from newest to oldest."""
    backups_dir = get_backups_dir()
    sessions = []

    for item in backups_dir.iterdir():
        if item.is_dir():
            meta_file = item / "metadata.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    sessions.append(meta)
                except Exception:
                    continue

    # Sort newest first
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return sessions


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get metadata and file paths for a specific session."""
    session_dir = get_backups_dir() / session_id
    meta_file = session_dir / "metadata.json"
    if not meta_file.exists():
        return None

    try:
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        data["dir_path"] = str(session_dir)
        data["rollback_script_path"] = str(session_dir / "rollback.ps1")
        data["fix_script_path"] = str(session_dir / "fix.ps1")
        return data
    except Exception:
        return None
