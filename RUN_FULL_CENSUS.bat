@echo off
REM === FULL CENSUS IMPORT (paste each block in order) ===
cd /d C:\fmcsa_sync
if not exist C:\fmcsa_sync mkdir C:\fmcsa_sync

REM Prefer backend venv python:
set PY=C:\Users\Administrator\Desktop\fmsca\fmsca_backend\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

powershell -ExecutionPolicy Bypass -File C:\fmcsa_sync\RUN_FULL_CENSUS.ps1
