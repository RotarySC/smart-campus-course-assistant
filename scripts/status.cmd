@echo off
rem Smart Campus Course Assistant - status (wraps scripts\status.ps1)
chcp 65001 >nul
setlocal
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0status.ps1" %*
exit /b %ERRORLEVEL%
