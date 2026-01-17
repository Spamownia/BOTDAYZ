import re
from datetime import datetime
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed

player_login_times = {}

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    if not line:
        return

    print(f"[PARSER] → {line}")

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    # CONNECT – zielony embed (dostosowane pod steamID= i has connected)
    if "is connected" in line or "has connected" in line:
        # Najpierw wersja z steamID=
        match_steam = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match_steam:
            name, steamid = match_steam.groups()
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="SteamID", value=steamid, inline=True)
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

        # Alternatywna wersja z id= lub bez
        match_id = re.search(r'Player "([^"]+)"\(id=([^)]+)\) is connected', line)
        if match_id:
            name, pid = match_id.groups()
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID", value=pid[:8] + "...", inline=True)
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

        # Linia "has connected" bez szczegółów
        match_has = re.search(r'Player ([^ ]+) \(id=([^)]+)\) has connected', line)
        if match_has:
            name, pid = match_has.groups()
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID", value=pid[:8] + "...", inline=True)
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # DISCONNECT – pomarańczowy embed
    if "has been disconnected" in line:
        match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
        if match:
            name, pid = match.groups()
            online_str = "nieznany"
            if name in player_login_times:
                delta = datetime.utcnow() - player_login_times[name]
                online_str = f"{int(delta.total_seconds() // 60)} min {int(delta.seconds % 60)} s"
                del player_login_times[name]
            embed = create_connect_embed(name, "disconnect")
            embed.add_field(name="ID", value=pid[:8] + "...", inline=True)
            embed.add_field(name="Czas online", value=online_str, inline=True)
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # COT – ANSI
    if "[COT]" in line:
        match = re.search(r'\[COT\] (\d{17,}): (.+)', line)
        if match:
            steamid, action = match.groups()
            action = action.strip().replace('[guid=.*?]', '').strip()
            msg = f"{log_time} ADMIN | [COT] {steamid} | {action}"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # KILL / DEATH – czerwony / szary embed (dostosuj, gdy pojawią się linie z zabójstwami)
    if "[HP: 0]" in line or "killed by" in line:
        # Przykład – rozszerz gdy zobaczysz pełne linie kill
        match_kill = re.search(r'Player "([^"]+)" .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_kill:
            victim, killer, weapon, dist = match_kill.groups()
            embed = create_kill_embed(victim, killer, weapon, dist)
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(embed=embed)
            return

    # Wysyłaj KAŻDĄ linię do debug (do testu – możesz później ograniczyć)
    debug_ch = client.get_channel(CHANNEL_IDS.get("debug"))
    if debug_ch:
        try:
            short = line[:1900] + "..." if len(line) > 1900 else line
            await debug_ch.send(f"```log\n{short}\n```")
            print("[DEBUG] Wysłałem linię do debug")
        except Exception as e:
            print(f"[DEBUG ERR] {e}")
