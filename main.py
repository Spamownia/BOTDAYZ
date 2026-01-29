import discord
from discord.ext import commands, tasks
import asyncio
import requests
import threading
from flask import Flask
import warnings
import logging
from config import DISCORD_TOKEN
from ftp_watcher import DayZLogWatcher
from log_parser import process_line

# ────────────────────────────────────────────────
# Wyciszenie ostrzeżeń
# ────────────────────────────────────────────────
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=r"Unclosed client session", category=Warning)
warnings.filterwarnings("ignore", message=r"Unclosed.*ClientSession", category=Warning)

logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

watcher = DayZLogWatcher()

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot Husaria – żyje!", 200

threading.Thread(
    target=lambda: flask_app.run(host='0.0.0.0', port=10000, debug=False),
    daemon=True
).start()

BATTLEMERTICS_SERVER_ID = "37055320"

@tasks.loop(seconds=60)
async def update_status():
    try:
        r = requests.get(f"https://api.battlemetrics.com/servers/{BATTLEMERTICS_SERVER_ID}", timeout=10)
        r.raise_for_status()
        d = r.json()["data"]["attributes"]
        await client.change_presence(activity=discord.Game(f"{d['players']}/{d['maxPlayers']} online"))
        print(f"[STATUS] {d['players']}/{d['maxPlayers']}")
    except Exception as e:
        print(f"[STATUS ERROR] {e}")

@client.event
async def on_ready():
    print(f"[BOT] Gotowy – {client.user}")
    update_status.start()
    
    print("[BOT] Uruchamiam watcher logów co 30 sekund...")
    # Uruchamiamy watcher w osobnym wątku
    threading.Thread(target=watcher.run, daemon=True).start()
    
    # Natychmiastowe pierwsze sprawdzenie
    print("[BOT] Natychmiastowe pierwsze sprawdzenie logów...")
    await check_and_parse_new_content()

async def check_and_parse_new_content():
    """Funkcja pomocnicza – pobiera i parsuje nowe linie"""
    content = watcher.get_new_content()
    if not content:
        print("[CHECK] Brak nowych danych")
        return
    
    lines = [l for l in content.splitlines() if l.strip()]
    print(f"[CHECK] Przetwarzam {len(lines)} linii")
    
    for line in lines:
        try:
            await process_line(client, line)
        except Exception as line_err:
            print(f"[LINE PROCESS ERROR] {line_err} → linia: {line[:120]}...")

def run_watcher_loop():
    """Pętla w watcherze – co 30 sekund pobiera i parsuje"""
    print("[WATCHER THREAD] Start pętli co 30 sekund")
    while True:
        try:
            asyncio.run_coroutine_threadsafe(check_and_parse_new_content(), client.loop)
        except Exception as e:
            print(f"[WATCHER THREAD ERROR] {e}")
        time.sleep(30)

@client.event
async def on_ready():
    print(f"[BOT] Gotowy – {client.user}")
    update_status.start()
    
    print("[BOT] Uruchamiam watcher logów co 30 sekund...")
    # Uruchamiamy watcher w osobnym wątku
    threading.Thread(target=run_watcher_loop, daemon=True).start()
    
    # Natychmiastowe pierwsze sprawdzenie
    print("[BOT] Natychmiastowe pierwsze sprawdzenie logów...")
    await check_and_parse_new_content()

# ────────────────────────────────────────────────
# Bezpieczne uruchamianie z backoff-em
# ────────────────────────────────────────────────
async def safe_run_bot():
    backoff = 5
    max_backoff = 120
    while True:
        try:
            await client.start(DISCORD_TOKEN)
            break
        except discord.errors.LoginFailure:
            print("[FATAL] Nieprawidłowy token – wyłączam bota")
            return
        except discord.errors.HTTPException as e:
            if e.status in (429, 1015):
                wait_time = backoff
                print(f"[RATE LIMIT / 1015] Czekam {wait_time}s...")
                await asyncio.sleep(wait_time)
                backoff = min(backoff * 2, max_backoff)
            else:
                print(f"[HTTP ERROR] {e} – retry za {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
        except Exception as e:
            print(f"[CRITICAL ERROR] {e} – restart za {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

if __name__ == "__main__":
    try:
        asyncio.run(safe_run_bot())
    except KeyboardInterrupt:
        print("[MAIN] Wyłączanie bota (Ctrl+C)")
    except Exception as e:
        print(f"[MAIN FATAL] {e}")
    finally:
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
                loop.close()
        except:
            pass
