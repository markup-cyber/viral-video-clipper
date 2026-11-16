@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (echo Python not found. Install from python.org ^(check "Add to PATH"^) & pause & exit /b 1)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv || (echo venv failed & pause & exit /b 1)
)
call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip >nul
pip install -r requirements.txt || (echo pip install failed & pause & exit /b 1)
pip install pyinstaller >nul

set EXTRA=
set "FF="
for /f "delims=" %%i in ('where ffmpeg 2^>nul') do if not defined FF set "FF=%%i"
if defined FF (
  for %%i in ("%FF%") do set "FFDIR=%%~dpi"
  echo Found ffmpeg - bundling it into the exe so end users do NOT need to install it...
  set EXTRA=%EXTRA% --add-binary "%FF%;."
  if exist "%FFDIR%ffprobe.exe" set EXTRA=%EXTRA% --add-binary "%FFDIR%ffprobe.exe;."
) else (
  echo ffmpeg NOT found - run "winget install Gyan.FFmpeg" first so it gets bundled.
)

pyinstaller --noconfirm --clean --onedir --console --name ViralClipper ^
  --collect-all streamlit ^
  --collect-all altair ^
  --collect-all yt_dlp ^
  --collect-all youtube_transcript_api ^
  --collect-all openai ^
  --collect-all cv2 ^
  --add-data "app.py;." ^
  --add-data "clipper;clipper" ^
  %EXTRA% ^
  entry.py

echo.
echo =====================================================
echo  Done!  Your app:  dist\ViralClipper\ViralClipper.exe
echo  Share by zipping the whole ViralClipper folder.
echo =====================================================
pause
