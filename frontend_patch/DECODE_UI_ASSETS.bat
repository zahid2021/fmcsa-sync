@echo off
title FMCSA UI — decode images from Notepad base64
set ROOT=C:\Users\Administrator\Desktop\fmsca\fmsca_frontend
set B64=%ROOT%\src\assets\b64
set OUT=%ROOT%\src\assets

if not exist "%OUT%" mkdir "%OUT%"
if not exist "%B64%" (
  echo ERROR: Folder missing: %B64%
  echo Create it and save the 4 .txt files from Notepad first.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$b64='%B64%'; $out='%OUT%';" ^
  "$map=@{ 'hero-truck.txt'='hero-truck.jpg'; 'hero-truck-thumb.txt'='hero-truck-thumb.jpg'; 'logo-cdl-brand.txt'='logo-cdl-brand.png'; 'logo-fmcsa-brand.txt'='logo-fmcsa-brand.png' };" ^
  "foreach($k in $map.Keys){ $src=Join-Path $b64 $k; $dst=Join-Path $out $map[$k]; if(-not (Test-Path $src)){ Write-Host 'MISSING:' $src -ForegroundColor Red; exit 1 }; $raw=(Get-Content -Raw $src) -replace '\s',''; [IO.File]::WriteAllBytes($dst,[Convert]::FromBase64String($raw)); Write-Host ('OK: '+$dst+' ('+(Get-Item $dst).Length+' bytes)') }"

if errorlevel 1 (
  echo.
  echo FAILED. Check all 4 txt files exist in %B64%
  pause
  exit /b 1
)

echo.
echo Done. Refresh browser: Ctrl+Shift+R
pause
