@echo off
setlocal
cd /d "%~dp0"
title Paper Assistant
where py >nul 2>nul
if %errorlevel%==0 goto usepy
where python >nul 2>nul
if %errorlevel%==0 goto usepython
echo Python 3.10 or newer is required.
echo Install it from https://www.python.org/downloads/ and tick "Add Python to PATH", then run this again.
goto end
:usepy
py -3 run.py
goto end
:usepython
python run.py
:end
pause
