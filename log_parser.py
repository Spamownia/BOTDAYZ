import re
from datetime import datetime
import os
import time
import requests
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

    # 1. Dołączony do kolejki logowania – zielony
    if "[Login]:" in line and "Adding player" in line:
        match = re.search(r'Adding player ([^ ]+) \((\d+)\) to login queue', line)
        if match:
            detected_events["join"] += 1
            name = match.group(1)
            dpnid = match.group(2)
            msg = f"{date_str} | {log_time} 🟢 Do kolejki → {name} (dpnid: {dpnid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 2. Połączono – zielony + oba ID w jednej linii (SteamID = ciąg znaków pierwszy, ID serverowe = cyfry drugi, po przecinku) + IP i lokalizacja
    if "is connected" in line and 'Player "' in line:
        match = re.search(
            r'Player "([^"]+)"\((?:steamID=([0-9a-zA-Z=]+)|id=([0-9]+))(?:, )?(?:steamID=([0-9a-zA-Z=]+)|id=([0-9]+))?\) is connected(?: from ([\d.:]+))?',
            line
        )
        if match:
            detected_events["join"] += 1
            name = match.group(1).strip()

            # SteamID = ciąg znaków (litery + cyfry + =)
            steamid_candidates = [match.group(2), match.group(4)]
            steamid = next((x for x in steamid_candidates if x and not x.isdigit()), None)

            # ID serverowe = same cyfry
            serverid_candidates = [match.group(3), match.group(5)]
            serverid = next((x for x in serverid_candidates if x and x.isdigit()), None)

            ids_str = ""
            if steamid and serverid:
                ids_str = f"SteamID: {steamid} , ID: {serverid}"
            elif steamid:
                ids_str = f"SteamID: {steamid}"
            elif serverid:
                ids_str = f"ID: {serverid}"

            player_login_times[name] = datetime.utcnow()

            msg = f"{date_str} | {log_time} 🟢 Połączono → {name}"
            if ids_str:
                msg += f" ({ids_str})"

            # IP + lokalizacja
            ip_port = match.group(6)
            if ip_port:
                ip = ip_port.split(':')[0]
                geo = ""
                try:
                    r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=3)
                    if r.status_code == 200:
                        data = r.json()
                        city = data.get('city', 'nieznane')
                        country = data.get('country_name', 'nieznane')
                        geo = f" z {city}, {country}"
                    else:
                        geo = f" z IP: {ip}"
                except:
                    geo = f" z IP: {ip}"
                msg += geo

            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 3. Rozłączono – czerwony (jest zawsze)
    if "disconnected" in line.lower():
        match = re.search(r'Player "([^"]+)"\((?:steamID|uid|id)?=([^)]+)\).*disconnected', line, re.IGNORECASE)
        if match:
            detected_events["disconnect"] += 1
            name = match.group(1).strip()
            id_val = match.group(2).strip()
           
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

    # 4. COT – biały
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

    # 5. Obrażenia i śmierci – pomarańczowy dla hit, czerwony dla śmierci
    if any(keyword in line for keyword in ["hit by", "killed by", "[HP: 0]", "CHAR_DEBUG - KILL"]):
        match_kill = re.search(r'Player "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_kill:
            detected_events["kill"] += 1
            victim = match_kill.group(1)
            attacker = match_kill.group(2)
            weapon = match_kill.group(3)
            dist = match_kill.group(4)
           
            msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return
        match_hit_player = re.search(r'Player "([^"]+)"(?: \(DEAD\))? .*hit by Player "([^"]+)" .*into (\w+)\(\d+\) for ([\d.]+) damage \(([^)]+)\) with ([\w ]+) from ([\d.]+) meters', line)
        if match_hit_player:
            detected_events["hit"] += 1
            victim = match_hit_player.group(1)
            attacker = match_hit_player.group(2)
            part = match_hit_player.group(3)
            dmg = match_hit_player.group(4)
            ammo = match_hit_player.group(5)
            weapon = match_hit_player.group(6)
            dist = match_hit_player.group(7)
            hp_match = re.search(r'\[HP: ([\d.]+)\]', line)
            hp = float(hp_match.group(1)) if hp_match else 100.0
            is_dead = hp <= 0 or "DEAD" in line
            color = "[38;5;208m" if not is_dead else "[31m"
            emoji = "⚡" if not is_dead else "☠️"
            extra = f" (HP: {hp})" if not is_dead else " (ŚMIERĆ)"
            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez {attacker} w {part} za {dmg} dmg ({ammo}) z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return
        match_hit_infected = re.search(r'Player "([^"]+)"(?: \(DEAD\))? .*hit by Infected .*into (\w+)\(\d+\) for ([\d.]+) damage \(([^)]+)\)(?: with ([\w ]+) from ([\d.]+) meters)?', line)
        if match_hit_infected:
            detected_events["hit"] += 1
            victim = match_hit_infected.group(1)
            part = match_hit_infected.group(2)
            dmg = match_hit_infected.group(3)
            ammo = match_hit_infected.group(4)
            weapon = match_hit_infected.group(5) or "brak"
            dist = match_hit_infected.group(6) or "brak"
            hp_match = re.search(r'\[HP: ([\d.]+)\]', line)
            hp = float(hp_match.group(1)) if hp_match else 100.0
            is_dead = hp <= 0 or "DEAD" in line
            color = "[38;5;208m" if not is_dead else "[31m"
            emoji = "⚡" if not is_dead else "☠️"
            extra = f" (HP: {hp})" if not is_dead else " (ŚMIERĆ)"
            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez Infected w {part} za {dmg} dmg ({ammo}) z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return
        if "CHAR_DEBUG - KILL" in line:
            detected_events["kill"] += 1
            match = re.search(r'player (\w+) \(dpnid = (\d+)\)', line)
            if match:
                player = match.group(1)
                dpnid = match.group(2)
                msg = f"{date_str} | {log_time} ☠️ Śmierć: {player} (dpnid: {dpnid})"
                ch = client.get_channel(CHANNEL_IDS["kills"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")
                return

    # CHAT
    if "[Chat -" in line:
        match = re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line)
        if match:
            detected_events["chat"] += 1
            channel_type, player, message = match.groups()
            color_map = {"Global": "[32m", "Admin": "[31m", "Team": "[34m", "Direct": "[37m", "Unknown": "[33m"}
            ansi_color = color_map.get(channel_type.strip(), color_map["Unknown"])
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            discord_ch_id = CHAT_CHANNEL_MAPPING.get(channel_type.strip(), CHANNEL_IDS["chat"])
            ch = client.get_channel(discord_ch_id)
            if ch:
                await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
            return

    # Nierozpoznane
    detected_events["other"] += 1

    # Zapis do pliku
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
    except Exception as e:
        print(f"[BŁĄD ZAPISU UNPARSED] {e}")
