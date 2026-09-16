@echo off
setlocal
cd /d "%~dp0"
python -m pip install -e . pyinstaller
if errorlevel 1 exit /b 1
pyinstaller --noconfirm --clean TrigrixStudio.spec
if errorlevel 1 exit /b 1
echo Build ready: dist\TRIGRIX Studio\TRIGRIX Studio.exe
if not exist "build\wix\light.exe" powershell -NoProfile -ExecutionPolicy Bypass -File tools\setup_wix.ps1
if errorlevel 1 exit /b 1
python tools\build_msi.py
if errorlevel 1 exit /b 1
