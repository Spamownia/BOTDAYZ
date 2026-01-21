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

# Dodajemy flagę globalną dla pierwszego sprawdzenia
is_first_check = True

async def process_line(bot, line: str):
    global last_summary_time, processed_count, is_first_check
   
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

    # Pomijamy przetwarzanie linii jeśli to pierwsze sprawdzenie (stare logi)
    if is_first_check:
        print(f"[SKIP OLD] Pomijam linię podczas pierwszego sprawdzenia: {line}")
        return

    # 1. Połączono – zielony
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(([^)]*)\) is connected', line)
        if match:
            detected_events["join"] += 1
            name = match.group(1).strip()
            parenth_content = match.group(2).strip()
            player_login_times[name] = datetime.utcnow()

            steam_id = "Brak"
            server_id = "Brak"

            if parenth_content:
                parts = [p.strip() for p in parenth_content.split(',') if p.strip()]

                for part in parts:
                    if '=' not in part:
                        # wartość bez klucza
                        if part.isdigit() and 16 <= len(part) <= 18:
                            steam_id = part
                        else:
                            server_id = part
                        continue

                    key, value = part.split('=', 1)
                    key_lower = key.lower().strip()
                    value = value.strip()

                    if 'steam' in key_lower:
                        steam_id = value
                    elif any(word in key_lower for word in ['id', 'guid', 'owner', 'uid']):
                        server_id = value
                    else:
                        # nieznany klucz – domyślnie traktujemy jako server_id
                        server_id = value

            # fallback – jeśli nic nie przypisano, ale coś było
            if steam_id == "Brak" and server_id == "Brak" and parenth_content:
                if parenth_content.isdigit() and 16 <= len(parenth_content) <= 18:
                    steam_id = parenth_content
                else:
                    server_id = parenth_content

            msg = (
                f"{date_str} | {log_time} 🟢 Połączono → {name} "
                f"(SteamID: {steam_id} | ID: {server_id})"
            )

            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # 2. Rozłączono – czerwony (poprawiony, bardziej elastyczny regex)
    if "has been disconnected" in line or "disconnected" in line.lower():
        # Obsługuje różne formaty, np. z guid, uid, steamID
        match = re.search(r'Player "([^"]+)"\((?:steamID|id|uid)?=([^)]+)\).*disconnected', line, re.IGNORECASE)
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
    # 3. COT – biały
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
    # 4. Obrażenia i śmierci – kolory i kanały rozdzielone
    if any(keyword in line for keyword in ["hit by", "killed by", "[HP: 0]", "CHAR_DEBUG - KILL"]):
        # Najpierw pełne zabójstwo – czerwone na kills-kanał
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
        # Hit by Player – pomarańczowy/żółty na damages-kanał
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
            if is_dead:
                color = "[31m"
                emoji = "☠️"
                extra = " (ŚMIERĆ)"
            elif hp < 20:
                color = "[38;5;208m" # pomarańczowy
                emoji = "🔥"
                extra = f" (krytycznie niski HP: {hp})"
            else:
                color = "[33m" # żółty
                emoji = "⚡"
                extra = f" (HP: {hp})"
            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez {attacker} w {part} za {dmg} dmg ({ammo}) z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return
        # Hit by Infected – pomarańczowy/żółty na damages
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
            if is_dead:
                color = "[31m"
                emoji = "☠️"
                extra = " (ŚMIERĆ)"
            elif hp < 20:
                color = "[38;5;208m" # pomarańczowy
                emoji = "🔥"
                extra = f" (krytycznie niski HP: {hp})"
            else:
                color = "[33m" # żółty
                emoji = "⚡"
                extra = f" (HP: {hp})"
            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez Infected w {part} za {dmg} dmg ({ammo}) z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return
        # CHAR_DEBUG - KILL – czerwone na kills
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
