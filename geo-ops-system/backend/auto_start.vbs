' GEO 运营系统 - 后台启动脚本
' 将此文件放入 Windows 启动文件夹可实现开机自启
' 启动文件夹路径: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """" & WshShell.CurrentDirectory & "\start.bat"""", 0, False
