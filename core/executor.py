"""Safe read-only command executor for OS diagnostics."""

import re
import subprocess
import time
from typing import Any, Dict, List, Tuple

from core.system_paths import find_powershell_executable, get_system_env

# Blacklisted destructive commands or operators that should NEVER run in read-only diagnostic mode
DANGEROUS_PATTERNS = [
    r"\bformat\b",
    r"\bdel\b",
    r"\berase\b",
    r"\brmdir\b",
    r"\bRemove-Item\b",
    r"\bStop-Process\b",
    r"\bSet-ItemProperty\b",
    r"\bNew-Item\b",
    r"\bRemove-ItemProperty\b",
    r"\bClear-Content\b",
    r"\bSet-Content\b",
    r"\bOut-File\b",
    r">",
    r"\bInvoke-WebRequest.*-OutFile\b",
    r"\bStart-Process.*-Verb\s+RunAs\b",
    r"\breg\s+add\b",
    r"\breg\s+delete\b",
    r"\bshutdown\b",
    r"\brestart-computer\b",
]


def is_command_safe(command: str) -> Tuple[bool, str]:
    """Validate that a diagnostic command does not contain destructive patterns.

    Args:
        command: PowerShell or shell command string.

    Returns:
        Tuple[bool, str]: (is_safe, reason_or_warning)
    """
    cmd_lower = command.strip()
    if not cmd_lower:
        return False, "Command is empty."

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return False, f"Command contains potentially modifying or dangerous pattern: '{pattern}'"

    return True, "Safe read-only command."


def execute_diagnostic_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute a read-only diagnostic command securely in PowerShell and capture output.

    Args:
        command: Command string to execute.
        timeout: Maximum seconds before terminating execution.

    Returns:
        Dict[str, Any] containing stdout, stderr, exit code, duration, and safety status.
    """
    is_safe, safety_msg = is_command_safe(command)
    if not is_safe:
        return {
            "command": command,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution blocked: {safety_msg}",
            "duration_sec": 0.0,
            "blocked": True,
        }

    start_time = time.time()
    try:
        ps_exe = find_powershell_executable()
        cmd = [
            ps_exe,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=get_system_env(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        duration = round(time.time() - start_time, 2)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Limit stdout length to avoid token bloat
        if len(stdout) > 3000:
            stdout = stdout[:3000] + "\n... [Output truncated for length]"

        return {
            "command": command,
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_sec": duration,
            "blocked": False,
        }

    except subprocess.TimeoutExpired:
        duration = round(time.time() - start_time, 2)
        return {
            "command": command,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds.",
            "duration_sec": duration,
            "blocked": False,
        }
    except Exception as ex:
        duration = round(time.time() - start_time, 2)
        return {
            "command": command,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution failed: {str(ex)}",
            "duration_sec": duration,
            "blocked": False,
        }


def execute_diagnostic_suite(commands: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Execute a series of diagnostic commands and capture results for AI analysis.

    Args:
        commands: List of dicts, e.g., [{"command": "icacls ...", "purpose": "..."}]

    Returns:
        List[Dict[str, Any]] containing execution results with purpose metadata.
    """
    results = []
    for item in commands:
        cmd_str = item.get("command", "") if isinstance(item, dict) else str(item)
        purpose = item.get("purpose", "Diagnostic check") if isinstance(item, dict) else "Diagnostic check"

        exec_res = execute_diagnostic_command(cmd_str)
        exec_res["purpose"] = purpose
        results.append(exec_res)

    return results
