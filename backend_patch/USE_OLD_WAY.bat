@echo off
REM ONE-TIME: after Notepad paste of new_backend.py — wire into OLD entrypoints
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend
copy /Y new_backend.py run.py
copy /Y new_backend.py backend.py
echo OK — ab sirf: python run.py
echo Or double-click START_OLD_WAY.bat
pause
