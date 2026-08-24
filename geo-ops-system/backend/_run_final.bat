@echo off
chcp 65001 >nul
cd /d "c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend"
"c:\Users\Administrator\Desktop\geo-ops-system\.venv\Scripts\python.exe" _fix_all_garbled.py > _garbled_fix_result.txt 2>&1
echo === RESULT ===
type _garbled_fix_result.txt
echo.
echo === COMPILE TEST ===
"c:\Users\Administrator\Desktop\geo-ops-system\.venv\Scripts\python.exe" -m py_compile app.py 2>&1
if %ERRORLEVEL%==0 (echo COMPILE SUCCESS!) else (echo COMPILE FAILED)
pause
