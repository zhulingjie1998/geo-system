@echo off
chcp 65001 >nul
echo ===================================
echo  打包前端 dist + app.py 上传包
echo ===================================

set BASE=c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system
set STAGE=%BASE%\_deploy_stage

echo [1/4] 清理暂存目录
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%\backend\static"
mkdir "%STAGE%\backend"

echo [2/4] 复制前端 dist 到 backend/static
xcopy "%BASE%\frontend\dist" "%STAGE%\backend\static" /E /I /Y /Q

echo [3/4] 复制 app.py
copy "%BASE%\backend\app.py" "%STAGE%\backend\app.py" /Y

echo [4/4] 打包 zip
cd /d "%STAGE%"
powershell -Command "Compress-Archive -Path '.\backend' -DestinationPath '%BASE%\geo-deploy.zip' -Force"

echo.
echo 完成! 文件: %BASE%\geo-deploy.zip
dir "%BASE%\geo-deploy.zip"
pause
