@echo off
REM Quick MCP2515 Reset - Easy launcher
echo ========================================
echo MX5 Telemetry - MCP Module Tools
echo ========================================
echo.
echo 1. Quick Reset (Fast fix - 10 seconds)
echo 2. Full Diagnostic (Detailed check - 30 seconds)
echo 3. Check Startup Errors
echo 4. Exit
echo.
set /p choice="Select option (1-4): "

if "%choice%"=="1" (
    echo.
    echo Running quick reset...
    python tools\quick_reset_mcp.py
    pause
    goto end
)

if "%choice%"=="2" (
    echo.
    echo Running full diagnostic...
    python tools\reset_mcp_modules.py
    pause
    goto end
)

if "%choice%"=="3" (
    echo.
    echo Checking startup errors...
    python tools\check_mcp_startup_errors.py
    pause
    goto end
)

:end
