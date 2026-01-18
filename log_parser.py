import re
from datetime import datetime
import os
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed

player_login_times = {}

# Plik do zapisywania nierozpoznanych linii (debug bez spamowania Discorda)
UNPARSED_LOG = "unparsed_lines.log"

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    if not line:
        return

    print(f"[DEBUG PARSER] Przetwarzam linię: {line}")

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    # Format daty: dd.mm.yyyy
    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")

    # 1. Dodany do kolejki logowania – zielony
    if "[Login]:" in line and "Adding player" in line:
        match = re.search(r'Adding player ([^ ]+) \((\d+)\) to login queue', line)
        if match:
            name = match.group(1)
            dpnid = match.group(2)
            msg = f"🟢 {date_str} | {log_time} Login → Gracz {name} → Dodany do kolejki logowania"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```{msg}```")
            return

    # 2. Połączono – zielony
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1).strip()
            steamid = match.group(2)
            player_login_times[name] = datetime.utcnow()
            msg = f"🟢 {date_str} | {log_time} Połączono → {name} (SteamID: {steamid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```{msg}```")
            return

    # 3. Rozłączono – czerwony + czas online
    if any(kw in line.lower() for kw in ["disconnected", "has quit", "left the server", "logged out", "has been disconnected", "quit", "left"]):
        match = re.search(r'Player "([^"]+)"\((?:steamID|id)=([^)]+)\)', line)
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
            msg = f"🔴 {date_str} | {log_time} Rozłączono → {name} ({id_val}) → {time_online}"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```{msg}```")
            return

    # 4. COT (bez zmian)
    if "[COT]" in line:
        match = re.search(r'\[COT\] (\d{17,}): (.+?)(?: \[guid=([^]]+)\])?$', line)
        if match:
            steamid = match.group(1)
            action = match.group(2).strip()
            guid = match.group(3) or "brak"
            msg = f"{date_str} | {log_time} ADMIN | [COT] {steamid} | {action} [guid={guid}]"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # 5. AUTO SAVE (bez zmian)
    if "CHAR_DEBUG - SAVE" in line:
        msg = f"{date_str} | {log_time} 💾 Autozapis gracza zakończony"
        ch = client.get_channel(CHANNEL_IDS["admin"])
        if ch:
            await ch.send(f"```ansi\n[32m{msg}[0m\n```")
        return

    # 6. CHAT MESSAGES (bez zmian)
    if "Chat(" in line:
        patterns = [
            r'Chat\("([^"]+)"\)\(([^)]+)\): "([^"]+)"',
            r'Chat\("([^"]+)"\): "([^"]+)"',
            r'Player "([^"]+)" said in channel ([^:]+): "([^"]+)"'
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                if len(match.groups()) == 3:
                    name, channel, message = match.groups()
                else:
                    name, message = match.groups()
                    channel = "Unknown"

                color_codes = {
                    "Global":   "[32m",
                    "Team":     "[36m",
                    "Direct":   "[35m",
                    "Admin":    "[34m",
                    "Unknown":  "[33m"
                }
                ansi_color = color_codes.get(channel.strip(), color_codes["Unknown"])
                
                msg = f"{date_str} | {log_time} [{channel.strip()}] {name}: {message}"
                
                discord_channel_id = CHAT_CHANNEL_MAPPING.get(channel.strip(), CHAT_CHANNEL_MAPPING["Unknown"])
                ch = client.get_channel(discord_channel_id)
                if ch:
                    await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
                return

    # Zapisuj nierozpoznane linie do pliku (bez wysyłania na Discord)
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
        print(f"[UNPARSED → plik] {line[:120]}...")
    except Exception as e:
        print(f"[BŁĄD ZAPISU UNPARSED] {e}")
