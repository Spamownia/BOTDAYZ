# main.py – główny plik bota z aktualizacją statusu graczy online

import discord
from discord.ext import commands, tasks
import asyncio
import requests
from config import DISCORD_TOKEN, CHECK_INTERVAL
from log_parser import process_line
from ftp_watcher import DayZLogWatcher

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)
watcher = DayZLogWatcher()

# ID serwera z BattleMetrics – ZMIEŃ NA SWOJE!
BATTLEMERTICS_SERVER_ID = "37055320"  # przykład – wstaw swoje

# Co ile sekund aktualizować status bota
PLAYERS_UPDATE_INTERVAL = 60

@client.event
async def on_ready():
    print(f"Zalogowano jako {client.user}")
    update_players_status.start()  # start pętli aktualizacji statusu

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

            await client.change_presence(
                activity=discord.Game(name=status_text)
            )
            print(f"[STATUS] Zaktualizowano: {status_text}")
        else:
            await client.change_presence(activity=None)
            print("[STATUS] Błąd pobierania z BattleMetrics")
    except Exception as e:
        print(f"[STATUS] Błąd: {e}")
        await client.change_presence(activity=None)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Tu możesz dodać obsługę komend, jeśli chcesz
    await client.process_commands(message)

# Główna pętla sprawdzania logów (pozostała bez zmian)
async def check_logs():
    while True:
        try:
            content = watcher.get_new_content()
            if content:
                for log_line in content.splitlines():
                    if log_line.strip():
                        await process_line(client, log_line)
        except Exception as e:
            print(f"Błąd sprawdzania logów: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# Uruchomienie bota
async def main():
    async with client:
        client.loop.create_task(check_logs())
        await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
