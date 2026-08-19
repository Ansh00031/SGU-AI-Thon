"""Security and privilege verification module."""

import ctypes
import os
import platform
import sys
from typing import Tuple


def is_admin() -> bool:
    """Check if the current process is running with administrative/root privileges.

    Returns:
        bool: True if elevated (Administrator on Windows, root on Unix), False otherwise.
    """
    system_name = platform.system()
    try:
        if system_name == "Windows":
            return bool(ctypes.windll.shell32.IsUserAnAdmin() != 0)
        else:
            # POSIX systems (Linux, macOS)
            return os.geteuid() == 0
    except Exception:
        return False


def get_elevation_details() -> Tuple[bool, str]:
    """Get privilege status and descriptive instruction for elevation if needed.

    Returns:
        Tuple[bool, str]: (is_elevated, guidance_message)
    """
    elevated = is_admin()
    system_name = platform.system()

    if elevated:
        return True, "Running with elevated privileges."

    if system_name == "Windows":
        msg = (
            "This application requires Windows Administrator privileges to execute system-level diagnostics and fixes.\n"
            "Please relaunch PowerShell / Terminal as Administrator (Right-click -> 'Run as administrator')."
        )
    else:
        msg = (
            "This application requires root privileges to execute system-level diagnostics and fixes.\n"
            "Please run with 'sudo python agent.py ...'."
        )

    return False, msg
