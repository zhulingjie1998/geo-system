@echo off
echo ========================================
echo   GEO 运营系统 - 重启 Flask 服务器
echo ========================================
echo.

:: 1. 停止所有 Python 进程
echo [1/3] 正在停止 Python 进程...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

:: 2. 等待端口释放
echo [2/3] 等待端口释放...
timeout /t 2 /nobreak >nul

:: 3. 启动新的 Flask 服务器
echo [3/3] 正在启动 Flask 服务器...
cd /d "c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend"
start "Flask Server" cmd /k "call .venv\Scripts\activate.bat && python dev_server.py"

echo.
echo ✅ 服务器已重启！
echo    后端地址: http://127.0.0.1:7008
echo    前端地址: http://localhost:3106
echo.
pause
