@echo off
title Poultry Farm App - LAN Share
rem One click: auto-detect IP, copy share URL, open app to the local network.
cd /d "%~dp0"
where uv >nul 2>nul
if %errorlevel%==0 (
    uv run python share_server.py %*
) else (
    python share_server.py %*
)
pause
