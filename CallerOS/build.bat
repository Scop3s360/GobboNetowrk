@echo off
cd /d "%~dp0"
echo ===================================================
echo   CallerOS - Native Windows Desktop Builder (V1.0.1)
echo ===================================================

:: Clean previous builds
echo [1/6] Terminating running instances and cleaning previous build artifacts...
taskkill /F /IM CallerOS.exe >nul 2>&1
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Release rmdir /s /q Release
if exist CallerOS.spec del /q CallerOS.spec

:: Install missing dependencies
echo [2/6] Verifying python dependencies...
pip install pywebview pyinstaller pillow python-dotenv openai pytest pytest-mock

:: Run unit tests before packaging
echo [3/6] Running full test suite...
pytest
if %errorlevel% neq 0 (
    echo [ERROR] Test suite failed! Aborting packaging.
    exit /b 1
)

:: Package CallerOS using PyInstaller (OneFile, NoConsole)
echo [4/6] Packaging application to standalone executable...
pyinstaller --clean --onefile --noconsole --name=CallerOS --icon=app_icon.ico --add-data "frontend;frontend" --additional-hooks-dir pyinstaller_hooks --collect-all pythonnet --collect-all pywebview run_app.py
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller packaging failed!
    exit /b 1
)

:: Generate the Release folder structure
echo [5/6] Generating portable Release folder...
mkdir Release
mkdir Release\docs
mkdir Release\plugins
mkdir Release\logs
mkdir Release\config

copy /Y dist\CallerOS.exe Release\CallerOS.exe
if errorlevel 1 (
    echo [ERROR] Failed to copy CallerOS.exe to Release folder!
    exit /b 1
)
copy .env.example Release\config\.env.example
copy ..\README.md Release\docs\README.md

:: Create the README.txt for the Release folder
echo CallerOS Version 1.0.1 > Release\README.txt
echo ===================== >> Release\README.txt
echo To launch the application, double-click CallerOS.exe. >> Release\README.txt
echo >> Release\README.txt
echo Settings can be configured inside the UI or via the .env file in the config/ directory. >> Release\README.txt

:: Copy example plugin to plugins
xcopy /E /I plugins\example_plugin Release\plugins\example_plugin

:: Verify Packaging
echo [6/6] Verifying packaging output...
if exist Release\CallerOS.exe (
    echo ===================================================
    echo   BUILD SUCCESSFUL! Portable Release folder ready.
    echo ===================================================
    exit /b 0
) else (
    echo [ERROR] Verification failed. CallerOS.exe was not created.
    exit /b 1
)
