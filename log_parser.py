import re
from discord import Embed
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed
from config import CHANNEL_IDS

# Regexy dla .RPT i .ADM
CONNECT_PATTERN = re.compile(r'Player "(.+?)"\(id=.+?\) (?:is connected|has connected)')
DISCONNECT_PATTERN = re.compile(r'Player "(.+?)"\(id=.+?\) (?:has been disconnected|kicked from server)')
KILL_PATTERN = re.compile(r'(.+?)\(id=.+?\) killed by (.+?)\(id=.+?\) with (.+?) from (\d+) meters?')
DEATH_PATTERN = re.compile(r'Player "(.+?)" \(DEAD\) .* died\.|Player "(.+?)" died')
CHAT_PATTERN = re.compile(r'\[Chat - (Global|Side|Direct|Vehicle|Admin)\]\("(.+?)"\(id=.+?\)\): (.+)')
ADMIN_PATTERN = re.compile(r'\b(kick|ban|shutdown|restart|admin kicked|admin banned)\b', re.IGNORECASE)

async def process_line(bot, line: str):
    client = bot

    # Połączenia
    if match := CONNECT_PATTERN.search(line):
        player = match.group(1)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(embed=create_connect_embed(player, "connect"))
        return

    # Rozłączenia / kicki
    if match := DISCONNECT_PATTERN.search(line):
        player = match.group(1)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(embed=create_connect_embed(f"{player} (rozłączono/kick)", "disconnect"))
        return

    # Zabójstwa PvP
    if match := KILL_PATTERN.search(line):
        victim, killer, weapon, distance = match.groups()
        channel = client.get_channel(CHANNEL_IDS["kills"])
        if channel:
            await channel.send(embed=create_kill_embed(victim, killer, weapon, distance))
        return

    # Śmierci
    if match := DEATH_PATTERN.search(line):
        player = match.group(1) or match.group(2)
        channel = client.get_channel(CHANNEL_IDS["deaths"])
        if channel:
            await channel.send(embed=create_death_embed(player, "śmierć (przyczyna nieznana)"))
        return

    # Chat z .ADM
    if match := CHAT_PATTERN.search(line):
        channel_type, player, message = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            await channel.send(embed=create_chat_embed(player, channel_type, message))
        return

    # Prawdziwe akcje admina
    if ADMIN_PATTERN.search(line):
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **ADMIN AKCJA** → {line.strip()}")
        return

    # Wszystko inne – ignorowane (zero spamu)
