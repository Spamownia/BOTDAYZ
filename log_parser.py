import re
from datetime import datetime
import os
import time
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed

player_login_times = {}

# Plik do zapisywania nierozpoznanych linii
UNPARSED_LOG = "unparsed_lines.log"

# Podsumowanie co ile sekund (możesz zmienić)
SUMMARY_INTERVAL = 30
last_summary_time = time.time()
processed_count = 0
detected_events = {
    "join": 0,
    "disconnect": 0,
    "cot": 0,
    "hit": 0,
    "kill": 0,
    "chat": 0,
    "other": 0
}

async def process_line(bot, line: str):
    global last_summary_time, processed_count
    
    client = bot
    line = line.strip()
    if not line:
        return

    # Zwiększ licznik przetworzonych linii
    processed_count += 1

    # Podsumowanie co SUMMARY_INTERVAL sekund
    now = time.time()
    if now - last_summary_time >= SUMMARY_INTERVAL:
        summary = f"[PARSER SUMMARY @ {datetime.utcnow().strftime('%H:%M:%S')}] {processed_count} linii | "
        summary += " | ".join(f"{k}: {v}" for k, v in detected_events.items() if v > 0)
        if not any(detected_events.values()):
            summary += " (nic nie wykryto)"
        print(summary)
        
        # Reset
        last_summary_time = now
        processed_count = 0
        for k in detected_events:
            detected_events[k] = 0

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")

    # 1. Dodany do kolejki logowania
    if "[Login]:" in line and "Adding player" in line:
        match = re.search(r'Adding player ([^ ]+) \((\d+)\) to login queue', line)
        if match:
            detected_events["join"] += 1
            name = match.group(1)
            dpnid = match.group(2)
            msg = f"{date_str} | {log_time} 🟢 Login → Gracz {name} → Dodany do kolejki logowania"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 2. Połączono
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\((?:steamID|id)=([^)]+)\) is connected', line)
        if match:
            detected_events["join"] += 1
            name = match.group(1).strip()
            id_val = match.group(2)
            player_login_times[name] = datetime.utcnow()
            msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {id_val})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 3. Rozłączono
    if "has been disconnected" in line:
        match = re.search(r'Player "([^"]+)"\((?:steamID|id)=([^)]+)\) has been disconnected', line)
        if match:
            detected_events["disconnect"] += 1
            name = match.group(1).strip()
            id_val = match.group(2)
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

    # 4. COT
    if "[COT]" in line:
        match = re.search(r'\[COT\] (\d{17,}): (.+?)(?: \[guid=([^]]+)\])?$', line)
        if match:
            detected_events["cot"] += 1
            steamid = match.group(1)
            action = match.group(2).strip()
            guid = match.group(3) or "brak"
            msg = f"{date_str} | {log_time} 🛡️ [COT] {steamid} | {action} [guid={guid}]"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # 5. Obrażenia / Hit / Death / Kill
    if any(keyword in line for keyword in ["hit by", "killed by", "[HP: 0]", "CHAR_DEBUG - KILL"]):
        # Hit / obrażenia
        match_hit = re.search(r'Player "([^"]+)"(?: \(DEAD\))? .*hit by (Infected|Player "([^"]+)") .*into (\w+)\(\d+\) for ([\d.]+) damage \(([^)]+)\) with ([\w ]+) from ([\d.]+) meters', line)
        if match_hit:
            detected_events["hit"] += 1
            victim = match_hit.group(1)
            attacker_type = match_hit.group(2)
            attacker_name = match_hit.group(3) if attacker_type == "Player" else "Infected"
            part = match_hit.group(4)
            dmg = match_hit.group(5)
            ammo_type = match_hit.group(6)
            weapon = match_hit.group(7)
            dist = match_hit.group(8)

            hp_match = re.search(r'\[HP: ([\d.]+)\]', line)
            hp = hp_match.group(1) if hp_match else "nieznane"
            is_dead = " (ŚMIERĆ)" if hp == "0" or "DEAD" in line else ""

            color = "[31m" if "DEAD" in line or hp == "0" else "[33m"
            emoji = "☠️" if "DEAD" in line or hp == "0" else "⚠️"

            msg = f"{date_str} | {log_time} {emoji} {victim}{is_dead} trafiony przez {attacker_name} w {part} za {dmg} dmg ({ammo_type}) z {weapon} z {dist}m (HP: {hp})"
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return

        # Killed / śmierć
        match_kill = re.search(r'Player "([^"]+)" \(DEAD\) .* killed by (Infected|Player "([^"]+)") .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_kill:
            detected_events["kill"] += 1
            victim = match_kill.group(1)
            attacker_type = match_kill.group(2)
            attacker_name = match_kill.group(3) if attacker_type == "Player" else "Infected"
            weapon = match_kill.group(4)
            dist = match_kill.group(5)

            msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker_name} z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return

        # CHAR_DEBUG - KILL
        if "CHAR_DEBUG - KILL" in line:
            match = re.search(r'player (\w+) \(dpnid = (\d+)\)', line)
            if match:
                detected_events["kill"] += 1
                player = match.group(1)
                dpnid = match.group(2)
                msg = f"{date_str} | {log_time} ☠️ Śmierć: {player} (dpnid: {dpnid})"
                ch = client.get_channel(CHANNEL_IDS["deaths"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")
                return

    # CHAT
    if "[Chat -" in line:
        match = re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line)
        if match:
            detected_events["chat"] += 1
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

    # Jeśli nic nie złapano → liczymy jako "other"
    detected_events["other"] += 1

    # Zapis do pliku (bez printa każdej linii)
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
    except Exception as e:
        print(f"[BŁĄD ZAPISU UNPARSED] {e}")
