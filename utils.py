from discord import Embed
from datetime import datetime

def create_connect_embed(player: str, action: str) -> Embed:
    color = 0x00FF00 if action == "connect" else 0xFF8800
    title = "🔗 Dołączył do serwera" if action == "connect" else "❌ Wyszedł z serwera"
    embed = Embed(title=title, description=player, color=color, timestamp=datetime.utcnow())
    embed.set_footer(text="DayZ Server Log")
    return embed

def create_kill_embed(victim: str, killer: str, weapon: str, distance: str) -> Embed:
    embed = Embed(
        title="💀 Zabójstwo",
        color=0xFF0000,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Ofiara", value=victim, inline=True)
    embed.add_field(name="Zabójca", value=killer, inline=True)
    embed.add_field(name="Broń", value=weapon, inline=False)
    embed.add_field(name="Dystans", value=f"{distance} m", inline=True)
    embed.set_footer(text="DayZ Server Log")
    return embed

def create_death_embed(victim: str, cause: str) -> Embed:
    embed = Embed(title="☠️ Śmierć gracza", description=f"**Gracz:** {victim}\n**Przyczyna:** {cause}", color=0x808080, timestamp=datetime.utcnow())
    embed.set_footer(text="DayZ Server Log")
    return embed

def create_chat_embed(player: str, channel_type: str, message: str) -> Embed:
    embed = Embed(title="💬 Chat w grze", color=0x00FFFF, timestamp=datetime.utcnow())
    embed.add_field(name="Gracz", value=player, inline=True)
    embed.add_field(name="Kanał", value=channel_type, inline=True)
    embed.add_field(name="Wiadomość", value=message, inline=False)
    embed.set_footer(text="DayZ Server Log")
    return embed
