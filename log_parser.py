# log_parser.py
import re
from datetime import datetime
import os
import time
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed
from collections import defaultdict

last_death_time = defaultdict(float)  # victim.lower() → timestamp ostatniego killa/death
player_login_times = {}
guid_to_name = {}                     # guid → nick dla KICK/BAN

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

    # Podsumowanie co 30 sekund
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

    # 2. Rozłączono / Kick / Ban
    if ("disconnected" in line.lower() or "has been disconnected" in line.lower() or
        "kicked" in line.lower() or "banned" in line.lower()) and 'Player ' in line:
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
        if is_kick and "connection with host has been lost" in line.lower():
            is_kick = False
        if is_ban:
            emoji = "☠️"
            color = "[31m"
            extra = " (BAN)"
        elif is_kick:
            emoji = "⚡"
            color = "[38;5;208m"
            extra = " (KICK)"
        else:
            emoji = "🔴"
            color = "[31m"
            extra = ""
        msg = f"{date_str} | {log_time} {emoji} Rozłączono → {name} (ID: {guid}) → {time_online}{extra}"
        ch = client.get_channel(CHANNEL_IDS["connections"])
        if ch:
            await ch.send(f"```ansi\n{color}{msg}[0m\n```")
        return

    # 3. COT + Kick from COT
    if "[COT]" in line:
        if "Kicked" in line:
            detected_events["disconnect"] += 1
            match = re.search(r'Kicked \[guid=(?P<guid>[^\]]+)\]', line)
            guid = match.group("guid") if match else "brak"
            name = guid_to_name.get(guid, "????")
            msg = f"{date_str} | {log_time} ⚡ KICK: {name} (guid={guid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[38;5;208m{msg}[0m\n```")
            return
        match = re.search(r'\[COT\] (?P<steamid>\d{17,}): (?P<action>.+?)(?: \[guid=(?P<guid>[^\]]+)\])?$', line)
        if match:
            detected_events["cot"] += 1
            steamid = match.group("steamid")
            action = match.group("action").strip()
            guid = match.group("guid") or "brak"
            msg = f"{date_str} | {log_time} 🛡️ [COT] {steamid} | {action} [guid={guid}]"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # 4. Hit / Kill / Death
    if any(kw in line.lower() for kw in ["hit by", "killed by", "died.", "char_debug - kill", "player killed"]):

        # 4.1 Zabójstwo (kill) – czerwony tekst
        kill_patterns = [
            # Kill by player
            r'Player "(?P<victim>[^"]+)" .*killed by Player "(?P<attacker>[^"]+)" .*with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters',
            # Kill by non-player (Infected, FallDamage itp.)
            r'Player "(?P<victim>[^"]+)" .*killed by (?P<attacker>[^ ]+)(?: with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters)?',
            # CHAR_DEBUG - KILL
            r'CHAR_DEBUG - KILL: Player "(?P<victim>[^"]+)" killed by (?P<attacker>[^ ]+)',
        ]

        for pattern in kill_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                victim = match.group("victim").strip()
                victim_key = victim.lower()
                if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                    return

                last_death_time[victim_key] = now
                detected_events["kill"] += 1
                detected_events["hit"] -= 1

                attacker = match.groupdict().get("attacker", "nieznany")
                weapon   = match.groupdict().get("weapon",   "brak")
                dist     = match.groupdict().get("dist",     "0")

                msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist} m"
                ch = client.get_channel(CHANNEL_IDS["kills"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")
                return

        # 4.2 Zwykła śmierć (died.)
        if "died." in line:
            match = re.search(r'Player "(?P<victim>[^"]+)" .*died.', line, re.IGNORECASE)
            if match:
                victim = match.group("victim").strip()
                victim_key = victim.lower()
                if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                    return

                last_death_time[victim_key] = now
                detected_events["kill"] += 1

                cause = "nieznana przyczyna"
                if "fall" in line.lower():
                    cause = "upadek"
                elif any(w in line.lower() for w in ["zombie", "infected"]):
                    cause = "zombie / infekcja"
                elif any(w in line.lower() for w in ["starv", "hunger", "thirst"]):
                    cause = "głód / odwodnienie"

                msg = f"{date_str} | {log_time} ☠️ {victim} zmarł – {cause}"
                ch = client.get_channel(CHANNEL_IDS["kills"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")
                return

        # 4.3 Hit – czytelny format, bez zbędnych ?
        hit_patterns = [
            # Hit by player
            r'Player "(?P<victim>[^"]+)" .*hit by Player "(?P<attacker>[^"]+)" .*into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+\)) with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters',
            # Hit by non-player (Infected itp.)
            r'Player "(?P<victim>[^"]+)" .*hit by (?P<attacker>[^ ]+) into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+\))',
            # Ogólny fallback
            r'Player "(?P<victim>[^"]+)" .*hit by (?P<attacker>[^ ]+) .*for (?P<dmg>[\d.]+) damage',
        ]

        for pattern in hit_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                victim   = match.group("victim").strip()
                attacker = match.group("attacker").strip()
                dmg      = match.groupdict().get("dmg",    "?")
                part     = match.groupdict().get("part",   "")
                ammo     = match.groupdict().get("ammo",   "")
                weapon   = match.groupdict().get("weapon", "")
                dist     = match.groupdict().get("dist",   "")
                hp_match = re.search(r'\[HP: (?P<hp>[\d.]+)\]', line)
                hp = float(hp_match.group("hp")) if hp_match else None

                is_dead = (hp is not None and hp <= 0) or "(DEAD)" in line

                if is_dead:
                    return  # Pomijamy hity z (DEAD) lub HP=0 – niech kill block obsłuży

                color = "[33m" if (hp and hp < 30) else "[38;5;226m"
                emoji = "🔥" if (hp and hp < 30) else "⚡"
                extra = f" (HP: {hp:.1f})" if hp is not None else ""
                part_str = f" w {part}" if part else ""
                ammo_str = f" ({ammo})" if ammo else ""
                weapon_str = f" z {weapon}" if weapon else ""
                dist_str = f" z {dist}m" if dist else ""
                msg = f"{date_str} | {log_time} {emoji} {victim}{extra}{part_str} trafiony przez {attacker} za {dmg} dmg{ammo_str}{weapon_str}{dist_str}"
                ch = client.get_channel(CHANNEL_IDS["damages"])
                if ch:
                    await ch.send(f"```ansi\n{color}{msg}[0m\n```")
                return

    # 5. Chat
    if "[Chat -" in line:
        match = re.search(r'\[Chat - (?P<channel_type>[^\]]+)\]\("(?P<player>[^"]+)"\(id=[^)]+\)\): (?P<message>.*)', line)
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
            else:
                fallback_ch = client.get_channel(CHANNEL_IDS["connections"])
                if fallback_ch:
                    await fallback_ch.send(f"```ansi\n{ansi_color}{msg} ({channel_type} fallback)[0m\n```")
            return

    # 6. Nierozpoznane
    detected_events["other"] += 1
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
    except Exception as e:
        print(f"[BŁĄD ZAPISU UNPARSED] {e}")
