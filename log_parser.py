# Na górze pliku, obok innych defaultdict
last_killed_time = defaultdict(float)

# ...

    # ───────────────────────────────────────────────────────────────
    # LINIA "killed by"
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

        # ... (reszta bez zmian)

        key = dedup_key("kill", victim)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1

        last_killed_time[victim.lower()] = now   # ← DODANE

        dist_str = f" z {distance} m" if distance else ""
        weapon_str = f" ({weapon})" if weapon else ""
        emoji = "🔫" if "Player" in killer_raw or "AI" in killer_raw else "🧟" if "Infected" in killer_raw else "🐺" if "Wolf" in killer_raw else "☠️"

        msg = f"{date_str} | {log_time} {emoji} {victim} zabity przez {killer}{weapon_str}{dist_str}"
        await safe_send("kills", msg, "[31m")
        last_death_time[victim.lower()] = now
        return

    # ───────────────────────────────────────────────────────────────
    # LINIA "died. Stats>"
    # ───────────────────────────────────────────────────────────────
    death_m = re.search(
        r'Player "(.+?)" \s*\(DEAD\).*?died\. Stats> Water: ([\d.]+) Energy: ([\d.]+) Bleed sources: (\d+)',
        line
    )
    if death_m:
        nick = death_m.group(1).strip()
        key = dedup_key("death", nick)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1

        lower_nick = nick.lower()

        if now - last_killed_time[lower_nick] < 5:   # ← DODANE – blokuje duplikat
            return

        # ... reszta bez zmian
