@echo off
title Autonomous OS Debugging Agent - Cloud Rescue
echo ===============================================================================
echo   Downloading and launching Autonomous OS Debugging Agent from Cloud...
echo ===============================================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; irm https://raw.githubusercontent.com/Ansh00031/SGU-AI-Thon/main/bootstrap.ps1 | iex"
pause
