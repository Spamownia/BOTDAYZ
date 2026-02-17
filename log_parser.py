# log_parser.py - POŁĄCZONA WERSJA ŚMIERCI (jedna wiadomość zamiast dwóch)
import re
from datetime import datetime
import time
from collections import defaultdict
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

last_death_time       = defaultdict(float)
last_killed_by_time   = defaultdict(float)
player_login_times    = {}
guid_to_name          = {}
last_hit_details      = defaultdict(lambda: (None, None, None))
UNPARSED_LOG          = "unparsed_lines.log"
SUMMARY_INTERVAL      = 30
last_summary_time     = time.time()
processed_count       = 0
detected_events = {"join":0, "disconnect":0, "cot":0, "hit":0, "kill":0, "chat":0, "other":0, "unconscious":0, "queue":0}
processed_events = set()

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

    # === POŁĄCZENIA / ROZŁĄCZENIA / CHAT / COT / UNCONSCIOUS (bez zmian) ===
    # (cała reszta kodu bez zmian – tylko sekcje hit i killed by zostały poprawione)

    # ───────────────────────────────────────────────────────────────
    # HITY – teraz BEZ duplikatu przy śmierci
    # ───────────────────────────────────────────────────────────────
    hit_m = re.search(
        r'Player "(.+?)" .*?\[HP: ([\d.]+)\] hit by (.+?) into (.+?)\((\d+)\) for ([\d.]+) damage \((.+?)\)',
        line
    )
    if hit_m:
        detected_events["hit"] += 1
        nick = hit_m.group(1).strip()
        hp = float(hit_m.group(2))
        source = hit_m.group(3).strip()
        part = hit_m.group(4).strip()
        dmg = hit_m.group(6)
        ammo = hit_m.group(7).strip()
        is_dead = "(DEAD)" in line

        # CZYSZCZENIE SOURCE (żeby nie było długiego (id=… pos=…))
        source_match = re.search(r'(?:Player|AI) "(.+?)"', source)
        if source_match:
            source = source_match.group(1).strip()
        elif re.search(r'Wolf', source, re.I):
            source = "Wolf"

        lower_nick = nick.lower()
        if float(dmg) > 0:
            last_hit_details[lower_nick] = (source, ammo, None)

        color = "[33m" if hp > 20 else "[35m"
        extra = " (ŚMIERĆ)" if is_dead else f" (HP: {hp:.1f})"
        emoji = "💀" if is_dead else "🔥"

        # WYŚLIJ HIT TYLKO jeśli to NIE jest śmiertelny cios
        if not is_dead:
            msg = f"{date_str} | {log_time} {emoji} {nick}{extra} trafiony przez {source} w {part} za {dmg} dmg ({ammo})"
            await safe_send("damages", msg, color)

        return

    # specjalne hity (Fall, Bleed itp.)
    special_hit_m = re.search(r'Player "(.+?)" .*?\[HP: ([\d.]+)\] hit by (FallDamageHealth|Bleed|Starvation|Dehydration|Cold)', line)
    if special_hit_m:
        detected_events["hit"] += 1
        nick = special_hit_m.group(1).strip()
        hp = float(special_hit_m.group(2))
        source = special_hit_m.group(3).strip()
        lower_nick = nick.lower()
        is_dead = "(DEAD)" in line

        last_hit_details[lower_nick] = (source, source, None)

        if not is_dead:
            msg = f"{date_str} | {log_time} 🔥 {nick} (HP: {hp:.1f}) otrzymał obrażenia od {source}"
            await safe_send("damages", msg, "[35m")
        return

    # (reszta sekcji: unconscious, connect, disconnect, chat, cot – bez zmian)

    # ───────────────────────────────────────────────────────────────
    # KILLED BY – GŁÓWNA ŚMIERĆ + POŁĄCZENIE INFORMACJI
    # ───────────────────────────────────────────────────────────────
    killed_m = re.search(
        r'Player "(.+?)" \s*\(DEAD\).*?killed by\s+(.+?)(?:\s+with\s+(.+?))?(?:\s+from\s+([\d.]+)\s*meters)?$',
        line, re.IGNORECASE
    )
    if killed_m:
        victim = killed_m.group(1).strip()
        killer_raw = killed_m.group(2).strip()
        weapon_raw = killed_m.group(3)
        distance = killed_m.group(4)

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
        hit_info = last_hit_details.get(lower_victim, (None, None, None))
        hit_ammo = hit_info[1]

        last_killed_by_time[lower_victim] = now
        dist_str = f" z {distance} m" if distance else ""
        weapon_str = f" ({weapon})" if weapon else ""
        extra_str = f" ({hit_ammo})" if hit_ammo and not weapon else ""

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

        msg = f"{date_str} | {log_time} {emoji} {victim} zabity przez {killer}{weapon_str}{dist_str}{extra_str}"
        await safe_send("kills", msg, "[31m")

        last_death_time[lower_victim] = now
        if lower_victim in last_hit_details:
            del last_hit_details[lower_victim]
        return

    # suicide i death_m – bez zmian (działają jak wcześniej)

    # ... reszta kodu (suicide_m, death_m, queue, unparsed) pozostaje taka sama ...

    # (dla kompletności – reszta pliku jest identyczna jak u Ciebie, tylko powyższe sekcje zmienione)
