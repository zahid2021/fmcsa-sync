@echo off
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend
echo === run.py has slice export? ===
findstr /C:"EXPORT_API_VERSION" run.py
findstr /C:"parse_export_range" run.py
echo.
echo === API version (need export_api_version: 4) ===
curl -s http://127.0.0.1:5000/export/drive/status
echo.
echo === Test 10k only (must show range_rows: 10000) ===
curl -s "http://127.0.0.1:5000/export/drive?filterkey=PHY_ST&filtervalue=HI&slug=verify&start_number=1&end_number=10000"
echo.
pause
