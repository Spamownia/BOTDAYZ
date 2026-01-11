# log_parser.py – WSZYSTKIE CHATY W BLOKU yaml (żółtawy kolor)

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

    # 1. KOLEJKOWANIE
    if "[Login]: Adding player" in line:
        match = re.search(r'Adding player (\w+) \((\d+)\)', line)
        if match:
            name = match.group(1)
            message = f"🟢 Login → Gracz {name} → Dodany do kolejki logowania"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # 2. FINALNE POŁĄCZENIE
    if 'Player "' in line and "is connected" in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1)
            steamid = match.group(2)

            player_login_times[name] = current_time

            message = f"🟢 Połączono → {name} (SteamID: {steamid})"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # 3. WYLOGOWANIE – z czasem online
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

            message = f"🔴 Rozłączono → {name} ({guid}) → {time_online_str}"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # 4. CHAT – wszystkie w bloku yaml (żółtawy kolor), zaczyna się od emotki
    if match := re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line):
        chat_type = match.group(1)          # Global, Admin, Team, Direct...
        player = match.group(2)
        message_text = match.group(3)

        # Godzina z logu lub aktualna
        time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
        chat_time = time_match.group(1) if time_match else current_time.strftime("%H:%M:%S")

        # Emotki na samym początku
        emoji_map = {
            "Global": "💬 ",    # dymek
            "Admin":  "🛡️ ",    # tarcza/admin
            "Team":   "👥 ",    # ludziki/grupa
            "Direct": "❗ ",    # wykrzyknik
            "Unknown": "❓ "
        }
        emoji = emoji_map.get(chat_type, emoji_map["Unknown"])

        # Wybór kanału Discord
        discord_channel_id = CHAT_CHANNEL_MAPPING.get(chat_type, CHAT_CHANNEL_MAPPING["Unknown"])
        channel = client.get_channel(discord_channel_id)

        if channel:
            # Jedna linia: emotka + nazwa chatu | godzina | nick: wiadomość
            message_line = f"{emoji}{chat_type} | {chat_time} | {player}: {message_text}"

            # Wszystkie chaty w bloku yaml (żółtawy kolor tekstu)
            await channel.send(f"```yaml\n{message_line}\n```")

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
