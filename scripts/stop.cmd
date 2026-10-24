@echo off
rem Smart Campus Course Assistant - stop (wraps scripts\stop.ps1)
chcp 65001 >nul
setlocal
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*
exit /b %ERRORLEVEL%
