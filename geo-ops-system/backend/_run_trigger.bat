@echo off
cd /d "c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend"
"c:\Users\Administrator\Desktop\geo-ops-system\.venv\Scripts\python.exe" _add_trigger.py > _trigger_output.txt 2>&1
echo EXIT_CODE=%ERRORLEVEL% >> _trigger_output.txt
type _trigger_output.txt
