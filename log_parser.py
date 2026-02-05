# log_parser.py - połączona wersja + poprawione zabójstwa i śmierci (dokładnie wg Twojego formatu)
import re
from datetime import datetime, timedelta
import time
from collections import defaultdict
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

last_death_time = defaultdict(float)
player_login_times = {}
guid_to_name = {}
last_hit_source = {}  # nick.lower() -> ostatni source trafienia
recent_godmode_events = {}  # guid -> timestamp ostatniego Set GodMode
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
            print(f"[DISCORD ERROR] Brak klucza '{channel_key}' w CHANNEL_IDS")
            return
        ch = client.get_channel(ch_id)
        if not ch:
            print(f"[DISCORD ERROR] Kanał '{channel_key}' (ID: {ch_id}) nie znaleziony!")
            return
        print(f"[DISCORD → {channel_key}] Wysyłam: {message[:80]}{'...' if len(message)>80 else ''}")
        try:
            await ch.send(f"```ansi\n{color_code}{message}[0m```")
        except Exception as e:
            print(f"[DISCORD SEND FAIL] {channel_key}: {e}")

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

    # 4. COT actions
    cot_m = re.search(r'\[COT\] (.+)', line)
    if cot_m:
        detected_events["cot"] += 1
        content = cot_m.group(1).strip()
        # Sprawdzamy, czy to Set GodMode dla gracza – zapisujemy timestamp
        godmode_m = re.search(r'Set GodMode To (true|false) \[guid=(.+?)\]', content)
        if godmode_m:
            guid = godmode_m.group(2)
            recent_godmode_events[guid] = now  # zapisujemy czas zdarzenia GodMode

        msg = f"{date_str} | {log_time} 🔧 [COT] {content}"
        await safe_send("admin", msg, "[35m")
        return

    # 5. Hits / Obrażenia
    hit_m = re.search(r'Player "(.+?)" \s*\(id=(.+?)\s*pos=<.+?>\)\[HP: ([\d.]+)\] hit by (.+?) into (.+?)\((\d+)\) for ([\d.]+) damage \((.+?)\)', line)
    if hit_m:
        detected_events["hit"] += 1
        nick = hit_m.group(1)
        hp = float(hit_m.group(3))
        source = hit_m.group(4)
        part = hit_m.group(5)
        dmg = hit_m.group(7)
        ammo = hit_m.group(8)
        last_hit_source[nick.lower()] = source
        is_dead = hp <= 0
        emoji = "☠️" if is_dead else "🔥" if hp < 20 else "⚡"
        color = "[31m" if is_dead else "[35m" if hp < 20 else "[33m"
        extra = " (ŚMIERĆ)" if is_dead else f" (HP: {hp:.1f})"
        msg = f"{date_str} | {log_time} {emoji} {nick}{extra} trafiony przez {source} w {part} za {dmg} dmg ({ammo})"
        await safe_send("damages", msg, color)
        if is_dead:
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

    # Połączona sekcja ZABÓJSTW i ŚMIERCI (najpierw dystans, potem stats/przyczyna)
    # Najpierw zabójstwo dystansowe – ale pomijamy jeśli niedawno był COT GodMode
    killed_m = re.search(r'Player "(.+?)" \s*\(DEAD\) .*? killed by (Player|AI) "(.+?)" .*? with (.+?) from ([\d.]+) meters', line)
    if killed_m:
        victim_name = killed_m.group(1).strip()
        killer_type = killed_m.group(2)
        killer_name = killed_m.group(3).strip()
        weapon = killed_m.group(4).strip()
        distance = killed_m.group(5)

        # Szukamy GUID ofiary (z innych linii lub zakładamy, że kill jest po hit)
        # Dla uproszczenia sprawdzamy, czy w ciągu 60s przed/po kill był COT GodMode dla dowolnego GUID
        should_send_kill = True
        for guid, ts in recent_godmode_events.items():
            if abs(now - ts) < 60:  # 60 sekund okna
                should_send_kill = False
                break

        if not should_send_kill:
            # Pomijamy wysyłanie kill jeśli był GodMode blisko w czasie
            return

        key = dedup_key("kill", victim_name)
        if key in processed_events: return
        processed_events.add(key)

        detected_events["kill"] += 1

        msg = f"{date_str} | {log_time} ☠️ {victim_name} zabity przez {killer_name} z {weapon} z {distance} m"
        await safe_send("kills", msg, "[31m")
        return

    # Potem śmierć z statsami / przyczyną
    death_m = re.search(r'Player "(.+?)" \(DEAD\) .*? died\. Stats> Water: ([\d.]+) Energy: ([\d.]+) Bleed sources: (\d+)', line)
    if death_m:
        detected_events["kill"] += 1
        nick = death_m.group(1).strip()
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
        msg = f"{date_str} | {log_time} {emoji_reason} {nick} zmarł ({reason})"
        await safe_send("kills", msg, "[31m")
        if lower_nick in last_hit_source:
            del last_hit_source[lower_nick]
        return

    # Nierozpoznane - zapisz
    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except:
        pass
