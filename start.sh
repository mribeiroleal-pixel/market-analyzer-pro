#!/bin/bash
set -e

echo "🚀 Starting Market Analyst Pro"
echo "=============================="

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

docker-compose up -d
sleep 15

mkdir -p logs models data

python backend/websocket_server.py
