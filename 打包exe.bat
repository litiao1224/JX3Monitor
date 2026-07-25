@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ================================
echo 正在打包 小鹦鹉记账...
echo ================================
echo.

python build_package.py

echo.
pause
