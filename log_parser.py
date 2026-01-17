import re
from datetime import datetime
from discord import Embed
from config import CHANNEL_IDS
from utils import create_connect_embed, create_kill_embed, create_death_embed

player_login_times = {}

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    if not line:
        return

    print(f"[PARSER] → {line}")

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    # CONNECT
    if "is connected" in line:
        m = re.search(r'Player "([^"]+)"\(id=([^)]+)\) is connected', line)
        if m:
            name, pid = m.groups()
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID", value=pid, inline=True)
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch: await ch.send(embed=embed)
            return

    # DISCONNECT
    if "has been disconnected" in line:
        m = re.search(r'Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
        if m:
            name, pid = m.groups()
            online = "nieznany"
            if name in player_login_times:
                delta = datetime.utcnow() - player_login_times[name]
                online = f"{int(delta.total_seconds() // 60)} min {delta.seconds % 60} s"
                del player_login_times[name]
            embed = create_connect_embed(name, "disconnect")
            embed.add_field(name="ID", value=pid, inline=True)
            embed.add_field(name="Online", value=online, inline=True)
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch: await ch.send(embed=embed)
            return

    # KILL PLAYER → PLAYER
    if "(DEAD)" in line and "hit by Player" in line:
        m = re.search(r'Player "([^"]+)" \(DEAD\) .* hit by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if m:
            victim, killer, weapon, dist = m.groups()
            embed = create_kill_embed(victim, killer, weapon, dist)
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch: await ch.send(embed=embed)
            return

    # DEATH by ZOMBIE
    if "[HP: 0]" in line and "hit by Infected" in line:
        m = re.search(r'Player "([^"]+)" .* hit by Infected .* for ([\d.]+) damage \(([^)]+)\)', line)
        if m:
            victim, dmg, cause = m.groups()
            embed = create_death_embed(victim, f"Zombie ({cause})")
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch: await ch.send(embed=embed)
            return

    # COT
    if "[COT]" in line:
        m = re.search(r'\[COT\] (\d{17,}): (.+?)(?: \[guid=.*?\])?$', line)
        if m:
            steamid, action = m.groups()
            msg = f"{log_time} [COT] {steamid} → {action.strip()}"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # Debug – surowe linie do kanału testowego
    debug_ch = client.get_channel(CHANNEL_IDS.get("debug"))
    if debug_ch:
        try:
            short = line[:1900] + "…" if len(line) > 1900 else line
            await debug_ch.send(f"```log\n{short}\n```")
        except:
            pass
