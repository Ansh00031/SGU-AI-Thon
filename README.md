<div align="center">

# ⚡ Autonomous OS Debugging Agent

**An AI-powered Tier-3 Systems Engineer CLI for autonomous OS error diagnostics, remediation, and zero-risk rollback.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CLI](https://img.shields.io/badge/CLI-Typer%20%7C%20Rich-green.svg)](https://typer.tiangolo.com/)
[![LLM Backend](https://img.shields.io/badge/LLM-OpenAI%20%7C%20Ollama%20%7C%20vLLM-purple.svg)](https://platform.openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg)]()

</div>

---

## 📌 Overview

Troubleshooting cryptic OS error codes (such as Windows Update `0x80070005` or `0x80240020`) usually involves hours of searching through forums, interpreting raw event logs, and running risky scripts blindly.

The **Autonomous OS Debugging Agent** is a local Python CLI tool that automates this entire lifecycle. It ingests OS error codes, gathers live system context & event logs, executes safe read-only diagnostic probes to confirm the root cause, synthesizes production-grade remediation scripts, and executes fixes with **strict human-in-the-loop approval** and **instant rollback capability**.

---

## ✨ Key Features

- 🔍 **Live Event Log Ingestion**: Extracts recent critical and error events from Windows Event Viewer (`System`, `Application`, `WindowsUpdateClient`) in real-time.
- 🧠 **Multi-Stage AI Reasoning Loop**:
  1. *Hypothesis Formulation*: Analyzes error code and system telemetry.
  2. *Read-Only Diagnostic Probes*: Generates and executes safe diagnostic commands (e.g., `icacls`, `Get-Service`, `Get-ItemProperty`).
  3. *Root Cause Confirmation*: Ingests command output evidence to confirm the exact failure point.
- 🛡️ **Security Guard & Blacklist Filter**: Automatically blocks destructive commands (`del`, `format`, `Remove-Item`, `reg delete`) during diagnostic phases.
- 👨‍💻 **Human-in-the-Loop Approval**: Renders proposed PowerShell fixes in the terminal with full syntax highlighting (`Monokai` theme) before requesting explicit user consent (`[y/N]`).
- ⚡ **Isolated Execution & Auto-Cleanup**: Executes approved fixes via temporary script files with guaranteed lifecycle cleanup.
- 🔄 **Pre-Fix Snapshot & One-Click Rollback**: Automatically captures system state prior to remediation, allowing users to revert any change via `python agent.py rollback`.
- 🌐 **Model Agnostic**: Works seamlessly with cloud providers (OpenAI GPT-4o) or 100% private local LLMs via **Ollama** (`llama3.1`, `mistral`, `deepseek-coder`).

---

## 🏗️ Architecture & Pipeline Flow

```
                                [ Target Error Code ]
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │  Step 1: Privilege & Config Validation│
                      └──────────────────┬────────────────────┘
                                         │
                                         ▼
                      ┌───────────────────────────────────────┐
                      │  Step 2: OS & Event Log Ingestion     │
                      │  (Windows Event Viewer / Metadata)    │
                      └──────────────────┬────────────────────┘
                                         │
                                         ▼
                      ┌───────────────────────────────────────┐
                      │  Step 3: AI Diagnostic Engine         │
                      │  - Formulate Diagnostic Hypothesis    │
                      │  - Run Safe Read-Only System Probes   │
                      │  - Confirm Evidence & Root Cause      │
                      └──────────────────┬────────────────────┘
                                         │
                                         ▼
                      ┌───────────────────────────────────────┐
                      │  Step 4: Fix Proposal & Approval Gate │
                      │  - Generate PowerShell Fix Script     │
                      │  - Syntax-Highlighted Terminal View   │
                      │  - Strict [Y/n] Confirmation Prompt   │
                      └──────────────────┬────────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                     (User 'n')                        (User 'y')
                        │                                 │
                        ▼                                 ▼
                 [ Abort Safely ]            [ Create Snapshot (.backups/) ]
                                                          │
                                                          ▼
                                             ┌────────────────────────────┐
                                             │ Step 5: Execute & Verify   │
                                             │ - Run Fix via Temp Subproc │
                                             │ - Execute Verification Cmd │
                                             │ - AI Post-Fix Health Check │
                                             │ - Guarantee Temp Cleanup   │
                                             └────────────┬───────────────┘
                                                          │
                                                          ▼
                                             [ Revert Anytime via Rollback ]
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+** installed
- **PowerShell** (Windows) or **Bash** (Linux/macOS)
- *(Optional)* Windows Administrator privileges for executing system-level fixes

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-username/os-debug-agent.git
cd os-debug-agent
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment file and configure your LLM settings:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# For OpenAI Cloud:
OPENAI_API_KEY=sk-your-openai-key-here
LLM_MODEL=gpt-4o

# OR for Local Offline Ollama:
# OPENAI_BASE_URL=http://localhost:11434/v1
# LLM_MODEL=llama3.1
```

> **Note:** The agent includes built-in expert heuristics and will function reliably for common system errors even if no external API key is provided!

---

## 💻 CLI Usage Guide

### 1. Diagnose an OS Error Code

Run full autonomous diagnostic and remediation pipeline:

```powershell
# Elevated mode (Administrator recommended):
python agent.py diagnose 0x80070005

# Dry-run / standard user mode (bypasses admin requirement):
python agent.py diagnose 0x80070005 --skip-admin-check
```

#### CLI Options:
| Flag | Short | Description |
|------|-------|-------------|
| `--max-events` | `-n` | Number of Event Viewer error logs to ingest (Default: 50) |
| `--skip-admin-check` | `-s` | Bypass administrative privilege requirement for dry-run |
| `--export-context` | `-e` | Export gathered system JSON payload to a file |
| `--print-json` | `-j` | Print raw collected JSON context payload to terminal |

---

### 2. View Remediation History & Snapshots

View all past debugging and fix sessions:

```powershell
python agent.py history
```

---

### 3. Rollback / Revert a Fix

Revert system changes from any past session:

```powershell
# Interactive rollback (defaults to latest session):
python agent.py rollback --skip-admin-check

# Rollback a specific session ID:
python agent.py rollback session_20260817_195408_80070005 --skip-admin-check
```

---

### 4. Check Environment & Security Status

```powershell
python agent.py check-env
```

---

## 📂 Project Structure

```
os-debug-agent/
├── agent.py               # Main CLI entrypoint (Typer app)
├── requirements.txt       # Python dependencies (typer, rich, openai, pydantic)
├── .env.example           # Environment template
├── .env                   # Local configuration
├── .backups/              # Session snapshot and rollback storage
└── core/
    ├── __init__.py
    ├── config.py          # Environment settings loader
    ├── security.py        # Administrator/Root privilege verification
    ├── system_paths.py    # Cross-platform executable and PATH resolver
    ├── collector.py       # OS metadata and Event Viewer log extractor
    ├── executor.py        # Secure read-only command runner with safety filters
    ├── remediation.py     # Subprocess script runner with auto-cleanup
    ├── snapshot.py        # Pre-fix snapshot and rollback engine
    ├── llm.py             # Multi-stage AI prompt engineering & reasoning engine
    └── ui.py              # Rich UI formatting, banners, tables, and spinners
```

---

## 🔒 Security Model & Safety Safeguards

1. **Privilege Enforcement**: Proactively warns and restricts execution if non-elevated.
2. **Command Blacklist**: Diagnostic probes are scanned against regex filters to prevent destructive actions (`del`, `format`, `Remove-Item`, `reg delete`, `shutdown`).
3. **Strict Human Gate**: Fix scripts are displayed in syntax-highlighted code boxes and require affirmative user confirmation (`[y/N]`).
4. **Temporary Sandbox Cleanup**: Scripts are written to temporary files and guaranteed to be unlinked in `finally:` blocks.
5. **Deterministic Rollback**: Every applied fix produces an inverse rollback script and session record before any modification occurs.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
#   S G U - A I - T h o n  
 