@echo off
rem Smart Campus Course Assistant - start (wraps scripts\start.ps1)
chcp 65001 >nul
setlocal
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
exit /b %ERRORLEVEL%
