@echo off
REM ============================================================
REM  Builds the Windows program:  dist\ShopStock\ShopStock.exe
REM  Run this ONCE on a Windows PC that has Python 3.11+ installed.
REM ============================================================
cd /d "%~dp0"
if not exist venv (python -m venv venv)
call venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean shopstock.spec
if errorlevel 1 (echo BUILD FAILED & pause & exit /b 1)
echo.
echo Done.  Program folder: dist\ShopStock   (double-click ShopStock.exe to test)
echo To make a one-file installer, install "Inno Setup" (jrsoftware.org) and compile installer.iss
pause
