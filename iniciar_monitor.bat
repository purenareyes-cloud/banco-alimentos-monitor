@echo off
title Monitor Banco de Alimentos
cd /d "%~dp0"
echo ============================================
echo   Monitor del Banco de Alimentos
echo   Deje esta ventana abierta.
echo   Para detenerlo: cierre la ventana o Ctrl+C
echo ============================================
:reinicio
python monitor.py
if errorlevel 3 goto yaexiste
echo.
echo El monitor se detuvo. Reiniciando en 30 segundos...
timeout /t 30 /nobreak >nul
goto reinicio
:yaexiste
echo.
echo Ya hay otro monitor corriendo. Esta ventana se cierra sola...
timeout /t 8 /nobreak >nul
