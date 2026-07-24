@echo off
echo ================================
echo Building 小鹦鹉记账...
echo ================================
echo.

echo [1/3] Installing dependencies...
pip install customtkinter Pillow pyinstaller --quiet 2>nul
if errorlevel 1 (
    python -m pip install customtkinter Pillow pyinstaller --quiet 2>nul
)
echo Done.
echo.

echo [2/3] Cleaning old files...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
echo Done.
echo.

echo [3/3] Starting build (1-2 minutes)...
echo Using spec: 小鹦鹉记账.spec
echo.

"C:\Users\litia\AppData\Local\Python\bin\python.exe" -m PyInstaller --noconfirm "小鹦鹉记账.spec"

if errorlevel 1 (
    echo.
    echo ================================
    echo BUILD FAILED! Check errors above.
    echo ================================
) else (
    echo.
    echo ================================
    echo Build complete!
    echo Output: dist\小鹦鹉记账\
    echo Executable: dist\小鹦鹉记账\小鹦鹉记账.exe
    echo ================================
    echo.
    echo Opening output folder...
    start dist\小鹦鹉记账
)

echo.
pause
