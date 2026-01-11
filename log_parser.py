# log_parser.py – WERSJA Z MINIMALISTYCZNYMI EMBEDAMI JAK NA SCREENIE

import re
from datetime import datetime
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

# Słownik: nazwa gracza → czas pełnego zalogowania
player_login_times = {}

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    current_time = datetime.utcnow()

    # 1. KOLEJKOWANIE (bez zmian)
    if "[Login]: Adding player" in line:
        match = re.search(r'Adding player (\w+) \((\d+)\)', line)
        if match:
            name = match.group(1)
            message = f"🟢 **Login** → Gracz {name} → Dodany do kolejki logowania"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # 2. FINALNE POŁĄCZENIE (bez zmian)
    if 'Player "' in line and "is connected" in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1)
            steamid = match.group(2)

            player_login_times[name] = current_time

            message = f"🟢 **Połączono** → {name} (SteamID: {steamid})"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # 3. WYLOGOWANIE (bez zmian)
    if "has been disconnected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
        if match:
            name = match.group(1)
            guid = match.group(2)

            time_online_str = "czas nieznany"
            if name in player_login_times:
                delta = current_time - player_login_times[name]
                minutes = int(delta.total_seconds() // 60)
                seconds = int(delta.total_seconds() % 60)
                time_online_str = f"{minutes} min {seconds} s"
                del player_login_times[name]

            message = f"🔴 **Rozłączono** → {name} ({guid}) → {time_online_str}"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # 4. CHAT – MINIMALISTYCZNE EMBEDY JAK NA SCREENIE
    if match := re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line):
        chat_type = match.group(1)          # Global, Admin, Team, Direct...
        player = match.group(2)
        message_text = match.group(3)

        # Godzina z logu lub aktualna (mała i szara na dole)
        time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
        chat_time = time_match.group(1) if time_match else current_time.strftime("%H:%M:%S")

        # Kolory paska embeda
        color_map = {
            "Global": 0x2ECC71,    # jasny zielony
            "Admin":  0xE74C3C,    # czerwony
            "Team":   0xF1C40F,    # żółty
            "Direct": 0xECF0F1,    # bardzo jasny szary/biały
            "Unknown": 0x95A5A6
        }
        embed_color = color_map.get(chat_type, color_map["Unknown"])

        # Wybór kanału Discord
        discord_channel_id = CHAT_CHANNEL_MAPPING.get(chat_type, CHAT_CHANNEL_MAPPING["Unknown"])
        channel = client.get_channel(discord_channel_id)

        if channel:
            embed = Embed(
                description=f"{player}: {message_text}",
                color=embed_color
            )
            embed.set_author(name=chat_type, icon_url=None)  # nazwa chatu na górze
            embed.timestamp = current_time
            embed.set_footer(text=chat_time)  # godzina mała i szara na dole

            await channel.send(embed=embed)

        return

    # 5. COT – bez zmian
    if "[COT]" in line:
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **COT Akcja**\n`{line}`")
        return

    # 6. DEBUG – bez zmian
    if CHANNEL_IDS.get("debug"):
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line[:1897] + "..." if len(line) > 1900 else line
            await debug_channel.send(f"```log\n{content}\n```")
