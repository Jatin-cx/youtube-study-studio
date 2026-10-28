@echo off
title YouTube Study Notes & PDF Generator
echo ========================================================
echo   Launching YouTube Study Notes & PDF Generator...
echo ========================================================
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run app.py
pause
