@echo off
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend
echo === LINE 151-155 (spaces matter) ===
python -c "lines=open('new_backend.py',encoding='utf-8',errors='replace').readlines();
[print(i+1, repr(lines[i][:80])) for i in range(148, min(160, len(lines)))]"
echo.
echo === ROUTES IN MODULE ===
python -c "import importlib; m=importlib.import_module('new_backend'); print(sorted(r.rule for r in m.app.url_map.iter_rules()))"
echo.
echo === LIVE ===
curl -s http://127.0.0.1:5000/
echo.
curl -s -o NUL -w "export HTTP %%{http_code}\n" "http://127.0.0.1:5000/export?filterkey=PHY_ST&filtervalue=TN"
