@echo off
chcp 65001 >nul 2>&1
title GEO 运营系统 - 开发服务器

echo ============================================
echo   GEO 运营系统 - 开发服务器启动中...
echo ============================================
echo.

cd /d "%~dp0"

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

:: 启动服务器
echo [INFO] 正在启动服务器...
echo [INFO] 地址: http://127.0.0.1:3106 (可通过 GEO_DEV_PORT 环境变量修改)
echo.
echo 按 Ctrl+C 停止服务器
echo --------------------------------------------
echo.

python dev_server.py

if errorlevel 1 (
    echo.
    echo [ERROR] 服务器异常退出
    pause
)
