@echo off
REM Make OLD start method serve /export (same as new_backend.py)
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend

echo === Which Python is the OLD way? (run this WHILE old way is running) ===
wmic process where "name='python.exe'" get ProcessId,CommandLine

echo.
echo === Copy new_backend OVER the usual entry files (backup first) ===
if exist new_backend.py (
  copy /Y backend.py backend.py.bak_before_export 2>nul
  copy /Y run.py run.py.bak_before_export 2>nul
  copy /Y app.py app.py.bak_before_export 2>nul
  copy /Y new_backend.py backend.py
  copy /Y new_backend.py run.py
  if exist app.py copy /Y new_backend.py app.py
  echo Done: backend.py / run.py / app.py now = new_backend.py (with /export)
) else (
  echo ERROR: new_backend.py missing
)

echo.
echo Ab PURANE tarike se start karo (jo pehle karte the).
echo Phir test:
echo   curl -s -o NUL -w "HTTP %%{http_code}\n" "http://127.0.0.1:5000/export?filterkey=PHY_ST&filtervalue=TN"
pause
