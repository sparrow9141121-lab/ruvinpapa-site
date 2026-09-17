@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

where py > nul 2>&1
if %errorlevel%==0 (
  py -3 "update-content.py"
) else (
  python "update-content.py"
)

echo.
pause
