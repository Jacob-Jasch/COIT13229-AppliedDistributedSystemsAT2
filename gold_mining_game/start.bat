@echo off
REM Start ZooKeeper first, then run this file.
start "Gold Miner Server" cmd /k python game_server.py
timeout /t 2
start "Gold Miner Bot 0" cmd /k python bot_client.py bot_0
start "Gold Miner Bot 1" cmd /k python bot_client.py bot_1
start "Gold Miner Bot 2" cmd /k python bot_client.py bot_2
timeout /t 1
python player_client.py
