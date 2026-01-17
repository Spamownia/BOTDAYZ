# log_parser.py – Dostosowany do formatu logów z przykładu (.ADM / .RPT)

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

    current_time = datetime.utcnow()
    print(f"[DEBUG PARSER] Przetwarzam linię: {line}")

    # Wyciągamy timestamp (HH:MM:SS | ...)
    time_match = re.search(r'^(\d{2}:\d{2}:\d{2})', line)
    log_time = time_match.group(1) if time_match else current_time.strftime("%H:%M:%S")

    # 1. POŁĄCZENIE (connect) – zielony, z ID
    if "is connected" in line and 'Player "' in line:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) \| Player "([^"]+)"\(id=([^)]+)\) is connected', line)
        if match:
            _, name, player_id = match.groups()
            player_login_times[name] = current_time
            embed = create_connect_embed(name, "connect")
            embed.add_field(name="ID", value=player_id, inline=True)
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(embed=embed)
            return

    # 2. ROZŁĄCZENIE (disconnect) – czerwony, z czasem online
    if "has been disconnected" in line and 'Player "' in line:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) \| Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
        if match:
            _, name, player_id = match.groups()
            time_online_str = "czas nieznany"
            if name in player_login_times:
                delta = current_time - player_login_times[name]
                minutes = int(delta.total_seconds() // 60)
                seconds = int(delta.total_seconds() % 60)
                time_online_str = f"{minutes} min {seconds} s"
                del player_login_times[name]
            embed = create_connect_embed(name, "disconnect")
            embed.add_field(name="ID", value=player_id, inline=True)
            embed.add_field(name="Czas online", value=time_online_str, inline=True)
            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(embed=embed)
            return

    # 3. ZABÓJSTWO GRACZA PRZEZ GRACZA (kill player vs player)
    if "(DEAD)" in line and 'hit by Player' in line:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) \| Player "([^"]+)" \(DEAD\) \(id=([^)]+) pos=<[^>]+>\)\[HP: 0\] hit by Player "([^"]+)" \(id=([^)]+) pos=<[^>]+>\) into (\w+)\((\d+)\) for ([\d.]+) damage \(([^)]+)\) with ([\w ]+) from ([\d.]+) meters', line)
        if match:
            _, victim, victim_id, killer, killer_id, part, part_id, dmg, ammo, weapon, dist = match.groups()
            embed = create_kill_embed(victim, killer, weapon, dist)
            embed.add_field(name="Część ciała", value=part, inline=True)
            embed.add_field(name="Obrażenia", value=dmg, inline=True)
            channel = client.get_channel(CHANNEL_IDS["kills"])
            if channel:
                await channel.send(embed=embed)
            return

    # 4. ŚMIERĆ GRACZA PRZEZ INFECTED / INNE (death)
    if "[HP: 0]" in line and 'hit by Infected' in line:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) \| Player "([^"]+)" \(id=([^)]+) pos=<[^>]+>\)\[HP: 0\] hit by Infected into (\w+)\((\d+)\) for ([\d.]+) damage \(([^)]+)\)', line)
        if match:
            _, victim, victim_id, part, part_id, dmg, melee_type = match.groups()
            cause = f"Atak zombie ({melee_type}) w {part}"
            embed = create_death_embed(victim, cause)
            channel = client.get_channel(CHANNEL_IDS["deaths"])
            if channel:
                await channel.send(embed=embed)
            return

    # 5. ATAK NA GRACZA (hit, nie śmierć)
    if "[HP:" in line and 'hit by Infected' in line and "[HP: 0]" not in line:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) \| Player "([^"]+)" \(id=([^)]+) pos=<[^>]+>\)\[HP: ([\d.]+)\] hit by Infected into (\w+)\((\d+)\) for ([\d.]+) damage \(([^)]+)\)', line)
        if match:
            _, victim, victim_id, hp_left, part, part_id, dmg, melee_type = match.groups()
            message = f"{log_time} ⚠️ Atak: {victim} trafiony przez zombie w {part} za {dmg} dmg (HP: {hp_left})"
            channel = client.get_channel(CHANNEL_IDS["deaths"])  # lub inny kanał
            if channel:
                await channel.send(f"```ansi\n[33m{message}[0m\n```")
            return

    # 6. ZABÓJSTWO AI PRZEZ GRACZA (opcjonalne, jeśli chcesz raportować)
    if "AI " in line and "(DEAD)" in line and 'hit by Player' in line:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) \| AI "([^"]+)" \(DEAD\) \(group=\d+ faction="[^"]+" pos=<[^>]+>\)\[HP: 0\] hit by Player "([^"]+)" \(id=([^)]+) pos=<[^>]+>\) into (\w+)\((\d+)\) for ([\d.]+) damage \(([^)]+)\) with (\w+) from ([\d.]+) meters', line)
        if match:
            _, ai_name, killer, killer_id, part, part_id, dmg, ammo, weapon, dist = match.groups()
            message = f"{log_time} 🤖 Zabito AI: {ai_name} przez {killer} z {weapon} z {dist} m"
            channel = client.get_channel(CHANNEL_IDS["kills"])
            if channel:
                await channel.send(f"```ansi\n[31m{message}[0m\n```")
            return

    # 7. COT / ADMIN KOMENDY – dostosowane do formatu z |
    if "[COT]" in line:
        steamid_match = re.search(r'\[COT\] (\d{17,}):', line)
        steamid = steamid_match.group(1) if steamid_match else "nieznany"

        action_text = line.split(":", 1)[1].strip() if ":" in line else line.strip()
        action_text = re.sub(r'\d{2}:\d{2}:\d{2} \| ', '', action_text).strip()
        action_text = re.sub(r'\[guid=.*?]', '', action_text).strip()

        message_line = f"{log_time} ADMIN | [COT] {steamid} | {action_text}"
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"```ansi\n[37m{message_line}[0m\n```")
        return

    # 8. CHAT – jeśli pojawi się w logach (dostosuj jeśli masz przykłady chatu)
    if "Chat:" in line or "[Chat" in line:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) \| \[Chat - ([^\]]+)\] \("([^"]+)"\(id=[^)]+\)\): (.+)', line)  # dostosuj jeśli inny format
        if match:
            _, chat_type, player, message_text = match.groups()
            embed = create_chat_embed(player, chat_type, message_text)
            discord_channel_id = CHAT_CHANNEL_MAPPING.get(chat_type, CHAT_CHANNEL_MAPPING["Unknown"])
            channel = client.get_channel(discord_channel_id)
            if channel:
                await channel.send(embed=embed)
            return

    # DEBUG: wysyłaj nierozpoznane linie do kanału debug (jeśli włączony)
    if CHANNEL_IDS.get("debug"):
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line[:1897] + "..." if len(line) > 1900 else line
            await debug_channel.send(f"```log\n{content}\n```")
