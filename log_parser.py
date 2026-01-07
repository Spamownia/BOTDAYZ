import re
from discord import TextChannel
from utils import create_kill_embed, create_connect_embed
from config import CHANNEL_IDS

# ----------------- Wzorce regex -----------------
CONNECT_PATTERN = re.compile(r"Player (.+) connected")
DISCONNECT_PATTERN = re.compile(r"Player (.+) disconnected")
KILL_PATTERN = re.compile(r"(.+) killed by (.+) with (.+) from (\d+) meters")
# Możesz dodać więcej, np.:
# DEATH_PATTERN = re.compile(r"(.+) died")
# CHAT_PATTERN = re.compile(r"(.+) \(Side channel\): (.+)")

async def process_line(bot, line: str):
    client = bot  # dla get_channel

    # Połączenia
    connect_match = CONNECT_PATTERN.search(line)
    if connect_match:
        player = connect_match.group(1)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            embed = create_connect_embed(player, "connect")
            await channel.send(embed=embed)
        return

    # Rozłączenia
    disconnect_match = DISCONNECT_PATTERN.search(line)
    if disconnect_match:
        player = disconnect_match.group(1)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            embed = create_connect_embed(player, "disconnect")
            await channel.send(embed=embed)
        return

    # Zabójstwa
    kill_match = KILL_PATTERN.search(line)
    if kill_match:
        victim = kill_match.group(1)
        killer = kill_match.group(2)
        weapon = kill_match.group(3)
        distance = kill_match.group(4)
        desc = f"**Ofiara:** {victim}\n**Zabójca:** {killer}\n**Broń:** {weapon}\n**Dystans:** {distance}m"
        channel = client.get_channel(CHANNEL_IDS["kills"])
        if channel:
            embed = discord.Embed(title="💀 Zabójstwo", description=desc, color=0xFF0000)
            await channel.send(embed=embed)
        return

    # Tu możesz dodać więcej warunków...

    # Debug – wszystko co niepasuje
    if CHANNEL_IDS["debug"]:
        channel = client.get_channel(CHANNEL_IDS["debug"])
        if channel:
            await channel.send(f"```log\n{line}\n```")
