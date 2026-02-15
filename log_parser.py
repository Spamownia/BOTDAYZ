# log_parser.py - połączona wersja + poprawione zabójstwa i śmierci + TYLKO KOLEJKA LOGOWANIA
import re
from datetime import datetime
import time
from collections import defaultdict
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

last_death_time       = defaultdict(float)
last_killed_by_time   = defaultdict(float)   # blokada duplikatów po linii "killed by"
player_login_times    = {}
guid_to_name          = {}
last_hit_details      = defaultdict(lambda: (None, None, None))  # nick.lower() -> (source, weapon, distance)
UNPARSED_LOG          = "unparsed_lines.log"
SUMMARY_INTERVAL      = 30
last_summary_time     = time.time()
processed_count       = 0
detected_events = {"join":0, "disconnect":0, "cot":0, "hit":0, "kill":0, "chat":0, "other":0, "unconscious":0, "queue":0}
processed_events = set()  # deduplikacja

async def process_line(bot, line: str):
    global last_summary_time, processed_count
    client = bot
    line = line.strip()
    if not line:
        return

    # FILTR – pomijamy prawie całe .RPT poza kolejką
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
    # Połączenia
    # ───────────────────────────────────────────────────────────────
    connect_m = re.search(r'Player "(.+?)"\s*\(id=(.+?)\)\s*is connected', line)
    if connect_m:
        name = connect_m.group(1).strip()
        guid = connect_m.group(2)
        key = dedup_key("connect", name)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["join"] += 1
        player_login_times[name] = log_dt
        guid_to_name[guid] = name
        msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (ID: {guid})"
        await safe_send("connections", msg, "[32m")
        return

    # ───────────────────────────────────────────────────────────────
    # Rozłączenia
    # ───────────────────────────────────────────────────────────────
    disconnect_m = re.search(r'Player "(.+?)"\s*\(id=(.+?)\)\s*has been disconnected', line)
    if disconnect_m:
        name = disconnect_m.group(1).strip()
        guid = disconnect_m.group(2)
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
        msg = f"{date_str} | {log_time} {emoji} Rozłączono → {name} (ID: {guid}) → {time_online}"
        await safe_send("connections", msg, color)
        return

    # ───────────────────────────────────────────────────────────────
    # Chat
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
    # COT
    # ───────────────────────────────────────────────────────────────
    cot_m = re.search(r'\[COT\] (.+)', line)
    if cot_m:
        detected_events["cot"] += 1
        content = cot_m.group(1).strip()
        emoji = "🔧"
        color = "[37m"
        if "Kicked" in content:
            emoji = "🚫"
            color = "[33m"
        msg = f"{date_str} | {log_time} {emoji} [COT] {content}"
        await safe_send("admin", msg, color)
        return

    # ───────────────────────────────────────────────────────────────
    # Hity
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
        color = "[33m" if hp > 20 else "[35m"
        extra = " (ŚMIERĆ)" if is_dead else f" (HP: {hp:.1f})"
        emoji = "💀" if is_dead else "🔥"
        lower_nick = nick.lower()
        if float(dmg) > 0:
            last_hit_details[lower_nick] = (source, ammo, None)
        msg = f"{date_str} | {log_time} {emoji} {nick}{extra} trafiony przez {source} w {part} za {dmg} dmg ({ammo})"
        await safe_send("damages", msg, color)
        if is_dead:
            kill_msg = f"{date_str} | {log_time} ☠️ {nick} zabity przez {source} ({ammo})"
            await safe_send("kills", kill_msg, "[31m")
        return

    special_hit_m = re.search(r'Player "(.+?)" .*?\[HP: ([\d.]+)\] hit by (FallDamageHealth|Bleed|Starvation|Dehydration|Cold)', line)
    if special_hit_m:
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
    # Nieprzytomność
    # ───────────────────────────────────────────────────────────────
    uncon_m = re.search(r'Player "(.+?)" .*? is unconscious', line)
    if uncon_m:
        detected_events["unconscious"] += 1
        nick = uncon_m.group(1)
        msg = f"{date_str} | {log_time} 😵 {nick} jest nieprzytomny"
        await safe_send("damages", msg, "[31m")
        return

    regain_m = re.search(r'Player "(.+?)" .*? regained consciousness', line)
    if regain_m:
        detected_events["unconscious"] += 1
        nick = regain_m.group(1)
        msg = f"{date_str} | {log_time} 🟢 {nick} odzyskał przytomność"
        await safe_send("damages", msg, "[32m")
        return

    # ───────────────────────────────────────────────────────────────
    # 1. LINIA "killed by" – najpewniejsza, blokuje wszystko inne
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

        # Czyszczenie nazwy zabójcy
        killer_match = re.search(r'(?:Player|AI) "(.+?)"', killer_raw)
        killer = killer_match.group(1) if killer_match else killer_raw

        # Czyszczenie broni
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

        msg = f"{date_str} | {log_time} {emoji} {victim} zabity przez {killer}{weapon_str}{dist_str}"
        await safe_send("kills", msg, "[31m")
        last_death_time[lower_victim] = now
        return

    # ───────────────────────────────────────────────────────────────
    # 2. Samobójstwo (committed suicide)
    # ───────────────────────────────────────────────────────────────
    suicide_m = re.search(r'Player "(.+?)" \s*\(DEAD\).*?committed suicide', line)
    if suicide_m:
        nick = suicide_m.group(1).strip()
        lower_nick = nick.lower()

        key = dedup_key("death", nick)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1

        msg = f"{date_str} | {log_time} 💀 {nick} popełnił samobójstwo"
        await safe_send("kills", msg, "[31m")
        last_death_time[lower_nick] = now
        return

    # ───────────────────────────────────────────────────────────────
    # 3. LINIA "died. Stats>" – tylko gdy nie było killed by / suicide
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

        # Blokada po linii killed by lub suicide (15 sekund)
        if now - last_killed_by_time[lower_nick] < 15:
            return

        water = float(death_m.group(2))
        energy = float(death_m.group(3))
        bleed = int(death_m.group(4))

        source, weapon_raw, distance = last_hit_details.get(lower_nick, (None, None, None))

        weapon = None
        if weapon_raw:
            weapon_match = re.search(r'\((.+?)\)', weapon_raw)
            weapon = weapon_match.group(1) if weapon_match else weapon_raw.strip()

        reason = "nieznana przyczyna"
        emoji_reason = "☠️"
        weapon_str = f" ({weapon})" if weapon else ""
        dist_str = f" z {distance} m" if distance else ""

        if source:
            if "Infected" in source or "Zombie" in source:
                reason = "zombie / infected"
                emoji_reason = "🧟"
            elif "Wolf" in source or "CanisLupus" in source:
                reason = "wilczur szary"
                emoji_reason = "🐺"
            elif "Bear" in source:
                reason = "niedźwiedź"
                emoji_reason = "🐻"
            elif "explosion" in source.lower() or "LandMine" in source:
                reason = "eksplozja / mina"
                emoji_reason = "💥"
            elif "Fall" in source or "FallDamage" in source:
                reason = "upadek"
                emoji_reason = "🪂"
            elif bleed > 0 and (water < 100 or energy < 200):
                reason = "wykrwawienie / wyczerpanie"
                emoji_reason = "🩸"
            else:
                reason = source

        msg = f"{date_str} | {log_time} {emoji_reason} {nick} zmarł ({reason}){weapon_str}{dist_str}"
        await safe_send("kills", msg, "[31m")
        last_death_time[lower_nick] = now

        if lower_nick in last_hit_details:
            del last_hit_details[lower_nick]
        return

    # KOLEJKA LOGOWANIA (z .RPT)
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

    # Nierozpoznane
    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except:
        pass
