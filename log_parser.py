import re
from discord import Embed
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed
from config import CHANNEL_IDS

# Poprawione regexy - lepiej dopasowane do Twoich logów .RPT
CONNECT_PATTERN = re.compile(r'Player (?:"(.+?)"(?:\(steamID=\d+\))?|(.+?)\s*\(id=.+?\)) (?:is connected|has connected)')
DISCONNECT_PATTERN = re.compile(r'Player (.+?)\s*\(\d+\) kicked from server: \d+ \((.+)\)|Player (.+?) disconnected')
KILL_PATTERN = re.compile(r'(.+?)\(id=.+?\) killed by (.+?)\(id=.+?\) with (.+?) from (\d+) meters?')
DEATH_PATTERN = re.compile(r'(.+?) (died|was killed by .+)')
CHAT_PATTERN = re.compile(r'(.+?) \((Side|Global|Direct|Vehicle|Command) channel\): (.+)')
ADMIN_PATTERN = re.compile(r'(admin|kick|ban|warning|shutdown)', re.IGNORECASE)

async def process_line(bot, line: str):
    client = bot
    print(f"[PARSER] Przetwarzam linię: {line[:50]}...")  # Debug do Rendera

    # Połączenia
    if match := CONNECT_PATTERN.search(line):
        player = match.group(1) or match.group(2)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            print(f"[PARSER] Wykryto połączenie: {player}")
            await channel.send(embed=create_connect_embed(player.strip(), "connect"))
        return

    # Rozłączenia / kicki
    if match := DISCONNECT_PATTERN.search(line):
        player = match.group(1) or match.group(3) or "Nieznany"
        reason = match.group(2) or "rozłączenie"
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            print(f"[PARSER] Wykryto rozłączenie: {player} ({reason})")
            await channel.send(embed=create_connect_embed(f"{player} ({reason})", "disconnect"))
        return

    # Zabójstwa PvP
    if match := KILL_PATTERN.search(line):
        victim, killer, weapon, distance = match.groups()
        channel = client.get_channel(CHANNEL_IDS["kills"])
        if channel:
            print(f"[PARSER] Wykryto zabójstwo: {victim} przez {killer}")
            await channel.send(embed=create_kill_embed(victim, killer, weapon, distance))
        return

    # Śmierci (nie PvP)
    if match := DEATH_PATTERN.search(line):
        victim, cause = match.groups()
        channel = client.get_channel(CHANNEL_IDS["deaths"])
        if channel:
            print(f"[PARSER] Wykryto śmierć: {victim} ({cause})")
            await channel.send(embed=create_death_embed(victim, cause))
        return

    # Chat w grze
    if match := CHAT_PATTERN.search(line):
        player, channel_type, message = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            print(f"[PARSER] Wykryto chat: {player} - {message}")
            await channel.send(embed=create_chat_embed(player, channel_type, message))
        return

    # Akcje admina / ważne
    if ADMIN_PATTERN.search(line):
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            print(f"[PARSER] Wykryto admin action: {line.strip()}")
            await channel.send(f"🛡️ **ADMIN / WAŻNE** → {line.strip()}")
        return

    # Debug – wszystko inne
    if CHANNEL_IDS["debug"]:
        channel = client.get_channel(CHANNEL_IDS["debug"])
        if channel:
            print(f"[PARSER] Debug: {line.strip()}")
            await channel.send(f"```log\n{line.strip()}\n```")
