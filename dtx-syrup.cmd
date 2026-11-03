@echo off
rem DTX Syrup launcher: starts the local server and opens the browser. Close this window (or Ctrl+C) to stop.
title DTX Syrup
cd /d "%~dp0"
python dtx_syrup.py serve
echo.
echo DTX Syrup stopped.
pause
