# main.py – Discord bot do logów DayZ + Flask + status graczy

import discord
from discord.ext import commands, tasks
import asyncio
import requests
import threading
from flask import Flask
from config import DISCORD_TOKEN, CHECK_INTERVAL
from ftp_watcher import DayZLogWatcher
from log_parser import process_line

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)
watcher = DayZLogWatcher()

# Flask – prosty serwer na porcie 10000 dla Rendera
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot Husaria żyje!", 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# ID serwera BattleMetrics – ZMIEŃ NA SWOJE
BATTLEMERTICS_SERVER_ID = "37055320"  # ← tutaj Twoje ID

PLAYERS_UPDATE_INTERVAL = 60

@tasks.loop(seconds=PLAYERS_UPDATE_INTERVAL)
async def update_players_status():
    try:
        url = f"https://api.battlemetrics.com/servers/{BATTLEMERTICS_SERVER_ID}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            online = data["data"]["attributes"]["players"]
            max_players = data["data"]["attributes"]["maxPlayers"]
            status_text = f"{online}/{max_players} online"

            await client.change_presence(activity=discord.Game(name=status_text))
            print(f"[STATUS] Zaktualizowano: {status_text}")
        else:
            await client.change_presence(activity=None)
            print("[STATUS] Błąd BattleMetrics")
    except Exception as e:
        print(f"[STATUS] Błąd: {e}")
        await client.change_presence(activity=None)

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_logs():
    print("[TASK] Sprawdzam nowe logi...")
    try:
        content = watcher.get_new_content()
        if content:
            print(f"[LOG] Pobrano {len(content.splitlines())} linii")
            for log_line in content.splitlines():
                if log_line.strip():
                    await process_line(client, log_line)
    except Exception as e:
        print(f"Błąd sprawdzania logów: {e}")

@client.event
async def on_ready():
    print(f"Zalogowano jako {client.user}")
    check_logs.start()                # ← TO BRAKOWAŁO !!!
    update_players_status.start()

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    await client.process_commands(message)

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
