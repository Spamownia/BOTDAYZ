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

    # 1. Dodany do kolejki logowania (nowy format)
    if "[Login]:" in line and "Adding player" in line:
        match = re.search(r'Adding player ([^ ]+) \((\d+)\) to login queue', line)
        if match:
            name = match.group(1)
            dpnid = match.group(2)
            msg = f"🟢 Login → Gracz {name} → Dodany do kolejki logowania"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```{msg}```")
            return

    # 2. Połączono (nowy format z SteamID)
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1).strip()
            steamid = match.group(2)
            player_login_times[name] = datetime.utcnow()
            msg = f"🟢 Połączono → {name} (SteamID: {steamid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```{msg}```")
            return

    # 3. Rozłączono (nowy format z czasem online)
    if any(kw in line.lower() for kw in ["disconnected", "has quit", "left the server", "logged out", "has been disconnected", "quit", "left"]):
        match = re.search(r'Player "([^"]+)"\((?:steamID|id)=([^)]+)\)', line)
        if match:
            name = match.group(1).strip()
            id_val = match.group(2)
            time_online = "nieznany"
            if name in player_login_times:
                delta = datetime.utcnow() - player_login_times[name]
                minutes = int(delta.total_seconds() // 60)
                seconds = int(delta.seconds % 60)
                time_online = f"{minutes} min {seconds} s"
                del player_login_times[name]
            msg = f"🔴 Rozłączono → {name} ({id_val}) → {time_online}"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(f"```{msg}```")
            return

    # 4. COT (bez zmian)
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

    # 5. CHAT (bez zmian)
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

    # 6. ZABÓJSTWA (bez zmian)
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
