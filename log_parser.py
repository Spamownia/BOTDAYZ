# log_parser.py – BEZ ŻADNYCH GWIAZDEK, KOLOR ANSI

import re
from datetime import datetime
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

player_login_times = {}

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    current_time = datetime.utcnow()

    # 1. KOLEJKOWANIE – zielony
    if "[Login]: Adding player" in line:
        match = re.search(r'Adding player (\w+) \((\d+)\)', line)
        if match:
            name = match.group(1)
            message_line = f"Login → Gracz {name} → Dodany do kolejki logowania"
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(f"```ansi\n[32m🟢 {message_line}[0m\n```")
        return

    # 2. FINALNE POŁĄCZENIE – zielony, bez gwiazdek
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

    # 3. WYLOGOWANIE – czerwony, bez gwiazdek
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

    # 4. CHAT – bez gwiazdek, tylko emotka + nazwa | godzina | nick: treść
    if match := re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line):
        chat_type = match.group(1)
        player = match.group(2)
        message_text = match.group(3)

        time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
        chat_time = time_match.group(1) if time_match else current_time.strftime("%H:%M:%S")

        emoji_map = {
            "Global": "💬 ",
            "Admin":  "🛡️ ",
            "Team":   "👥 ",
            "Direct": "❗ ",
            "Unknown": "❓ "
        }
        emoji = emoji_map.get(chat_type, emoji_map["Unknown"])

        ansi_color_map = {
            "Global": "[32m",   # zielony
            "Admin":  "[31m",   # czerwony
            "Team":   "[34m",   # niebieski
            "Direct": "[37m",   # biały
            "Unknown": "[0m"
        }
        color_code = ansi_color_map.get(chat_type, ansi_color_map["Unknown"])

        discord_channel_id = CHAT_CHANNEL_MAPPING.get(chat_type, CHAT_CHANNEL_MAPPING["Unknown"])
        channel = client.get_channel(discord_channel_id)

        if channel:
            # Bez gwiazdek: emotka + nazwa | godzina | nick: treść
            message_line = f"{emoji}{chat_type} | {chat_time} | {player}: {message_text}"
            await channel.send(f"```ansi\n{color_code}{message_line}[0m\n```")

        return

    # 5. COT – biały ANSI, format: ADMIN | STEAMID | treść (bez gwiazdek)
    if "[COT]" in line:
        steamid_match = re.search(r'\[COT\]\s*(\d{17,}):', line)
        steamid = steamid_match.group(1) if steamid_match else "nieznany"

        action_text = line.split(":", 1)[1].strip() if ":" in line else line.strip()
        action_text = re.sub(r'\[guid=.*?]', '', action_text).strip()

        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            message_line = f"ADMIN | {steamid} | {action_text}"
            await channel.send(f"```ansi\n[37m{message_line}[0m\n```")

        return

    # 6. DEBUG – wyłącz po testach
    if CHANNEL_IDS.get("debug"):
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line[:1897] + "..." if len(line) > 1900 else line
            await debug_channel.send(f"```log\n{content}\n```")
