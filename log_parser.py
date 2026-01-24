import re
from datetime import datetime
import os
import time
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed

player_login_times = {}

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

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")

    # 1. Połączono
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "(?P<name>[^"]+)"\((?:steamID|id)=(?P<id_val>[^)]+)\) is connected', line)
        if match:
            detected_events["join"] += 1
            name = match.group("name").strip()
            id_val = match.group("id_val")
            player_login_times[name] = datetime.utcnow()
            msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {id_val})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 2. Rozłączono
    if ("disconnected" in line.lower() or "kicked from server" in line.lower()) and 'Player ' in line:
        name_match = re.search(r'Player\s*(?:"([^"]+)"|([^(]+))\s*\(', line, re.IGNORECASE)
        if name_match:
            name = (name_match.group(1) or name_match.group(2)).strip()
        else:
            detected_events["disconnect"] += 1
            msg = f"{date_str} | {log_time} 🔴 Rozłączono → ???? (nie udało się odczytać nicku)"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return

        id_match = re.search(r'\(\s*(?:(?:steamID|id|uid)\s*=\s*)?([^)\s]+)(?:\s+pos=<[^>]+>)?\)', line, re.IGNORECASE)
        id_val = id_match.group(1).strip() if id_match else "brak"

        detected_events["disconnect"] += 1
        
        time_online = "nieznany"
        if name in player_login_times:
            delta = datetime.utcnow() - player_login_times[name]
            minutes = int(delta.total_seconds() // 60)
            seconds = int(delta.total_seconds() % 60)
            time_online = f"{minutes} min {seconds} s"
            del player_login_times[name]
        
        msg = f"{date_str} | {log_time} 🔴 Rozłączono → {name} (ID: {id_val}) → {time_online}"
        ch = client.get_channel(CHANNEL_IDS["connections"])
        if ch:
            await ch.send(f"```ansi\n[31m{msg}[0m\n```")
        return

    # 3. COT
    if "[COT]" in line:
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

    # 4. Kille i obrażenia
    if any(kw in line for kw in ["hit by", "killed by", "CHAR_DEBUG - KILL"]):

        # Pełny kill
        match_kill = re.search(
            r'Player "(?P<victim>[^"]+)"(?: \((?:DEAD|id=[^)]+)\))? .*killed by Player "(?P<attacker>[^"]+)" .*with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters',
            line
        )
        if match_kill:
            detected_events["kill"] += 1
            victim = match_kill.group("victim")
            attacker = match_kill.group("attacker")
            weapon = match_kill.group("weapon")
            dist = match_kill.group("dist")
            
            msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist} m"
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return

        # Hit by Player
        match_hit_player = re.search(
            r'Player "(?P<victim>[^"]+)"(?: \((?:DEAD|id=[^)]+)\))? .*hit by Player "(?P<attacker>[^"]+)" .*into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+)\) with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters',
            line
        )
        if match_hit_player:
            detected_events["hit"] += 1
            victim = match_hit_player.group("victim")
            attacker = match_hit_player.group("attacker")
            part = match_hit_player.group("part")
            dmg = match_hit_player.group("dmg")
            ammo = match_hit_player.group("ammo")
            weapon = match_hit_player.group("weapon")
            dist = match_hit_player.group("dist")
            hp_match = re.search(r'\[HP: (?P<hp>[\d.]+)\]', line)
            hp = float(hp_match.group("hp")) if hp_match else 100.0
            is_dead = hp <= 0 or "(DEAD)" in line

            if is_dead:
                color = "[31m"
                emoji = "☠️"
                extra = " (ŚMIERĆ)"
                kill_msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist} m"
                kill_ch = client.get_channel(CHANNEL_IDS["kills"])
                if kill_ch:
                    await kill_ch.send(f"```ansi\n[31m{kill_msg}[0m\n```")
            elif hp < 20:
                color = "[38;5;208m"
                emoji = "🔥"
                extra = f" (HP: {hp:.1f})"
            else:
                color = "[33m"
                emoji = "⚡"
                extra = f" (HP: {hp:.1f})"

            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez {attacker} w {part} za {dmg} dmg ({ammo}) z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return

        # Hit by Infected
        match_hit_infected = re.search(
            r'Player "(?P<victim>[^"]+)"(?: \((?:DEAD|id=[^)]+)\))? .*hit by Infected .*into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+)\)',
            line
        )
        if match_hit_infected:
            detected_events["hit"] += 1
            victim = match_hit_infected.group("victim")
            part = match_hit_infected.group("part")
            dmg = match_hit_infected.group("dmg")
            ammo = match_hit_infected.group("ammo")
            hp_match = re.search(r'\[HP: (?P<hp>[\d.]+)\]', line)
            hp = float(hp_match.group("hp")) if hp_match else 100.0
            is_dead = hp <= 0 or "(DEAD)" in line

            if is_dead:
                color = "[31m"
                emoji = "☠️"
                extra = " (ŚMIERĆ)"
                kill_msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez Infected w {part} za {dmg} dmg"
                kill_ch = client.get_channel(CHANNEL_IDS["kills"])
                if kill_ch:
                    await kill_ch.send(f"```ansi\n[31m{kill_msg}[0m\n```")
            elif hp < 20:
                color = "[38;5;208m"
                emoji = "🔥"
                extra = f" (HP: {hp:.1f})"
            else:
                color = "[33m"
                emoji = "⚡"
                extra = f" (HP: {hp:.1f})"

            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez Infected w {part} za {dmg} dmg ({ammo})"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return

        # CHAR_DEBUG - KILL
        if "CHAR_DEBUG - KILL" in line:
            detected_events["kill"] += 1
            match = re.search(r'player (?P<player>[^ ]+) \(dpnid = (?P<dpnid>\d+)\)', line)
            if match:
                player = match.group("player")
                dpnid = match.group("dpnid")
                msg = f"{date_str} | {log_time} ☠️ Śmierć: {player} (dpnid: {dpnid})"
                ch = client.get_channel(CHANNEL_IDS["kills"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return

    # CHAT – dopasowany do Twojego logu
    if "[Chat -" in line:
        match = re.search(r'\[Chat - (?P<channel_type>[^\]]+)\]\("(?P<player>[^"]+)"\(id=[^)]+\)\): (?P<message>.+)', line)
        if match:
            detected_events["chat"] += 1
            channel_type = match.group("channel_type").strip()
            player = match.group("player")
            message = match.group("message").strip()
            color_map = {"Global": "[32m", "Admin": "[31m", "Team": "[34m", "Direct": "[37m", "Unknown": "[33m"}
            ansi_color = color_map.get(channel_type, color_map["Unknown"])
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            discord_ch_id = CHAT_CHANNEL_MAPPING.get(channel_type, CHANNEL_IDS["chat"])
            ch = client.get_channel(discord_ch_id)
            if ch:
                await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
            return

    # Nierozpoznane
    detected_events["other"] += 1
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
    except Exception as e:
        print(f"[BŁĄD ZAPISU UNPARSED] {e}")
