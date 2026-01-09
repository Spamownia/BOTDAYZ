# log_parser.py – WERSJA Z DZIAŁAJĄCYM CZASEM ONLINE PRZY WYLOGOWANIU

import re
from datetime import datetime, timedelta
from discord import Embed
from config import CHANNEL_IDS

# Słownik: nazwa gracza → (steamid, guid, czas_logowania)
player_data = {}

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    current_time = datetime.utcnow()

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

    # === 2. FINALNE POŁĄCZENIE – zapisujemy dane gracza ===
    if 'Player "' in line and "is connected" in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1)
            steamid = match.group(2)

            # Zapamiętujemy czas i SteamID pod nazwą gracza
            player_data[name] = {
                "steamid": steamid,
                "guid": None,  # GUID przyjdzie później z .ADM
                "login_time": current_time
            }

            message = f"🟢 **Połączono** → {name} (SteamID: {steamid})"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === 3. WYLOGOWANIE Z .ADM – obliczamy czas online ===
    if "has been disconnected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
        if match:
            name = match.group(1)
            guid = match.group(2)

            # Aktualizujemy GUID, jeśli jeszcze nie mamy
            if name in player_data:
                player_data[name]["guid"] = guid

            # Obliczamy czas online
            time_online_str = "czas nieznany"
            if name in player_data and player_data[name]["login_time"]:
                delta = current_time - player_data[name]["login_time"]
                minutes = int(delta.total_seconds() // 60)
                seconds = int(delta.total_seconds() % 60)
                time_online_str = f"{minutes} min {seconds} s"

                # Czyścimy z pamięci
                del player_data[name]

            identifier = guid if guid else "nieznany"
            message = f"🔴 **Rozłączono** → {name} ({identifier}) → {time_online_str}"

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
