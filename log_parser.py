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

    # === KOLEJKA LOGOWANIA – PRZENIESIONA NA SAMĄ GÓRĘ ===
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
        return   # <-- ważne: kończymy przetwarzanie tej linii

    # CACHE COORDYNAT Z KAŻDEJ LINII Z (DEAD)
    if "(DEAD)" in line:
        pos_m = re.search(r'pos=<([\d\.-]+),\s*([\d\.-]+),\s*([\d\.-]+)>', line)
        name_m = re.search(r'(?:Player|AI) "(.+?)"', line)
        if pos_m and name_m:
            x = round(float(pos_m.group(1)), 1)
            y = round(float(pos_m.group(2)), 1)
            z = round(float(pos_m.group(3)), 1)
            last_death_pos[name_m.group(1).lower()] = f" pos=<{x}, {y}, {z}>"

    # POBIERANIE STEAMID64 Z LINII COT + WYSYŁANIE NA KANAŁ ADMIN
    cot_m = re.search(r'\[COT\] (\d{17}): (.*?)(?: \[guid=([a-zA-Z0-9_=-]+)\])?$', line)
    if cot_m:
        steamid64 = cot_m.group(1)
        action = cot_m.group(2).strip()
        guid = cot_m.group(3) if cot_m.group(3) else "brak GUID"
        if guid != "brak GUID":
            guid_to_steamid[guid] = steamid64
        detected_events["cot"] += 1
        msg = f"{date_str} | {log_time} 🛠️ [COT] {action} | SteamID64: {steamid64} (GUID: {guid})"
        await safe_send("admin", msg, "[36m")
        return

    # POŁĄCZENIA
    connect_m = re.search(r'Player "(.+?)"\s*\(id=([^)\s]+)(?:\s+pos=<[^>]+>)?\)\s*is connected', line)
    if connect_m:
        name = connect_m.group(1).strip()
        guid = connect_m.group(2).strip()
        key = dedup_key("connect", name)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["join"] += 1
        player_login_times[name] = log_dt
        guid_to_name[guid] = name
        steamid = guid_to_steamid.get(guid, "brak danych")
        msg = f"{date_str} | {log_time} 🟢 Połączono → {name} (GUID: {guid}) (SteamID64: {steamid})"
        await safe_send("connections", msg, "[32m")
        return

    # ROZŁĄCZENIA
    disconnect_m = re.search(r'Player "(.+?)"\s*\(id=([^)\s]+)(?:\s+pos=<[^>]+>)?\)\s*has been disconnected', line)
    if disconnect_m:
        name = disconnect_m.group(1).strip()
        guid = disconnect_m.group(2).strip()
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
        steamid = guid_to_steamid.get(guid, "brak danych")
        emoji = "🔴"
        color = "[31m"
        msg = f"{date_str} | {log_time} {emoji} Rozłączono → {name} (GUID: {guid}) (SteamID64: {steamid}) → {time_online}"
        await safe_send("connections", msg, color)
        return

    # ... reszta kodu (chat, hity, kill, suicide, death, unparsed) pozostaje bez zmian ...
    # (wklej tutaj całą resztę od # CHAT aż do końca funkcji)

    # NIEROZPOZNANE
    detected_events["other"] += 1
    try:
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
    except:
        pass
