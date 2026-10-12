@echo off
rem Loads any new Ginnie Mae files from your Downloads folder into Azure.
rem Double-click it, or schedule it with Windows Task Scheduler.
cd /d "%~dp0"
python gnma_loader.py --inbox "%USERPROFILE%\Downloads" >> gnma_loader.log 2>&1
