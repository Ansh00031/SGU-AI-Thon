@echo off
title Autonomous OS Debugging Agent - Cloud Rescue
echo ===============================================================================
echo   Downloading and launching Autonomous OS Debugging Agent from Cloud...
echo ===============================================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; irm https://raw.githubusercontent.com/ansh6/os-debug-agent/main/bootstrap.ps1 | iex"
pause
