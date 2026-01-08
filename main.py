import discord
from discord.ext import commands, tasks
from config import DISCORD_TOKEN, CHECK_INTERVAL, CHANNEL_IDS
from ftp_watcher import DayZLogWatcher
from log_parser import process_line
import logging
from flask import Flask
import threading
import os
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

app = Flask(__name__)
@app.route('/')
def home():
    return """
    <h1>🟢 Bot DayZ działa!</h1>
    <p>Monitoruje logi serwera i wysyła powiadomienia na Discord.</p>
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
    
    if not watcher.connect():
        print("[TASK] ❌ Brak połączenia FTP")
        return
    
    content = watcher.get_new_content()
    if not content:
        print("[TASK] Brak nowych danych")
        return
    
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    print(f"[TASK] Znaleziono {len(lines)} nowych linii")
    
    # Ochrona przed floodem starych logów przy pierwszym uruchomieniu
    if len(lines) > 500:
        print(f"[TASK] ⚠️ ZA DUŻO LINII ({len(lines)}) – pomijam (stare logi). Od następnego cyklu będzie OK.")
        return
    
    for line in lines:
        try:
            await process_line(bot, line)
        except Exception as e:
            print(f"[BŁĄD przetwarzania linii]: {e}")

@bot.event
async def on_ready():
    print("════════════════════════════════════════════════")
    print(f"Bot zalogowany jako: {bot.user}")
    print(f"Połączony z {len(bot.guilds)} serwerami")
    print("════════════════════════════════════════════════")
    await asyncio.sleep(3)
    if not check_logs.is_running():
        check_logs.start()
        print("[TASK] check_logs STARTED")

@bot.command()
@commands.has_permissions(administrator=True)
async def status(ctx):
    await ctx.send("✅ Bot online i monitoruje logi")

@bot.command()
@commands.has_permissions(administrator=True)
async def restartftp(ctx):
    watcher.__init__()
    await ctx.send("🔄 FTP watcher zresetowany")

@bot.command()
@commands.has_permissions(administrator=True)
async def ftpstatus(ctx):
    if watcher.connect():
        await ctx.send("🟢 FTP połączone")
    else:
        await ctx.send("🔴 FTP błąd połączenia")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Uruchamiam bota Discord...")
    bot.run(DISCORD_TOKEN)
