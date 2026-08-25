@echo off
title FMCSA — OLD WAY ONLY (run.py :5000)
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend

REM Keep run.py + backend.py in sync with the patched file (once after paste)
if exist new_backend.py (
  copy /Y new_backend.py run.py >nul
  copy /Y new_backend.py backend.py >nul
)

if exist env\Scripts\activate.bat (
  call env\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)

echo.
echo === OLD WAY: python run.py on :5000 ===
echo Keep this window OPEN. Browser = localhost:5173
echo Filter: Header PHY_ST + value TN + Apply
echo Export = one file (no Chunks)
echo.
python run.py
pause
