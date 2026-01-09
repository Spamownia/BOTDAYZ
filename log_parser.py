# Słownik: nazwa gracza → czas logowania
player_login_times = {}

# ... reszta kodu ...

# FINALNE POŁĄCZENIE – zapisujemy czas po NAZWIE GRACZA
if 'Player "' in line and "is connected" in line:
    match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
    if match:
        name = match.group(1)
        steamid = match.group(2)

        player_login_times[name] = datetime.utcnow()

        message = f"🟢 **Połączono** → {name} (SteamID: {steamid})"
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(message)
    return

# WYLOGOWANIE – obliczamy czas po NAZWIE GRACZA
if "has been disconnected" in line and 'Player "' in line:
    match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
    if match:
        name = match.group(1)
        guid = match.group(2)

        time_online_str = "czas nieznany"
        if name in player_login_times:
            delta = datetime.utcnow() - player_login_times[name]
            minutes = int(delta.total_seconds() // 60)
            seconds = int(delta.total_seconds() % 60)
            time_online_str = f"{minutes} min {seconds} s"
            del player_login_times[name]  # czyścimy po wyjściu

        message = f"🔴 **Rozłączono** → {name} ({guid}) → {time_online_str}"
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(message)
    return
