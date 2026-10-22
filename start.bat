@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 start.py %*
goto finished
:use_python
python start.py %*
:finished
if errorlevel 1 pause
endlocal
