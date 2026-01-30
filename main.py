import discord
from discord.ext import commands, tasks
import asyncio
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import warnings
import logging
import time
from datetime import datetime

# Importy Twoich modułów
from config import DISCORD_TOKEN, CHANNEL_IDS, CHAT_CHANNEL_MAPPING, BATTLEMERTICS_SERVER_ID
from ftp_watcher import DayZLogWatcher
from log_parser import process_line

# Wyciszenie ostrzeżeń i logów
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Unclosed.*ClientSession")
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = commands.Bot(command_prefix="!", intents=intents)
watcher = DayZLogWatcher()

# ────────────────────────────────────────────────
# Prosty serwer health-check zamiast Flask
# ────────────────────────────────────────────────
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Husaria – żyje! 🚀")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()


def run_health_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    print("[HEALTH] Uruchamiam prosty serwer health-check na :10000")
    server.serve_forever()


# Uruchom health-check w osobnym wątku
threading.Thread(target=run_health_server, daemon=True).start()

# ────────────────────────────────────────────────
# Status online / gracze z BattleMetrics
# ────────────────────────────────────────────────
@tasks.loop(seconds=60)
async def update_status():
    try:
        r = requests.get(f"https://api.battlemetrics.com/servers/{BATTLEMERTICS_SERVER_ID}", timeout=10)
        r.raise_for_status()
        d = r.json()["data"]["attributes"]
        await client.change_presence(activity=discord.Game(f"{d['players']}/{d['maxPlayers']} online"))
        print(f"[STATUS] {d['players']}/{d['maxPlayers']} | {datetime.utcnow().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"[STATUS ERROR] {e}")

# ────────────────────────────────────────────────
# Główna pętla pobierania i parsowania logów
# ────────────────────────────────────────────────
async def check_and_parse_new_content():
    content = watcher.get_new_content()
    if not content:
        print("[CHECK] Brak nowych danych z FTP")
        return

    lines = [l.strip() for l in content.splitlines() if l.strip()]
    print(f"[CHECK] Przetwarzam {len(lines)} linii ({datetime.utcnow().strftime('%H:%M:%S')})")

    for line in lines:
        try:
            await process_line(client, line)
        except Exception as line_err:
            print(f"[LINE PROCESS ERROR] {line_err} → {line[:140]}...")


def run_watcher_loop():
    print("[WATCHER THREAD] Start pętli co ~30 sekund")
    while True:
        try:
            future = asyncio.run_coroutine_threadsafe(check_and_parse_new_content(), client.loop)
            future.result(timeout=15)  # czekamy max 15s
        except Exception as e:
            print(f"[WATCHER THREAD ERROR] {e}")
        time.sleep(30)


# ────────────────────────────────────────────────
# on_ready
# ────────────────────────────────────────────────
@client.event
async def on_ready():
    print(f"\n[BOT] === GOTOWY === {client.user} (ID: {client.user.id})")
    print(f"[BOT] Serwery: {len(client.guilds)}")

    if client.guilds:
        guild = client.guilds[0]
        print(f"[BOT] Główny serwer: {guild.name} ({guild.id})")
        print(f"[BOT] Widoczne kanały: {len(list(guild.text_channels))}")

    # Testowe wysłanie wiadomości
    test_ids = {
        "connections": CHANNEL_IDS.get("connections"),
        "kills": CHANNEL_IDS.get("kills"),
        "damages": CHANNEL_IDS.get("damages"),
        "chat": CHANNEL_IDS.get("chat"),
    }

    for name, ch_id in test_ids.items():
        if not ch_id:
            print(f"[TEST] Brak ID dla kanału: {name}")
            continue

        ch = client.get_channel(ch_id)
        if ch is None:
            print(f"[TEST] {name} → get_channel({ch_id}) = None")
            try:
                ch = await client.fetch_channel(ch_id)
                print(f"[TEST] fetch_channel({ch_id}) → OK")
            except Exception as e:
                print(f"[TEST FETCH {name}] {e}")
        else:
            print(f"[TEST] {name} → OK: {ch.name} ({ch.id})")

        if ch:
            try:
                await ch.send(f"**TEST START {name.upper()}** – bot widzi kanał 🟢 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"[TEST] Wiadomość testowa WYSŁANA na {name}")
            except Exception as e:
                print(f"[TEST SEND {name}] {e}")

    update_status.start()
    print("[BOT] Uruchamiam watcher logów...")
    threading.Thread(target=run_watcher_loop, daemon=True).start()

    # Pierwsze sprawdzenie od razu
    await check_and_parse_new_content()


# ────────────────────────────────────────────────
# Bezpieczne uruchamianie z retry
# ────────────────────────────────────────────────
async def safe_run_bot():
    backoff = 5
    max_backoff = 180
    while True:
        try:
            print("[BOT] Próba logowania...")
            await client.start(DISCORD_TOKEN)
            break
        except discord.errors.LoginFailure:
            print("[FATAL] Nieprawidłowy token – wyłączam")
            return
        except discord.errors.HTTPException as e:
            if e.status in (429, 1015):
                print(f"[RATE LIMIT] Czekam {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            else:
                print(f"[HTTP ERROR] {e} – retry za {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
        except Exception as e:
            print(f"[CRITICAL] {e} – restart za {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


# ────────────────────────────────────────────────
# Główny punkt wejścia
# ────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(safe_run_bot())
    except KeyboardInterrupt:
        print("[MAIN] Wyłączanie (Ctrl+C)")
    except Exception as e:
        print(f"[MAIN FATAL] {e}")
    finally:
        print("[MAIN] Kończenie – czyszczenie sesji...")
        try:
            if hasattr(client, 'http') and hasattr(client.http, 'session') and client.http.session is not None:
                print("[MAIN] Zamykam sesję HTTP discord.py...")
                try:
                    asyncio.run_coroutine_threadsafe(client.http.session.close(), client.loop).result(timeout=5)
                except:
                    pass
        except Exception as e:
            print(f"[MAIN CLOSE HTTP] {e}")

        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                print("[MAIN] Zamykam pętlę asyncio...")
                loop.run_until_complete(client.close())
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
                loop.close()
        except Exception as e:
            print(f"[MAIN LOOP CLOSE] {e}")
