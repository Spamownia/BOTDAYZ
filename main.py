import discord
from discord.ext import commands, tasks
from config import DISCORD_TOKEN, CHECK_INTERVAL
from ftp_watcher import DayZLogWatcher
from log_parser import process_line
import logging
from flask import Flask
import threading
import os
import asyncio

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>🟢 Bot DayZ działa!</h1>
    <p>Monitoruje logi serwera i wysyła powiadomienia na Discord.</p>
    <p>Sprawdź logi Rendera po nowe komunikaty.</p>
    """

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

watcher = DayZLogWatcher()

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_logs():
    print(f"[TASK] Sprawdzam nowe logi (co {CHECK_INTERVAL}s)...")
    content = watcher.get_new_content()
    if not content:
        print("[TASK] Brak nowych danych z FTP")
        return

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    print(f"[TASK] Znaleziono {len(lines)} nowych linii z logów DayZ!")
    for line in lines:
        await process_line(bot, line)

@bot.event
async def on_ready():
    print("════════════════════════════════════════════════")
    print(f"Bot zalogowany jako: {bot.user} (ID: {bot.user.id})")
    print(f"Połączony z {len(bot.guilds)} serwerami")
    print(f"Task check_logs uruchomiony co {CHECK_INTERVAL} sekund")
    print("════════════════════════════════════════════════")
    
    # Ręczny start taska z opóźnieniem
    await asyncio.sleep(2)
    if not check_logs.is_running():
        check_logs.start()
        print("[TASK] Task check_logs STARTED")

@bot.command()
@commands.has_permissions(administrator=True)
async def status(ctx):
    await ctx.send("✅ Bot jest online i monitoruje logi DayZ")

@bot.command()
@commands.has_permissions(administrator=True)
async def restartftp(ctx):
    watcher.__init__()
    await ctx.send("🔄 Połączenie FTP zresetowane")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Uruchamiam bota Discord...")
    bot.run(DISCORD_TOKEN)
