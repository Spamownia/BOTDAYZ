# log_parser.py - poprawiona wersja 2026-02-02
import re
from datetime import datetime
import time
from collections import defaultdict

last_death_time = defaultdict(float)
player_login_times = {}
guid_to_name = {}
UNPARSED_LOG = "unparsed_lines.log"
SUMMARY_INTERVAL = 30
last_summary_time = time.time()
processed_count = 0
detected_events = {"join":0, "disconnect":0, "cot":0, "hit":0, "kill":0, "chat":0, "other":0, "unconscious":0}

processed_events = set()  # deduplikacja

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
        summary += " | ".join(f"{k}: {v}" for k,v in detected_events.items() if v > 0)
        print(summary)
        last_summary_time = now
        processed_count = 0
        for k in detected_events: detected_events[k] = 0

    time_match = re.search(r'^(\d{1,2}:\d{2}:\d{2})(?:\.\d+)?', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")
    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")
    log_dt = datetime.combine(today.date(), datetime.strptime(log_time, "%H:%M:%S").time())

    def dedup_key(action, name=""):
        return (log_time, name.lower(), action)

    # ────────────────────────────────────────────────
    # 1. Połączenia / Rozłączenia
    # ────────────────────────────────────────────────
    if "is connected" in line and 'Player "' in line:
        m = re.search(r'Player "(?P<name>[^"]+)"\s*\(id=(?P<guid>[^)]+)\)\s+is connected', line)
        if m:
            name = m.group("name").strip()
            guid = m.group("guid")
            key = dedup_key("connect", name)
            if key in processed_events: return
            processed_events.add(key)
            detected_events["join"] += 1
            player_login_times[name] = log_dt
            guid_to_name[guid] = name
            msg = f"{date_str} | {log_time} 🟢 **Połączono** → {name} (ID: {guid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch: await ch.send(f"```ansi\n[32m{msg}[0m```")
            return

    if any(x in line.lower() for x in ["disconnected", "kicked", "banned"]) and 'Player "' in line:
        m = re.search(r'Player "(?P<name>[^"]+)"\s*\(id=(?P<guid>[^)]+)\)', line)
        if m:
            name = m.group("name").strip()
            guid = m.group("guid")
            key = dedup_key("disconnect", name)
            if key in processed_events: return
            processed_events.add(key)
            detected_events["disconnect"] += 1
            time_online = "nieznany"
            if name in player_login_times:
                delta = (log_dt - player_login_times[name]).total_seconds() // 60
                time_online = f"{int(delta)} min"
                del player_login_times[name]
            emoji = "☠️" if "banned" in line.lower() else "⚡" if "kicked" in line.lower() else "🔴"
            color  = "[31m" if emoji in "☠️⚡" else "[31m"
            msg = f"{date_str} | {log_time} {emoji} **Rozłączono** → {name} (ID: {guid}) → {time_online}"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch: await ch.send(f"```ansi\n{color}{msg}[0m```")
            return

    # ────────────────────────────────────────────────
    # 2. Chat – poprawiony regex (bez spacji przed id)
    # ────────────────────────────────────────────────
    if "[Chat -" in line:
        m = re.search(r'\[Chat - (?P<ch>[^]]+)\]\("(?P<nick>[^"]+)"\(id=[^)]+\)\): (?P<msg>.*)', line)
        if m:
            detected_events["chat"] += 1
            channel = m.group("ch").strip()
            nick    = m.group("nick").strip()
            message = m.group("msg").strip() or "[brak treści]"
            colors = {"Global":"[34m", "Admin":"[31m", "Team":"[36m", "Direct":"[37m", "Side":"[35m"}
            col = colors.get(channel, "[33m")
            msg = f"{date_str} | {log_time} 💬 **{channel}** {nick}: {message}"
            target_id = CHAT_CHANNEL_MAPPING.get(channel, CHANNEL_IDS["chat"])
            ch = client.get_channel(target_id)
            if ch:
                await ch.send(f"```ansi\n{col}{msg}[0m```")
            return

    # ────────────────────────────────────────────────
    # 3. COT – wszystkie linie
    # ────────────────────────────────────────────────
    if "[COT]" in line:
        detected_events["cot"] += 1
        content = line.split("[COT] ", 1)[1].strip()
        msg = f"{date_str} | {log_time} 🔧 **COT** {content}"
        ch = client.get_channel(CHANNEL_IDS.get("admin", CHANNEL_IDS["connections"]))
        if ch: await ch.send(f"```ansi\n[35m{msg}[0m```")
        return

    # ────────────────────────────────────────────────
    # 4. Hit by Infected / Zombie
    # ────────────────────────────────────────────────
    if "hit by Infected" in line or "hit by Animal" in line:
        m = re.search(
            r'Player "(?P<nick>[^"]+)" .*?\[HP: (?P<hp>[\d.]+)\] hit by (?P<source>Infected|Animal|Zombie).*?into (?P<zone>[^(]+)\(\d+\) for (?P<dmg>[\d.]+) damage',
            line
        )
        if m:
            detected_events["hit"] += 1
            nick = m.group("nick")
            hp   = float(m.group("hp"))
            source = m.group("source")
            zone = m.group("zone").strip()
            dmg  = m.group("dmg")
            emoji = "☠️" if hp <= 0 else "🔥" if hp < 30 else "⚡"
            color = "[31m" if emoji == "☠️" else "[35m" if emoji == "🔥" else "[33m"
            extra = " **ŚMIERĆ**" if hp <= 0 else f" (HP: {hp:.1f})"
            msg = f"{date_str} | {log_time} {emoji} **{nick}** {extra} → trafiony przez {source} w {zone} za {dmg} dmg"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch: await ch.send(f"```ansi\n{color}{msg}[0m```")
            return

    # ────────────────────────────────────────────────
    # 5. Explosion / LandMine / unconscious / regained
    # ────────────────────────────────────────────────
    if "hit by explosion" in line or "LandMineExplosion" in line:
        m = re.search(r'Player "(?P<nick>[^"]+)" .*?\[HP: (?P<hp>[\d.]+)\] hit by explosion \((?P<type>[^)]+)\)', line)
        if m:
            detected_events["hit"] += 1
            nick = m.group("nick")
            hp   = float(m.group("hp"))
            typ  = m.group("type")
            emoji = "💥"
            color = "[31m"
            extra = " **ŚMIERĆ**" if hp <= 0 else f" (HP: {hp:.1f})"
            msg = f"{date_str} | {log_time} {emoji} **{nick}** {extra} → eksplozja ({typ})"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch: await ch.send(f"```ansi\n{color}{msg}[0m```")
            return

    if "is unconscious" in line:
        m = re.search(r'Player "(?P<nick>[^"]+)" .*? is unconscious', line)
        if m:
            detected_events["unconscious"] += 1
            nick = m.group("nick")
            msg = f"{date_str} | {log_time} 😵 **{nick}** → nieprzytomny"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch: await ch.send(f"```ansi\n[31m{msg}[0m```")
            return

    if "regained consciousness" in line:
        m = re.search(r'Player "(?P<nick>[^"]+)" .*? regained consciousness', line)
        if m:
            detected_events["unconscious"] += 1
            nick = m.group("nick")
            msg = f"{date_str} | {log_time} 🟢 **{nick}** → odzyskał przytomność"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch: await ch.send(f"```ansi\n[32m{msg}[0m```")
            return

    # ────────────────────────────────────────────────
    # Reszta → unknown
    # ────────────────────────────────────────────────
    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except:
        pass
