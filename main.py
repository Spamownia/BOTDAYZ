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

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot Husaria – żyje!", 200

threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=10000, debug=False), daemon=True).start()

BATTLEMERTICS_SERVER_ID = "37055320"

@tasks.loop(seconds=60)
async def update_status():
    try:
        r = requests.get(f"https://api.battlemetrics.com/servers/{BATTLEMERTICS_SERVER_ID}", timeout=10)
        if r.status_code == 200:
            d = r.json()["data"]["attributes"]
            await client.change_presence(activity=discord.Game(f"{d['players']}/{d['maxPlayers']} online"))
            print(f"[STATUS] {d['players']}/{d['maxPlayers']}")
    except Exception as e:
        print(f"[STATUS ERR] {e}")

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_logs():
    print("[CHECK] Start sprawdzania logów...")
    content = watcher.get_new_content()
    if not content:
        print("[CHECK] Brak nowych danych")
        return

    lines = [l for l in content.splitlines() if l.strip()]
    print(f"[CHECK] Przetwarzam {len(lines)} linii")

    for line in lines:
        await process_line(client, line)

@client.event
async def on_ready():
    print(f"[BOT] Gotowy – {client.user}")
    update_status.start()
    check_logs.start()
    print("[BOT] Natychmiastowe pierwsze sprawdzenie...")
    await check_logs()   # pierwsze wywołanie od razu

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
