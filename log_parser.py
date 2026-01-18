import re
from datetime import datetime
import os
from discord import Embed
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
from utils import create_connect_embed, create_kill_embed, create_death_embed

player_login_times = {}

# Plik do zapisywania nierozpoznanych linii (debug bez spamowania Discorda)
UNPARSED_LOG = "unparsed_lines.log"

async def process_line(bot, line: str):
    client = bot
    line = line.strip()
    if not line:
        return

    print(f"[DEBUG PARSER] Przetwarzam linię: {line}")

    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    # 1. JOIN / CONNECT
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

    # 2. DISCONNECT
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

    # 3. COT (Community Online Tools)
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
        # PvP
        match_pvp = re.search(r'Player "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_pvp:
            victim, killer, weapon, dist = match_pvp.groups()
            embed = create_kill_embed(victim, killer, weapon, dist)
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(embed=embed)
            return

        # AI kill
        match_ai = re.search(r'AI "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_ai:
            ai, killer, weapon, dist = match_ai.groups()
            msg = f"{log_time} 💀 AI {ai} zabity przez {killer} ({weapon}, {dist}m)"
            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return

    # 6. AUTO SAVE
    if "CHAR_DEBUG - SAVE" in line:
        msg = f"{log_time} 💾 Autozapis gracza zakończony"
        ch = client.get_channel(CHANNEL_IDS["admin"])
        if ch:
            await ch.send(f"```ansi\n[32m{msg}[0m\n```")
        return

    # 7. CHAT MESSAGES
    if "Chat(" in line:
        # Przykładowe formaty, które najczęściej występują w DayZ
        patterns = [
            r'Chat\("([^"]+)"\)\(([^)]+)\): "([^"]+)"',                    # klasyczny
            r'Chat\("([^"]+)"\): "([^"]+)"',                               # bez kanału
            r'Player "([^"]+)" said in channel ([^:]+): "([^"]+)"'        # alternatywny
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                if len(match.groups()) == 3:
                    name, channel, message = match.groups()
                else:  # bez kanału
                    name, message = match.groups()
                    channel = "Unknown"

                color_codes = {
                    "Global":   "[32m",  # zielony
                    "Team":     "[36m",  # cyjan
                    "Direct":   "[35m",  # magenta
                    "Admin":    "[34m",  # niebieski
                    "Unknown":  "[33m"   # żółty
                }
                ansi_color = color_codes.get(channel.strip(), color_codes["Unknown"])
                
                msg = f"{log_time} [{channel.strip()}] {name}: {message}"
                
                discord_channel_id = CHAT_CHANNEL_MAPPING.get(channel.strip(), CHAT_CHANNEL_MAPPING["Unknown"])
                ch = client.get_channel(discord_channel_id)
                if ch:
                    await ch.send(f"```ansi\n{ansi_color}{msg}[0m\n```")
                return

    # ==============================================
    # Jeśli żadna reguła nie pasuje → zapisujemy do pliku (bez wysyłania na Discord!)
    # ==============================================
    try:
        timestamp = datetime.utcnow().isoformat()
        with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {line}\n")
        print(f"[UNPARSED → plik] {line[:120]}...")
    except Exception as e:
        print(f"[BŁĄD ZAPISU UNPARSED] {e}")
