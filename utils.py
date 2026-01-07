import discord

def create_kill_embed(line: str) -> discord.Embed:
    """Tworzy ładny embed dla zabójstwa"""
    embed = discord.Embed(
        title="💀 Zabójstwo",
        description=line,
        color=0xFF0000,
        timestamp=discord.utils.utcnow()
    )
    return embed

def create_connect_embed(player: str, action: str) -> discord.Embed:
    color = 0x00FF00 if action == "connect" else 0xFF8800
    title = "🔗 Dołączył" if action == "connect" else "❌ Wyszedł"
    embed = discord.Embed(title=title, description=player, color=color)
    return embed
