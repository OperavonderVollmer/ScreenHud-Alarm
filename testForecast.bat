@echo off
setlocal

cd /d "%~dp0"

title ScreenHud-REST


call ".\.venv\Scripts\activate.bat"

python ".\main.py"
