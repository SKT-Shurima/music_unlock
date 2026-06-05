@echo off
REM music-tool Windows launcher
REM Requires: Python 3.8+, Node.js
set TOOL_DIR=%USERPROFILE%\.music-tool
python3 "%TOOL_DIR%\unlock.py" %*
