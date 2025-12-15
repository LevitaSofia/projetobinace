@echo off
echo Parando o sistema de trading...
taskkill /F /IM pythonw3.13.exe
taskkill /F /IM pythonw.exe
taskkill /F /IM python.exe
echo.
echo Sistema parado com sucesso!
pause