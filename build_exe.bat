@echo off
chcp 65001 >nul
cd /d "%~dp0"

set PY=%USERPROFILE%\.workbuddy-ai\binaries\python\envs\gui\Scripts\python.exe
if not exist "%PY%" set PY=python

echo [1/2] 清理旧产物 ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist LKTool.spec del /q LKTool.spec

echo [2/2] 开始打包 ...
"%PY%" -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name LKTool ^
  --paths . ^
  --hidden-import lk_core ^
  --hidden-import lk_gui ^
  --hidden-import capstone ^
  --exclude-module numpy ^
  --exclude-module PIL ^
  --exclude-module matplotlib ^
  LKTool.py

if errorlevel 1 (
  echo 打包失败
  pause
  exit /b 1
)

echo.
echo 完成: %~dp0dist\LKTool.exe
pause
