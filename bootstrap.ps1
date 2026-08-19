<#
========================================================================================
AUTONOMOUS OS DEBUGGING AGENT - 1-LINE CLOUD BOOTSTRAPPER & RECOVERY RUNNER
========================================================================================
Usage in WinRE / PowerShell / Command Prompt:
    irm https://raw.githubusercontent.com/<YOUR_GITHUB_USERNAME>/os-debug-agent/main/bootstrap.ps1 | iex

Or in CMD / WinRE Command Prompt:
    powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/<YOUR_GITHUB_USERNAME>/os-debug-agent/main/bootstrap.ps1 | iex"
========================================================================================
#>

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ErrorActionPreference = 'SilentlyContinue'

Write-Host @"
===============================================================================
       ⚡ AUTONOMOUS OS DEBUGGING AGENT - CLOUD RESCUE INSTALLER ⚡
===============================================================================
[+] Initializing live cloud recovery environment...
"@ -ForegroundColor Cyan

# 1. Determine Working Directory
$targetDir = if ($env:TEMP) { "$env:TEMP\os-debug-agent" } else { "C:\os-debug-agent" }
if (!(Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}
Set-Location $targetDir
Write-Host "[1/4] Recovery workspace set to: $targetDir" -ForegroundColor Green

# 2. Check for Python on the machine or in internal drives (C:, D:, etc.)
Write-Host "[2/4] Searching for Python runtime across system drives..." -ForegroundColor Cyan
$pythonExe = $null

# Check current PATH
$sysPython = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if ($sysPython) {
    $pythonExe = $sysPython
}

# Scan offline drives if inside WinRE (where boot drive is C: or D:)
if (-not $pythonExe) {
    $searchDrives = @("C:", "D:", "E:", "X:")
    foreach ($drive in $searchDrives) {
        if (Test-Path $drive) {
            $candidates = Get-ChildItem -Path "$drive\Users\*\AppData\Local\Programs\Python\Python*\python.exe", "$drive\Python*\python.exe", "$drive\Program Files\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
            if ($candidates) {
                $pythonExe = $candidates[0]
                break
            }
        }
    }
}

if ($pythonExe) {
    Write-Host "[✓] Found Python runtime: $pythonExe" -ForegroundColor Green
} else {
    Write-Host "[!] No local Python found. Downloading lightweight portable Python runtime (~15MB)..." -ForegroundColor Yellow
    $portableUrl = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
    $zipPath = "$targetDir\python_portable.zip"
    $pyDir = "$targetDir\python_env"
    
    Invoke-WebRequest -Uri $portableUrl -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $pyDir -Force
    $pythonExe = "$pyDir\python.exe"
    Write-Host "[✓] Portable Python initialized: $pythonExe" -ForegroundColor Green
}

# 3. Download Latest Agent Source from GitHub Repository
Write-Host "[3/4] Fetching latest Autonomous OS Debugging Agent files from cloud..." -ForegroundColor Cyan

# Default repository URL
$rawBase = "https://raw.githubusercontent.com/Ansh00031/SGU-AI-Thon/main"

$coreFiles = @(
    "agent.py",
    "core/__init__.py",
    "core/collector.py",
    "core/config.py",
    "core/executor.py",
    "core/llm.py",
    "core/remediation.py",
    "core/security.py",
    "core/snapshot.py",
    "core/system_paths.py",
    "core/reboot_manager.py",
    "core/autostart.py",
    "core/ui.py"
)

# Create core directory
if (!(Test-Path "$targetDir\core")) {
    New-Item -ItemType Directory -Path "$targetDir\core" -Force | Out-Null
}

foreach ($f in $coreFiles) {
    $fileUrl = "$rawBase/$f"
    $dest = "$targetDir\$f"
    Write-Host "  -> Downloading: $f" -ForegroundColor DarkGray
    Invoke-WebRequest -Uri $fileUrl -OutFile $dest -UseBasicParsing -ErrorAction SilentlyContinue
}

# Install minimal CLI dependencies if pip available
& $pythonExe -m pip install typer rich pydantic --quiet -ErrorAction SilentlyContinue

# 4. Launch the Autonomous Diagnostic Agent
Write-Host "`n[4/4] 🚀 Launching Autonomous OS Debugging Agent..." -ForegroundColor Green
Write-Host "===============================================================================" -ForegroundColor Cyan

& $pythonExe "$targetDir\agent.py" startup-monitor

# Keep interactive shell ready
Write-Host @"

[✓] Rescue environment is live!
You can now run:
    python agent.py diagnose 0x80070005
    python agent.py diagnose BOOT_LOOP
===============================================================================
"@ -ForegroundColor Yellow
