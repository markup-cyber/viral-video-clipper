@echo off
title ViralClipper
cd /d "%~dp0"
where python >nul 2>nul || (echo Python not found. Install from python.org and check "Add to PATH". & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv || (echo Failed to create venv & pause & exit /b 1)
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
echo Starting ViralClipper... your browser will open automatically.
streamlit run app.py
pause
