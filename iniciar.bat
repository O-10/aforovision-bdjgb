@echo off
chcp 65001 >nul
cd /d "%~dp0"
title AforoVision BDJGB - Control de aforo
echo.
echo  AforoVision - Biblioteca Departamental Jorge Garces Borrero
echo  Desarrollado por Oscar Ivan Solarte Ceron - 3154013707
echo  Abriendo http://127.0.0.1:8000 ...
echo.
start "" http://127.0.0.1:8000
py -m uvicorn server:app --host 127.0.0.1 --port 8000
pause
