    # 2. Rozłączono + Kick/Ban
    if any(x in line.lower() for x in ["disconnected", "has been disconnected", "kicked", "banned"]) and 'Player ' in line:
        name_match = re.search(r'Player\s*(?:"([^"]+)"|([^(]+))', line, re.IGNORECASE)
        name = (name_match.group(1) or name_match.group(2)).strip() if name_match else "????"

        id_match = re.search(r'\((?:id|steamID|uid)?=(?P<guid>[^ )]+)(?:\s+pos=<[^>]+>)?\)', line, re.IGNORECASE)
        guid = id_match.group("guid").strip() if id_match else "brak"

        if guid in guid_to_name:
            name = guid_to_name[guid]

        detected_events["disconnect"] += 1

        time_online = "nieznany"
        if name in player_login_times:
            delta = datetime.utcnow() - player_login_times[name]
            minutes = int(delta.total_seconds() // 60)
            seconds = int(delta.total_seconds() % 60)
            time_online = f"{minutes} min {seconds} s"
            del player_login_times[name]

        is_kick = "kicked" in line.lower() or "Kicked" in line
        is_ban = "banned" in line.lower() or "Banned" in line

        if is_kick and "connection with host has been lost" in line.lower():
            is_kick = False

        if is_ban:
            emoji = "☠️"
            color = "[31m"
            extra = " (BAN)"
        elif is_kick:
            emoji = "⚡"
            color = "[38;5;208m"
            extra = " (KICK)"
        else:
            emoji = "🔴"
            color = "[31m"
            extra = ""

        msg = f"{date_str} | {log_time} {emoji} Rozłączono → {name} (ID: {guid}) → {time_online}{extra}"
        ch = client.get_channel(CHANNEL_IDS["connections"])
        if ch:
            await ch.send(f"```ansi\n{color}{msg}[0m\n```")
        return
