@echo off
cd /d c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system

echo ===== Creating deployment package =====
echo Excluding: node_modules, __pycache__, .git, dist, _deploy_stage

REM Use tar (built into Windows 10+) to create zip, excluding unwanted dirs
tar --exclude='node_modules' --exclude='__pycache__' --exclude='.git' --exclude='dist' --exclude='_deploy_stage' -czvf ..\geo-ops-system-V1.1.0.tar.gz backend frontend docs

echo.
if exist ..\geo-ops-system-V1.1.0.tar.gz (
    echo ===== Package created successfully! =====
    for %%A in (..\geo-ops-system-V1.1.0.tar.gz) do echo Size: %%~zA bytes
) else (
    echo ERROR: Package creation failed
)
