@echo off
REM End-to-end Drive export test (slug -> FMCSA\slug\chunk_*.xlsx)
setlocal

echo Drive status:
curl -s "http://127.0.0.1:5000/export/drive/status"
echo.
echo.

echo Export test: PHY_ST=HI slug=test_user start=1 row_count=10000
curl -s "http://127.0.0.1:5000/export/drive?filterkey=PHY_ST&filtervalue=HI&slug=test_user&start_number=1&row_count=10000"
echo.
echo.

echo If ok, open folder:
echo   %%FMCSA_DRIVE_ROOT%%\test_user
echo   Expect: chunk_1.xlsx chunk_2.xlsx ...
echo.
if defined FMCSA_DRIVE_ROOT (
  explorer "%FMCSA_DRIVE_ROOT%\test_user"
) else (
  echo FMCSA_DRIVE_ROOT not set in this CMD. Open Google Drive\My Drive\FMCSA\test_user manually.
)
pause
