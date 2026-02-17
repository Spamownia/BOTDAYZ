# === CACHE COORDÓW (już działał, zostawiam) ===
if "(DEAD)" in line:
    pos_m = re.search(r'pos=<([\d\.-]+),\s*([\d\.-]+),\s*([\d\.-]+)>', line)
    name_m = re.search(r'Player "(.+?)"', line)
    if pos_m and name_m:
        x = round(float(pos_m.group(1)), 1)
        y = round(float(pos_m.group(2)), 1)
        z = round(float(pos_m.group(3)), 1)
        last_death_pos[name_m.group(1).lower()] = f" pos=<{x}, {y}, {z}>"

# ───────────────────────────────────────────────────────────────
# NOWA FUNKCJA CZYSZCZENIA ZABÓJCY
# ───────────────────────────────────────────────────────────────
def clean_killer(raw: str) -> str:
    raw = raw.strip()
    # AI
    m = re.search(r'AI "(.+?)"', raw)
    if m:
        return f"{m.group(1)} (AI)"
    # Player
    m = re.search(r'Player "(.+?)"', raw)
    if m:
        return m.group(1)
    # Wilk
    if re.search(r'(?i)(wolf|canislupus)', raw):
        return "wilczur szary"
    # Upadek
    if "FallDamageHealth" in raw:
        return "upadek"
    # Inne zwierzęta / specjalne (możesz rozbudować)
    if re.search(r'(?i)bear', raw):
        return "niedźwiedź"
    return raw  # fallback

# ───────────────────────────────────────────────────────────────
# KILLED BY – POPRAWIONY REGEX + CZYSZCZENIE
# ───────────────────────────────────────────────────────────────
killed_m = re.search(
    r'Player "(.+?)" .*?\(DEAD\).*? (?:killed by|hit by) (.+?)(?: into | with | from | \( |$)',
    line, re.IGNORECASE
)
if killed_m:
    victim = killed_m.group(1).strip()
    killer_raw = killed_m.group(2).strip()

    killer = clean_killer(killer_raw)
    weapon_raw = None
    distance = None

    # dodatkowe wyciągnięcie broni i dystansu (jeśli jest)
    w_m = re.search(r'with\s+(.+?)(?:\s+from\s+([\d.]+)\s*m)?', line, re.I)
    if w_m:
        weapon_raw = w_m.group(1).strip()
        distance = w_m.group(2)

    key = dedup_key("kill", victim)
    if key in processed_events: return
    processed_events.add(key)
    detected_events["kill"] += 1

    lower_victim = victim.lower()
    last_killed_by_time[lower_victim] = now

    dist_str = f" z {distance} m" if distance else ""
    weapon_str = f" ({weapon_raw})" if weapon_raw else ""

    # emoji
    if "wilczur szary" in killer or "Wolf" in killer_raw:
        emoji = "🐺"
    elif "AI" in killer:
        emoji = "🔫"
    elif "upadek" in killer:
        emoji = "🪂"
    elif "Infected" in killer_raw or "Zombie" in killer_raw:
        emoji = "🧟"
    else:
        emoji = "☠️"

    coords_str = last_death_pos.get(lower_victim, "")
    msg = f"{date_str} | {log_time} {emoji} {victim} zabity przez {killer}{weapon_str}{dist_str}{coords_str}"
    await safe_send("kills", msg, "[31m")

    if lower_victim in last_death_pos:
        del last_death_pos[lower_victim]
    last_death_time[lower_victim] = now
    return
