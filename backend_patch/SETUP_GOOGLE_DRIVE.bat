@echo off
REM ============================================================
REM Google Drive + FMCSA folder setup (Anthony RDP)
REM Client video: login with client Gmail, folder FMCSA, export xlsx chunks
REM ============================================================
setlocal EnableExtensions

echo.
echo === 1) Install Google Drive for desktop (if not installed) ===
echo    Download: https://www.google.com/drive/download/
echo    Login with CLIENT email + password (from client message).
echo    Wait until "My Drive" sync folder appears.
echo.
pause

echo.
echo === 2) Finding My Drive folder ===
set "FOUND="

if exist "%USERPROFILE%\Google Drive\My Drive" set "FOUND=%USERPROFILE%\Google Drive\My Drive"
if exist "%USERPROFILE%\My Drive" set "FOUND=%USERPROFILE%\My Drive"
if exist "G:\My Drive" set "FOUND=G:\My Drive"
if exist "C:\Users\Administrator\Google Drive\My Drive" set "FOUND=C:\Users\Administrator\Google Drive\My Drive"
if exist "C:\Users\Administrator\My Drive" set "FOUND=C:\Users\Administrator\My Drive"

if "%FOUND%"=="" (
  echo My Drive NOT found.
  echo After Drive login, run this bat again.
  echo Or set path manually below.
  set /p FOUND=Paste full path to "My Drive" folder: 
)

if "%FOUND%"=="" (
  echo No path. Exit.
  pause
  exit /b 1
)

echo Using My Drive: %FOUND%
mkdir "%FOUND%\FMCSA" 2>nul
set "FMCSA_ROOT=%FOUND%\FMCSA"
echo FMCSA folder: %FMCSA_ROOT%

echo.
echo === 3) Save path for Flask (permanent) ===
setx FMCSA_DRIVE_ROOT "%FMCSA_ROOT%"
set "FMCSA_DRIVE_ROOT=%FMCSA_ROOT%"

echo.
echo FMCSA_DRIVE_ROOT=%FMCSA_DRIVE_ROOT%
echo.
echo === 4) Install openpyxl (Excel export) ===
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend
python -m pip install openpyxl
echo.
echo DONE. Next: copy new_backend.py to run.py and restart:
echo   copy /Y new_backend.py run.py
echo   copy /Y new_backend.py backend.py
echo   python run.py
echo.
echo Then run TEST_DRIVE_EXPORT.bat
pause
