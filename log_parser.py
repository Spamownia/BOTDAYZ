import re
from datetime import datetime
import time
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

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

    time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")
    date_str = datetime.utcnow().strftime("%d.%m.%Y")

    # ===================== LOGIN =====================
    if "connected" in line.lower() and '"' in line:
        match = re.search(r'"([^"]+)"\s*\((?:steamID|id|uid)?=?\s*(\d+)\)', line)
        if match:
            detected_events["join"] += 1
            name, id_val = match.groups()
            player_login_times[name] = datetime.utcnow()
            msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {id_val})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```ansi\n[32m{msg}[0m\n```")
            return

    # ===================== LOGOUT (POPRAWIONE) =====================
    if any(x in line.lower() for x in ["disconnected", "kicked from server", "logout"]):
        name = None
        id_val = None

        match = re.search(r'"([^"]+)"\s*\((?:steamID|id|uid)?=?\s*(\d+)\)', line)
        if match:
            name, id_val = match.groups()

        if not name:
            m2 = re.search(r'disconnected[: ]+\s*([^\(]+)\s*\((?:uid|id)=(\d+)\)', line, re.IGNORECASE)
            if m2:
                name, id_val = m2.groups()

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

    # ===================== CHAT – FORMAT 1 (DAYZ) =====================
    if "[Chat -" in line:
        match = re.search(r'\[Chat - ([^\]]+)\].*?"([^"]+)".*?: (.+)', line)
        if match:
            detected_events["chat"] += 1
            channel_type, player, message = match.groups()
            ansi = {"Global":"[32m","Admin":"[31m","Team":"[34m","Direct":"[37m"}.get(channel_type, "[33m")
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            ch = client.get_channel(CHAT_CHANNEL_MAPPING.get(channel_type, CHANNEL_IDS["chat"]))
            if ch:
                await ch.send(f"```ansi\n{ansi}{msg}[0m\n```")
            return

    # ===================== CHAT – FORMAT 2 (HUSARIABOT) =====================
    if "💬" in line:
        match = re.search(r'💬\s*\[([^\]]+)\]\s*([^:]+):\s*(.+)', line)
        if match:
            detected_events["chat"] += 1
            channel_type, player, message = match.groups()
            ansi = {"Global":"[32m","Admin":"[31m","Team":"[34m","Direct":"[37m"}.get(channel_type, "[33m")
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            ch = client.get_channel(CHAT_CHANNEL_MAPPING.get(channel_type, CHANNEL_IDS["chat"]))
            if ch:
                await ch.send(f"```ansi\n{ansi}{msg}[0m\n```")
            return

    # ===================== UNPARSED =====================
    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except Exception as e:
        print(f"[UNPARSED WRITE ERROR] {e}")
