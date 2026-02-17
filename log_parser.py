# log_parser.py - WERSJA Z COORDAMI + ROZSZERZONE PRZYCZYNY ŚMIERCI
import re
from datetime import datetime
import time
from collections import defaultdict
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

last_death_time     = defaultdict(float)
last_killed_by_time = defaultdict(float)
player_login_times  = {}
guid_to_name        = {}
last_hit_details    = defaultdict(lambda: (None, None, None))  # source, weapon, distance
last_death_pos      = defaultdict(str)                         # nick.lower() -> " pos=<x, y, z>"
UNPARSED_LOG        = "unparsed_lines.log"
SUMMARY_INTERVAL    = 30
last_summary_time   = time.time()
processed_count     = 0
detected_events     = {"join":0, "disconnect":0, "cot":0, "hit":0, "kill":0, "chat":0, "other":0, "unconscious":0, "queue":0}
processed_events    = set()

async def process_line(bot, line: str):
    global last_summary_time, processed_count
    client = bot
    line = line.strip()
    if not line:
        return

    # FILTR RPT (tylko kolejka)
    if '[Login]: Adding player' not in line:
        rpt_markers = ['[CE][', 'Conflicting addon', 'Updating base class', 'String "', 'Localization not present', '!!! [CE][', 'CHAR_DEBUG']
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

    def dedup_key(action, name=""):
        return (log_time, name.lower(), action)

    async def safe_send(channel_key, message, color_code):
        ch_id = CHANNEL_IDS.get(channel_key)
        if not ch_id: return
        ch = client.get_channel(ch_id)
        if not ch: return
        try:
            await ch.send(f"```ansi\n{color_code}{message}[0m```")
        except:
            pass

    # === CACHE COORDÓW Z KAŻDEJ LINII (DEAD) ===
    if "(DEAD)" in line:
        pos_m = re.search(r'pos=<([\d\.-]+),\s*([\d\.-]+),\s*([\d\.-]+)>', line)
        name_m = re.search(r'Player "(.+?)"', line)
        if pos_m and name_m:
            x = round(float(pos_m.group(1)), 1)
            y = round(float(pos_m.group(2)), 1)
            z = round(float(pos_m.group(3)), 1)
            last_death_pos[name_m.group(1).lower()] = f" pos=<{x}, {y}, {z}>"

    # ───────────────────────────────────────────────────────────────
    # POŁĄCZENIA / ROZŁĄCZENIA / CHAT / COT / UNCONSCIOUS (bez zmian)
    # (cała reszta sekcji connect, disconnect, chat, cot, hit, uncon, regain – taka sama jak w poprzedniej wersji)
    # Dla oszczędności miejsca – wklejam tylko zmienione sekcje śmierci.
    # Pełny plik masz w poprzedniej wiadomości – wystarczy zamienić sekcje poniżej.

    # ───────────────────────────────────────────────────────────────
    # HITY (bez zmian – nie wysyłamy śmierci w hitach)
    # ───────────────────────────────────────────────────────────────
    # ... (hit_m i special_hit_m bez zmian)

    # ───────────────────────────────────────────────────────────────
    # KILLED BY + COORDY
    # ───────────────────────────────────────────────────────────────
    killed_m = re.search(
        r'Player "(.+?)" \s*\(DEAD\).*?(killed by|hit by)\s+(.+?)(?:\s+with\s+(.+?))?(?:\s+from\s+([\d.]+)\s*meters)?',
        line, re.IGNORECASE
    )
    if killed_m:
        victim = killed_m.group(1).strip()
        killer_raw = killed_m.group(3).strip()
        weapon_raw = killed_m.group(4)
        distance = killed_m.group(5)

        killer_match = re.search(r'(?:Player|AI) "(.+?)"', killer_raw)
        killer = killer_match.group(1) if killer_match else killer_raw

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

        if "Wolf" in killer_raw or "CanisLupus" in killer_raw:
            emoji = "🐺"
            killer = "wilczur szary"
        elif "Bear" in killer_raw:
            emoji = "🐻"
            killer = "niedźwiedź"
        elif "Infected" in killer_raw or "Zombie" in killer_raw:
            emoji = "🧟"
        elif "Player" in killer_raw or "AI" in killer_raw:
            emoji = "🔫"
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
    # SAMOBÓJSTWO + COORDY
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
    # DEATH STATS + COORDY + ROZSZERZONE PRZYCZYNY
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

        # === ROZSZERZONE PRZYCZYNY ===
        line_lower = line.lower()
        if "bled out" in line_lower:
            reason = "wykrwawienie"
            emoji_reason = "🩸"
        elif "falldamagehealth" in line_lower or (source and "fall" in source.lower()):
            reason = "upadek"
            emoji_reason = "🪂"
        elif source and "cold" in source.lower():
            reason = "wychłodzenie"
            emoji_reason = "❄️"
        elif bleed > 0:
            reason = "wykrwawienie"
            emoji_reason = "🩸"
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

    # KOLEJKA + reszta (bez zmian)
    # ... (queue_m, unparsed – identycznie jak wcześniej)

    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except:
        pass
