# log_parser.py – WERSJA Z CZASEM ONLINE PRZY WYLOGOWANIU

import re
from datetime import datetime, timedelta
from discord import Embed
from config import CHANNEL_IDS

# Słownik do przechowywania czasu logowania gracza (SteamID → datetime obiektu połączenia)
player_login_times = {}

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    current_time = datetime.utcnow()  # przybliżony czas serwera (DayZ używa UTC)

    # === 1. DODANIE DO KOLEJKI LOGOWANIA ===
    if "[Login]: Adding player" in line:
        match = re.search(r'Adding player (\w+) \((\d+)\)', line)
        if match:
            name = match.group(1)
            message = f"🟢 **Login** → Gracz {name} → Dodany do kolejki logowania"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === 2. FINALNE POŁĄCZENIE – zapisujemy czas logowania ===
    if 'Player "' in line and "is connected" in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1)
            steamid = match.group(2)

            # Zapamiętujemy przybliżony czas połączenia
            player_login_times[steamid] = current_time

            message = f"🟢 **Połączono** → {name} (SteamID: {steamid})"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === 3. WYLOGOWANIE Z .ADM – z obliczeniem czasu online ===
    if "has been disconnected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
        if match:
            name = match.group(1)
            guid = match.group(2)  # to jest GUID

            # Szukamy czasu logowania po SteamID – jeśli nie ma, próbujemy po GUID (rzadko, ale na wszelki wypadek)
            time_online_str = "czas nieznany"
            for steamid, login_time in player_login_times.items():
                if steamid in guid or guid in steamid:  # luźne dopasowanie
                    delta = current_time - login_time
                    minutes = int(delta.total_seconds() // 60)
                    seconds = int(delta.total_seconds() % 60)
                    time_online_str = f"{minutes} min {seconds} s"
                    # Usuwamy z pamięci po wylogowaniu
                    del player_login_times[steamid]
                    break

            message = f"🔴 **Rozłączono** → {name} ({guid}) → {time_online_str}"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === CHAT Z .ADM ===
    if match := re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line):
        channel_type, player, msg = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            embed = Embed(
                title=f"💬 Chat [{channel_type}]",
                color=0x00FFFF,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Gracz", value=player, inline=True)
            embed.add_field(name="Wiadomość", value=msg, inline=False)
            embed.set_footer(text="DayZ Server Log")
            await channel.send(embed=embed)
        return

    # === COT – akcje admina ===
    if "[COT]" in line:
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **COT Akcja**\n`{line}`")
        return

    # === DEBUG – opcjonalny ===
    if CHANNEL_IDS["debug"]:
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line
            if len(content) > 1900:
                content = content[:1897] + "..."
            await debug_channel.send(f"```log\n{content}\n```")
