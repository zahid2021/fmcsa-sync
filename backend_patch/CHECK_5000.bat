@echo off
title FMCSA check Flask :5000
echo === Is anyone on 5000? ===
netstat -ano | findstr :5000
echo.
echo === Filter test ===
curl -s -o NUL -w "filter HTTP %{http_code}\n" "http://127.0.0.1:5000/filter/?filterkey=PHY_ST&filtervalue=TN&page=1&per_page=1"
echo === Export test ===
curl -s -o NUL -w "export HTTP %{http_code}\n" "http://127.0.0.1:5000/export?filterkey=PHY_ST&filtervalue=TN"
echo.
echo If HTTP 000 / Connection refused: start python run.py first (keep window open).
pause
