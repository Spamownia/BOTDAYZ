import discord
from discord.ext import commands, tasks
from config import DISCORD_TOKEN, CHECK_INTERVAL
from ftp_watcher import DayZLogWatcher
from log_parser import process_line
import logging
from flask import Flask
import threading
import os

# Logi do konsoli Rendera
logging.basicConfig(level=logging.INFO)

# Minimalny Flask – otwiera port, żeby Render był zadowolony
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>🟢 Bot DayZ jest online i działa!</h1>
    <p>Monitoruje logi serwera DayZ i wysyła powiadomienia na Discord.</p>
    <p>Aktualny czas serwera: January 08, 2026</p>
    """

def run_flask():
    # Render wymaga zmiennej środowiskowej PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Discord bot
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

@bot.event
async def on_ready():
    print("════════════════════════════════════════════════")
    print(f"Bot zalogowany jako: {bot.user} (ID: {bot.user.id})")
    print(f"Połączony z {len(bot.guilds)} serwerami Discord")
    print(f"Monitorowanie logów DayZ włączone (co {CHECK_INTERVAL}s)")
    print(f"Flask działa na porcie {os.environ.get('PORT', 10000)}")
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
    await ctx.send("🔄 Połączenie z FTP zostało zresetowane.")

# Uruchamiamy Flask w tle, potem bota Discord
if __name__ == "__main__":
    # Flask w osobnym wątku
    threading.Thread(target=run_flask, daemon=True).start()
    print("Uruchamiam bota Discord...")
    bot.run(DISCORD_TOKEN)
