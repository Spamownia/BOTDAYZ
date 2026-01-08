import re
from discord import Embed
from utils import create_connect_embed, create_kill_embed, create_death_embed, create_chat_embed
from config import CHANNEL_IDS

# Lepsze regexy
CONNECT_PATTERN = re.compile(r'Player "([^"]+)"\(id=.*?\) is connected')
DISCONNECT_PATTERN = re.compile(r'Player "([^"]+)"\(id=.*?\) has been (disconnected|kicked)')
CHAT_PATTERN = re.compile(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=.*?\)\): (.+)')

async def process_line(bot, line: str):
    client = bot

    # Połączenia
    if match := CONNECT_PATTERN.search(line):
        player = match.group(1)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(embed=create_connect_embed(player, "connect"))
        return

    # Rozłączenia / kicki zwykłe
    if match := DISCONNECT_PATTERN.search(line):
        player = match.group(1)
        reason = "kick" if "kicked" in line.lower() else "disconnect"
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(embed=create_connect_embed(player, reason))
        return

    # Chat w grze
    if match := CHAT_PATTERN.search(line):
        channel_type, player, message = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            await channel.send(embed=create_chat_embed(player, channel_type, message))
        return

    # COT – wszystkie akcje (GodMode, Kick, Ban, Activated itp.)
    if "[COT]" in line:
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **COT Akcja**\n`{line.strip()}`")
        return

    # Debug – wszystkie linie (wyłącz później ustawiając debug: None w config)
    if CHANNEL_IDS["debug"]:
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel and line.strip():
            content = line.strip()
            if len(content) > 1900:
                content = content[:1897] + "..."
            await debug_channel.send(f"```log\n{content}\n```")
