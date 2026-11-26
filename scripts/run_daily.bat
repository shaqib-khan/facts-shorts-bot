@echo off
cd /d "c:\Users\shaqi\Downloads\ai"
if not exist "output" mkdir "output"
echo ===== Run started at %date% %time% ===== >> "output\daily_task.log"
".venv\Scripts\python.exe" scripts\run_pipeline.py --upload --privacy public >> "output\daily_task.log" 2>&1

