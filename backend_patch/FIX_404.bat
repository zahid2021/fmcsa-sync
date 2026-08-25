@echo off
title FIX 404 — kill old Flask, start run.py OLD WAY
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend

echo.
echo === 1) Who is on port 5000? ===
netstat -ano | findstr :5000
echo.
echo If you see LISTENING, note the last number (PID).
echo This script will try to free port 5000...
echo.

for /f "tokens=5" %%p in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
  echo Killing PID %%p
  taskkill /PID %%p /F
)

timeout /t 2 >nul
echo.
echo === 2) Port should be free now ===
netstat -ano | findstr :5000
echo.

echo === 3) Confirm routes in run.py ===
findstr /C:"export/drive/status" run.py
echo.

set FMCSA_DRIVE_ROOT=G:\My Drive\My Drive\FMCSA
echo FMCSA_DRIVE_ROOT=%FMCSA_DRIVE_ROOT%

if exist env\Scripts\activate.bat (
  call env\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)

echo.
echo === 4) Starting OLD WAY: python run.py ===
echo Keep this window OPEN. Watch for ROUTES with /export/drive
echo.
python run.py
pause
