@echo off
title FMCSA — OLD WAY (auto-copy + start)
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend

if exist new_backend.py (
  copy /Y new_backend.py run.py
  copy /Y new_backend.py backend.py
  echo Copied new_backend.py -^> run.py
) else (
  echo WARNING: new_backend.py missing — paste patch first!
)

findstr /C:"export_api_version" run.py >nul
if errorlevel 1 (
  echo ERROR: run.py is OLD — no slice export. Paste new_backend.py first.
  pause
  exit /b 1
)

if exist env\Scripts\activate.bat (
  call env\Scripts\activate.bat
)

set FMCSA_DRIVE_ROOT=G:\My Drive\My Drive\FMCSA
echo FMCSA_DRIVE_ROOT=%FMCSA_DRIVE_ROOT%
echo Export needs Start number + End number e.g. 1 to 10000
echo.
python run.py
pause
