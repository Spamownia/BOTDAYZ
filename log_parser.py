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
    "join": 0, "disconnect": 0, "cot": 0,
    "hit": 0, "kill": 0, "chat": 0,
    "kick": 0, "ban": 0, "other": 0
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
        print(summary)
        last_summary_time = now
        processed_count = 0
        for k in detected_events:
            detected_events[k] = 0

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")
    date_str = datetime.utcnow().strftime("%d.%m.%Y")

    # ===================== LOGIN =====================
    if "connected" in line.lower() and '"' in line:
        match = re.search(r'"(?P<name>[^"]+)"\s*\((?:steamID|id|uid)?=?\s*(?P<id>\d+)\)', line)
        if match:
            detected_events["join"] += 1
            name = match.group("name").strip()
            id_val = match.group("id")
            player_login_times[name] = datetime.utcnow()
            msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {id_val})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # ===================== LOGOUT =====================
    if any(x in line.lower() for x in ["disconnected", "kicked from server", "logout"]):
        match = re.search(r'"(?P<name>[^"]+)"\s*\((?:steamID|id|uid)?=?\s*(?P<id>\d+)\)', line)

        name = None
        id_val = None

        if match:
            name = match.group("name").strip()
            id_val = match.group("id")
        else:
            # ADM fallback: Player disconnected: Name (uid=123)
            m2 = re.search(r'disconnected[: ]+\s*(?P<name>[^\(]+)\s*\((?:uid|id)=(?P<id>\d+)\)', line, re.IGNORECASE)
            if m2:
                name = m2.group("name").strip()
                id_val = m2.group("id")
            else:
                # ADM fallback: uid=123 disconnected
                m3 = re.search(r'(?:uid|id)=(?P<id>\d+)', line, re.IGNORECASE)
                if m3:
                    id_val = m3.group("id")
                    # próbujemy dopasować nick z loginów
                    name = next((n for n in player_login_times.keys()), "Unknown")

        if not name:
            name = "????"
        if not id_val:
            id_val = "brak"

        detected_events["disconnect"] += 1
        time_online = "nieznany"
        if name in player_login_times:
            delta = datetime.utcnow() - player_login_times[name]
            time_online = f"{int(delta.total_seconds()//60)} min {int(delta.total_seconds()%60)} s"
            del player_login_times[name]

        msg = f"{date_str} | {log_time} 🔴 Rozłączono → {name} (ID: {id_val}) → {time_online}"
        ch = client.get_channel(CHANNEL_IDS["connections"])
        if ch:
            await ch.send(f"```ansi\n[31m{msg}[0m\n```")
        return

    # ===================== COT =====================
    if "[COT]" in line:
        match = re.search(r'\[COT\]\s*(\d+):\s*(.+?)(?:\s*\[guid=(.+?)\])?$', line)
        if match:
            detected_events["cot"] += 1
            steamid, action, guid = match.groups()
            guid = guid or "brak"
            msg = f"{date_str} | {log_time} 🛡️ [COT] {steamid} | {action} [guid={guid}]"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # ===================== HIT =====================
    if "hit by" in line:
        match_hit = re.search(
            r'"(?P<victim>[^"]+)".*hit by (?P<src>Player "(?P<attacker>[^"]+)"|Infected).*into (?P<part>[A-Za-z]+).*for (?P<dmg>[\d.]+).*?\((?P<ammo>[^)]+)\)',
            line
        )
        if match_hit:
            detected_events["hit"] += 1
            victim = match_hit.group("victim")
            attacker = match_hit.group("attacker") if match_hit.group("attacker") else "Infected"
            part = match_hit.group("part")
            dmg = match_hit.group("dmg")
            ammo = match_hit.group("ammo")

            hp_match = re.search(r'\[HP:\s*([\d.]+)\]', line)
            hp = float(hp_match.group(1)) if hp_match else 100.0

            if hp <= 0 or "(DEAD)" in line:
                color = "[31m"
                emoji = "☠️"
                extra = " (ŚMIERĆ)"
            elif hp < 20:
                color = "[38;5;208m"
                emoji = "🔥"
                extra = f" (HP: {hp:.1f})"
            else:
                color = "[33m"
                emoji = "⚡"
                extra = f" (HP: {hp:.1f})"

            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez {attacker} w {part} za {dmg} dmg ({ammo})"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")

    # ===================== KILL =====================
    if "killed by" in line or "(DEAD)" in line:
        match_kill = re.search(
            r'"(?P<victim>[^"]+)".*killed by Player "(?P<attacker>[^"]+)".*with (?P<weapon>.+?) from (?P<dist>[\d.]+)',
            line
        )
        if match_kill:
            detected_events["kill"] += 1
            victim, attacker, weapon, dist = match_kill.groups()
            msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist} m"
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")

    # ===================== CHAR_DEBUG =====================
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

    # ===================== KICK / BAN =====================
    if any(x in line.lower() for x in ["kicked", "banned", "ban added"]):
        detected_events["kick"] += 1
        msg = f"{date_str} | {log_time} 🚫 {line}"
        ch = client.get_channel(CHANNEL_IDS["admin"])
        if ch:
            await ch.send(f"```ansi\n[31m{msg}[0m\n```")
        return

    # ===================== CHAT =====================
    if "[Chat -" in line:
        match = re.search(r'\[Chat - ([^\]]+)\].*?"([^"]+)".*?: (.+)', line)
        if match:
            detected_events["chat"] += 1
            channel_type, player, message = match.groups()
            color_map = {"Global":"[32m","Admin":"[31m","Team":"[34m","Direct":"[37m"}
            ansi_color = color_map.get(channel_type, "[33m")
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            ch = client.get_channel(CHAT_CHANNEL_MAPPING.get(channel_type, CHANNEL_IDS["chat"]))
            if ch:
                await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
            return

    # ===================== UNPARSED =====================
    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except Exception as e:
        print(f"[UNPARSED WRITE ERROR] {e}")
