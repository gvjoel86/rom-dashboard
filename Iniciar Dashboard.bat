@echo off
title ROM Dashboard
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo No encuentro Python. Instalalo desde la Microsoft Store ^(Python 3.13^)
  echo o desde https://www.python.org/downloads/ y vuelve a abrir este archivo.
  pause
  exit /b 1
)
:arrancar
%PY% rom_dashboard.py
rem Codigo 3 = se acaba de actualizar: arrancar de nuevo con la version nueva
if %errorlevel%==3 goto arrancar
if errorlevel 1 pause
