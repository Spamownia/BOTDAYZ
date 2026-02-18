# log_parser.py - WERSJA Z COORDAMI + POPRAWIONE NAZWY ZABÓJCÓW + ROZSZERZONE PRZYCZYNY
import re
from datetime import datetime
import time
from collections import defaultdict
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

last_death_time = defaultdict(float)
last_killed_by_time = defaultdict(float)
player_login_times = {}
guid_to_name = {}
last_hit_details = defaultdict(lambda: (None, None, None))  # source, weapon, distance
last_death_pos = defaultdict(str)  # nick.lower() -> " pos=<x, y, z>"
UNPARSED_LOG = "unparsed_lines.log"
SUMMARY_INTERVAL = 30
last_summary_time = time.time()
processed_count = 0
detected_events = {"join":0, "disconnect":0, "cot":0, "hit":0, "kill":0, "chat":0, "other":0, "unconscious":0, "queue":0}
processed_events = set()

async def process_line(bot, line: str):
    global last_summary_time, processed_count
    client = bot
    line = line.strip()
    if not line:
        return

    # FILTR – pomijamy prawie całe .RPT poza kolejką logowania
    if '[Login]: Adding player' not in line:
        rpt_markers = [
            '[CE][', 'Conflicting addon', 'Updating base class', 'String "',
            'Localization not present', '!!! [CE][', 'CHAR_DEBUG', 'Wreck_',
            'StaticObj_', 'Land_', 'DZ\\', 'Version 1.', 'Exe timestamp:',
            'Current time:', 'Initializing stats manager', 'Weather->',
            'Overcast->', 'Names->', 'base class ->'
        ]
        if any(marker in line for marker in rpt_markers):
            return

    processed_count += 1
    now = time.time()
    if now - last_summary_time >= SUMMARY_INTERVAL:
        summary = f"[PARSER SUMMARY @ {datetime.utcnow().strftime('%H:%M:%S')}] {processed_count} linii | "
        summary += " | ".join(f"{k}: {v}" for k,v in detected_events.items() if v > 0)
        print(summary)
        last_summary_time = now
        processed_count = 0
        for k in detected_events:
            detected_events[k] = 0

    time_match = re.search(r'^(\d{1,2}:\d{2}:\d{2})(?:\.\d+)?', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")
    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")
    log_dt = datetime.combine(today.date(), datetime.strptime(log_time, "%H:%M:%S").time())

    def dedup_key(action, name=""):
        return (log_time, name.lower(), action)

    async def safe_send(channel_key, message, color_code):
        ch_id = CHANNEL_IDS.get(channel_key)
        if not ch_id:
            return
        ch = client.get_channel(ch_id)
        if not ch:
            return
        try:
            await ch.send(f"```ansi\n{color_code}{message}[0m```")
        except:
            pass

    # ───────────────────────────────────────────────────────────────
    # CACHE COORDYNAT Z KAŻDEJ LINII Z (DEAD)
    # ───────────────────────────────────────────────────────────────
    if "(DEAD)" in line:
        pos_m = re.search(r'pos=<([\d\.-]+),\s*([\d\.-]+),\s*([\d\.-]+)>', line)
        name_m = re.search(r'Player "(.+?)"', line)
        if pos_m and name_m:
            x = round(float(pos_m.group(1)), 1)
            y = round(float(pos_m.group(2)), 1)
            z = round(float(pos_m.group(3)), 1)
            last_death_pos[name_m.group(1).lower()] = f" pos=<{x}, {y}, {z}>"

    # ───────────────────────────────────────────────────────────────
    # POŁĄCZENIA – poprawione parsowanie ID
    # ───────────────────────────────────────────────────────────────
    connect_m = re.search(r'Player "(.+?)"\(id=([^)]+)\)\s*is connected', line)
    if connect_m:
        name = connect_m.group(1).strip()
        player_id = connect_m.group(2).strip()  # GUID / BattlEye ID z ADM
        key = dedup_key("connect", name)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["join"] += 1
        player_login_times[name] = log_dt
        guid_to_name[player_id] = name
        msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {player_id})"
        await safe_send("connections", msg, "[32m")
        return

    # ───────────────────────────────────────────────────────────────
    # ROZŁĄCZENIA – poprawione parsowanie ID
    # ───────────────────────────────────────────────────────────────
    disconnect_m = re.search(r'Player "(.+?)"\(id=([^)]+)\)\s*has been disconnected', line)
    if disconnect_m:
        name = disconnect_m.group(1).strip()
        player_id = disconnect_m.group(2).strip()
        key = dedup_key("disconnect", name)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["disconnect"] += 1
        time_online = "nieznany"
        if name in player_login_times:
            delta = (log_dt - player_login_times[name]).total_seconds()
            minutes = int(delta // 60)
            seconds = int(delta % 60)
            time_online = f"{minutes} min {seconds} s"
            del player_login_times[name]
        emoji = "🔴"
        color = "[31m"
        msg = f"{date_str} | {log_time} {emoji} Rozłączono → {name} (ID: {player_id}) → {time_online}"
        await safe_send("connections", msg, color)
        return

    # ───────────────────────────────────────────────────────────────
    # CHAT
    # ───────────────────────────────────────────────────────────────
    chat_m = re.search(r'\[Chat - (.+?)\]\("(.+?)"\(id=(.+?)\)\): (.*)', line)
    if chat_m:
        detected_events["chat"] += 1
        channel = chat_m.group(1).strip()
        nick = chat_m.group(2).strip()
        message = chat_m.group(4).strip() or "[brak]"
        colors = {"Global": "[34m", "Admin": "[31m", "Team": "[36m", "Direct": "[37m", "Side": "[35m"}
        col = colors.get(channel, "[33m")
        msg = f"{date_str} | {log_time} 💬 [{channel}] {nick}: {message}"
        target_id = CHAT_CHANNEL_MAPPING.get(channel, CHANNEL_IDS["chat"])
        ch = client.get_channel(target_id)
        if ch:
            await ch.send(f"```ansi\n{col}{msg}[0m```")
        return

    # ───────────────────────────────────────────────────────────────
    # HITY (tylko nieśmiertelne – śmierć wysyłamy w killed by / died)
    # ───────────────────────────────────────────────────────────────
    hit_m = re.search(
        r'Player "(.+?)" .*?\[HP: ([\d.]+)\] hit by (.+?) into (.+?)\((\d+)\) for ([\d.]+) damage \((.+?)\)',
        line
    )
    if hit_m and "(DEAD)" not in line:
        detected_events["hit"] += 1
        nick = hit_m.group(1).strip()
        hp = float(hit_m.group(2))
        source = hit_m.group(3).strip()
        part = hit_m.group(4).strip()
        dmg = hit_m.group(6)
        ammo = hit_m.group(7).strip()
        # czyszczenie source
        source_match = re.search(r'(?:Player|AI) "(.+?)"', source)
        if source_match:
            source = source_match.group(1).strip()
        elif re.search(r'Wolf', source, re.I):
            source = "Wolf"
        lower_nick = nick.lower()
        if float(dmg) > 0:
            last_hit_details[lower_nick] = (source, ammo, None)
        color = "[33m" if hp > 20 else "[35m"
        emoji = "🔥"
        msg = f"{date_str} | {log_time} {emoji} {nick} (HP: {hp:.1f}) trafiony przez {source} w {part} za {dmg} dmg ({ammo})"
        await safe_send("damages", msg, color)
        return

    # specjalne obrażenia (upadek, bleed itp.)
    special_hit_m = re.search(r'Player "(.+?)" .*?\[HP: ([\d.]+)\] hit by (FallDamageHealth|Bleed|Starvation|Dehydration|Cold)', line)
    if special_hit_m and "(DEAD)" not in line:
        detected_events["hit"] += 1
        nick = special_hit_m.group(1).strip()
        hp = float(special_hit_m.group(2))
        source = special_hit_m.group(3).strip()
        lower_nick = nick.lower()
        last_hit_details[lower_nick] = (source, source, None)
        msg = f"{date_str} | {log_time} 🔥 {nick} (HP: {hp:.1f}) otrzymał obrażenia od {source}"
        await safe_send("damages", msg, "[35m")
        return

    # ───────────────────────────────────────────────────────────────
    # FUNKCJA CZYSZCZENIA NAZWY ZABÓJCY
    # ───────────────────────────────────────────────────────────────
    def clean_killer(raw: str) -> str:
        raw = raw.strip()
        # Player
        m = re.search(r'Player "(.+?)"', raw)
        if m:
            return m.group(1).strip()
        # AI / bot / NPC
        m = re.search(r'AI "(.+?)"', raw)
        if m:
            return f"{m.group(1).strip()} (AI)"
        # Zwierzęta
        if re.search(r'(?i)(wolf|canislupus)', raw):
            return "wilczur szary"
        if re.search(r'(?i)bear', raw):
            return "niedźwiedź"
        # Upadek / środowisko
        if "FallDamageHealth" in raw or "Fall" in raw:
            return "upadek"
        if "Cold" in raw:
            return "wychłodzenie"
        if "Starvation" in raw:
            return "głód"
        if "Dehydration" in raw:
            return "odwodnienie"
        # Infected / zombie
        if re.search(r'(?i)(infected|zombie)', raw):
            return "zombie / infected"
        # fallback – ostatnia sensowna część
        parts = raw.split()
        if len(parts) > 1:
            return " ".join(parts[:3])  # max 3 słowa
        return raw or "nieznany"

    # ───────────────────────────────────────────────────────────────
    # KILLED BY – GŁÓWNA ŚMIERĆ Z BRONIĄ I DYSTANSEM
    # ───────────────────────────────────────────────────────────────
    killed_m = re.search(
        r'Player "(.+?)" \s*\(DEAD\).*?(?:killed by|hit by)\s+(.+?)(?:\s+with\s+(.+?))?(?:\s+from\s+([\d.]+)\s*meters)?$',
        line, re.IGNORECASE
    )
    if killed_m:
        victim = killed_m.group(1).strip()
        killer_raw = killed_m.group(2).strip()
        weapon_raw = killed_m.group(3)
        distance = killed_m.group(4)
        killer = clean_killer(killer_raw)
        weapon = None
        if weapon_raw:
            weapon_match = re.search(r'\((.+?)\)', weapon_raw)
            weapon = weapon_match.group(1) if weapon_match else weapon_raw.strip()
        key = dedup_key("kill", victim)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1
        lower_victim = victim.lower()
        last_killed_by_time[lower_victim] = now
        dist_str = f" z {distance} m" if distance else ""
        weapon_str = f" ({weapon})" if weapon else ""
        # emoji
        if "wilczur szary" in killer:
            emoji = "🐺"
        elif "niedźwiedź" in killer:
            emoji = "🐻"
        elif "zombie" in killer or "infected" in killer:
            emoji = "🧟"
        elif "(AI)" in killer:
            emoji = "🔫"
        elif "upadek" in killer:
            emoji = "🪂"
        else:
            emoji = "☠️"
        coords_str = last_death_pos.get(lower_victim, "")
        msg = f"{date_str} | {log_time} {emoji} {victim} zabity przez {killer}{weapon_str}{dist_str}{coords_str}"
        await safe_send("kills", msg, "[31m")
        if lower_victim in last_death_pos:
            del last_death_pos[lower_victim]
        last_death_time[lower_victim] = now
        return

    # ───────────────────────────────────────────────────────────────
    # SAMOBÓJSTWO
    # ───────────────────────────────────────────────────────────────
    suicide_m = re.search(r'Player "(.+?)" \s*\(DEAD\).*?committed suicide', line)
    if suicide_m:
        nick = suicide_m.group(1).strip()
        lower_nick = nick.lower()
        key = dedup_key("death", nick)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1
        coords_str = last_death_pos.get(lower_nick, "")
        msg = f"{date_str} | {log_time} 💀 {nick} popełnił samobójstwo{coords_str}"
        await safe_send("kills", msg, "[31m")
        if lower_nick in last_death_pos:
            del last_death_pos[lower_nick]
        last_death_time[lower_nick] = now
        return

    # ───────────────────────────────────────────────────────────────
    # ŚMIERĆ Z STATYSTYK (ostatnia linia – bled out, upadek itp.)
    # ───────────────────────────────────────────────────────────────
    death_m = re.search(
        r'Player "(.+?)" \s*\(DEAD\).*?died\. Stats> Water: ([\d.]+) Energy: ([\d.]+) Bleed sources: (\d+)',
        line
    )
    if death_m:
        nick = death_m.group(1).strip()
        lower_nick = nick.lower()
        key = dedup_key("death", nick)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1
        # blokada duplikatów po killed by / suicide
        if now - last_killed_by_time[lower_nick] < 15:
            return
        water = float(death_m.group(2))
        energy = float(death_m.group(3))
        bleed = int(death_m.group(4))
        source, weapon_raw, _ = last_hit_details.get(lower_nick, (None, None, None))
        weapon = None
        if weapon_raw:
            weapon_match = re.search(r'\((.+?)\)', weapon_raw)
            weapon = weapon_match.group(1) if weapon_match else weapon_raw.strip()
        reason = "nieznana przyczyna"
        emoji_reason = "☠️"
        weapon_str = f" ({weapon})" if weapon else ""
        line_lower = line.lower()
        if "bled out" in line_lower or bleed > 0:
            reason = "wykrwawienie"
            emoji_reason = "🩸"
        elif "falldamagehealth" in line_lower or (source and "fall" in source.lower()):
            reason = "upadek"
            emoji_reason = "🪂"
        elif source and "cold" in source.lower():
            reason = "wychłodzenie"
            emoji_reason = "❄️"
        elif source and ("starvation" in source.lower() or energy < 200):
            reason = "głód"
            emoji_reason = "🍽️"
        elif source and ("dehydration" in source.lower() or water < 100):
            reason = "odwodnienie"
            emoji_reason = "💧"
        elif source:
            if "infected" in source.lower() or "zombie" in source.lower():
                reason = "zombie / infected"
                emoji_reason = "🧟"
            elif "wolf" in source.lower() or "canislupus" in source.lower():
                reason = "wilczur szary"
                emoji_reason = "🐺"
        coords_str = last_death_pos.get(lower_nick, "")
        msg = f"{date_str} | {log_time} {emoji_reason} {nick} zmarł ({reason}){weapon_str}{coords_str}"
        await safe_send("kills", msg, "[31m")
        if lower_nick in last_death_pos:
            del last_death_pos[lower_nick]
        if lower_nick in last_hit_details:
            del last_hit_details[lower_nick]
        last_death_time[lower_nick] = now
        return

    # ───────────────────────────────────────────────────────────────
    # KOLEJKA LOGOWANIA
    # ───────────────────────────────────────────────────────────────
    queue_m = re.search(r'\[Login\]: Adding player (.+?) \((\d+)\) to login queue at position (\d+)', line)
    if queue_m:
        name = queue_m.group(1).strip()
        player_id = queue_m.group(2)
        position = queue_m.group(3)
        key = dedup_key("queue", name)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["queue"] += 1
        msg = f"{date_str} | {log_time} 🕒 {name} (ID: {player_id}) dołączył do kolejki logowania na pozycji {position}"
        await safe_send("connections", msg, "[33m")
        return

    # ───────────────────────────────────────────────────────────────
    # NIEROZPOZNANE
    # ───────────────────────────────────────────────────────────────
    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except:
        pass
