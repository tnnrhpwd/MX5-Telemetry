@echo off
rem ============================================================================
rem  Build the native ESP32-S3 display UI simulator (Windows / MSVC).
rem  Compiles the REAL ui_core.cpp against the mock LCD backend.
rem ============================================================================
setlocal
cd /d "%~dp0"

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
    echo [ERROR] vswhere.exe not found. Install Visual Studio Build Tools with C++.
    exit /b 1
)

for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSDIR=%%i"
if not defined VSDIR (
    echo [ERROR] MSVC C++ toolchain not found.
    exit /b 1
)

call "%VSDIR%\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] VsDevCmd.bat failed.
    exit /b 1
)

echo Building ESP32-S3 UI simulator (native)...
cl /nologo /std:c++17 /O2 /EHsc /DUI_CORE_NATIVE /D_CRT_SECURE_NO_WARNINGS /wd4996 ^
   /I..\..\..\display\src\ui_core ^
   /I..\..\..\display\include ^
   /I..\..\..\display\lib\WaveshareDisplay ^
   /I. ^
   ..\..\..\display\src\ui_core\ui_core.cpp ^
   ..\..\..\display\lib\WaveshareDisplay\fonts_hires.cpp ^
   native_display.cpp ^
   native_main.cpp ^
   /Fe:esp32_ui_simulator.exe ^
   /link user32.lib gdi32.lib

if errorlevel 1 (
    echo.
    echo [FAILED] Build failed.
    exit /b 1
)

echo.
echo [OK] Built esp32_ui_simulator.exe
exit /b 0
