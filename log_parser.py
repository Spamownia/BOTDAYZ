# log_parser.py - połączona wersja + poprawione zabójstwa i śmierci + TYLKO KOLEJKA LOGOWANIA (bez StateMachine)
import re
from datetime import datetime
import time
from collections import defaultdict
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

last_death_time = defaultdict(float)
player_login_times = {}
guid_to_name = {}
last_hit_source = {}  # nick.lower() -> ostatni source trafienia
UNPARSED_LOG = "unparsed_lines.log"
SUMMARY_INTERVAL = 30
last_summary_time = time.time()
processed_count = 0
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

    # DEBUG PRINT TYLKO DLA ADM (bez .d+ w time)
    time_match = re.search(r'^(\d{1,2}:\d{2}:\d{2})(?:\.\d+)?', line)
    if time_match:
        full_match = time_match.group(0)
        is_rpt = '.' in full_match
    else:
        is_rpt = True

    if not is_rpt:
        print(f"[PARSER DEBUG] Przetwarzam linię: {line[:120]}{'...' if len(line)>120 else ''}")

    processed_count += 1
    now = time.time()
    if now - last_summary_time >= SUMMARY_INTERVAL:
        summary = f"[PARSER SUMMARY @ {datetime.utcnow().strftime('%H:%M:%S')}] {processed_count} linii | "
        summary += " | ".join(f"{k}: {v}" for k,v in detected_events.items() if v > 0)
        print(summary)
        last_summary_time = now
        processed_count = 0
        for k in detected_events: detected_events[k] = 0

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
            await ch.send(f"```ansi
        except:
            pass

    # 1. Połączenia
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

    # 2. Rozłączenia
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

    # 3. Chat
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
            print(f"[DISCORD → chat/{channel}] Wysyłam: {msg[:80]}...")
            await ch.send(f"```ansi\n{col}{msg}[0m```")
        else:
            print(f"[DISCORD ERROR] Kanał dla {channel} (ID: {target_id}) nie znaleziony!")
        return

    # 4. COT actions (z wyróżnieniem kicków)
    cot_m = re.search(r'\[COT\] (.+)', line)
    if cot_m:
        detected_events["cot"] += 1
        content = cot_m.group(1).strip()
        emoji = "🔧"
        color = "[37m"
        if "Kicked" in content:
            emoji = "🚫"
            color = "[33m" # żółty dla kicków
        msg = f"{date_str} | {log_time} {emoji} [COT] {content}"
        await safe_send("admin", msg, color)
        return

    # 5. Hity i obrażenia (elastyczny regex)
    hit_m = re.search(r'Player "(.+?)" \s*\(id=(.+?)\s*pos=<.+?>\)\[HP: ([\d.]+)\] hit by (.+?)( into (.+?)\((\d+)\) for ([\d.]+) damage \((.+?)\))?', line)
    if hit_m:
        detected_events["hit"] += 1
        nick = hit_m.group(1).strip()
        hp = float(hit_m.group(3))
        source = hit_m.group(4).strip()
        if hit_m.group(5):  # jeśli jest "into"
            part = hit_m.group(6).strip()
            dmg = hit_m.group(8)
            ammo = hit_m.group(9).strip()
        else:
            part = "nieznana"
            dmg = "nieznane"
            ammo = "nieznane"
        is_dead = "(DEAD)" in line or hp <= 0
        color = "[33m" if hp > 20 else "[35m"
        extra = " (ŚMIERĆ)" if is_dead else f" (HP: {hp:.1f})"
        emoji = "💀" if is_dead else "🔥"
        lower_nick = nick.lower()
        last_hit_source[lower_nick] = source
        msg = f"{date_str} | {log_time} {emoji} {nick}{extra} trafiony przez {source} w {part} za {dmg} dmg ({ammo})"
        await safe_send("damages", msg, color)
        if is_dead:
            if "FallDamage" in source:
                kill_msg = f"{date_str} | {log_time} 🪂 {nick} zmarł (upadek z wysokości)"
            elif "Infected" in source or "Zombie" in source:
                kill_msg = f"{date_str} | {log_time} 🧟 {nick} zabity przez zombie"
            else:
                kill_msg = f"{date_str} | {log_time} ☠️ {nick} zabity przez {source}"
            await safe_send("kills", kill_msg, "[31m")
        return

    # 6. Nieprzytomność
    uncon_m = re.search(r'Player "(.+?)" \s*\(id=(.+?)\s*pos=<.+?>\) is unconscious', line)
    if uncon_m:
        detected_events["unconscious"] += 1
        nick = uncon_m.group(1)
        msg = f"{date_str} | {log_time} 😵 {nick} jest nieprzytomny"
        await safe_send("damages", msg, "[31m")
        return

    regain_m = re.search(r'Player "(.+?)" \s*\(id=(.+?)\s*pos=<.+?>\) regained consciousness', line)
    if regain_m:
        detected_events["unconscious"] += 1
        nick = regain_m.group(1)
        msg = f"{date_str} | {log_time} 🟢 {nick} odzyskał przytomność"
        await safe_send("damages", msg, "[32m")
        return

    # Połączona sekcja ZABÓJSTW i ŚMIERCI (elastyczny regex)
    killed_m = re.search(r'Player "(.+?)" \s*\(DEAD\).*?killed by (.+?)( with (.+?) from ([\d.]+) meters)?', line)
    if killed_m:
        victim_name = killed_m.group(1).strip()
        killer = killed_m.group(2).strip().replace('"', '')  # usuwanie cudzysłowów
        if "Player " in killer:
            killer = killer.replace("Player ", "")
        if "AI " in killer:
            killer = killer.replace("AI ", "")
        if group(3):
            weapon = killed_m.group(4).strip()
            distance = killed_m.group(5)
            msg = f"{date_str} | {log_time} ☠️ {victim_name} zabity przez {killer} z {weapon} z {distance} m"
        else:
            if "Animal_CanisLupus" in killer:
                msg = f"{date_str} | {log_time} 🐺 {victim_name} zabity przez wilka ({killer})"
            else:
                msg = f"{date_str} | {log_time} ☠️ {victim_name} zabity przez {killer}"
        key = dedup_key("kill", victim_name)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1
        await safe_send("kills", msg, "[31m")
        return

    death_m = re.search(r'Player "(.+?)" \s*\(DEAD\).*?died\. Stats> Water: ([\d.]+) Energy: ([\d.]+) Bleed sources: (\d+)', line)
    if death_m:
        nick = death_m.group(1).strip()
        key = dedup_key("death", nick)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1
        water = float(death_m.group(2))
        energy = float(death_m.group(3))
        bleed = int(death_m.group(4))
        lower_nick = nick.lower()
        reason = "nieznana przyczyna"
        emoji_reason = "☠️"
        if lower_nick in last_hit_source:
            last_source = last_hit_source[lower_nick]
            if "Infected" in last_source or "Zombie" in last_source:
                reason = "zainfekowany / zombie"
                emoji_reason = "🧟"
            elif "explosion" in last_source.lower() or "LandMine" in last_source:
                reason = "eksplozja / mina"
                emoji_reason = "💥"
            elif "Player" in last_source:
                reason = "zabity przez gracza"
                emoji_reason = "🔫"
            elif "Fall" in last_source or "FallDamage" in last_source:
                reason = "upadek z wysokości"
                emoji_reason = "🪂"
            elif bleed > 0 and water < 100 and energy < 200:
                reason = "wykrwawienie / wyczerpanie"
                emoji_reason = "🩸"
            else:
                reason = f"ostatni hit: {last_source}"
            del last_hit_source[lower_nick]
        msg = f"{date_str} | {log_time} {emoji_reason} {nick} zmarł ({reason})"
        await safe_send("kills", msg, "[31m")
        return

    # TYLKO KOLEJKA LOGOWANIA (z .RPT) - z debugiem
    queue_m = re.search(r'\[Login\]: Adding player (.+?) \((\d+)\) to login queue at position (\d+)', line)
    if queue_m:
        name = queue_m.group(1).strip()
        player_id = queue_m.group(2)
        position = queue_m.group(3)
        key = dedup_key("queue", name)
        if key in processed_events:
            return
        processed_events.add(key)
        detected_events["queue"] += 1
        msg = f"{date_str} | {log_time} 🕒 {name} (ID: {player_id}) dołączył do kolejki logowania na pozycji {position}"
        await safe_send("connections", msg, "[33m") # żółty
        return

    # Debug dla innych linii "Login" (bez kolejki) - tylko print, bez wysyłania
    if "Login" in line and "queue" not in line.lower():
        pass  # cichy debug - nie spamuje konsoli

    # Nierozpoznane - zapisz do pliku
    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except:
        pass
