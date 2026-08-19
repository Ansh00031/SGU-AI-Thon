"""System path and executable resolution utilities."""

import os
import platform
import shutil
from typing import List, Optional


def find_powershell_executable() -> str:
    """Find the full absolute path to the PowerShell executable on the system.

    Returns:
        str: Path to powershell.exe or pwsh.exe, or fallback to 'powershell.exe'.
    """
    if platform.system() != "Windows":
        # On POSIX (Linux/macOS), check for pwsh or fallback to bash
        for name in ["pwsh", "powershell", "bash", "sh"]:
            found = shutil.which(name)
            if found:
                return found
        return "bash"

    # 1. Check PATH for powershell / pwsh
    for name in ["powershell.exe", "pwsh.exe", "powershell", "pwsh"]:
        found = shutil.which(name)
        if found and os.path.isfile(found):
            return found

    # 2. Check standard Windows System paths explicitly
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate_paths: List[str] = [
        os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        os.path.join(system_root, "SysWOW64", "WindowsPowerShell", "v1.0", "powershell.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "PowerShell", "7", "pwsh.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "PowerShell", "7", "pwsh.exe"),
    ]

    for path in candidate_paths:
        if os.path.isfile(path):
            return path

    return "powershell.exe"


def get_system_env() -> dict:
    """Return an environment dictionary guaranteed to contain essential system paths in PATH.

    Ensures System32, WindowsPowerShell, and system utilities (icacls, regsvr32, etc.) are always resolvable.
    """
    env = os.environ.copy()
    if platform.system() == "Windows":
        system_root = env.get("SystemRoot", r"C:\Windows")
        system32 = os.path.join(system_root, "System32")
        sys_powershell = os.path.join(system32, "WindowsPowerShell", "v1.0")
        sys_wbem = os.path.join(system32, "Wbem")

        current_path = env.get("PATH", "")
        # Prepend critical Windows directories to PATH
        core_paths = [system32, sys_powershell, system_root, sys_wbem]
        new_path_entries = [p for p in core_paths if p.lower() not in current_path.lower()]

        if new_path_entries:
            env["PATH"] = os.pathsep.join(new_path_entries) + os.pathsep + current_path

    return env
