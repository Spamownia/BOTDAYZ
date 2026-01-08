import re
from discord import Embed
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed
from config import CHANNEL_IDS

# Regexy tylko na naprawdę ważne rzeczy
CONNECT_PATTERN = re.compile(r'Player (?:"(.+?)"(?:\(steamID=\d+\))?|(.+?)\s*\(id=.+?\)) (?:is connected|has connected)')
DISCONNECT_PATTERN = re.compile(r'Player (.+?)\s*\(\d+\) kicked from server|Player (.+?) disconnected|Player (.+?) has been disconnected')
KILL_PATTERN = re.compile(r'(.+?)\(id=.+?\) killed by (.+?)\(id=.+?\) with (.+?) from (\d+) meters?')
DEATH_PATTERN = re.compile(r'(.+?) (died|was killed by Zombie|was killed by fall|was killed by .+)')
CHAT_PATTERN = re.compile(r'(.+?) \((Side|Global|Direct|Vehicle|Command) channel\): (.+)')

# Tylko prawdziwe akcje admina – kick, ban, shutdown itp. (bez zwykłych warningów)
ADMIN_PATTERN = re.compile(r'\b(kick|ban|shutdown|restart|admin kicked|admin banned)\b', re.IGNORECASE)

async def process_line(bot, line: str):
    client = bot

    # 1. Połączenia
    if match := CONNECT_PATTERN.search(line):
        player = match.group(1) or match.group(2)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(embed=create_connect_embed(player.strip(), "connect"))
        return

    # 2. Rozłączenia / kicki
    if match := DISCONNECT_PATTERN.search(line):
        player = match.group(1) or match.group(2) or match.group(3) or "Nieznany"
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(embed=create_connect_embed(f"{player} (rozłączono/kick)", "disconnect"))
        return

    # 3. Zabójstwa PvP
    if match := KILL_PATTERN.search(line):
        victim, killer, weapon, distance = match.groups()
        channel = client.get_channel(CHANNEL_IDS["kills"])
        if channel:
            await channel.send(embed=create_kill_embed(victim, killer, weapon, distance))
        return

    # 4. Śmierci
    if match := DEATH_PATTERN.search(line):
        victim = match.group(1)
        cause = match.group(2)
        channel = client.get_channel(CHANNEL_IDS["deaths"])
        if channel:
            await channel.send(embed=create_death_embed(victim, cause))
        return

    # 5. Chat
    if match := CHAT_PATTERN.search(line):
        player, channel_type, message = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            await channel.send(embed=create_chat_embed(player, channel_type, message))
        return

    # 6. Tylko prawdziwe akcje admina (kick, ban, shutdown itp.)
    if ADMIN_PATTERN.search(line):
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **ADMIN AKCJA** → {line.strip()}")
        return

    # Wszystko inne – ignorowane (zero spamu!)
    # Jeśli chcesz debug – odkomentuj poniższe i ustaw debug: ID_kanału w config.py
    # if CHANNEL_IDS["debug"]:
    #     channel = client.get_channel(CHANNEL_IDS["debug"])
    #     if channel:
    #         await channel.send(f"```log\n{line.strip()}\n```")
