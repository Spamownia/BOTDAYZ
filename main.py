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

from config import DISCORD_TOKEN, CHANNEL_IDS, CHAT_CHANNEL_MAPPING, BATTLEMETRICS_SERVER_ID
from ftp_watcher import DayZLogWatcher
from log_parser import process_line

warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message="Unclosed client session")
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = commands.Bot(command_prefix="!", intents=intents)
watcher = DayZLogWatcher()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Bot Husaria - żyje!".encode('utf-8'))

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_health_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    print("[HEALTH] Uruchamiam health-check na :10000")
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

@tasks.loop(seconds=60)
async def update_status():
    server_id = BATTLEMETRICS_SERVER_ID
    print(f"[STATUS DEBUG] Wartość BATTLEMETRICS_SERVER_ID = '{server_id}' (typ: {type(server_id).__name__})")
    
    if not server_id or not str(server_id).strip().isdigit():
        print("[STATUS] Brak poprawnego ID BattleMetrics → fallback")
        await client.change_presence(activity=discord.Game("BM ID nie ustawiony"))
        return

    url = f"https://api.battlemetrics.com/servers/{server_id}"
    print(f"[STATUS] Zapytanie do: {url}")

    try:
        r = requests.get(url, timeout=12)
        print(f"[STATUS] Status HTTP: {r.status_code}")

        if r.status_code != 200:
            print(f"[STATUS ERROR] HTTP {r.status_code} → {r.text[:300]}")
            await client.change_presence(activity=discord.Game(f"BM błąd {r.status_code}"))
            return

        data = r.json()
        attrs = data.get("data", {}).get("attributes", {})
        players = attrs.get("players", "?")
        max_players = attrs.get("maxPlayers", "?")
        status_text = f"{players}/{max_players} online"
        print(f"[STATUS SUCCESS] Ustawiam: {status_text}")
        await client.change_presence(activity=discord.Game(status_text))

    except Exception as e:
        print(f"[STATUS ERROR] {e}")
        await client.change_presence(activity=discord.Game("BM API niedostępne"))

async def check_and_parse_new_content():
    content = watcher.get_new_content()
    if content:
        print(f"[DEBUG MAIN] Pobrano {len(content.splitlines())} linii – wysyłam do parsera")
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        for line in lines:
            try:
                await process_line(client, line)
            except Exception as e:
                print(f"[PARSER LINE ERROR] {e} → {line[:140]}...")
    else:
        print("[DEBUG MAIN] get_new_content() → pusty string, nic do parsowania")

def run_watcher_loop():
    print("[WATCHER THREAD] Start pętli co 30 sekund")
    while True:
        try:
            future = asyncio.run_coroutine_threadsafe(check_and_parse_new_content(), client.loop)
            future.result(timeout=15)
        except Exception as e:
            print(f"[WATCHER THREAD ERROR] {e}")
        time.sleep(30)

@client.event
async def on_ready():
    print(f"\n[BOT] === GOTOWY === {client.user} (ID: {client.user.id})")
    print(f"[BOT] Serwery: {len(client.guilds)}")

    test_ids = {
        "connections": CHANNEL_IDS.get("connections"),
        "kills": CHANNEL_IDS.get("kills"),
        "damages": CHANNEL_IDS.get("damages"),
        "chat": CHANNEL_IDS.get("chat"),
    }

    for name, ch_id in test_ids.items():
        if not ch_id:
            continue
        ch = client.get_channel(ch_id)
        if ch:
            try:
                await ch.send(f"**TEST START {name.upper()}** – bot widzi kanał 🟢 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                print(f"[TEST {name}] {e}")

    print("[BOT] Uruchamiam update_status i watcher...")
    update_status.start()
    threading.Thread(target=run_watcher_loop, daemon=True).start()
    await check_and_parse_new_content()

async def safe_run_bot():
    backoff = 5
    max_backoff = 900
    while True:
        try:
            await client.start(DISCORD_TOKEN)
            break
        except discord.errors.LoginFailure:
            print("[FATAL] Nieprawidłowy token")
            return
        except Exception as e:
            print(f"[CRITICAL] {e} – retry za {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

if __name__ == "__main__":
    try:
        asyncio.run(safe_run_bot())
    except KeyboardInterrupt:
        print("[MAIN] Wyłączanie (Ctrl+C)")
    except Exception as e:
        print(f"[MAIN FATAL] {e}")
    finally:
        print("[MAIN] Kończenie sesji...")
        try:
            asyncio.run_coroutine_threadsafe(client.close(), client.loop)
        except:
            pass
