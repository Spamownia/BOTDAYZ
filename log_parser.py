# log_parser.py – Dostosowany pod format .ADM z przykładu (connect, hit, kill, COT, death)

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

    print(f"[DEBUG PARSER] Przetwarzam linię: {line}")

    # Wyciągamy godzinę (HH:MM:SS | ...)
    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")

    # 1. CONNECT – zielony embed
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(id=([^=]+)=\) is connected', line)
        if match:
            name = match.group(1)
            player_id = match.group(2)
            player_login_times[name] = datetime.utcnow()
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID", value=player_id[:8] + "...", inline=True)
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(embed=embed)
            return

    # 2. DISCONNECT – czerwony embed + czas online (zakładany format – przetestuj)
    if "has been disconnected" in line and 'Player "' in line:
        match = re.search(r'Player "([^"]+)"\(id=([^=]+)=\) has been disconnected', line)
        if match:
            name = match.group(1)
            player_id = match.group(2)
            time_online_str = "czas nieznany"
            if name in player_login_times:
                delta = datetime.utcnow() - player_login_times[name]
                minutes = int(delta.total_seconds() // 60)
                seconds = int(delta.total_seconds() % 60)
                time_online_str = f"{minutes} min {seconds} s"
                del player_login_times[name]
            embed = create_connect_embed(name, "disconnect")
            embed.add_field(name="ID", value=player_id[:8] + "...", inline=True)
            embed.add_field(name="Czas online", value=time_online_str, inline=True)
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(embed=embed)
            return

    # 3. HIT BY INFECTED – ostrzeżenie (żółty ANSI, jeśli HP > 0)
    if "[HP:" in line and "hit by Infected" in line and not "DEAD" in line:
        match = re.search(r'Player "([^"]+)" \(id=([^=]+)= pos=<[^>]+>\)\[HP: ([\d.]+)\] hit by Infected into (\w+)\((\d+)\) for ([\d.]+) damage \(([^)]+)\)', line)
        if match:
            name = match.group(1)
            player_id = match.group(2)
            hp = match.group(3)
            part = match.group(4)
            dmg = match.group(6)
            melee_type = match.group(7)
            message_line = f"{log_time} ⚠️ Atak zombie: {name} trafiony w {part} za {dmg} dmg (HP: {hp})"
            channel = client.get_channel(CHANNEL_IDS["deaths"])
            if channel:
                await channel.send(f"```ansi\n[33m{message_line}[0m\n```")
            return

    # 4. DEATH / KILL PLAYER – szary / czerwony embed
    if "killed by" in line and "DEAD" in line:
        # Player killed by Player
        match_player = re.search(r'Player "([^"]+)" \(DEAD\) \(id=([^=]+)= pos=<[^>]+>\) killed by Player "([^"]+)" \(id=([^=]+)= pos=<[^>]+>\) with ([\w ]+) from ([\d.]+) meters', line)
        if match_player:
            victim = match_player.group(1)
            killer = match_player.group(3)
            weapon = match_player.group(5)
            dist = match_player.group(6)
            embed = create_kill_embed(victim, killer, weapon, dist)
            channel = client.get_channel(CHANNEL_IDS["kills"])
            if channel:
                await channel.send(embed=embed)
            return

        # Player killed by Infected (jeśli jest)
        match_infected = re.search(r'Player "([^"]+)" \(DEAD\) \(id=([^=]+)= pos=<[^>]+>\) killed by Infected with ([\w ]+) from ([\d.]+) meters', line)
        if match_infected:
            victim = match_infected.group(1)
            weapon = match_infected.group(3)
            dist = match_infected.group(4)
            embed = create_death_embed(victim, f"Zombie z {weapon} z {dist} m")
            channel = client.get_channel(CHANNEL_IDS["deaths"])
            if channel:
                await channel.send(embed=embed)
            return

    # 5. AI KILLED – czerwony ANSI (opcjonalnie, jeśli chcesz raportować)
    if "AI " in line and "DEAD" in line and "killed by Player" in line:
        match = re.search(r'AI "([^"]+)" \(DEAD\) .* killed by Player "([^"]+)" .* with ([\w ]+) from ([\d.]+) meters', line)
        if match:
            ai_name = match.group(1)
            killer = match.group(2)
            weapon = match.group(3)
            dist = match.group(4)
            message_line = f"{log_time} 🤖 Zabito AI: {ai_name} przez {killer} z {weapon} z {dist} m"
            channel = client.get_channel(CHANNEL_IDS["kills"])
            if channel:
                await channel.send(f"```ansi\n[31m{message_line}[0m\n```")
            return

    # 6. COT – biały ANSI
    if "[COT]" in line:
        match = re.search(r'\[COT\] (\d{17,}): ([\w ]+) \[(guid=([^=]+)=)\]', line)
        if match:
            steamid = match.group(1)
            action = match.group(2).strip()
            guid = match.group(4)
            message_line = f"{log_time} ADMIN | [COT] {steamid} | {action} [guid={guid}]"
            channel = client.get_channel(CHANNEL_IDS["admin"])
            if channel:
                await channel.send(f"```ansi\n[37m{message_line}[0m\n```")
            return

        # Alternatywa dla COT bez [guid=]
        match_no_guid = re.search(r'\[COT\] (\d{17,}): ([\w ]+)', line)
        if match_no_guid:
            steamid = match_no_guid.group(1)
            action = match_no_guid.group(2).strip()
            message_line = f"{log_time} ADMIN | [COT] {steamid} | {action}"
            channel = client.get_channel(CHANNEL_IDS["admin"])
            if channel:
                await channel.send(f"```ansi\n[37m{message_line}[0m\n```")
            return

    # Debug – wysyłaj nierozpoznane linie do kanału debug
    if CHANNEL_IDS.get("debug"):
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line[:1897] + "..." if len(line) > 1900 else line
            await debug_channel.send(f"```log\n{content}\n```")
