# Na górze pliku – dodaj / zmień
last_seen_killed_by = defaultdict(float)   # kiedy ostatnio była linia killed by dla tego nicka

# W sekcji killed_m (po detected_events["kill"] += 1 i przed msg = ...):
        lower_victim = victim.lower()
        last_seen_killed_by[lower_victim] = now   # ← zapisujemy, że była linia killed by

        # ... reszta bez zmian (dist_str, weapon_str, emoji, msg, safe_send)

# W sekcji death_m – ZAMIEŃ cały blok if death_m: na to:
    if death_m:
        nick = death_m.group(1).strip()
        lower_nick = nick.lower()

        key = dedup_key("death", nick)
        if key in processed_events: return
        processed_events.add(key)
        detected_events["kill"] += 1

        # Jeśli w ciągu ostatnich 300 sekund była linia killed by → NIE wysyłamy nic
        if now - last_seen_killed_by[lower_nick] < 300:
            return

        # Tutaj jesteśmy tylko w przypadkach, gdy NIE było killed by (zombie, upadek, wilk itp.)
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
