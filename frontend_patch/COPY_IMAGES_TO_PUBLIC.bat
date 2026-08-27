@echo off
title FMCSA — copy hero + logos to public folder
set SRC=%~dp0assets
set DST=C:\Users\Administrator\Desktop\fmsca\fmsca_frontend\public

if not exist "%DST%" mkdir "%DST%"

copy /Y "%SRC%\hero-bg.jpg" "%DST%\hero-bg.jpg"
copy /Y "%SRC%\logo-cdl-brand.jpg" "%DST%\logo-cdl-brand.jpg"
copy /Y "%SRC%\logo-fmcsa-brand.jpg" "%DST%\logo-fmcsa-brand.jpg"

echo.
echo Copied to %DST%:
dir /B "%DST%\hero-bg.jpg" "%DST%\logo-cdl-brand.jpg" "%DST%\logo-fmcsa-brand.jpg"
echo.
echo Now paste MainData.css + MainData.tsx and Ctrl+Shift+R
pause
