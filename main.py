import discord
from discord.ext import commands, tasks
from config import DISCORD_TOKEN, CHECK_INTERVAL
from ftp_watcher import DayZLogWatcher
from log_parser import process_line

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

watcher = DayZLogWatcher()

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_logs():
    content = watcher.get_new_content()
    if not content:
        return

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for line in lines:
        await process_line(bot, line)

@bot.event
async def on_ready():
    print(f"Bot zalogowany jako {bot.user}")
    if not check_logs.is_running():
        check_logs.start()
        print("Rozpoczęto monitorowanie logów DayZ")

@bot.command()
@commands.has_permissions(administrator=True)
async def logstatus(ctx):
    await ctx.send("✅ Monitorowanie logów DayZ jest aktywne.")

bot.run(DISCORD_TOKEN)
