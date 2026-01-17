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

    # CONNECT – zielony embed
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) is connected', line)
        if match:
            name, pid = match.groups()
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID", value=pid[:8] + "...", inline=True)
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # DISCONNECT – pomarańczowy embed + czas online
    if "has been disconnected" in line and 'Player "' in line:
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

    # KILL PLAYER vs PLAYER – czerwony embed
    if "(DEAD)" in line and "killed by Player" in line:
        match = re.search(r'Player "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match:
            victim, killer, weapon, dist = match.groups()
            embed = create_kill_embed(victim, killer, weapon, dist)
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(embed=embed)
            return

    # DEATH by ZOMBIE / INNE – szary embed
    if "[HP: 0]" in line and "hit by" in line:
        match = re.search(r'Player "([^"]+)" .* hit by (Infected|Player) .* for ([\d.]+) damage \(([^)]+)\)', line)
        if match:
            victim, cause_type, dmg, weapon = match.groups()
            cause = f"{cause_type} ({weapon}) za {dmg} dmg"
            embed = create_death_embed(victim, cause)
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(embed=embed)
            return

    # COT / ADMIN – biały ANSI
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

    # Wysyłaj KAŻDĄ linię do debug (tymczasowo – usuń później jeśli chcesz)
    debug_ch = client.get_channel(CHANNEL_IDS.get("debug"))
    if debug_ch:
        try:
            short_line = line[:1900] + "..." if len(line) > 1900 else line
            await debug_ch.send(f"```log\n{short_line}\n```")
            print("[DEBUG] Wysłałem surową linię do debug kanału")
        except Exception as e:
            print(f"[DEBUG ERR] Błąd wysyłki do debug: {e}")
