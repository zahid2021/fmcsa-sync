@echo off
REM Run on Anthony RDP — proves Flask has /export and returns 1000 rows
echo.
echo ==== 1) Is Flask up? ====
curl -s http://127.0.0.1:5000/
echo.
echo.
echo ==== 2) Export route exists? (must NOT say Not Found) ====
curl -s -o NUL -w "HTTP %%{http_code}\n" "http://127.0.0.1:5000/export?filterkey=PHY_ST&filtervalue=TN"
echo.
echo ==== 3) Row count on page 1 (must be ~1000) ====
curl -s "http://127.0.0.1:5000/filter/?filterkey=PHY_ST&filtervalue=TN&page=1&per_page=1000" > "%TEMP%\fmcsa_page.json"
powershell -NoProfile -Command "$j=Get-Content -Raw $env:TEMP\fmcsa_page.json | ConvertFrom-Json; Write-Host ('total_count=' + $j.total_count); Write-Host ('rows_this_page=' + $j.data.Count)"
echo.
echo If routes missing /export OR rows_this_page not 1000: paste new_backend.py + restart Flask.
pause
