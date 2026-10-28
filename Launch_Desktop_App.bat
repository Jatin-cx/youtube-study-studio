@echo off
title Launch YouTube Study Studio App
cd /d "%~dp0"
call .venv\Scripts\python.exe launch_app.py
exit
