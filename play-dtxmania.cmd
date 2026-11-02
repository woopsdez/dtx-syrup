@echo off
rem play-dtxmania launcher: starts the local server and opens the browser. Close this window (or Ctrl+C) to stop.
title play-dtxmania
cd /d "%~dp0"
python play_dtxmania.py serve
echo.
echo play-dtxmania stopped.
pause
