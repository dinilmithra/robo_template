@echo off
REM kill_browser.cmd - Calls the Python script to kill stale browsers

REM Activate the correct environment if needed (optional)
REM call path\to\venv\Scripts\activate.bat

REM Call the Python script
python "%~dp0scripts\kill_stale_browsers.py" %*
