# log_parser.py – WERSJA Z POPRAWIONYMI REGEXAMI + DEBUGIEM LOGIN/LOGOUT

import re
from datetime import datetime
from config import CHANNEL_IDS

# Elastyczne regexy dla loginu i logoutu z .RPT
# Przykład login: Login ID: 76561199031037111 IP: 190.8.165.124 (VE) Name: JuanDavid
LOGIN_PATTERN = re.compile(r'Login ID:\s*(\w+)\s+IP:\s*([\d.]+)\s*\(VE\)\s*Name:\s*(\w+)')

# Przykład logout: Logout ID: 76561199031037111 Minutes: 1.07 Name: JuanDavid Location: -451190.188 -893436.062 390.130
LOGOUT_PATTERN = re.compile(r'Logout ID:\s*(\w+)\s+Minutes:\s*([\d.]+)\s+Name:\s*(\w+)\s+Location:\s*([-.\d]+)\s+([-.\d]+)\s+([-.\d]+)')

# Chat z .ADM
CHAT_PATTERN = re.compile(r'\[Chat - ([^\]]+)\]\("([^"]+)"\(id=.*?\)\): (.+)')

async def process_line(bot, line: str):
    client = bot
    line = line.strip()

    # === TYMCZASOWY DEBUG – wszystkie linie z Login/Logout (wyłącz później) ===
    if "Login ID:" in line or "Logout ID:" in line:
        debug_channel = client.get_channel(CHANNEL_IDS["debug"]) if CHANNEL_IDS["debug"] else None
        if debug_channel:
            await debug_channel.send(f"```log\nRAW LINE: {line}\n```")

    # === LOGIN – tekstowa wiadomość ===
    if match := LOGIN_PATTERN.search(line):
        player_id = match.group(1)
        ip = match.group(2)
        name = match.group(3)

        message = f"🟢 Login ID: {player_id} IP: {ip} (VE) Name: {name}"

        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(message)
        return

    # === LOGOUT – tekstowa wiadomość ===
    if match := LOGOUT_PATTERN.search(line):
        player_id = match.group(1)
        minutes = match.group(2)
        name = match.group(3)
        x, y, z = match.group(4), match.group(5), match.group(6)

        message = (
            f"🔴 Logout ID: {player_id} Minutes: {minutes} Name: {name} Location:\n"
            f"{x} {y} {z}"
        )

        channel = client.get_channel(CHANNEL_IDS["connections"])
        if channel:
            await channel.send(message)
        return

    # === CHAT ===
    if match := CHAT_PATTERN.search(line):
        channel_type, player, message_text = match.groups()
        channel = client.get_channel(CHANNEL_IDS["chat"])
        if channel:
            embed = discord.Embed(
                title="💬 Chat w grze",
                color=0x00FFFF,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Gracz", value=player, inline=True)
            embed.add_field(name="Kanał", value=channel_type, inline=True)
            embed.add_field(name="Wiadomość", value=message_text, inline=False)
            embed.set_footer(text="DayZ Server Log")
            await channel.send(embed=embed)
        return

    # === COT ===
    if "[COT]" in line:
        channel = client.get_channel(CHANNEL_IDS["admin"])
        if channel:
            await channel.send(f"🛡️ **COT Akcja**\n`{line}`")
        return

    # === OGÓLNY DEBUG (wszystko) – wyłącz po testach ===
    if CHANNEL_IDS["debug"]:
        debug_channel = client.get_channel(CHANNEL_IDS["debug"])
        if debug_channel:
            content = line
            if len(content) > 1900:
                content = content[:1897] + "..."
            await debug_channel.send(f"```log\n{content}\n```")
