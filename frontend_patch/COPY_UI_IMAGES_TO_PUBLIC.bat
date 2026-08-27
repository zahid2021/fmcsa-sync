@echo off
title Copy UI images to public folder (fixes hero background)
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_frontend
if not exist public mkdir public
copy /Y src\assets\hero-truck.jpg public\
copy /Y src\assets\hero-truck-thumb.jpg public\
copy /Y src\assets\logo-cdl-brand.jpg public\
copy /Y src\assets\logo-fmcsa-brand.jpg public\
echo.
dir public\hero-truck.jpg public\logo-*.jpg
echo.
echo Done. Paste MainData.css if not yet, then Ctrl+Shift+R
pause
