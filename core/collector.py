"""System diagnostic and Event Log context gathering module."""

import datetime
import getpass
import json
import os
import platform
import subprocess
from typing import Any, Dict, List, Optional

from core.security import is_admin
from core.system_paths import find_powershell_executable, get_system_env


def get_system_metadata() -> Dict[str, Any]:
    """Gather core OS metadata, architecture, and user privilege details."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor() or platform.uname().processor,
        "hostname": platform.node(),
        "current_user": getpass.getuser(),
        "is_elevated": is_admin(),
        "python_version": platform.python_version(),
    }


def query_windows_event_logs(
    error_code: Optional[str] = None,
    max_events: int = 50,
) -> Dict[str, Any]:
    """Query recent critical and error events from Windows Event Log using PowerShell.

    Queries channels like System, Application, and WindowsUpdateClient.

    Args:
        error_code: Target error code to prioritize or search.
        max_events: Maximum number of events to return.

    Returns:
        Dict[str, Any] containing captured events and query diagnostics.
    """
    events: List[Dict[str, Any]] = []
    channels_queried = ["System", "Application", "Microsoft-Windows-WindowsUpdateClient/Operational"]
    captured_channels: List[str] = []
    error_msg: Optional[str] = None

    # PowerShell script to safely query events and format as JSON
    # Level 1 = Critical, Level 2 = Error
    ps_script = f"""
    $ErrorActionPreference = 'SilentlyContinue'
    $results = @()
    $channels = @('System', 'Application', 'Microsoft-Windows-WindowsUpdateClient/Operational')

    foreach ($chan in $channels) {{
        try {{
            $logEvents = Get-WinEvent -FilterHashtable @{{
                LogName = $chan
                Level = 1, 2
            }} -MaxEvents {max_events} 2>$null

            if ($logEvents) {{
                foreach ($evt in $logEvents) {{
                    $msg = $evt.Message
                    if ($msg -and $msg.Length -gt 500) {{
                        $msg = $msg.Substring(0, 500) + '... [truncated]'
                    }}
                    $results += [PSCustomObject]@{{
                        Channel = $evt.LogName
                        ProviderName = $evt.ProviderName
                        Id = $evt.Id
                        Level = $evt.LevelDisplayName
                        TimeCreated = $evt.TimeCreated.ToString("yyyy-MM-dd HH:mm:ss")
                        Message = if ($msg) {{ $msg }} else {{ "(No message content)" }}
                    }}
                }}
            }}
        }} catch {{}}
    }}

    # Sort descending by TimeCreated and take top {max_events}
    $results = $results | Sort-Object -Property TimeCreated -Descending | Select-Object -First {max_events}
    if ($results) {{
        $results | ConvertTo-Json -Depth 3 -Compress
    }} else {{
        "[]"
    }}
    """

    try:
        # Run PowerShell without creating pop-up windows
        ps_exe = find_powershell_executable()
        cmd = [
            ps_exe,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_script,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            env=get_system_env(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        stdout = result.stdout.strip()
        if stdout:
            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, list):
                    events = parsed
                elif isinstance(parsed, dict):
                    events = [parsed]
            except json.JSONDecodeError:
                # Fallback: if single line or slightly malformed JSON
                error_msg = f"Failed to parse Event Viewer JSON: {stdout[:200]}"
        else:
            if result.stderr:
                error_msg = result.stderr.strip()

    except subprocess.TimeoutExpired:
        error_msg = "Event log query timed out after 15 seconds."
    except FileNotFoundError:
        error_msg = "powershell.exe not found on PATH."
    except Exception as ex:
        error_msg = f"Unexpected error during Event Log query: {str(ex)}"

    return {
        "channels_queried": channels_queried,
        "total_events_captured": len(events),
        "events": events,
        "error": error_msg,
    }


def query_linux_syslog(max_events: int = 50) -> Dict[str, Any]:
    """Fallback collector for Linux / POSIX systems using journalctl or dmesg."""
    events: List[Dict[str, Any]] = []
    error_msg: Optional[str] = None

    try:
        # Query journalctl for errors in last 24h
        cmd = ["journalctl", "-p", "err", "-n", str(max_events), "--output=json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and result.stdout:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    events.append({
                        "Channel": "journald",
                        "ProviderName": entry.get("_SYSTEMD_UNIT", "system"),
                        "Id": entry.get("PRIORITY", "err"),
                        "Level": "Error",
                        "TimeCreated": entry.get("__REALTIME_TIMESTAMP", ""),
                        "Message": entry.get("MESSAGE", ""),
                    })
                except Exception:
                    continue
        else:
            error_msg = result.stderr.strip() or "No journalctl entries available."
    except Exception as ex:
        error_msg = f"Linux log query failed: {str(ex)}"

    return {
        "channels_queried": ["journald"],
        "total_events_captured": len(events),
        "events": events,
        "error": error_msg,
    }


def gather_system_context(
    error_code: str,
    max_events: int = 50,
) -> Dict[str, Any]:
    """Gather comprehensive system and log context formatted for AI diagnostic ingestion.

    Args:
        error_code: Target error code (e.g., '0x80070005').
        max_events: Number of critical/error log events to collect.

    Returns:
        Dict[str, Any]: Structured JSON-ready dictionary.
    """
    sys_meta = get_system_metadata()
    current_os = sys_meta["system"]

    if current_os == "Windows":
        logs = query_windows_event_logs(error_code=error_code, max_events=max_events)
    else:
        logs = query_linux_syslog(max_events=max_events)

    context: Dict[str, Any] = {
        "target_error_code": error_code,
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "os_info": sys_meta,
        "event_logs_summary": {
            "total_events_captured": logs.get("total_events_captured", 0),
            "channels_queried": logs.get("channels_queried", []),
            "query_error": logs.get("error"),
        },
        "event_logs": logs.get("events", []),
    }

    return context
