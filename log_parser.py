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

    print(f"[DEBUG PARSER] Przetwarzam linię: {line}")

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    # 1. JOIN (is connected / has connected)
    if any(keyword in line for keyword in ["is connected", "has connected"]) and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if not match:
            match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) (?:is|has) connected', line)
        if match:
            name = match.group(1).strip()
            id_val = match.group(2)
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID/SteamID", value=id_val, inline=True)
            embed.set_footer(text=f"Godzina: {log_time}")
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # 2. DISCONNECT (jeśli się pojawi – przetestuj wyjście)
    if "has been disconnected" in line:
        match = re.search(r'Player "([^"]+)"\(.*?(?:id|steamID)=([^)]+)\) has been disconnected', line)
        if match:
            name = match.group(1).strip()
            id_val = match.group(2)
            time_online = "nieznany"
            if name in player_login_times:
                delta = datetime.utcnow() - player_login_times[name]
                time_online = f"{delta.seconds // 60} min {delta.seconds % 60} s"
                del player_login_times[name]
            embed = create_connect_embed(name, "disconnect")
            embed.add_field(name="ID/SteamID", value=id_val, inline=True)
            embed.add_field(name="Czas online", value=time_online, inline=True)
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                await ch.send(embed=embed)
            return

    # 3. COT – biały ANSI
    if "[COT]" in line:
        match = re.search(r'\[COT\] (\d{17,}): (.+?)(?: \[guid=([^]]+)\])?$', line)
        if match:
            steamid = match.group(1)
            action = match.group(2).strip()
            guid = match.group(3) or "brak"
            msg = f"{log_time} ADMIN | [COT] {steamid} | {action} [guid={guid}]"
            ch = client.get_channel(CHANNEL_IDS["admin"])
            if ch:
                await ch.send(f"```ansi\n[37m{msg}[0m\n```")
            return

    # 4. HIT BY INFECTED / ZOMBIE
    if "hit by Infected" in line:
        match = re.search(r'Player "([^"]+)" .*hit by Infected into (\w+)\(\d+\) for ([\d.]+) damage \(([^)]+)\)', line)
        if match:
            name, part, dmg, type_attack = match.groups()
            msg = f"{log_time} ⚠️ {name} trafiony zombie w {part} za {dmg} dmg ({type_attack})"
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(f"```ansi\n[33m{msg}[0m\n```")
            return

    # 5. KILL / DEATH PLAYER
    if "killed by" in line and "DEAD" in line:
        # Kill player vs player
        match_pvp = re.search(r'Player "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_pvp:
            victim, killer, weapon, dist = match_pvp.groups()
            embed = create_kill_embed(victim, killer, weapon, dist)
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(embed=embed)
            return

        # Kill AI lub inne
        match_ai = re.search(r'AI "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_ai:
            ai, killer, weapon, dist = match_ai.groups()
            msg = f"{log_time} 💀 AI {ai} zabity przez {killer} ({weapon}, {dist}m)"
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return

    # 6. SAVE GRACZA (CHAR_DEBUG - SAVE) – opcjonalnie zielony komunikat
    if "CHAR_DEBUG - SAVE" in line:
        msg = f"{log_time} 💾 Autozapis gracza zakończony"
        ch = client.get_channel(CHANNEL_IDS["admin"])
        if ch:
            await ch.send(f"```ansi\n[32m{msg}[0m\n```")
        return

    # Jeśli nic nie złapało – wyślij do debug (jeśli włączony)
    debug_ch = client.get_channel(CHANNEL_IDS.get("debug"))
    if debug_ch:
        try:
            short = line[:1900] + "..." if len(line) > 1900 else line
            await debug_ch.send(f"```log\n{short}\n```")
        except:
            pass
