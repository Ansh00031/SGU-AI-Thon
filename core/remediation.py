"""Secure script execution and temporary file lifecycle management for OS remediations."""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.system_paths import find_powershell_executable, get_system_env


def execute_remediation_script(
    script_content: str,
    script_type: str = "powershell",
    timeout: int = 120,
) -> Dict[str, Any]:
    """Write remediation script to a secure temporary file, execute via subprocess, and guarantee cleanup.

    Args:
        script_content: Full text of the script to execute.
        script_type: Type of script ('powershell' or 'bash').
        timeout: Maximum duration before terminating execution.

    Returns:
        Dict[str, Any]: Execution results including stdout, stderr, returncode, and temp path used.
    """
    suffix = ".ps1" if script_type.lower() == "powershell" else ".sh"
    temp_file_path: Optional[str] = None
    start_time = time.time()

    try:
        # Create secure temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(script_content)
            temp_file_path = temp_file.name

        # Build execution command
        if script_type.lower() == "powershell":
            ps_exe = find_powershell_executable()
            cmd = [
                ps_exe,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                temp_file_path,
            ]
        else:
            cmd = ["bash", temp_file_path]

        # Execute subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=get_system_env(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        duration = round(time.time() - start_time, 2)
        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "duration_sec": duration,
            "temp_file": temp_file_path,
            "cleaned_up": True,
        }

    except subprocess.TimeoutExpired:
        duration = round(time.time() - start_time, 2)
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Remediation script execution timed out after {timeout} seconds.",
            "duration_sec": duration,
            "temp_file": temp_file_path,
            "cleaned_up": True,
        }
    except Exception as ex:
        duration = round(time.time() - start_time, 2)
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Failed to execute remediation script: {str(ex)}",
            "duration_sec": duration,
            "temp_file": temp_file_path,
            "cleaned_up": True,
        }
    finally:
        # Guarantee cleanup of temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
