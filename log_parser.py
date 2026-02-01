
To jest Twoja wersja – jeśli nadal nie działa, to problem jest w regex – z toola wiemy, że nie pasuje.

Aby dopasować, w bloku if not killed: dodaj po match_hit_player:

match_hit_infected = re.search(r'Player "(?P<victim>[^"]+)" $$   (?:id=[^)]+ pos=<[^>]+>)? \$\$\$\$ HP: (?P<hp>[\d.]+)   $$ hit by (?P<attacker>[^ ]+) into (?P<part>\w+)$$   \d+   $$ for (?P<dmg>[\d.]+) damage $$   (?P<ammo>[^)]+)   $$', line)
if match_hit_infected:
    # the same code as for match_hit_player

Yes, duplicate the code for match_hit_infected.

This way, it's consistent with your style.

Final code with this addition.<|control12|>```python
# log_parser.py
import re
from datetime import datetime
import os
import time
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed
from collections import defaultdict

last_death_time = defaultdict(float) # victim.lower() → timestamp ostatniego killa
player_login_times = {}
guid_to_name = {} # Mapowanie guid → nick dla KICK/BAN

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
    time_match = re.search(r'^\s*(\d{1,2}:\d{2}:\d{2})(?:\.\d+)?', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")
    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")
    # 1. Połączono
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "(?P<name>[^"]+)"\((?:steamID|id)=(?P<guid>[^)]+)\) is connected', line)
        if match:
            detected_events["join"] += 1
            name = match.group("name").strip()
            guid = match.group("guid")
            player_login_times[name] = datetime.utcnow()
            guid_to_name[guid] = name
            msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {guid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return
    # 2. Rozłączono + Kick/Ban – poprawione rozróżnianie
    if ("disconnected" in line.lower() or "has been disconnected" in line.lower() or "kicked" in line.lower() or "banned" in line.lower()) and 'Player ' in line:
        name_match = re.search(r'Player\s*(?:"([^"]+)"|([^(]+))', line, re.IGNORECASE)
        name = (name_match.group(1) or name_match.group(2)).strip() if name_match else "????"
        id_match = re.search(r'\((?:id|steamID|uid)?=(?P<guid>[^ )]+)(?:\s+pos=<[^>]+>)?\)', line, re.IGNORECASE)
        guid = id_match.group("guid").strip() if id_match else "brak"
        if guid in guid_to_name:
            name = guid_to_name[guid]
        detected_events["disconnect"] += 1
        time_online = "nieznany"
        if name in player_login_times:
            delta = datetime.utcnow() - player_login_times[name]
            minutes = int(delta.total_seconds() // 60)
            seconds = int(delta.total_seconds() % 60)
            time_online = f"{minutes} min {seconds} s"
            del player_login_times[name]
        is_kick = "kicked" in line.lower() or "Kicked" in line
        is_ban = "banned" in line.lower() or "Banned" in line
        # Specjalny warunek: jeśli to "kicked from server: 4 (Connection with host has been lost.)", traktuj jako normalny disconnect
        if is_kick and "connection with host has been lost" in line.lower():
            is_kick = False
        if is_ban:
            emoji = "☠️"
            color = "[31m"
            extra = " (BAN)"
        elif is_kick:
            emoji = "⚡"
            color = "[38;5;208m" # pomara
