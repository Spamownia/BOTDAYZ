# log_parser.py – WERSJA Z KOLEJKOWANIEM, LOGOWANIEM I WYLOGOWANIEM

import re
from discord import Embed
from datetime import datetime
from config import CHANNEL_IDS

async def process_line(bot, line: str):
    client = bot
    line = line.strip()

    # === 1. KOLEJKOWANIE – dodanie do kolejki logowania ===
    if "[Login]: Adding player" in line:
        match = re.search(r'Adding player (\w+) \((\d+)\)', line)
        if match:
            name = match.group(1)
            dpnid = match.group(2)
            message = f"🟢 **Login** → Gracz {name} (dpnid: {dpnid}) dodany do kolejki logowania"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === 2. FINALNE POŁĄCZENIE – gracz w pełni zalogowany ===
    if 'Player "' in line and "is connected" in line:
        match = re.search(r'Player "([^"]+)"\(steamID=(\d+)\) is connected', line)
        if match:
            name = match.group(1)
            steamid = match.group(2)
            message = f"🟢 **Połączono** → {name} (SteamID: {steamid})"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === 3. WYLOGOWANIE / ROZŁĄCZENIE – wszystkie linie z [Disconnect]: ===
    if "[Disconnect]:" in line:
        message = f"🔴 **Rozłączono** → {line.split(':', 1)[1].strip()}"

        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(message)
        return

    # === DODATKOWO – standardowa wiadomość "has been disconnected" (z .ADM) ===
    if "has been disconnected" in line:
        match = re.search(r'Player "([^"]+)"\(id=([^)]+)\) has been disconnected', line)
        if match:
            name = match.group(1)
            player_id = match.group(2)
            message = f"🔴 **Wyszedł z serwera** → {name} (id: {player_id})"

            channel = client.get_channel(CHANNEL_IDS["connections"])
            if channel:
                await channel.send(message)
        return

    # === CHAT Z .ADM ===
    if match := re.search(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=[^)]+\)\): (.+)', line):
        channel_type, player, msg = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            embed = Embed(
                title=f"💬 Chat [{channel_type}]",
                color=0x00FFFF,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Gracz", value=player, inline=True)
            embed.add_field(name="Wiadomość", value=msg, inline=False)
            embed.set_footer(text="DayZ Server Log")
            await channel.send(embed=embed)
        return

    # === COT – akcje admina ===
    if "[COT]" in line:
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **COT Akcja**\n`{line}`")
        return

    # === DEBUG – opcjonalny (wyłącz po testach) ===
    if CHANNEL_IDS["debug"]:
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line
            if len(content) > 1900:
                content = content[:1897] + "..."
            await debug_channel.send(f"```log\n{content}\n```")
