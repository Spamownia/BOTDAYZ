# log_parser.py – FINALNA WERSJA Z CZASEM ONLINE

import re
from datetime import datetime
from discord import Embed
from config import CHANNEL_IDS

# Słownik: nazwa gracza → czas logowania
player_login_time = {}

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    current_time = datetime.utcnow()

    # === 1. DODANIE DO KOLEJKI ===
    if "[Login]: Adding player" in line:
        match = re.search(r'Adding player (\w+) \((\d+)\)', line)
        if match:
            name = match.group(1)
            message = f"🟢 **Login** → Gracz {name} → Dodany do kolejki logowania"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === 2. FINALNE POŁĄCZENIE – zapisujemy czas ===
    if 'Player "' in line and "is connected" in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1)
            steamid = match.group(2)

            # Zapamiętujemy czas pod nazwą gracza
            player_login_time[name] = current_time

            message = f"🟢 **Połączono** → {name} (SteamID: {steamid})"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === 3. WYLOGOWANIE – z czasem online ===
    if "has been disconnected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
        if match:
            name = match.group(1)
            guid = match.group(2)

            time_online_str = "czas nieznany"
            if name in player_login_time:
                delta = current_time - player_login_time[name]
                minutes = int(delta.total_seconds() // 60)
                seconds = int(delta.total_seconds() % 60)
                time_online_str = f"{minutes} min {seconds} s"
                del player_login_time[name]  # czyścimy

            message = f"🔴 **Rozłączono** → {name} ({guid}) → {time_online_str}"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === CHAT ===
    if match := re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line):
        channel_type, player, msg = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            embed = Embed(title=f"💬 Chat [{channel_type}]", color=0x00FFFF, timestamp=datetime.utcnow())
            embed.add_field(name="Gracz", value=player, inline=True)
            embed.add_field(name="Wiadomość", value=msg, inline=False)
            embed.set_footer(text="DayZ Server Log")
            await channel.send(embed=embed)
        return

    # === COT ===
    if "[COT]" in line:
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **COT Akcja**\n`{line}`")
        return

    # === DEBUG (wyłącz po testach) ===
    if CHANNEL_IDS["debug"]:
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line[:1897] + "..." if len(line) > 1900 else line
            await debug_channel.send(f"```log\n{content}\n```")
