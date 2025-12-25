#!/bin/bash
cd /home/ubuntu/projetobinace
# Kill any existing instances first
pkill -f server.py
sleep 2
# Start fresh
nohup /home/ubuntu/projetobinace/venv/bin/python3 /home/ubuntu/projetobinace/server.py > output.log 2>&1 &
echo $! > server.pid
