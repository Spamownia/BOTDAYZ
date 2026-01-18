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

    # Wyciągamy godzinę
    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    # Format daty: dd.mm.yyyy
    today = datetime.utcnow()
    date_str = today.strftime("%d.%m.%Y")

    # 1. JOIN (logowanie)
    if any(kw in line for kw in ["is connected", "has connected"]) and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\((?:steamID|id)=(\d+)\)', line)
        if match:
            name = match.group(1).strip()
            id_val = match.group(2)
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID/SteamID", value=id_val, inline=True)
            embed.set_footer(text=f"{date_str} | {log_time}")
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # 2. DISCONNECT (wylogowanie) – rozszerzony warunek
    if any(kw in line.lower() for kw in ["disconnected", "has quit", "left the server", "logged out", "has been disconnected", "quit", "left"]):
        match = re.search(r'Player "([^"]+)"\((?:steamID|id)=(\d+)\)', line)
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
            embed.set_footer(text=f"{date_str} | {log_time}")
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # 3. COT
    if "[COT]" in line:
        match = re.search(r'\[COT\] (\d{17,}): (.+)', line)
        if match:
            steamid = match.group(1)
            action = match.group(2).strip()
            msg = f"{date_str} | {log_time} 🛡️ [COT] {steamid} | {action}"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # 4. CHAT
    if any(kw in line for kw in ["[Chat", "Chat:", "said in channel"]):
        match = re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line)
        if match:
            channel_type, player, message = match.groups()
            color_map = {
                "Global": "[32m",
                "Admin": "[31m",
                "Team": "[34m",
                "Direct": "[37m",
                "Unknown": "[33m"
            }
            ansi_color = color_map.get(channel_type.strip(), color_map["Unknown"])
            msg = f"{date_str} | {log_time} 💬 [{channel_type}] {player}: {message}"
            discord_ch_id = CHAT_CHANNEL_MAPPING.get(channel_type.strip(), CHANNEL_IDS["chat"])
            ch = client.get_channel(discord_ch_id)
            if ch:
                await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
            return

    # 5. ZABÓJSTWA
    if any(kw in line for kw in ["killed by", "hit by", "[HP: 0]", "DEAD"]):
        match_pvp = re.search(r'Player "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_pvp:
            victim, killer, weapon, dist = match_pvp.groups()
            embed = create_kill_embed(victim, killer, weapon, dist)
            embed.set_footer(text=f"{date_str} | {log_time}")
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(embed=embed)
            return

        match_zombie = re.search(r'Player "([^"]+)" .*hit by Infected .* for ([\d.]+) damage \(([^)]+)\)', line)
        if match_zombie and "[HP: 0]" in line:
            victim, dmg, cause = match_zombie.groups()
            embed = create_death_embed(victim, f"Zombie ({cause}) za {dmg} dmg")
            embed.set_footer(text=f"{date_str} | {log_time}")
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(embed=embed)
            return

    # ŻADNA INNA LINIA NIE JEST WYSYŁANA
