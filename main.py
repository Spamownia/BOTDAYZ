import discord
from discord.ext import commands, tasks
from config import DISCORD_TOKEN, CHECK_INTERVAL
from ftp_watcher import DayZLogWatcher
from log_parser import process_line
import logging

# Pokazujemy więcej informacji w konsoli Rendera
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

watcher = DayZLogWatcher()

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_logs():
    content = watcher.get_new_content()
    if not content:
        return

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if lines:
        print(f"[LOGI DayZ] Znaleziono {len(lines)} nowych linii z pliku .RPT")
        for line in lines:
            await process_line(bot, line)
    # Jeśli nic nowego – nie spamujemy konsoli

@bot.event
async def on_ready():
    print("════════════════════════════════════════════════")
    print(f"Bot zalogowany jako: {bot.user} (ID: {bot.user.id})")
    print(f"Połączony z {len(bot.guilds)} serwerami Discord")
    print(f"Monitorowanie logów DayZ włączone (co {CHECK_INTERVAL}s)")
    print("════════════════════════════════════════════════")
    if not check_logs.is_running():
        check_logs.start()

@bot.command()
@commands.has_permissions(administrator=True)
async def logstatus(ctx):
    await ctx.send("✅ Monitorowanie logów DayZ jest aktywne i działa prawidłowo.")

@bot.command()
@commands.has_permissions(administrator=True)
async def restartftp(ctx):
    watcher.__init__()  # reset połączenia FTP
    await ctx.send("🔄 Połączenie FTP zostało zresetowane.")

print("Uruchamiam bota Discord...")
bot.run(DISCORD_TOKEN)
