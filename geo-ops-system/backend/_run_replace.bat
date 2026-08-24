@echo off
cd /d "c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend"
"c:\Users\Administrator\Desktop\geo-ops-system\.venv\Scripts\python.exe" _replace_garbled.py > _replace_out.txt 2>&1
type _replace_out.txt
