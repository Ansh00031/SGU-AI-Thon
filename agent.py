"""Autonomous OS Debugging Agent CLI Entry Point.

Usage:
    python agent.py diagnose 0x80070005
    python agent.py diagnose 0x80070005 --skip-admin-check
    python agent.py history
    python agent.py rollback session_20260817_...
    python agent.py resume session_20260817_...
"""

import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Auto-install dependencies if launched in a fresh environment
try:
    import typer
    from rich.panel import Panel
    from rich.prompt import Confirm
    from rich.syntax import Syntax
    from rich.table import Table
except ImportError:
    print("[*] First-time setup: Installing required CLI packages (typer, rich, pydantic)...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "typer", "rich", "pydantic", "--disable-pip-version-check"]
        )
    except Exception:
        # Fallback with --user if global permissions are restricted
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "typer", "rich", "pydantic", "--user", "--disable-pip-version-check"]
        )
    import typer
    from rich.panel import Panel
    from rich.prompt import Confirm
    from rich.syntax import Syntax
    from rich.table import Table

from core.autostart import (
    disable_autostart as disable_autostart_func,
    enable_autostart as enable_autostart_func,
    is_autostart_enabled,
    read_startup_log,
)
from core.collector import gather_system_context
from core.config import settings
from core.executor import execute_diagnostic_command
from core.llm import (
    confirm_root_cause,
    evaluate_verification_result,
    generate_initial_diagnosis,
    generate_remediation_proposal,
    generate_rollback_proposal,
)
from core.reboot_manager import (
    get_resume_state,
    is_reboot_pending,
    register_reboot_hook,
    unregister_reboot_hook,
)
from core.remediation import execute_remediation_script
from core.security import get_elevation_details, is_admin
from core.snapshot import (
    create_pre_fix_snapshot,
    generate_session_id,
    get_session,
    list_sessions,
    update_session_status,
)
from core.ui import (
    console,
    print_banner,
    print_command_execution,
    print_context_summary,
    print_diagnostic_commands,
    print_final_report,
    print_fix_execution,
    print_fix_proposal,
    print_initial_diagnosis,
    print_reboot_notice,
    print_resume_header,
    print_rollback_proposal,
    print_root_cause_analysis,
    print_active_and_solved_issues,
    print_sessions_history,
    print_status_summary,
)

app = typer.Typer(
    name="os-debug-agent",
    help="Autonomous OS Debugging Agent: AI-powered diagnostic, repair, and rollback CLI for system errors.",
    add_completion=False,
    no_args_is_help=True,
)


@app.command(name="diagnose")
def diagnose(
    error_code: str = typer.Argument(
        ...,
        help="The OS error code or error string to investigate (e.g., '0x80070005', '0x80240020').",
    ),
    max_events: int = typer.Option(
        50,
        "--max-events",
        "-n",
        help="Maximum number of critical/error event log entries to collect.",
    ),
    skip_admin_check: bool = typer.Option(
        False,
        "--skip-admin-check",
        "-s",
        help="Bypass Administrator / Root privilege enforcement for dry-run or testing.",
    ),
    export_context: Optional[str] = typer.Option(
        None,
        "--export-context",
        "-e",
        help="Path to export the gathered JSON context payload.",
    ),
    print_json: bool = typer.Option(
        False,
        "--print-json",
        "-j",
        help="Print the raw collected JSON context payload to terminal.",
    ),
) -> None:
    """Run autonomous multi-step diagnostic, remediation, and snapshot pipeline."""
    print_banner()

    is_elevated, elevation_guidance = get_elevation_details()
    os_detail = f"{platform.system()} {platform.release()} ({platform.machine()})"
    is_valid_llm, llm_msg = settings.validate_llm_config()
    session_id = generate_session_id(error_code)

    # Step 1: Privilege Verification Check
    if not is_elevated and not skip_admin_check:
        console.print(
            Panel(
                f"[bold red]Elevation Required[/bold red]\n\n"
                f"{elevation_guidance}\n\n"
                f"[dim]Tip: Use '--skip-admin-check' if you want to test in dry-run mode without elevation.[/dim]",
                title="[bold yellow]Privilege Warning[/bold yellow]",
                border_style="yellow",
            )
        )
        should_continue = Confirm.ask(
            "[yellow]Do you want to continue in restricted dry-run mode anyway?[/yellow]",
            default=False,
        )
        if not should_continue:
            console.print("[red]Aborted. Please relaunch with administrative privileges.[/red]")
            raise typer.Exit(code=1)
        console.print("[dim]Continuing with '--skip-admin-check' enabled...[/dim]\n")

    # Display session parameters
    llm_display = f"[green]{llm_msg}[/green]" if is_valid_llm else f"[yellow]{llm_msg}[/yellow]"
    print_status_summary(
        error_code=error_code,
        is_elevated=is_elevated or skip_admin_check,
        llm_status=llm_display,
        os_info=os_detail,
    )
    console.print(f"[dim]Session ID: [cyan]{session_id}[/cyan][/dim]\n")

    # Step 2: Log Ingestion & Context Gathering
    with console.status(
        f"[bold cyan]Gathering OS metadata & querying Windows Event Viewer for '{error_code}'...[/bold cyan]",
        spinner="dots",
    ) as status:
        context = gather_system_context(error_code=error_code, max_events=max_events)
        status.update("[bold green]System context & event logs successfully extracted![/bold green]")

    # Display rich summary tables
    print_context_summary(context)

    # Export / Print JSON if requested
    if export_context:
        out_path = Path(export_context)
        out_path.write_text(json.dumps(context, indent=2), encoding="utf-8")
        console.print(f"[bold green]Saved context payload to:[/bold green] [cyan]{out_path.resolve()}[/cyan]\n")

    if print_json:
        json_str = json.dumps(context, indent=2)
        console.print(Panel(Syntax(json_str, "json", theme="monokai", word_wrap=True), title="AI Ingestion Payload"))

    # Step 3: AI Diagnostic Engine (Reasoning Loop)
    with console.status(
        "[bold cyan]AI Reasoning: Analyzing error context & formulating diagnostic hypothesis...[/bold cyan]",
        spinner="dots",
    ) as status:
        initial_diag = generate_initial_diagnosis(error_code=error_code, system_context=context)
        status.update("[bold green]Hypothesis formulated and diagnostic commands prepared![/bold green]")

    # Display initial AI diagnosis and proposed commands
    print_initial_diagnosis(initial_diag)
    diag_commands = initial_diag.get("diagnostic_commands", [])
    print_diagnostic_commands(diag_commands)

    # Execute read-only diagnostic commands securely
    console.print("[bold cyan]Executing read-only diagnostic commands to verify system state...[/bold cyan]\n")
    exec_results = []
    total_cmds = len(diag_commands)

    for i, cmd_spec in enumerate(diag_commands, 1):
        cmd_str = cmd_spec.get("command", "") if isinstance(cmd_spec, dict) else str(cmd_spec)
        purpose = cmd_spec.get("purpose", "Diagnostic check") if isinstance(cmd_spec, dict) else "Diagnostic check"
        with console.status(f"[bold cyan][{i}/{total_cmds}] Running: {purpose}...[/bold cyan]", spinner="dots"):
            res = execute_diagnostic_command(cmd_str)
            res["purpose"] = purpose
            exec_results.append(res)
        print_command_execution(res, index=i, total=total_cmds)

    # Feed outputs back into LLM to confirm root cause
    with console.status(
        "[bold cyan]AI Reasoning: Ingesting command outputs to confirm exact root cause...[/bold cyan]",
        spinner="dots",
    ) as status:
        root_cause_data = confirm_root_cause(
            error_code=error_code,
            initial_diagnosis=initial_diag,
            execution_results=exec_results,
        )
        status.update("[bold green]Root cause confirmed![/bold green]")

    print_root_cause_analysis(root_cause_data)

    # Step 4: Fix Proposal & Human-in-the-Loop
    with console.status(
        "[bold cyan]AI Reasoning: Synthesizing targeted remediation script...[/bold cyan]",
        spinner="dots",
    ) as status:
        fix_proposal = generate_remediation_proposal(
            error_code=error_code,
            root_cause_data=root_cause_data,
            system_context=context,
        )
        rollback_proposal = generate_rollback_proposal(
            error_code=error_code,
            proposal=fix_proposal,
        )
        status.update("[bold green]Remediation and rollback plans generated![/bold green]")

    # Display proposed fix with Rich syntax highlighting
    print_fix_proposal(fix_proposal)

    # Strict Human-in-the-Loop Confirmation Prompt
    should_execute = Confirm.ask(
        "[bold yellow]Do you want to execute this fix? (This requires Administrator privileges)[/bold yellow]",
        default=False,
    )

    if not should_execute:
        console.print(
            Panel(
                "[yellow]Fix execution declined by user.[/yellow]\n"
                "No system changes or scripts were executed.\n"
                "You can inspect the generated script above or copy it manually.",
                title="[bold yellow]Remediation Aborted[/bold yellow]",
                border_style="yellow",
            )
        )
        raise typer.Exit(code=0)

    # Pre-fix Snapshot & Backup Creation
    with console.status(
        "[bold cyan]Creating pre-fix system snapshot and rollback point...[/bold cyan]",
        spinner="dots",
    ) as status:
        snapshot_dir = create_pre_fix_snapshot(
            session_id=session_id,
            error_code=error_code,
            proposal=fix_proposal,
            rollback_script=rollback_proposal.get("rollback_script", ""),
            system_context=context,
        )
        status.update(f"[bold green]Snapshot created at {snapshot_dir.name}![/bold green]")

    console.print(
        f"[dim]Snapshot saved to: [cyan]{snapshot_dir}[/cyan] (Rollback available via: [bold]python agent.py rollback {session_id}[/bold])[/dim]\n"
    )

    # Step 5: Execution & Verification
    script_content = fix_proposal.get("script_content", "")
    script_type = fix_proposal.get("script_type", "powershell")
    verify_cmd = fix_proposal.get("verification_command", "Get-Service wuauserv, bits | Select-Object Name, Status")

    with console.status(
        "[bold cyan]Executing remediation script in secure isolated environment...[/bold cyan]",
        spinner="dots",
    ) as status:
        fix_result = execute_remediation_script(
            script_content=script_content,
            script_type=script_type,
        )
        status.update("[bold green]Remediation execution finished![/bold green]")

    # Display execution details
    print_fix_execution(fix_result)

    # Final Verification Step
    console.print(f"[bold cyan]Running verification check:[/bold cyan] [yellow]{verify_cmd}[/yellow]\n")
    with console.status("[bold cyan]Executing post-fix verification command...[/bold cyan]", spinner="dots") as status:
        verify_result = execute_diagnostic_command(verify_cmd)
        verify_result["purpose"] = "Post-remediation verification"
        status.update("[bold green]Verification check complete![/bold green]")

    print_command_execution(verify_result, index=1, total=1)

    # AI Verification Outcome Analysis
    with console.status(
        "[bold cyan]AI Reasoning: Evaluating verification output for final resolution report...[/bold cyan]",
        spinner="dots",
    ) as status:
        final_report_data = evaluate_verification_result(
            error_code=error_code,
            proposal=fix_proposal,
            fix_result=fix_result,
            verify_result=verify_result,
        )
        status.update("[bold green]Final report synthesized![/bold green]")

    # Update session status
    update_session_status(session_id, final_report_data.get("status", "COMPLETED"))

    print_final_report(final_report_data)

    # Check if a reboot is required or pending
    reboot_needed = fix_proposal.get("requires_reboot", False) or is_reboot_pending()
    if reboot_needed:
        enable_hook = Confirm.ask(
            "[bold yellow]A system restart is recommended for full activation. Enable automatic post-reboot verification?[/bold yellow]",
            default=True,
        )
        if enable_hook:
            success, msg = register_reboot_hook(session_id, verify_cmd)
            print_reboot_notice(session_id, is_registered=success)


@app.command(name="resume")
def resume(
    session_id: str = typer.Argument(
        ...,
        help="The session ID to resume and verify post-reboot.",
    ),
    skip_admin_check: bool = typer.Option(
        False,
        "--skip-admin-check",
        "-s",
        help="Bypass Administrator / Root privilege enforcement for dry-run or testing.",
    ),
) -> None:
    """Resume an existing session post-reboot, execute verification, and finalize status."""
    print_banner()
    print_resume_header(session_id)

    # Cleanup RunOnce registry hook so it only fires once
    unregister_reboot_hook()

    session_data = get_session(session_id)
    if not session_data:
        console.print(f"[red]Error: Session '{session_id}' could not be located.[/red]")
        raise typer.Exit(code=1)

    verify_cmd = session_data.get("verification_command") or "Get-Service wuauserv, bits | Select-Object Name, Status"
    error_code = session_data.get("error_code", "OS_ERROR")

    console.print(f"[bold cyan]Executing post-reboot verification check:[/bold cyan] [yellow]{verify_cmd}[/yellow]\n")
    with console.status("[bold cyan]Running verification check...[/bold cyan]", spinner="dots") as status:
        verify_result = execute_diagnostic_command(verify_cmd)
        verify_result["purpose"] = "Post-reboot verification check"
        status.update("[bold green]Verification completed![/bold green]")

    print_command_execution(verify_result, index=1, total=1)

    # Re-evaluate with AI
    with console.status("[bold cyan]AI Reasoning: Evaluating post-reboot health status...[/bold cyan]", spinner="dots") as status:
        final_report = evaluate_verification_result(
            error_code=error_code,
            proposal=session_data,
            fix_result={"success": True, "exit_code": 0, "stdout": "Completed prior to reboot"},
            verify_result=verify_result,
        )
        status.update("[bold green]Post-reboot report ready![/bold green]")

    update_session_status(session_id, status="VERIFIED_POST_REBOOT")
    print_final_report(final_report)


@app.command(name="history")
def history() -> None:
    """View past diagnostic and remediation sessions with snapshot history."""
    print_banner()
    sessions = list_sessions()
    print_sessions_history(sessions)


@app.command(name="rollback")
def rollback(
    session_id: Optional[str] = typer.Argument(
        None,
        help="Session ID to rollback (e.g. 'session_20260817_195500_80070005'). If omitted, shows interactive list.",
    ),
    skip_admin_check: bool = typer.Option(
        False,
        "--skip-admin-check",
        "-s",
        help="Bypass Administrator / Root privilege check for testing.",
    ),
) -> None:
    """Revert changes from a previous remediation session using its stored snapshot."""
    print_banner()

    is_elevated, elevation_guidance = get_elevation_details()
    if not is_elevated and not skip_admin_check:
        console.print(
            Panel(
                f"[bold red]Elevation Required[/bold red]\n\n{elevation_guidance}",
                title="[bold yellow]Privilege Warning[/bold yellow]",
                border_style="yellow",
            )
        )
        should_continue = Confirm.ask(
            "[yellow]Do you want to continue in restricted dry-run mode anyway?[/yellow]",
            default=False,
        )
        if not should_continue:
            raise typer.Exit(code=1)

    sessions = list_sessions()
    if not sessions:
        console.print("[yellow]No historical remediation sessions found to rollback.[/yellow]")
        raise typer.Exit(code=0)

    if not session_id:
        print_sessions_history(sessions)
        target_session = sessions[0]  # default to newest
        session_id = target_session["session_id"]
        use_newest = Confirm.ask(
            f"[yellow]Rollback most recent session ([bold cyan]{session_id}[/bold cyan])?[/yellow]",
            default=True,
        )
        if not use_newest:
            console.print("[dim]Please specify session ID: 'python agent.py rollback <session_id>'[/dim]")
            raise typer.Exit(code=0)

    session_data = get_session(session_id)
    if not session_data:
        console.print(f"[red]Error: Session '{session_id}' not found.[/red]")
        raise typer.Exit(code=1)

    rollback_script_path = Path(session_data["rollback_script_path"])
    if not rollback_script_path.exists():
        console.print(f"[red]Error: Rollback script missing for session '{session_id}'.[/red]")
        raise typer.Exit(code=1)

    rollback_script = rollback_script_path.read_text(encoding="utf-8")
    print_rollback_proposal(session_data, rollback_script)

    confirm_rollback = Confirm.ask(
        "[bold red]Execute rollback script now to revert system changes?[/bold red]",
        default=False,
    )
    if not confirm_rollback:
        console.print("[yellow]Rollback aborted by user. No changes made.[/yellow]")
        raise typer.Exit(code=0)

    with console.status("[bold magenta]Executing rollback script...[/bold magenta]", spinner="dots") as status:
        res = execute_remediation_script(rollback_script, script_type="powershell")
        status.update("[bold green]Rollback execution finished![/bold green]")

    print_fix_execution(res)

    # Verification
    verify_cmd = session_data.get("verification_command") or "Get-Service wuauserv, bits | Select-Object Name, Status"
    with console.status("[bold cyan]Verifying system state post-rollback...[/bold cyan]", spinner="dots") as status:
        v_res = execute_diagnostic_command(verify_cmd)
        v_res["purpose"] = "Post-rollback verification"
        status.update("[bold green]Verification completed![/bold green]")

    print_command_execution(v_res, index=1, total=1)
    update_session_status(session_id, status="ROLLED_BACK", rollback_executed=True)

    console.print(
        Panel(
            f"[bold green]Session '{session_id}' has been successfully rolled back.[/bold green]\n"
            "System configuration restored to baseline state.",
            title="[bold green]Rollback Complete[/bold green]",
            border_style="green",
        )
    )


@app.command(name="enable-autostart")
def enable_autostart_cmd() -> None:
    """Register the agent to automatically launch and monitor system health on PC startup."""
    print_banner()
    success, msg = enable_autostart_func()
    if success:
        console.print(
            Panel(
                f"[bold green]Auto-Start Successfully Configured[/bold green]\n\n"
                f"{msg}\n\n"
                "[dim]The agent will automatically check system health whenever you start or restart Windows.[/dim]",
                title="[bold green]Auto-Start Active[/bold green]",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]Failed to Enable Auto-Start[/bold red]\n\n{msg}",
                title="[bold red]Configuration Error[/bold red]",
                border_style="red",
            )
        )


@app.command(name="disable-autostart")
def disable_autostart_cmd() -> None:
    """Remove automatic startup launchers and registry entries."""
    print_banner()
    success, msg = disable_autostart_func()
    console.print(
        Panel(
            f"[yellow]{msg}[/yellow]",
            title="[bold yellow]Auto-Start Disabled[/bold yellow]",
            border_style="yellow",
        )
    )


@app.command(name="startup-log")
def startup_log_cmd() -> None:
    """View the execution history log of automatic startup health checks."""
    print_banner()
    log_content = read_startup_log()
    console.print(
        Panel(
            log_content.strip(),
            title="[bold cyan]Startup Health Check Execution Log[/bold cyan]",
            border_style="cyan",
        )
    )


@app.command(name="startup-monitor")
def startup_monitor_cmd() -> None:
    """Run startup health monitoring, clearly separating currently active problems from solved issues."""
    print_banner()

    # Query all historical sessions
    sessions = list_sessions()
    solved_issues = []
    active_issues = []

    for s in sessions:
        st = str(s.get("status", "")).upper()
        if any(k in st for k in ["COMPLETED", "SUCCESS", "VERIFIED"]) and not s.get("rollback_executed", False):
            solved_issues.append(s)
        elif any(k in st for k in ["FAILED", "PARTIAL", "AWAITING_REBOOT"]):
            active_issues.append({
                "error_code": s.get("error_code", "PENDING_FIX"),
                "description": s.get("summary") or "Remediation was interrupted or requires post-reboot verification.",
                "recommended_action": f"Run 'python agent.py resume {s.get('session_id')}' or 'python agent.py diagnose {s.get('error_code')}'",
            })

    # Check live services state
    verify_cmd = "Get-Service wuauserv, bits, cryptsvc -ErrorAction SilentlyContinue | Select-Object Name, Status, StartType"
    verify_res = execute_diagnostic_command(verify_cmd)
    live_output = verify_res.get("stdout", "")

    # Display clean Active vs Solved Panel
    print_active_and_solved_issues(active_issues, solved_issues, live_services=live_output)

    # Print general system environment table
    is_elevated, elevation_guidance = get_elevation_details()
    is_valid_llm, llm_msg = settings.validate_llm_config()
    autostart_on, autostart_details = is_autostart_enabled()

    from rich.table import Table
    table = Table(title="System Environment & Auto-Run Status", border_style="cyan")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row(
        "Privileges",
        "[bold green]PASS[/bold green]" if is_elevated else "[bold yellow]STANDARD USER[/bold yellow]",
        "Administrator / Elevated" if is_elevated else "Dry-Run Mode Enabled",
    )
    table.add_row(
        "LLM Engine",
        "[bold green]ACTIVE (Cloud)[/bold green]" if is_valid_llm else "[bold green]ACTIVE (Built-in Heuristics / Local)[/bold green]",
        llm_msg.split("\n")[0],
    )
    table.add_row(
        "OS Platform",
        "[bold green]ONLINE[/bold green]",
        f"{platform.system()} {platform.release()} ({platform.machine()})",
    )
    table.add_row(
        "Reboot Status",
        "[bold yellow]RESTART PENDING[/bold yellow]" if is_reboot_pending() else "[green]NORMAL (No reboot pending)[/green]",
        "Windows Update / Servicing state",
    )
    table.add_row(
        "Startup Auto-Run",
        "[bold green]ACTIVE[/bold green]" if autostart_on else "[dim]DISABLED[/dim]",
        autostart_details,
    )

    console.print(table)


@app.command(name="check-env")
def check_env() -> None:
    """Verify environment configuration, LLM keys, and system permissions."""
    print_banner()
    is_elevated, elevation_guidance = get_elevation_details()
    is_valid_llm, llm_msg = settings.validate_llm_config()
    autostart_on, autostart_details = is_autostart_enabled()

    from rich.table import Table
    table = Table(title="Environment & Security Status", border_style="cyan")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row(
        "Privileges",
        "[bold green]PASS[/bold green]" if is_elevated else "[bold red]FAIL[/bold red]",
        "Administrator / Root" if is_elevated else elevation_guidance.split("\n")[0],
    )
    table.add_row(
        "LLM Config",
        "[bold green]PASS[/bold green]" if is_valid_llm else "[bold yellow]WARN[/bold yellow]",
        llm_msg.split("\n")[0],
    )
    table.add_row(
        "OS Platform",
        "[bold green]DETECTED[/bold green]",
        f"{platform.system()} {platform.release()} ({platform.machine()})",
    )
    table.add_row(
        "Reboot Pending",
        "[bold yellow]YES (Restart Required)[/bold yellow]" if is_reboot_pending() else "[green]NO[/green]",
        "Windows Update / CBS servicing status",
    )
    table.add_row(
        "Startup Auto-Run",
        "[bold green]ENABLED[/bold green]" if autostart_on else "[dim]DISABLED[/dim]",
        autostart_details,
    )

    console.print(table)


if __name__ == "__main__":
    app()
