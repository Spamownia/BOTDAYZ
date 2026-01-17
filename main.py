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

# Flask – health check dla Rendera
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot Husaria żyje! 🚀", 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# BattleMetrics – ID Twojego serwera
BATTLEMERTICS_SERVER_ID = "37055320"  # ← zmień jeśli inny

PLAYERS_UPDATE_INTERVAL = 60

# Anty-duplikaty – proste, ale skuteczne
processed_hashes = set()
MAX_CACHE_SIZE = 12000  # ~ kilka dni logów

@tasks.loop(seconds=PLAYERS_UPDATE_INTERVAL)
async def update_players_status():
    try:
        url = f"https://api.battlemetrics.com/servers/{BATTLEMERTICS_SERVER_ID}"
        response = requests.get(url, timeout=12)
        if response.status_code == 200:
            data = response.json()
            online = data["data"]["attributes"]["players"]
            max_players = data["data"]["attributes"]["maxPlayers"]
            status_text = f"{online}/{max_players} online"
            await client.change_presence(activity=discord.Game(name=status_text))
            print(f"[STATUS] Zaktualizowano: {status_text}")
        else:
            print(f"[STATUS] Błąd BattleMetrics – kod {response.status_code}")
            await client.change_presence(activity=None)
    except Exception as e:
        print(f"[STATUS] Błąd: {e}")
        await client.change_presence(activity=None)

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_logs():
    print("[TASK] Sprawdzam nowe logi...")

    try:
        content = watcher.get_new_content()
        if not content:
            print("[TASK] Brak nowych danych (pusty content)")
            return

        lines = content.splitlines()
        new_lines_count = len(lines)
        print(f"[TASK] Pobrano {new_lines_count} linii")

        processed_this_cycle = 0

        for log_line in lines:
            stripped = log_line.strip()
            if not stripped:
                continue

            line_hash = hash(stripped)
            if line_hash in processed_hashes:
                # print(f"[SKIP] Duplikat: {stripped[:80]}...")
                continue

            processed_hashes.add(line_hash)
            processed_this_cycle += 1

            if len(processed_hashes) > MAX_CACHE_SIZE:
                processed_hashes.pop()

            print(f"[DEBUG PARSER] → {stripped}")
            await process_line(client, log_line)

        print(f"[TASK] Przetworzono w tej turze: {processed_this_cycle} unikalnych linii")

    except Exception as e:
        print(f"[TASK] Błąd podczas sprawdzania logów: {type(e).__name__} → {e}")

@client.event
async def on_ready():
    print(f"[BOT] Zalogowano jako {client.user} (ID: {client.user.id})")
    print(f"[BOT] CHECK_INTERVAL = {CHECK_INTERVAL} sekund")
    print("[BOT] Startuję pętle...")
    check_logs.start()
    update_players_status.start()

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    await client.process_commands(message)

if __name__ == "__main__":
    print("[MAIN] Uruchamiam bota...")
    client.run(DISCORD_TOKEN)
