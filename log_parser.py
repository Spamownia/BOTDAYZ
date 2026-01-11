# log_parser.py – KOLOROWY TEKST ANSI (logi i chat w kolorach)

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

    # 1. KOLEJKOWANIE – zielony tekst ANSI
    if "[Login]: Adding player" in line:
        match = re.search(r'Adding player (\w+) \((\d+)\)', line)
        if match:
            name = match.group(1)
            message_line = f"Login → Gracz {name} → Dodany do kolejki logowania"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(f"```ansi\n[32m🟢 {message_line}[0m\n```")
        return

    # 2. FINALNE POŁĄCZENIE – zielony tekst ANSI
    if 'Player "' in line and "is connected" in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1)
            steamid = match.group(2)

            player_login_times[name] = current_time

            message_line = f"Połączono → {name} (SteamID: {steamid})"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(f"```ansi\n[32m🟢 {message_line}[0m\n```")
        return

    # 3. WYLOGOWANIE – czerwony tekst ANSI
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

            message_line = f"Rozłączono → {name} ({guid}) → {time_online_str}"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(f"```ansi\n[31m🔴 {message_line}[0m\n```")
        return

    # 4. CHAT – różne kolory ANSI (jak wcześniej)
    if match := re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line):
        chat_type = match.group(1)          # Global, Admin, Team, Direct...
        player = match.group(2)
        message_text = match.group(3)

        # Godzina z logu lub aktualna
        time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
        chat_time = time_match.group(1) if time_match else current_time.strftime("%H:%M:%S")

        # Emotki na samym początku
        emoji_map = {
            "Global": "💬 ",
            "Admin":  "🛡️ ",
            "Team":   "👥 ",
            "Direct": "❗ ",
            "Unknown": "❓ "
        }
        emoji = emoji_map.get(chat_type, emoji_map["Unknown"])

        # Kolory ANSI – tekst kolorowy
        ansi_color_map = {
            "Global": "[32m",   # zielony
            "Admin":  "[31m",   # czerwony
            "Team":   "[34m",   # niebieski
            "Direct": "[37m",   # biały / jasnoszary
            "Unknown": "[0m"
        }
        color_code = ansi_color_map.get(chat_type, ansi_color_map["Unknown"])

        # Wybór kanału Discord
        discord_channel_id = CHAT_CHANNEL_MAPPING.get(chat_type, CHAT_CHANNEL_MAPPING["Unknown"])
        channel = client.get_channel(discord_channel_id)

        if channel:
            # Jedna linia: emotka + nazwa chatu | godzina | nick: wiadomość
            message_line = f"{emoji}{chat_type} | {chat_time} | {player}: {message_text}"

            # Wysyłamy w bloku ansi z kolorem tekstu
            await channel.send(f"```ansi\n{color_code}{message_line}[0m\n```")

        return

    # 5. COT – akcje admina
    if "[COT]" in line:
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **COT Akcja**\n`{line}`")
        return

    # 6. DEBUG – wyłącz po testach
    if CHANNEL_IDS.get("debug"):
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line[:1897] + "..." if len(line) > 1900 else line
            await debug_channel.send(f"```log\n{content}\n```")
