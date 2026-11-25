@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Atlachia - instalacion
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 instalar.py
) else (
  python instalar.py
)
echo.
pause
