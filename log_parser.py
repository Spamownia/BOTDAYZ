import re
from datetime import datetime
import os
import time
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed
from collections import defaultdict
from collections import deque
import asyncio

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
pending_disconnects = deque(maxlen=20)          # max 20 ostatnich podejrzanych disconnectów
DISCONNECT_GRACE_PERIOD = 2.5                   # sekund

async def clean_pending_disconnects(client):
    while True:
        await asyncio.sleep(1.0)
        now = time.time()
        to_send = []
        i = 0
        while i < len(pending_disconnects):
            item = pending_disconnects[i]
            if now - item["timestamp"] > DISCONNECT_GRACE_PERIOD:
                # timeout → normalne wyjście
                name = item["name"]
                guid = item["guid"]
                time_online = "nieznany"
                if name in player_login_times:
                    delta = datetime.utcnow() - player_login_times[name]
                    time_online = f"{int(delta.total_seconds() // 60)} min {int(delta.total_seconds() % 60)} s"
                    del player_login_times[name]

                msg = f"{item['date_str']} | {item['log_time']} 🔴 Rozłączono → {name} (ID: {guid}) → {time_online}"
                ch = client.get_channel(CHANNEL_IDS["connections"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")

                pending_disconnects.popleft()
            else:
                i += 1

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
    # 1. Połączono – mapowanie guid → nick
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

    # ────────────────────────────────────────────────
    # Nowa logika disconnect / kick / ban
    # ────────────────────────────────────────────────
    lower_line = line.lower()

    is_disconnect_line = any(x in lower_line for x in ["disconnected", "has been disconnected"])
    is_kick_line      = any(x in lower_line for x in ["kicked", "kick ", "kick:", "kicked [guid="])
    is_ban_line       = any(x in lower_line for x in ["banned", "ban ", "banned [guid="])

    player_name = "????"
    guid = "brak"

    # Próbujemy wyciągnąć name i guid z każdej linii
    name_match = re.search(r'Player\s*(?:"([^"]+)"|([^(]+))', line, re.IGNORECASE)
    if name_match:
        player_name = (name_match.group(1) or name_match.group(2)).strip()

    guid_match = re.search(r'\((?:id|steamID|uid|guid)=(?P<guid>[^ )]+)', line, re.IGNORECASE)
    if guid_match:
        guid = guid_match.group("guid").strip()
    elif "guid=" in line:
        m = re.search(r'guid=(?P<guid>[^\s\]]+)', line)
        if m:
            guid = m.group("guid")

    if guid in guid_to_name:
        player_name = guid_to_name[guid]

    # ─── 1. Linia o kicku / banie ───────────────────────────────────────
    if is_kick_line or is_ban_line:
        # Szukamy czy jest powiązany pending disconnect
        found = False
        for i in range(len(pending_disconnects) - 1, -1, -1):
            item = pending_disconnects[i]
            if item["name"].lower() == player_name.lower() or item["guid"] == guid:
                # Był pending → oznaczamy go jako kick/ban i usuwamy z kolejki
                del pending_disconnects[i]
                found = True
                break

        emoji = "⚡" if is_kick_line else "☠️"
        color = "[33m" if is_kick_line else "[31m"
        extra = " (KICK)" if is_kick_line else " (BAN)"
        time_online = "nieznany"
        if player_name in player_login_times:
            delta = datetime.utcnow() - player_login_times[player_name]
            time_online = f"{int(delta.total_seconds() // 60)} min {int(delta.total_seconds() % 60)} s"
            del player_login_times[player_name]

        msg = f"{date_str} | {log_time} {emoji} Rozłączono → {player_name} (ID: {guid}) → {time_online}{extra}"
        ch = client.get_channel(CHANNEL_IDS["connections"])
        if ch:
            await ch.send(f"```ansi\n{color}{msg}[0m\n```")

        detected_events["disconnect"] += 1
        return

    # ─── 2. Zwykła linia disconnected → do kolejki ───────────────────────
    if is_disconnect_line and "Player " in line:
        detected_events["disconnect"] += 1

        pending_disconnects.append({
            "timestamp": time.time(),
            "name": player_name,
            "guid": guid,
            "raw_line": line,
            "log_time": log_time,
            "date_str": date_str
        })

        # Nie wysyłamy od razu – czekamy
        return

    # ─── 3. Jeśli żaden z powyższych – normalne przetwarzanie ─────────────

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
                await ch.send(f"```ansi\n[33m{msg}[0m\n```")
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
    # 4. Hit / Kill – tylko jedna linia kill, bez hitów z (ŚMIERĆ)
    if "hit by" in line or "killed by" in line or "CHAR_DEBUG - KILL" in line or "died." in line:
        hp_match = re.search(r'\[HP: (?P<hp>[\d.]+)\]', line)
        hp = float(hp_match.group("hp")) if hp_match else None
        # Najpierw sprawdzamy KILL – wysyłamy tylko jedną linię kill
        killed = False
        # Kill (gracz) – z pos=
        match_kill = re.search(r'Player "(?P<victim>[^"]+)" \((?:id=[^)]+ pos=<[^>]+>)?\)\[HP: [\d.]+\] .*killed by Player "(?P<attacker>[^"]+)" .*with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters', line)
        if match_kill:
            victim = match_kill.group("victim").strip()
            victim_key = victim.lower()
            if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                return
            last_death_time[victim_key] = now
            killed = True
            detected_events["kill"] += 1
            attacker = match_kill.group("attacker")
            weapon = match_kill.group("weapon")
            dist = match_kill.group("dist")
            msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist} m"
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return # Return po killu
        # Kill (gracz) – bez pos=
        if not killed:
            match_kill_simple = re.search(r'Player "(?P<victim>[^"]+)" .*killed by Player "(?P<attacker>[^"]+)" .*with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters', line)
            if match_kill_simple:
                victim = match_kill_simple.group("victim").strip()
                victim_key = victim.lower()
                if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                    return
                last_death_time[victim_key] = now
                killed = True
                detected_events["kill"] += 1
                attacker = match_kill_simple.group("attacker")
                weapon = match_kill_simple.group("weapon")
                dist = match_kill_simple.group("dist")
                msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist} m"
                ch = client.get_channel(CHANNEL_IDS["kills"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")
                return
        # "died." jako kill
        if not killed and "died." in line:
            match = re.search(r'Player "(?P<victim>[^"]+)" .*died.', line)
            if match:
                victim = match.group("victim").strip()
                victim_key = victim.lower()
                if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                    return
                last_death_time[victim_key] = now
                killed = True
                detected_events["kill"] += 1
                msg = f"{date_str} | {log_time} ☠️ {victim} zmarł (died.)"
                ch = client.get_channel(CHANNEL_IDS["kills"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")
                return
        # Hit – wysyłamy tylko jeśli nie is_dead (pomijamy hity powodujące śmierć – kill wysłany z "killed by")
        if not killed:
            # Hit by Player – z pos=
            match_hit_player = re.search(r'Player "(?P<victim>[^"]+)" \((?:id=[^)]+ pos=<[^>]+>)?\)\[HP: (?P<hp>[\d.]+)\] hit by Player "(?P<attacker>[^"]+)" .*into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+)\) with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters', line)
            if match_hit_player:
                victim = match_hit_player.group("victim").strip()
                victim_key = victim.lower()
                hp = float(match_hit_player.group("hp"))
                is_dead = hp <= 0 or "(DEAD)" in line
                if is_dead:
                    return # Pomijamy hit powodujący śmierć
                if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                    return
                detected_events["hit"] += 1
                attacker = match_hit_player.group("attacker")
                part = match_hit_player.group("part")
                dmg = match_hit_player.group("dmg")
                ammo = match_hit_player.group("ammo")
                weapon = match_hit_player.group("weapon")
                dist = match_hit_player.group("dist")
                if hp < 20:
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
            # Hit by Player – bez pos=
            match_hit_player_simple = re.search(r'Player "(?P<victim>[^"]+)" .*hit by Player "(?P<attacker>[^"]+)" .*into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+)\) with (?P<weapon>[^ ]+) from (?P<dist>[\d.]+) meters', line)
            if match_hit_player_simple:
                victim = match_hit_player_simple.group("victim").strip()
                victim_key = victim.lower()
                hp_match = re.search(r'\[HP: (?P<hp>[\d.]+)\]', line)
                hp = float(hp_match.group("hp")) if hp_match else 100.0
                is_dead = hp <= 0 or "(DEAD)" in line
                if is_dead:
                    return # Pomijamy hit powodujący śmierć
                if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                    return
                detected_events["hit"] += 1
                attacker = match_hit_player_simple.group("attacker")
                part = match_hit_player_simple.group("part")
                dmg = match_hit_player_simple.group("dmg")
                ammo = match_hit_player_simple.group("ammo")
                weapon = match_hit_player_simple.group("weapon")
                dist = match_hit_player_simple.group("dist")
                if hp < 20:
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
            # Hit by Infected – z pos=
            match_hit_infected = re.search(r'Player "(?P<victim>[^"]+)" \((?:id=[^)]+ pos=<[^>]+>)?\)\[HP: (?P<hp>[\d.]+)\] hit by Infected .*into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+)\)', line)
            if match_hit_infected:
                victim = match_hit_infected.group("victim").strip()
                victim_key = victim.lower()
                hp = float(match_hit_infected.group("hp"))
                is_dead = hp <= 0 or "(DEAD)" in line
                if is_dead:
                    return # Pomijamy hit powodujący śmierć
                if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                    return
                detected_events["hit"] += 1
                part = match_hit_infected.group("part")
                dmg = match_hit_infected.group("dmg")
                ammo = match_hit_infected.group("ammo")
                if hp < 20:
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
            # Hit by Infected – bez pos=
            match_hit_infected_simple = re.search(r'Player "(?P<victim>[^"]+)" .*hit by Infected .*into (?P<part>\w+)\(\d+\) for (?P<dmg>[\d.]+) damage \((?P<ammo>[^)]+)\)', line)
            if match_hit_infected_simple:
                victim = match_hit_infected_simple.group("victim").strip()
                victim_key = victim.lower()
                hp_match = re.search(r'\[HP: (?P<hp>[\d.]+)\]', line)
                hp = float(hp_match.group("hp")) if hp_match else 100.0
                is_dead = hp <= 0 or "(DEAD)" in line
                if is_dead:
                    return # Pomijamy hit powodujący śmierć
                if victim_key in last_death_time and now - last_death_time[victim_key] < 2.0:
                    return
                detected_events["hit"] += 1
                part = match_hit_infected_simple.group("part")
                dmg = match_hit_infected_simple.group("dmg")
                ammo = match_hit_infected_simple.group("ammo")
                if hp < 20:
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
    # CHAT
    if "[Chat -" in line:
        print(f"[CHAT DEBUG] Przetwarzam linię chatu: {line[:150]}...")
       
        match = re.search(r'\[Chat - (?P<channel_type>[^\]]+)\]\("(?P<player>[^"]+)"\(id=[^)]+\)\): (?P<message>.*)', line)
        if match:
            detected_events["chat"] += 1
            channel_type = match.group("channel_type").strip()
            player = match.group("player").strip()
            message = match.group("message").strip() or "[brak]"
            print(f"[CHAT DEBUG] Rozpoznano: {channel_type} | Gracz: {player} | Wiadomość: '{message}'")
           
            color_map = {"Global": "[32m", "Admin": "[31m", "Team": "[34m", "Direct": "[37m", "Unknown": "[33m"}
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
