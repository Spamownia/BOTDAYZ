# log_parser.py – WERSJA Z EMBEDAMI JAK NA SCREENIE (login/logout z .RPT)

import re
from discord import Embed
from datetime import datetime
from config import CHANNEL_IDS

# Regexy z .RPT – dokładne linie login/logout
LOGIN_PATTERN = re.compile(r'Login ID: (\w+) IP: ([\d.]+) \(VE\) Name: (\w+)')
LOGOUT_PATTERN = re.compile(r'Logout ID: (\w+) Minutes: ([\d.]+) Name: (\w+) Location: ([-.\d]+), ([-.\d]+), ([-.\d]+)')

# Stare regexy z .ADM (opcjonalnie – możesz je zostawić lub usunąć)
CONNECT_PATTERN = re.compile(r'Player "([^"]+)"\(id=.*?\) is connected')
DISCONNECT_PATTERN = re.compile(r'Player "([^"]+)"\(id=.*?\) has been (disconnected|kicked)')
CHAT_PATTERN = re.compile(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=.*?\)\): (.+)')

async def process_line(bot, line: str):
    client = bot

    # === LOGIN Z .RPT – zielony, jak na screenie ===
    if match := LOGIN_PATTERN.search(line):
        player_id = match.group(1)
        ip = match.group(2)
        name = match.group(3)

        embed = Embed(
            title="Login ID: " + player_id + " IP: " + ip + " (VE) Name: " + name,
            color=0x00FF00,  # zielony
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="DayZ Server Log")

        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(embed=embed)
        return

    # === LOGOUT Z .RPT – czerwony, z czasem i lokalizacją ===
    if match := LOGOUT_PATTERN.search(line):
        player_id = match.group(1)
        minutes = match.group(2)
        name = match.group(3)
        x = match.group(4)
        y = match.group(5)
        z = match.group(6)

        embed = Embed(
            title=f"Logout ID: {player_id} Minutes: {minutes} Name: {name} Location:",
            description=f"{x} {y} {z}",
            color=0xFF0000,  # czerwony
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="DayZ Server Log")

        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(embed=embed)
        return

    # === CHAT Z .ADM ===
    if match := CHAT_PATTERN.search(line):
        channel_type, player, message = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            embed = Embed(
                title="💬 Chat w grze",
                color=0x00FFFF,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Gracz", value=player, inline=True)
            embed.add_field(name="Kanał", value=channel_type, inline=True)
            embed.add_field(name="Wiadomość", value=message, inline=False)
            embed.set_footer(text="DayZ Server Log")
            await channel.send(embed=embed)
        return

    # === COT – akcje admina ===
    if "[COT]" in line:
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **COT Akcja**\n`{line.strip()}`")
        return

    # === STARE CONNECT/DISCONNECT Z .ADM – opcjonalnie zostaw, jeśli chcesz dodatkowe info ===
    if match := CONNECT_PATTERN.search(line):
        player = match.group(1)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            embed = Embed(title="🔗 Dołączył do serwera", description=player, color=0x00FF00, timestamp=datetime.utcnow())
            embed.set_footer(text="DayZ Server Log")
            await channel.send(embed=embed)
        return

    if match := DISCONNECT_PATTERN.search(line):
        player = match.group(1)
        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            embed = Embed(title="❌ Wyszedł z serwera", description=player, color=0xFF8800, timestamp=datetime.utcnow())
            embed.set_footer(text="DayZ Server Log")
            await channel.send(embed=embed)
        return

    # === DEBUG – wszystkie linie (wyłącz po testach) ===
    if CHANNEL_IDS["debug"]:
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel and line.strip():
            content = line.strip()
            if len(content) > 1900:
                content = content[:1897] + "..."
            await debug_channel.send(f"```log\n{content}\n```")
