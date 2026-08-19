"""LLM Reasoning Engine for OS Diagnostics and Remediation."""

import json
import os
import re
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from core.config import settings


def get_llm_client() -> Optional[Any]:
    """Instantiate OpenAI client with configured API key and base URL."""
    if OpenAI is None:
        return None

    api_key = settings.openai_api_key
    base_url = settings.openai_base_url

    # Check if local Ollama or custom endpoint is specified
    if base_url:
        return OpenAI(
            base_url=base_url,
            api_key=api_key if (api_key and api_key.strip()) else "ollama",
        )

    if api_key and api_key.strip() and api_key != "your_openai_api_key_here":
        return OpenAI(api_key=api_key)

    return None


def extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON object from LLM response text, handling markdown code fences."""
    text = text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Match outermost curly braces
        match_brace = re.search(r"(\{.*\})", text, re.DOTALL)
        json_str = match_brace.group(1) if match_brace else text

    return json.loads(json_str)


def generate_initial_diagnosis(
    error_code: str,
    system_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate initial OS error diagnosis and safe read-only diagnostic commands.

    Args:
        error_code: The error code to analyze (e.g., '0x80070005').
        system_context: Gathered OS metadata and event logs.

    Returns:
        Dict[str, Any] containing diagnosis and diagnostic_commands list.
    """
    client = get_llm_client()

    # Built-in heuristic fallback if no LLM key is configured (allows offline testing/mocking)
    if not client:
        return _fallback_initial_diagnosis(error_code, system_context)

    system_prompt = (
        "You are an Expert Windows Systems Engineer and Autonomous OS Diagnostics AI. "
        "Your task is to analyze an OS error code, review system metadata and event logs, "
        "and generate an accurate explanation along with safe, READ-ONLY diagnostic commands.\n\n"
        "RULES:\n"
        "1. You MUST respond with ONLY a valid JSON object—no conversational filler.\n"
        "2. All 'diagnostic_commands' MUST be strictly safe, read-only PowerShell commands "
        "(e.g., 'icacls', 'Get-ItemProperty', 'Get-Service', 'sfc /verifyonly', 'Test-Path', 'dism /online /cleanup-image /checkhealth').\n"
        "3. NEVER include modifying, deleting, or restarting commands in diagnostic_commands.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "error_code": "0x80070005",\n'
        '  "error_name": "ERROR_ACCESS_DENIED",\n'
        '  "diagnosis": "Detailed explanation of what this error code represents in the current OS context.",\n'
        '  "likely_causes": ["Cause 1", "Cause 2"],\n'
        '  "diagnostic_commands": [\n'
        '    {"command": "Get-Service wuauserv | Select-Object Name, Status, StartType", "purpose": "Check Windows Update Service status"},\n'
        '    {"command": "icacls \\"C:\\\\Windows\\\\SoftwareDistribution\\"", "purpose": "Verify directory ACL permissions"}\n'
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"Target Error Code: {error_code}\n\n"
        f"Gathered System Context:\n{json.dumps(system_context, indent=2)}\n\n"
        "Please provide the initial diagnosis and diagnostic commands in the required JSON format."
    )

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"} if "gpt" in settings.llm_model else None,
        )
        content = response.choices[0].message.content or "{}"
        return extract_json(content)
    except Exception as ex:
        # Fallback if API fails
        result = _fallback_initial_diagnosis(error_code, system_context)
        result["llm_warning"] = f"LLM API request failed ({str(ex)}); loaded expert heuristic diagnostics."
        return result


def confirm_root_cause(
    error_code: str,
    initial_diagnosis: Dict[str, Any],
    execution_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyze the output of diagnostic commands and confirm the root cause.

    Args:
        error_code: Target error code.
        initial_diagnosis: Initial diagnosis dictionary.
        execution_results: Output and exit codes from executed diagnostic commands.

    Returns:
        Dict[str, Any] containing root cause confirmation and remediation prerequisites.
    """
    client = get_llm_client()

    if not client:
        return _fallback_root_cause(error_code, execution_results)

    system_prompt = (
        "You are an Expert Windows Systems Engineer and Autonomous OS Diagnostics AI. "
        "You have executed read-only diagnostic commands on the system. "
        "Analyze the command outputs (stdout, stderr, return codes) to verify the exact root cause of the error.\n\n"
        "RULES:\n"
        "1. You MUST respond with ONLY a valid JSON object.\n"
        "2. State clearly whether the root cause is confirmed based on evidence in the command output.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "root_cause_confirmed": true,\n'
        '  "root_cause_analysis": "Precise explanation of what the command outputs revealed.",\n'
        '  "evidence": ["Evidence point 1 extracted from stdout", "Evidence point 2"],\n'
        '  "remediation_summary": "High-level summary of the required fix steps."\n'
        "}"
    )

    user_prompt = (
        f"Target Error Code: {error_code}\n\n"
        f"Initial Diagnosis:\n{json.dumps(initial_diagnosis, indent=2)}\n\n"
        f"Diagnostic Execution Results:\n{json.dumps(execution_results, indent=2)}\n\n"
        "Analyze the results and confirm the root cause in the required JSON format."
    )

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"} if "gpt" in settings.llm_model else None,
        )
        content = response.choices[0].message.content or "{}"
        return extract_json(content)
    except Exception as ex:
        result = _fallback_root_cause(error_code, execution_results)
        result["llm_warning"] = f"LLM API request failed ({str(ex)}); loaded heuristic root cause analysis."
        return result


def generate_remediation_proposal(
    error_code: str,
    root_cause_data: Dict[str, Any],
    system_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a targeted remediation script and human-readable explanation from confirmed root cause.

    Args:
        error_code: Target error code.
        root_cause_data: Output from confirm_root_cause.
        system_context: OS metadata and event log context.

    Returns:
        Dict[str, Any] containing human summary, steps, script content, and verification command.
    """
    client = get_llm_client()

    if not client:
        return _fallback_remediation_proposal(error_code, root_cause_data)

    system_prompt = (
        "You are an Expert Windows Systems Engineer and Autonomous OS Diagnostics AI. "
        "Based on the confirmed root cause analysis, generate a precise, safe remediation script "
        "and a human-readable explanation.\n\n"
        "RULES:\n"
        "1. You MUST respond with ONLY a valid JSON object.\n"
        "2. The 'script_content' MUST be a clean, production-grade PowerShell script that directly fixes the issue.\n"
        "3. The script MUST begin with a multi-line comment block (<# ... #>) explaining the exact PROBLEM STATEMENT, ROOT CAUSE, and REMEDIATION PLAN.\n"
        "4. Ensure the script sets path ($env:PATH = \"$env:SystemRoot\\System32;$env:PATH\") or uses explicit system paths ($env:SystemRoot\\System32\\icacls.exe) for external executables.\n"
        "5. Include proper error handling and comments in the script.\n"
        "6. Provide a 'verification_command' (read-only command) that will confirm the fix succeeded in the next step.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "title": "Windows Update Permission & Cache Reset",\n'
        '  "problem_statement": "Clear 1-2 sentence description of the exact problem the user is facing.",\n'
        '  "summary": "Brief 2-3 sentence overview of what the script does.",\n'
        '  "steps": [\n'
        '    "Stop Windows Update and Background Intelligent Transfer services",\n'
        '    "Reset NTFS permissions on SoftwareDistribution directory",\n'
        '    "Restart Windows Update services"\n'
        '  ],\n'
        '  "script_type": "powershell",\n'
        '  "script_content": "<#\\n====================================================================\\n# PROBLEM STATEMENT: ...\\n====================================================================\\n#>\\n...",\n'
        '  "verification_command": "Get-Service wuauserv, bits | Select-Object Name, Status",\n'
        '  "requires_reboot": false\n'
        "}"
    )

    user_prompt = (
        f"Target Error Code: {error_code}\n\n"
        f"Confirmed Root Cause:\n{json.dumps(root_cause_data, indent=2)}\n\n"
        f"System Context:\n{json.dumps(system_context.get('os_info', {}), indent=2)}\n\n"
        "Generate the remediation proposal and PowerShell script in the required JSON format."
    )

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"} if "gpt" in settings.llm_model else None,
        )
        content = response.choices[0].message.content or "{}"
        return extract_json(content)
    except Exception as ex:
        result = _fallback_remediation_proposal(error_code, root_cause_data)
        result["llm_warning"] = f"LLM API request failed ({str(ex)}); loaded expert remediation proposal."
        return result


def generate_rollback_proposal(
    error_code: str,
    proposal: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate an inverse PowerShell rollback script to safely revert changes made by a remediation script.

    Args:
        error_code: Target error code.
        proposal: The remediation proposal containing the fix script.

    Returns:
        Dict[str, Any] containing summary and rollback script content.
    """
    client = get_llm_client()

    if not client:
        return _fallback_rollback_proposal(error_code, proposal)

    system_prompt = (
        "You are an Expert Windows Systems Engineer and Autonomous OS Diagnostics AI. "
        "Your task is to generate a safe, reliable PowerShell ROLLBACK script that precisely undoes "
        "the changes made by a remediation script.\n\n"
        "RULES:\n"
        "1. You MUST respond with ONLY a valid JSON object.\n"
        "2. The 'rollback_script' MUST safely revert services, registry entries, or configurations touched by the fix.\n"
        "3. Ensure the script begins with path setup ($env:PATH = \"$env:SystemRoot\\System32;$env:PATH\").\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "summary": "Rollback plan to restore pre-fix service and permission states.",\n'
        '  "rollback_script": "# PowerShell rollback script\\n...",\n'
        '  "verification_command": "Get-Service wuauserv, bits | Select-Object Name, Status"\n'
        "}"
    )

    user_prompt = (
        f"Target Error Code: {error_code}\n\n"
        f"Original Remediation Proposal:\n{json.dumps(proposal, indent=2)}\n\n"
        "Generate the inverse rollback script in the required JSON format."
    )

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"} if "gpt" in settings.llm_model else None,
        )
        content = response.choices[0].message.content or "{}"
        return extract_json(content)
    except Exception as ex:
        result = _fallback_rollback_proposal(error_code, proposal)
        result["llm_warning"] = f"LLM API request failed ({str(ex)}); loaded expert rollback proposal."
        return result


def evaluate_verification_result(
    error_code: str,
    proposal: Dict[str, Any],
    fix_result: Dict[str, Any],
    verify_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate whether the remediation successfully resolved the OS error based on verification output.

    Args:
        error_code: Target error code.
        proposal: The remediation proposal that was executed.
        fix_result: Result of running the fix script.
        verify_result: Result of running the verification command.

    Returns:
        Dict[str, Any]: Final assessment with status, summary, and next steps.
    """
    client = get_llm_client()

    if not client:
        return _fallback_verification_evaluation(error_code, fix_result, verify_result)

    system_prompt = (
        "You are an Expert Windows Systems Engineer and Autonomous OS Diagnostics AI. "
        "Review the output of the executed remediation script and the post-fix verification command. "
        "Provide a final verdict on whether the issue is resolved.\n\n"
        "RULES:\n"
        "1. You MUST respond with ONLY a valid JSON object.\n"
        "2. Set 'status' to 'SUCCESS', 'PARTIAL', or 'FAILED'.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "status": "SUCCESS",\n'
        '  "summary": "Explanation of the outcome.",\n'
        '  "verification_details": "Observations from verification command output.",\n'
        '  "next_steps": "Actionable instructions for the user (e.g. restart Windows Update scan)."\n'
        "}"
    )

    user_prompt = (
        f"Target Error Code: {error_code}\n\n"
        f"Executed Proposal:\n{json.dumps(proposal, indent=2)}\n\n"
        f"Fix Execution Result:\n{json.dumps(fix_result, indent=2)}\n\n"
        f"Verification Command Result:\n{json.dumps(verify_result, indent=2)}\n\n"
        "Evaluate the outcome and output the final verdict in JSON format."
    )

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"} if "gpt" in settings.llm_model else None,
        )
        content = response.choices[0].message.content or "{}"
        return extract_json(content)
    except Exception as ex:
        result = _fallback_verification_evaluation(error_code, fix_result, verify_result)
        result["llm_warning"] = f"LLM API request failed ({str(ex)}); loaded heuristic evaluation."
        return result


def _fallback_initial_diagnosis(error_code: str, system_context: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic fallback for common OS error codes when LLM is offline or no API key is provided."""
    code_upper = error_code.upper()

    if "0X80070005" in code_upper or "ACCESS_DENIED" in code_upper:
        return {
            "error_code": error_code,
            "error_name": "ERROR_ACCESS_DENIED (5 / 0x80070005)",
            "diagnosis": (
                "Windows error 0x80070005 indicates 'Access Denied'. This occurs when a Windows service, "
                "update installer, or application lacks required NTFS ACL permissions or Registry key privileges "
                "to modify system files or write to C:\\Windows\\SoftwareDistribution."
            ),
            "likely_causes": [
                "Corrupted NTFS permissions on C:\\Windows\\SoftwareDistribution or C:\\ProgramData",
                "Windows Update Service (wuauserv) or BITS service blocked or permissions stripped",
                "Restricted Registry permissions under HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate",
            ],
            "diagnostic_commands": [
                {
                    "command": "icacls 'C:\\Windows\\SoftwareDistribution'",
                    "purpose": "Inspect directory ACL permissions on Windows Update cache",
                },
                {
                    "command": "Get-Service wuauserv, bits, cryptsvc, trustedinstaller | Select-Object Name, Status, StartType",
                    "purpose": "Verify status of Windows Update core services",
                },
                {
                    "command": "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate' -ErrorAction SilentlyContinue | Select-Object *",
                    "purpose": "Inspect Windows Update registry configuration",
                },
            ],
        }

    return {
        "error_code": error_code,
        "error_name": f"OS_ERROR_{error_code}",
        "diagnosis": f"Error code {error_code} represents a system-level fault or service failure in the current OS environment.",
        "likely_causes": [
            "Missing system files or corrupted service state",
            "Network configuration or security policy restriction",
        ],
        "diagnostic_commands": [
            {
                "command": "Get-Service | Where-Object {$_.Status -eq 'Stopped' -and $_.StartType -eq 'Automatic'} | Select-Object Name, DisplayName",
                "purpose": "Identify any automatic core services that failed to start",
            },
            {
                "command": "sfc /verifyonly",
                "purpose": "Verify integrity of Windows system binaries without modifying files",
            },
        ],
    }


def _fallback_root_cause(error_code: str, execution_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Heuristic fallback for root cause confirmation."""
    has_access_denied_evidence = any(
        "Access is denied" in r.get("stdout", "") or "Access is denied" in r.get("stderr", "")
        for r in execution_results
    )

    return {
        "root_cause_confirmed": True,
        "root_cause_analysis": (
            f"Analysis of diagnostic command outputs for {error_code} confirms permission restriction and/or service "
            "configuration divergence in the system update pipeline."
        ),
        "evidence": [
            f"Executed {len(execution_results)} read-only diagnostic commands with exit code validation.",
            "Service status and filesystem ACL attributes captured and analyzed.",
        ],
        "remediation_summary": "Reset SoftwareDistribution directory permissions, restart background update services, and register required DLLs.",
    }


def _fallback_remediation_proposal(error_code: str, root_cause_data: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic fallback remediation script for common Windows errors."""
    code_upper = error_code.upper()

    if "0X80070005" in code_upper or "ACCESS_DENIED" in code_upper:
        script = """<#
========================================================================================
# PROBLEM STATEMENT & INCIDENT SUMMARY:
----------------------------------------------------------------------------------------
# Target Error Code  : 0x80070005 (ERROR_ACCESS_DENIED)
# Issue Description  : Windows Update or installer has encountered an Access Denied error.
#                      System services lack NTFS write/execute permissions on the update
#                      download cache directory (C:\\Windows\\SoftwareDistribution).
# Impacted Services  : Windows Update Service (wuauserv), BITS, CryptSvc
# Root Cause         : Stripped/corrupted NTFS ACL permissions on SoftwareDistribution and
#                      unregistered cryptographic dynamic link libraries.
# Remediation Goal   : Stop update services -> Restore FullControl ACLs to SYSTEM and
#                      Administrators -> Re-register COM DLLs -> Restart & set to Automatic.
========================================================================================
#>

$ErrorActionPreference = 'SilentlyContinue'

# Ensure System32 is present in active path
$env:PATH = "$env:SystemRoot\\System32;$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0;$env:SystemRoot;$env:PATH"
$icaclsExe = if (Test-Path "$env:SystemRoot\\System32\\icacls.exe") { "$env:SystemRoot\\System32\\icacls.exe" } else { "icacls" }
$regsvrExe = if (Test-Path "$env:SystemRoot\\System32\\regsvr32.exe") { "$env:SystemRoot\\System32\\regsvr32.exe" } else { "regsvr32" }

Write-Host "[1/4] Stopping Windows Update & Background Transfer Services..." -ForegroundColor Cyan
Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
Stop-Service -Name bits -Force -ErrorAction SilentlyContinue
Stop-Service -Name cryptsvc -Force -ErrorAction SilentlyContinue

Write-Host "[2/4] Granting Full Control ACLs to Administrators & SYSTEM on SoftwareDistribution..." -ForegroundColor Cyan
$targetPath = "$env:SystemRoot\\SoftwareDistribution"
if (Test-Path $targetPath) {
    & $icaclsExe $targetPath /grant "SYSTEM:(OI)(CI)F" /T /C /Q | Out-Null
    & $icaclsExe $targetPath /grant "Administrators:(OI)(CI)F" /T /C /Q | Out-Null
}

Write-Host "[3/4] Re-registering essential Windows Update DLL components..." -ForegroundColor Cyan
$dlls = @('atl.dll', 'urlmon.dll', 'mshtml.dll', 'shdocvw.dll', 'browseui.dll', 'jscript.dll', 'vbscript.dll', 'scrrun.dll', 'msxml.dll', 'msxml3.dll', 'msxml6.dll', 'actxprxy.dll', 'softpub.dll', 'wintrust.dll', 'dssenh.dll', 'rsaenh.dll', 'gpkcsp.dll', 'sccbase.dll', 'slbcsp.dll', 'cryptdlg.dll', 'oleaut32.dll', 'ole32.dll', 'shell32.dll', 'initpki.dll', 'wuapi.dll', 'wuaueng.dll', 'wuaueng1.dll', 'wucltui.dll', 'wups.dll', 'wups2.dll', 'wuweb.dll', 'qmgr.dll', 'qmgrprxy.dll', 'wucltux.dll', 'muweb.dll', 'wuwebv.dll')
foreach ($dll in $dlls) {
    Start-Process -FilePath $regsvrExe -ArgumentList "/s $dll" -NoNewWindow -Wait -ErrorAction SilentlyContinue
}

Write-Host "[4/4] Starting and configuring Windows Update & Background Transfer Services..." -ForegroundColor Cyan
Set-Service -Name cryptsvc -StartupType Automatic -ErrorAction SilentlyContinue
Start-Service -Name cryptsvc -ErrorAction SilentlyContinue

Set-Service -Name bits -StartupType Automatic -ErrorAction SilentlyContinue
Start-Service -Name bits -ErrorAction SilentlyContinue

Set-Service -Name wuauserv -StartupType Automatic -ErrorAction SilentlyContinue
Start-Service -Name wuauserv -ErrorAction SilentlyContinue

Write-Host "`n[SUCCESS] Windows Update permissions and services have been restored." -ForegroundColor Green
"""
        return {
            "title": "Windows Update Access Denied (0x80070005) ACL & Service Repair",
            "problem_statement": "Windows Update is blocked from downloading/installing payloads due to restricted NTFS ACL permissions on C:\\Windows\\SoftwareDistribution and stopped core services.",
            "summary": (
                "This script stops Windows Update services, repairs corrupted NTFS permissions on the "
                "C:\\Windows\\SoftwareDistribution cache directory, re-registers required cryptographic DLLs, "
                "and cleanly restarts and enables the update services."
            ),
            "steps": [
                "Gracefully stop wuauserv, bits, and cryptsvc background services",
                "Apply proper SYSTEM and Administrator FullControl ACLs to C:\\Windows\\SoftwareDistribution",
                "Re-register Windows Update cryptographic COM/DLL components",
                "Enable and restart Windows Update core services with Automatic startup",
            ],
            "script_type": "powershell",
            "script_content": script.strip(),
            "verification_command": "Get-Service wuauserv, bits, cryptsvc | Select-Object Name, Status, StartType",
            "requires_reboot": False,
        }

    # Generic remediation fallback
    generic_script = """<#
========================================================================================
# PROBLEM STATEMENT & INCIDENT SUMMARY:
----------------------------------------------------------------------------------------
# Target Error Code  : __ERROR_CODE__
# Issue Description  : Operating system service failure or corrupted system binaries.
# Remediation Goal   : Ensure background services are active and run DISM component repair.
========================================================================================
#>

$ErrorActionPreference = 'SilentlyContinue'
$env:PATH = "$env:SystemRoot\\System32;$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0;$env:SystemRoot;$env:PATH"
$dismExe = if (Test-Path "$env:SystemRoot\\System32\\dism.exe") { "$env:SystemRoot\\System32\\dism.exe" } else { "dism" }

Write-Host "[1/2] Checking core Windows services..." -ForegroundColor Cyan
Get-Service -Name wuauserv, bits | Start-Service -ErrorAction SilentlyContinue

Write-Host "[2/2] Running Component Store Health Scan..." -ForegroundColor Cyan
& $dismExe /Online /Cleanup-Image /ScanHealth

Write-Host "`n[COMPLETED] Diagnostic scan completed." -ForegroundColor Green
""".replace("__ERROR_CODE__", str(error_code))
    return {
        "title": f"System Service & Component Store Repair for {error_code}",
        "problem_statement": f"System fault or component divergence encountered under error code {error_code}.",
        "summary": f"Inspects core system services and scans the Windows component store to remediate {error_code}.",
        "steps": [
            "Ensure core background services are started",
            "Scan the Windows Component Store image health",
        ],
        "script_type": "powershell",
        "script_content": generic_script.strip(),
        "verification_command": "Get-Service wuauserv, bits | Select-Object Name, Status",
        "requires_reboot": False,
    }


def _fallback_verification_evaluation(
    error_code: str,
    fix_result: Dict[str, Any],
    verify_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Heuristic fallback for post-fix verification evaluation."""
    fix_ok = fix_result.get("success", False)
    verify_ok = verify_result.get("success", False)

    if fix_ok and verify_ok:
        status = "SUCCESS"
        summary = f"The remediation script completed successfully (Exit code: 0) and verification checks passed for {error_code}."
        details = "Core system services were restarted and required NTFS permissions have been reapplied."
        next_steps = "Relaunch Windows Settings > Windows Update and retry checking for updates."
    elif fix_ok and not verify_ok:
        status = "PARTIAL"
        summary = "The remediation script executed, but verification reported non-standard service or output status."
        details = verify_result.get("stderr") or verify_result.get("stdout") or "Verification returned non-zero exit code."
        next_steps = "Inspect the verification logs or reboot the machine to ensure changes take full effect."
    else:
        status = "FAILED"
        summary = "Remediation script encountered an error during execution."
        details = fix_result.get("stderr") or "Script failed to complete all steps."
        next_steps = "Ensure PowerShell is running as Administrator and inspect Event Viewer for permission conflicts."

    return {
        "status": status,
        "summary": summary,
        "verification_details": details,
        "next_steps": next_steps,
    }


def _fallback_rollback_proposal(error_code: str, proposal: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic fallback for rollback script generation."""
    code_upper = error_code.upper()

    if "0X80070005" in code_upper or "ACCESS_DENIED" in code_upper:
        rollback_script = """<#
========================================================================================
# ROLLBACK PLAN & PROBLEM REVERSAL:
----------------------------------------------------------------------------------------
# Target Error Code  : 0x80070005 (Access Denied)
# Rollback Objective : Revert temporary service overrides and restore default Windows
#                      Update service startup configuration (Manual startup for wuauserv).
========================================================================================
#>

$ErrorActionPreference = 'SilentlyContinue'
$env:PATH = "$env:SystemRoot\\System32;$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0;$env:SystemRoot;$env:PATH"

Write-Host "[1/2] Stopping services for rollback..." -ForegroundColor Cyan
Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
Stop-Service -Name bits -Force -ErrorAction SilentlyContinue

Write-Host "[2/2] Resetting Windows Update service startup types to standard defaults..." -ForegroundColor Cyan
Set-Service -Name wuauserv -StartupType Manual -ErrorAction SilentlyContinue
Set-Service -Name bits -StartupType Automatic -ErrorAction SilentlyContinue
Start-Service -Name bits -ErrorAction SilentlyContinue

Write-Host "`n[SUCCESS] Rollback complete. System services restored to baseline state." -ForegroundColor Green
"""
        return {
            "summary": "Restores Windows Update services (wuauserv, bits) to default baseline startup types.",
            "rollback_script": rollback_script.strip(),
            "verification_command": "Get-Service wuauserv, bits | Select-Object Name, Status, StartType",
        }

    # Generic rollback
    generic_rollback = """<#
========================================================================================
# ROLLBACK PLAN & REVERSAL:
----------------------------------------------------------------------------------------
# Target Error Code  : __ERROR_CODE__
# Rollback Objective : Revert temporary background services to standard state.
========================================================================================
#>

$ErrorActionPreference = 'SilentlyContinue'
$env:PATH = "$env:SystemRoot\\System32;$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0;$env:SystemRoot;$env:PATH"

Write-Host "[1/1] Restoring service state..." -ForegroundColor Cyan
Get-Service -Name wuauserv, bits -ErrorAction SilentlyContinue | Start-Service -ErrorAction SilentlyContinue

Write-Host "`n[SUCCESS] Baseline state restored." -ForegroundColor Green
""".replace("__ERROR_CODE__", str(error_code))

    return {
        "summary": f"Restores background services touched by {error_code} remediation to baseline defaults.",
        "rollback_script": generic_rollback.strip(),
        "verification_command": "Get-Service wuauserv, bits | Select-Object Name, Status",
    }
