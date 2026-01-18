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

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    # 1. JOIN (logowanie) – zielony embed
    if any(x in line for x in ["is connected", "has connected", "joined the server"]) and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if not match:
            match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) (?:is|has) connected', line)
        if match:
            name = match.group(1).strip()
            id_val = match.group(2)
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID/SteamID", value=id_val, inline=True)
            embed.set_footer(text=f"{datetime.utcnow().date()} | {log_time}")
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # 2. DISCONNECT (wylogowanie) – pomarańczowy embed
    if any(x in line.lower() for x in ["disconnected", "has quit", "left the server", "logged out"]):
        match = re.search(r'Player "([^"]+)"\(.*?(?:steamID|id)=([^)]+)\)', line)
        if match:
            name = match.group(1).strip()
            id_val = match.group(2)
            time_online = "nieznany"
            if name in player_login_times:
                delta = datetime.utcnow() - player_login_times[name]
                time_online = f"{int(delta.total_seconds() // 60)} min {int(delta.seconds % 60)} s"
                del player_login_times[name]
            embed = create_connect_embed(name, "disconnect")
            embed.add_field(name="ID/SteamID", value=id_val, inline=True)
            embed.add_field(name="Czas online", value=time_online, inline=True)
            embed.set_footer(text=f"{datetime.utcnow().date()} | {log_time}")
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # 3. COT (akcje admina) – biały ANSI
    if "[COT]" in line:
        match = re.search(r'\[COT\] (\d{17,}): (.+?)(?: \[guid=([^]]+)\])?$', line)
        if match:
            steamid = match.group(1)
            action = match.group(2).strip()
            guid = match.group(3) or "brak"
            msg = f"{datetime.utcnow().date()} | {log_time} 🛡️ [COT] {steamid} | {action} [guid={guid}]"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # 4. ZABÓJSTWA / ŚMIERĆ
    if "killed by" in line or "[HP: 0]" in line or "hit by" in line:
        # Player vs Player
        match_pvp = re.search(r'Player "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_pvp:
            victim, killer, weapon, dist = match_pvp.groups()
            embed = create_kill_embed(victim, killer, weapon, dist)
            embed.set_footer(text=f"{datetime.utcnow().date()} | {log_time}")
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(embed=embed)
            return

        # Player vs Zombie
        match_zombie = re.search(r'Player "([^"]+)" .*hit by Infected .* for ([\d.]+) damage \(([^)]+)\)', line)
        if match_zombie and "[HP: 0]" in line:
            victim, dmg, cause = match_zombie.groups()
            embed = create_death_embed(victim, f"Zombie ({cause}) za {dmg} dmg")
            embed.set_footer(text=f"{datetime.utcnow().date()} | {log_time}")
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(embed=embed)
            return

    # 5. CHAT – różne kolory ANSI
    if "[Chat" in line or "Chat:" in line:
        match = re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line)
        if match:
            channel_type, player, message = match.groups()
            color_map = {
                "Global": "[32m",   # zielony
                "Admin": "[31m",    # czerwony
                "Team": "[34m",     # niebieski
                "Direct": "[37m",   # szary
                "Unknown": "[33m"   # żółty
            }
            ansi_color = color_map.get(channel_type.strip(), color_map["Unknown"])
            msg = f"{datetime.utcnow().date()} | {log_time} 💬 [{channel_type}] {player}: {message}"
            discord_ch_id = CHAT_CHANNEL_MAPPING.get(channel_type.strip(), CHAT_CHANNEL_MAPPING["Unknown"])
            ch = client.get_channel(discord_ch_id)
            if ch:
                await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
            return

    # 6. ZNISZCZONE POJAZDY – czerwony ANSI
    if "destroyed" in line.lower() and any(x in line.lower() for x in ["vehicle", "car", "truck", "uaz", "gyrocopter", "plane"]):
        msg = f"{datetime.utcnow().date()} | {log_time} 🚗 Pojazd zniszczony: {line[:150]}..."
        ch = client.get_channel(CHANNEL_IDS["kills"])
        if ch:
            await ch.send(f"```ansi\n[31m{msg}[0m\n```")
        return

    # ŻADNA INNA LINIA NIE JEST WYSYŁANA – reszta ignorowana
