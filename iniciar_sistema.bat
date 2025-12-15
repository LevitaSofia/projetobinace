@echo off
cd /d "C:\Users\levit\Downloads\Algoritimo rev02\projetobinace"
echo Iniciando o sistema de trading em segundo plano...
set PYTHONIOENCODING=utf-8
start /B pythonw server.py > console_output.log 2>&1
echo.
echo Sistema iniciado! 
echo - O terminal pode ser fechado agora.
echo - Acesse http://localhost:5000
echo - Para ver os logs, abra os arquivos 'sistema_trading.log' e 'console_output.log'
echo.
timeout /t 5