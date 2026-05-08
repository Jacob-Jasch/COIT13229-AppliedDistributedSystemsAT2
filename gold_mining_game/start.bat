@echo off
pip install -r requirements.txt
start /b python game_server.py
timeout /t 2
python player_client.py
pause