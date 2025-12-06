@echo off
REM ============================================================================
REM ESP32-S3 Round Display Quick Actions
REM ============================================================================
REM Double-click this file to open the interactive menu
REM ============================================================================

cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "scripts\quick_actions.ps1"
pause
