import re
from datetime import datetime
import os
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed

player_login_times = {}

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    if not line:
        return

    print(f"[DEBUG PARSER] Przetwarzam linię: {line}")

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")

    # 1. Dodany do kolejki logowania – zielony ANSI
    if "[Login]:" in line and "Adding player" in line:
        match = re.search(r'Adding player ([^ ]+) \((\d+)\) to login queue', line)
        if match:
            name = match.group(1)
            dpnid = match.group(2)
            msg = f"{date_str} | {log_time} 🟢 Login → Gracz {name} → Dodany do kolejki logowania"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 2. Połączono – zielony ANSI
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\((?:steamID|id)=([^)]+)\) is connected', line)
        if match:
            name = match.group(1).strip()
            id_val = match.group(2)
            player_login_times[name] = datetime.utcnow()
            msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {id_val})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 3. Rozłączono – czerwony ANSI + czas online
    if "has been disconnected" in line:
        match = re.search(r'Player "([^"]+)"\((?:steamID|id)=([^)]+)\) has been disconnected', line)
        if match:
            name = match.group(1).strip()
            id_val = match.group(2)
            time_online = "nieznany"
            if name in player_login_times:
                delta = datetime.utcnow() - player_login_times[name]
                minutes = int(delta.total_seconds() // 60)
                seconds = int(delta.seconds % 60)
                time_online = f"{minutes} min {seconds} s"
                del player_login_times[name]
            msg = f"{date_str} | {log_time} 🔴 Rozłączono → {name} ({id_val}) → {time_online}"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return

    # 4. COT – biały ANSI
    if "[COT]" in line:
        match = re.search(r'\[COT\] (\d{17,}): (.+?)(?: \[guid=([^]]+)\])?$', line)
        if match:
            steamid = match.group(1)
            action = match.group(2).strip()
            guid = match.group(3) or "brak"
            msg = f"{date_str} | {log_time} 🛡️ [COT] {steamid} | {action} [guid={guid}]"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # 5. Hit / Death – żółty/czerwony
    if "hit by" in line or "[HP: 0]" in line:
        match_hit = re.search(r'Player "([^"]+)" .*hit by Infected into (\w+)\(\d+\) for ([\d.]+) damage \(([^)]+)\)', line)
        if match_hit:
            name, part, dmg, cause = match_hit.groups()
            hp_match = re.search(r'\[HP: ([\d.]+)\]', line)
            hp = hp_match.group(1) if hp_match else "nieznane"
            color = "[31m" if hp == "0" else "[33m"
            emoji = "☠️" if hp == "0" else "⚠️"
            msg = f"{date_str} | {log_time} {emoji} {name} trafiony zombie w {part} za {dmg} dmg (HP: {hp})"
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return

    # AUTO SAVE – WYŁĄCZONY (zakomentowany)
    # if "CHAR_DEBUG - SAVE" in line:
    #     msg = f"{date_str} | {log_time} 💾 Autozapis gracza zakończony"
    #     ch = client.get_channel(CHANNEL_IDS["admin"])
    #     if ch:
    #         await ch.send(f"```ansi\n[32m{msg}[0m\n```")
    #     return

    # CHAT
    if "[Chat -" in line:
        match = re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line)
        if match:
            channel_type, player, message = match.groups()
            color_map = {
                "Global": "[32m",
                "Admin": "[31m",
                "Team": "[34m",
                "Direct": "[37m",
                "Unknown": "[33m"
            }
            ansi_color = color_map.get(channel_type.strip(), color_map["Unknown"])
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            discord_ch_id = CHAT_CHANNEL_MAPPING.get(channel_type.strip(), CHANNEL_IDS["chat"])
            ch = client.get_channel(discord_ch_id)
            if ch:
                await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
            return

    # Zapisuj nierozpoznane linie do pliku
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
        print(f"[UNPARSED → plik] {line[:120]}...")
    except Exception as e:
        print(f"[BŁĄD ZAPISU UNPARSED] {e}")
