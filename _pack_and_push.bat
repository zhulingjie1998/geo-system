@echo off
set PATH=C:\Program Files\Git\cmd;%PATH%
cd /d c:\Users\Administrator\Desktop\geo-ops-system
git add -A
git commit -m "V1.1.0: deploy scripts and ranking analysis"
git push origin main
echo.
echo ===== Push to GitHub done =====
echo.
echo Now creating deployment package...
cd /d c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system

REM Create zip (exclude node_modules, __pycache__, .git, _deploy_stage)
echo Packing geo-ops-system.zip...
powershell -Command "Compress-Archive -Path 'backend','frontend','docs' -DestinationPath '..\geo-ops-system-V1.1.0.zip' -Force"
echo.
echo ===== Package created: geo-ops-system-V1.1.0.zip =====
echo Location: c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system-V1.1.0.zip
