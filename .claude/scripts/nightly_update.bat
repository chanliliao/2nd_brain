@echo off
cd /d C:\Users\cliao\Desktop\2nd_Brain

C:\Users\cliao\Desktop\2nd_Brain\.claude\venv\Scripts\python.exe .claude\scripts\heartbeat.py --once --skip-hours-check >> .claude\data\logs\heartbeat.log 2>&1

C:\Users\cliao\Desktop\2nd_Brain\.claude\venv\Scripts\python.exe -m graphify vault --update >> .claude\data\logs\graphify.log 2>&1

C:\Users\cliao\Desktop\2nd_Brain\.claude\venv\Scripts\python.exe .claude\scripts\memory\dream.py >> .claude\data\logs\dream.log 2>&1

C:\Users\cliao\Desktop\2nd_Brain\.claude\venv\Scripts\python.exe .claude\scripts\nightly_log_cleanup.py >> .claude\data\logs\nightly_cleanup.log 2>&1
