@echo off
set PATH=C:\Program Files\Git\cmd;%PATH%
cd /d c:\Users\Administrator\Desktop\geo-ops-system
git add -A
git commit -m "V1.1.0: ranking analysis page, deploy scripts"
git push origin main
echo.
echo ===== Done =====
