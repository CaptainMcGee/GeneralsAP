@echo off
setlocal
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\windows_debug_run.ps1" %*
endlocal
