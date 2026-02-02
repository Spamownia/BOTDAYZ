# log_parser.py
import re
from datetime import datetime
import os
import time
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed
from collections import defaultdict

last_death_time = defaultdict(float)  # victim.lower() → timestamp ostatniego killa
player_login_times = {}
guid_to_name = {}  # Mapowanie guid → nick dla KICK/BAN
UNPARSED_LOG = "unparsed_lines.log"
SUMMARY_INTERVAL = 30
last_summary_time = time.time()
processed_count = 0
detected_events = {
    "join": 0, "disconnect": 0, "cot": 0, "hit": 0, "kill": 0, "chat": 0, "other": 0
}

# Dodane: Zbiór do deduplikacji wydarzeń connect/disconnect na podstawie czasu, nazwy i akcji
processed_events = set()

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
    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")

    # Klucz deduplikacji - używamy log_time + name + action
    def get_event_key(action, name):
        return (log_time, name.lower(), action)

    # 1. Połączono
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "(?P<name>[^"]+)"(?:\s*\((?:steamID|id)=(?P<guid>[^)]+)\))?\s+is connected', line)
        if match:
            name = match.group("name").strip()
            guid = match.group("guid") or "brak"
            event_key = get_event_key('connect', name)
            if event_key in processed_events:
                print(f"[DEDUP] Pominięto duplikat connect: {name} @ {log_time}")
                return
            processed_events.add(event_key)
            detected_events["join"] += 1
            player_login_times[name] = datetime.utcnow()
            guid_to_name[guid] = name
            msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {guid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 2. Rozłączono + Kick/Ban
    if any(x in line.lower() for x in ["disconnected", "has been disconnected", "kicked", "banned"]) and 'Player ' in line:
        name_match = re.search(r'Player\s*(?:"([^"]+)"|([^(]+))', line, re.IGNORECASE)
        name = (name_match.group(1) or name_match.group(2)).strip() if name_match else "????"
        id_match = re.search(r'((?:id|steamID|uid)?=(?P<guid>[^ )]+)(?:\s+pos=<[^>]+>)?)', line, re.IGNORECASE)
        guid = id_match.group("guid").strip() if id_match else "brak"
        if guid in guid_to_name:
            name = guid_to_name[guid]
        event_key = get_event_key('disconnect', name)
        if event_key in processed_events:
            print(f"[DEDUP] Pominięto duplikat disconnect: {name} @ {log_time}")
            return
        processed_events.add(event_key)
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
            color = "[33m"
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
            match = re.search(r'Kicked [guid=(?P<guid>[^]]+)]', line)
            guid = match.group("guid") if match else "brak"
            name = guid_to_name.get(guid, "????")
            msg = f"{date_str} | {log_time} ⚡ KICK: {name} (guid={guid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[33m{msg}[0m\n```")
            return
        detected_events["cot"] += 1
        msg = f"{date_str} | {log_time} 🔧 [COT] {line.split('[COT]')[1].strip()}"
        ch = client.get_channel(CHANNEL_IDS.get("admin", CHANNEL_IDS["connections"]))
        if ch:
            await ch.send(f"```ansi\n[35m{msg}[0m\n```")
        return

    # 4. Trafienia / Śmierci / Zabójstwa
    if "hit by" in line:
        detected_events["hit"] += 1
        victim_key = ""
        # Hit by zombie
        match_hit_z = re.search(
            r'Player "(?P<victim>[^"]+)"((?:id=[^)]+ pos=<[^>]+>)?)[HP: (?P<hp>[\d.]+)] hit by (?P<z_type>Infected|Animal|Wolf|Bear) into (?P<part>\w+)(\d+) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+)\)',
            line
        )
        if match_hit_z:
            victim = match_hit_z.group("victim").strip()
            victim_key = victim.lower()
            hp_val = float(match_hit_z.group("hp"))
            is_dead = hp_val <= 0 or "(DEAD)" in line
            if is_dead and victim_key in last_death_time and now - last_death_time[victim_key] < 1.5:
                return
            if is_dead:
                last_death_time[victim_key] = now
            z_type = match_hit_z.group("z_type")
            part = match_hit_z.group("part")
            dmg = match_hit_z.group("dmg")
            ammo = match_hit_z.group("ammo")
            if is_dead:
                emoji = "☠️"
                color = "[31m"
                extra = " (ŚMIERĆ)"
            elif hp_val < 20:
                emoji = "🔥"
                color = "[35m"
                extra = f" (HP: {hp_val:.1f})"
            else:
                emoji = "⚡"
                color = "[33m"
                extra = f" (HP: {hp_val:.1f})"
            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez {z_type} w {part} za {dmg} dmg ({ammo})"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return

        # Hit by vehicle/explosion/fall/environment
        match_hit_env = re.search(
            r'Player "(?P<victim>[^"]+)"((?:id=[^)]+ pos=<[^>]+>)?)[HP: (?P<hp>[\d.]+)] hit by (?P<type>FallDamage|(?P<vehicle>[^ ]+)|explosion) .*for (?P<dmg>[\d.]+) damage',
            line
        )
        if match_hit_env:
            victim = match_hit_env.group("victim").strip()
            victim_key = victim.lower()
            hp_val = float(match_hit_env.group("hp"))
            is_dead = hp_val <= 0 or "(DEAD)" in line
            if is_dead and victim_key in last_death_time and now - last_death_time[victim_key] < 1.5:
                return
            if is_dead:
                last_death_time[victim_key] = now
            dmg_type = match_hit_env.group("type")
            dmg = match_hit_env.group("dmg")
            vehicle = match_hit_env.group("vehicle") or ""
            if dmg_type == "FallDamage":
                emoji = "🪂"
                color = "[33m"
                extra = f" (HP: {hp_val:.1f})"
            elif dmg_type == "explosion":
                emoji = "💥"
                color = "[31m"
                extra = f" (HP: {hp_val:.1f})"
            else:
                emoji = "🚗"
                color = "[33m"
                extra = f" (HP: {hp_val:.1f})"
            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} → trafiony przez {vehicle} (pojazd)"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return
        # Hit player vs player
        match_hit_player = re.search(
            r'Player "(?P<victim>[^"]+)"((?:id=[^)]+ pos=<[^>]+>)?)[HP: (?P<hp>[\d.]+)] hit by Player "(?P<attacker>[^"]+)" .*into (?P<part>\w+)(\d+) for (?P<dmg>[\d.]+) damage ((?P<ammo>[^)]+)) with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters',
            line
        )
        if match_hit_player:
            victim = match_hit_player.group("victim").strip()
            victim_key = victim.lower()
            hp_val = float(match_hit_player.group("hp"))
            is_dead = hp_val <= 0 or "(DEAD)" in line
            if is_dead and victim_key in last_death_time and now - last_death_time[victim_key] < 1.5:
                return
            if is_dead:
                last_death_time[victim_key] = now
            detected_events["hit"] += 1
            attacker = match_hit_player.group("attacker")
            part = match_hit_player.group("part")
            dmg = match_hit_player.group("dmg")
            ammo = match_hit_player.group("ammo")
            weapon = match_hit_player.group("weapon")
            dist = match_hit_player.group("dist")
            if is_dead:
                color = "[31m"
                emoji = "☠️"
                extra = " (ŚMIERĆ)"
                kill_msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist} m"
                kill_ch = client.get_channel(CHANNEL_IDS["kills"])
                if kill_ch:
                    await kill_ch.send(f"```ansi\n[31m{kill_msg}[0m\n```")
            elif hp_val < 20:
                color = "[35m"
                emoji = "🔥"
                extra = f" (HP: {hp_val:.1f})"
            else:
                color = "[33m"
                emoji = "⚡"
                extra = f" (HP: {hp_val:.1f})"
            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez {attacker} w {part} za {dmg} dmg ({ammo}) z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return

    # 5. Chat
    if "[Chat -" in line:
        print(f"[CHAT DEBUG] Przetwarzam linię chatu: {line[:150]}...")
        match = re.search(r'[Chat - (?P<channel_type>[^]]+)]("(?P<player>[^"]+)"(id=[^)]+)): (?P<message>.*)', line)
        if match:
            detected_events["chat"] += 1
            channel_type = match.group("channel_type").strip()
            player = match.group("player").strip()
            message = match.group("message").strip() or "[brak]"
            print(f"[CHAT DEBUG] Rozpoznano: {channel_type} | Gracz: {player} | Wiadomość: '{message}'")
            color_map = {"Global": "[34m", "Admin": "[31m", "Team": "[34m", "Direct": "[37m", "Unknown": "[33m"}
            ansi_color = color_map.get(channel_type, color_map["Unknown"])
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            discord_ch_id = CHAT_CHANNEL_MAPPING.get(channel_type, CHANNEL_IDS["chat"])
            ch = client.get_channel(discord_ch_id)
            if ch:
                await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
                print(f"[CHAT] Wysłano na kanał {discord_ch_id} ({channel_type})")
            else:
                print(f"[CHAT ERROR] Kanał {discord_ch_id} nie znaleziony – fallback do connections")
                fallback_ch = client.get_channel(CHANNEL_IDS["connections"])
                if fallback_ch:
                    await fallback_ch.send(f"```ansi\n{ansi_color}{msg} ({channel_type} fallback)[0m\n```")
            return
        else:
            print(f"[CHAT DEBUG] Regex NIE pasuje – linia trafi do other: {line[:150]}...")

    # Nierozpoznane
    detected_events["other"] += 1
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
    except Exception as e:
        print(f"[BŁĄD ZAPISU UNPARSED] {e}")
