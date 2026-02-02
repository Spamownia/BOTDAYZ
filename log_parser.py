# log_parser.py
import re
from datetime import datetime
import os
import time
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from collections import defaultdict

last_death_time = defaultdict(float)  # victim.lower() → timestamp ostatniego killa
player_login_times = {}               # name.lower() → timestamp połączenia
guid_to_name = {}                     # guid → nick dla kick/ban
UNPARSED_LOG = "unparsed_lines.log"
SUMMARY_INTERVAL = 30
last_summary_time = time.time()
processed_count = 0
detected_events = {
    "join": 0, "disconnect": 0, "cot": 0, "hit": 0, "kill": 0, "chat": 0, "other": 0
}

async def process_line(bot, line: str):
    global last_summary_time, processed_count
    client = bot
    line = line.strip()
    if not line:
        return

    processed_count += 1
    now = time.time()

    if now - last_summary_time >= SUMMARY_INTERVAL:
        summary = f"[PARSER SUMMARY @ {datetime.utcnow().strftime('%H:%M:%S')}] {processed_count} linii | "
        summary += " | ".join(f"{k}: {v}" for k, v in detected_events.items() if v > 0)
        if not any(detected_events.values()):
            summary += " (nic nie wykryto)"
        print(summary)
        last_summary_time = now
        processed_count = 0
        for k in detected_events:
            detected_events[k] = 0

    time_match = re.search(r'^\s*(\d{1,2}:\d{2}:\d{2})(?:.\d+)?', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")
    date_str = datetime.utcnow().strftime("%d.%m.%Y")

    # 1. Połączono (już działa u Ciebie)
    if "is connected" in line and 'Player "' in line:
        match = re.search(
            r'Player\s+"(?P<name>[^"]+)"'
            r'(?:\s*\(?(?:steamID|id)=(?P<guid>[^)]+)?\)?)?'
            r'\s+is connected',
            line, re.IGNORECASE
        )
        if match:
            detected_events["join"] += 1
            name = match.group("name").strip()
            guid = match.group("guid") or "brak"
            player_login_times[name.lower()] = datetime.utcnow()
            if guid != "brak":
                guid_to_name[guid] = name
            msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {guid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            print(f"[PARSER] JOIN: {name} ({guid})")
            return

    # 2. Rozłączono / Disconnect / Kick / Ban
    if any(x in line.lower() for x in ["disconnected", "has been disconnected", "kicked", "banned"]) and 'Player "' in line:
        name_match = re.search(r'Player\s+"(?P<name>[^"]+)"', line)
        name = name_match.group("name").strip() if name_match else "????"
        guid_match = re.search(r'\((?:id|steamID)=(?P<guid>[^)]+)\)', line)
        guid = guid_match.group("guid") if guid_match else "brak"
        if guid in guid_to_name:
            name = guid_to_name[guid]
        detected_events["disconnect"] += 1
        time_online = "nieznany"
        name_key = name.lower()
        if name_key in player_login_times:
            delta = now - player_login_times[name_key].timestamp()
            minutes = int(delta // 60)
            seconds = int(delta % 60)
            time_online = f"{minutes}m {seconds}s"
            del player_login_times[name_key]
        is_kick = "kicked" in line.lower()
        is_ban = "banned" in line.lower()
        if is_kick and "connection with host has been lost" in line.lower():
            is_kick = False
        emoji = "☠️" if is_ban else "⚡" if is_kick else "🔴"
        color = "[31m" if is_ban or not is_kick else "[33m"
        extra = " (BAN)" if is_ban else " (KICK)" if is_kick else ""
        msg = f"{date_str} | {log_time} {emoji} Rozłączono → {name} (ID: {guid}) → {time_online}{extra}"
        ch = client.get_channel(CHANNEL_IDS["connections"])
        if ch:
            await ch.send(f"```ansi\n{color}{msg}[0m\n```")
        print(f"[PARSER] DISCONNECT: {name} ({time_online})")
        return

    # 3. COT – rozszerzona obsługa (wszystkie akcje)
    if "[COT]" in line:
        detected_events["cot"] += 1
        # Przykłady: Activated, GodMode, Teleported, Overcast, Date, Entered Free Camera itp.
        match = re.search(r'\[COT\] (?P<steamid>\d{17,}): (?P<action>.+?)(?: \[guid=(?P<guid>[^]]+)\])?$', line)
        if match:
            steamid = match.group("steamid")
            action = match.group("action").strip()
            guid = match.group("guid") or "brak"
            msg = f"{date_str} | {log_time} 🛡️ [COT] {steamid} | {action} [guid={guid}]"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[33m{msg}[0m\n```")
            print(f"[PARSER] COT: {action}")
            return

    # 4. Chat – obsługa wszystkich kanałów
    if "[Chat -" in line:
        match = re.search(r'\[Chat - (?P<channel_type>[^]]+)\]\("(?P<player>[^"]+)"\(id=[^)]+\)\): (?P<message>.*)', line)
        if match:
            detected_events["chat"] += 1
            channel_type = match.group("channel_type").strip()
            player = match.group("player").strip()
            message = match.group("message").strip() or "[brak]"
            color_map = {"Global": "[34m", "Admin": "[31m", "Team": "[34m", "Direct": "[37m", "Unknown": "[33m"}
            ansi_color = color_map.get(channel_type, color_map["Unknown"])
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            discord_ch_id = CHAT_CHANNEL_MAPPING.get(channel_type, CHANNEL_IDS["chat"])
            ch = client.get_channel(discord_ch_id)
            if ch:
                await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
            print(f"[PARSER] CHAT: {channel_type} | {player}: {message}")
            return

    # 5. Hit / Kill / Death – pełna obsługa (z Twojego starego kodu + poprawki)
    if any(x in line for x in ["hit by", "killed by", "died.", "bled out"]):
        hp_match = re.search(r'\[HP: (?P<hp>[\d.]+)\]', line)
        hp = float(hp_match.group("hp")) if hp_match else None

        # Hit od Infected / Zombie
        if "hit by Infected" in line:
            match = re.search(r'Player "(?P<victim>[^"]+)" .* pos=<[^>]+>\)\[HP: (?P<hp>[\d.]+)\] hit by Infected into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<type>MeleeInfected(?:Long)?)\)', line)
            if match:
                detected_events["hit"] += 1
                victim = match.group("victim")
                hp = float(match.group("hp"))
                part = match.group("part")
                dmg = match.group("dmg")
                dmg_type = match.group("type")
                is_dead = hp <= 0
                emoji = "☠️" if is_dead else "🧟"
                color = "[31m" if is_dead else "[33m"
                extra = " (ŚMIERĆ od zombie)" if is_dead else f" (HP: {hp:.1f})"
                msg = f"{date_str} | {log_time} {emoji} {victim}{extra} → trafiony przez Infected w {part} za {dmg} dmg ({dmg_type})"
                ch = client.get_channel(CHANNEL_IDS["damages"] if not is_dead else CHANNEL_IDS["kills"])
                if ch:
                    await ch.send(f"```ansi\n{color}{msg}[0m\n```")
                return

        # Pozostałe hity / kill – jeśli masz więcej wariantów, dodaj tutaj

    # Nierozpoznane linie
    detected_events["other"] += 1
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
        print(f"[PARSER] Linia nierozpoznana → zapisana do unparsed_lines.log")
    except Exception as e:
        print(f"[PARSER] Błąd zapisu unparsed: {e}")
