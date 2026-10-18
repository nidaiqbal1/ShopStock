@echo off
REM Double-click to start ShopStock from the project folder (first run sets everything up).
cd /d "%~dp0"
if not exist venv (
  echo First run: setting up, please wait...
  python -m venv venv
  call venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call venv\Scripts\activate
)
python app.py
pause
