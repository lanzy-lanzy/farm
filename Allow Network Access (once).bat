@echo off
title Allow Network Access (one-time setup)
rem Opens Windows Firewall for the shared farm app so phones/PCs can connect.
rem Run this ONCE as administrator. It re-requests elevation automatically.

net session >nul 2>nul
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

netsh advfirewall firewall add rule name="Poultry Farm App Share" dir=in action=allow protocol=TCP localport=8000-8010 >nul
if %errorlevel% equ 0 (
    echo.
    echo   [OK] Firewall rule added. Devices on your Wi-Fi/LAN can now
    echo        open the farm app and API on ports 8000-8010.
) else (
    echo   [!] Failed to add the firewall rule.
)
echo.
pause
