@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ====================================
echo 小鹦鹉记账 - 桌面版一键打包 (EXE & ZIP)
echo ====================================
echo.

set "PYTHON_CMD="

where python >nul 2>nul
if !errorlevel! equ 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py -3"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [错误] 未在系统 PATH 中检测到 Python 环境！
    echo 请先安装 Python 3.10+ 并勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

echo 正在使用 Python 环境: %PYTHON_CMD%
echo 正在开始打包流程，请稍候...
echo.

%PYTHON_CMD% build_package.py

if !errorlevel! neq 0 (
    echo.
    echo ====================================
    echo [打包失败] 请检查上方报错信息。
    echo ====================================
) else (
    echo.
    echo ====================================
    echo [打包完成]
    echo 1. 独立解压运行版: dist\小鹦鹉记账\小鹦鹉记账.exe
    echo 2. 绿色免安装压缩包: dist\小鹦鹉记账.zip
    echo ====================================
    echo.
    if exist "dist" start dist
)

echo.
pause
