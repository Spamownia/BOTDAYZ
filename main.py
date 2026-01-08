# main.py – OSTATECZNA WERSJA

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

# Lepsze logowanie do konsoli Rendera
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

# Flask – żeby Render nie wyłączał bota
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>🟢 Bot DayZ działa!</h1>
    <p>Monitoruje logi serwera i wysyła powiadomienia na Discord.</p>
    <p>Aktualny czas: live</p>
    """

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Intents
intents = discord.Intents.default()

# Bot
bot = commands.Bot(command_prefix="!", intents=intents)
watcher = DayZLogWatcher()

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_logs():
    print(f"[TASK] Sprawdzam nowe logi (co {CHECK_INTERVAL}s)...")
    
    if not watcher.connect():
        print("[TASK] ❌ Nie udało się połączyć z FTP – pomijam cykl")
        return
    
    content = watcher.get_new_content()
    
    if not content:
        print("[TASK] Brak nowych danych z logów")
        return
    
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    print(f"[TASK] Znaleziono {len(lines)} nowych linii do przetworzenia")
    
    # Ochrona przed ogromną ilością linii przy pierwszym uruchomieniu po długiej przerwie
    if len(lines) > 500:
        print(f"[TASK] ⚠️ ZA DUŻO LINII ({len(lines)}) – to stare logi. Pomijam przetwarzanie w tym cyklu.")
        print("[TASK] Od następnego cyklu bot będzie działał normalnie (tylko nowe linie).")
        return
    
    print(f"[TASK] Przetwarzam {len(lines)} linii...")
    for line in lines:
        try:
            await process_line(bot, line)
        except Exception as e:
            print(f"[BŁĄD] Nie udało się przetworzyć linii: {line[:100]}... | Error: {e}")

@bot.event
async def on_ready():
    print("════════════════════════════════════════════════")
    print(f"Bot zalogowany jako: {bot.user} (ID: {bot.user.id})")
    print(f"Połączony z {len(bot.guilds)} serwerami Discord")
    print(f"Task check_logs uruchomiony co {CHECK_INTERVAL} sekund")
    print("════════════════════════════════════════════════")
    
    # Start taska z opóźnieniem
    await asyncio.sleep(3)
    if not check_logs.is_running():
        check_logs.start()
        print("[TASK] check_logs успешно STARTED")
    else:
        print("[TASK] check_logs już działa")

# Komendy administracyjne
@bot.command()
@commands.has_permissions(administrator=True)
async def status(ctx):
    await ctx.send("✅ Bot jest online i monitoruje logi DayZ")

@bot.command()
@commands.has_permissions(administrator=True)
async def restartftp(ctx):
    watcher.__init__()  # reset watcher'a i state
    await ctx.send("🔄 Połączenie FTP i stan logów zostały zresetowane")

@bot.command()
@commands.has_permissions(administrator=True)
async def ftpstatus(ctx):
    if watcher.connect():
        await ctx.send("🟢 Połączenie FTP jest aktywne")
    else:
        await ctx.send("🔴 Problem z połączeniem FTP – sprawdź dane w .env")

# Uruchomienie
if __name__ == "__main__":
    # Flask w tle
    threading.Thread(target=run_flask, daemon=True).start()
    print("Uruchamiam Flask i bota Discord...")
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Nie udało się uruchomić bota Discord: {e}")
