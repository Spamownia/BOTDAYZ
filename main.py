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

# Importy z Twoich plików
from config import DISCORD_TOKEN, CHANNEL_IDS, CHAT_CHANNEL_MAPPING, BATTLEMETRICS_SERVER_ID
from ftp_watcher import DayZLogWatcher
from log_parser import process_line

# Wyciszenie ostrzeżeń (pozostawiamy, ale dodajemy bardziej precyzyjne)
warnings.filterwarnings("ignore", category=ResourceWarning)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("aiohttp.client").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = commands.Bot(command_prefix="!", intents=intents)
watcher = DayZLogWatcher()

# ────────────────────────────────────────────────
# Prosty serwer health-check (na Render) – poprawiony port
# ────────────────────────────────────────────────
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
    # Render przekazuje PORT przez zmienną środowiskową – używamy jej
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"[HEALTH] Uruchamiam health-check na :{port}")
    server.serve_forever()


threading.Thread(target=run_health_server, daemon=True).start()

# ────────────────────────────────────────────────
# Status BattleMetrics – bez zmian
# ────────────────────────────────────────────────
@tasks.loop(seconds=60)
async def update_status():
    server_id = BATTLEMETRICS_SERVER_ID
   
    print(f"[STATUS DEBUG] Wartość BATTLEMETRICS_SERVER_ID = '{server_id}' (typ: {type(server_id).__name__})")
   
    if not server_id or not str(server_id).strip().isdigit():
        print("[STATUS] Brak poprawnego ID BattleMetrics → ustawiam fallback")
        try:
            await client.change_presence(activity=discord.Game("BM ID nie ustawiony"))
        except Exception as e:
            print(f"[STATUS FALLBACK ERROR] {e}")
        return

    url = f"https://api.battlemetrics.com/servers/{server_id}"
    print(f"[STATUS] Zapytanie do: {url}")

    try:
        r = requests.get(url, timeout=12)
        print(f"[STATUS] Status HTTP: {r.status_code}")

        if r.status_code != 200:
            error_text = r.text[:300].replace('\n', ' ') if r.text else '(brak treści)'
            print(f"[STATUS ERROR] HTTP {r.status_code} → {error_text}")
           
            if r.status_code == 404:
                await client.change_presence(activity=discord.Game("Serwer nie znaleziony w BM"))
            elif r.status_code == 429:
                await client.change_presence(activity=discord.Game("BM rate limit"))
            else:
                await client.change_presence(activity=discord.Game(f"BM błąd {r.status_code}"))
            return

        data = r.json()
        attrs = data.get("data", {}).get("attributes", {})
       
        players = attrs.get("players", "?")
        max_players = attrs.get("maxPlayers", "?")
       
        status_text = f"{players}/{max_players} online"
        print(f"[STATUS SUCCESS] Ustawiam: {status_text}")

        await client.change_presence(activity=discord.Game(status_text))

    except requests.exceptions.RequestException as req_err:
        print(f"[STATUS REQUEST ERROR] {req_err.__class__.__name__}: {req_err}")
        await client.change_presence(activity=discord.Game("BM API niedostępne"))
    except Exception as e:
        print(f"[STATUS CRITICAL ERROR] {e.__class__.__name__}: {e}")
        await client.change_presence(activity=discord.Game("Błąd statusu"))

# ────────────────────────────────────────────────
# Pętla sprawdzania logów – dodajemy lepszą obsługę błędów w pętli
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
            future.result(timeout=20)   # zwiększony timeout – 15→20
        except asyncio.TimeoutError:
            print("[WATCHER THREAD] Timeout przetwarzania – kontynuuję")
        except Exception as e:
            print(f"[WATCHER THREAD ERROR] {type(e).__name__}: {e}")
        time.sleep(30)

# ────────────────────────────────────────────────
# on_ready + test kanałów – bez zmian
# ────────────────────────────────────────────────
@client.event
async def on_ready():
    print(f"\n[BOT] === GOTOWY === {client.user} (ID: {client.user.id})")
    print(f"[BOT] Serwery: {len(client.guilds)}")

    if client.guilds:
        guild = client.guilds[0]
        print(f"[BOT] Główny serwer: {guild.name} ({guild.id})")

    test_ids = {
        "connections": CHANNEL_IDS.get("connections"),
        "kills":       CHANNEL_IDS.get("kills"),
        "damages":     CHANNEL_IDS.get("damages"),
        "admin":       CHANNEL_IDS.get("admin"),
        "chat":        CHANNEL_IDS.get("chat"),
    }

    for name, ch_id in test_ids.items():
        if not ch_id:
            print(f"[TEST] Brak ID dla kanału: {name}")
            continue

        ch = client.get_channel(ch_id)
        if ch:
            test_msg = f"**TEST START {name.upper()}** – bot widzi kanał 🟢 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            print(f"[TEST] {test_msg}")  # Tylko w konsoli rendera
            # Zakomentowane – nie wysyła na Discord
        else:
            print(f"[TEST] {name} → kanał {ch_id} nie znaleziony")

    print("[BOT] Uruchamiam update_status i watcher...")
    update_status.start()
    threading.Thread(target=run_watcher_loop, daemon=True).start()

    await check_and_parse_new_content()

# ────────────────────────────────────────────────
# Bezpieczne uruchamianie – upraszczamy + używamy bot.run()
# ────────────────────────────────────────────────
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("[FATAL] Brak DISCORD_TOKEN w zmiennych środowiskowych!")
        exit(1)

    print("[MAIN] Uruchamiam bota...")
    try:
        client.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("[MAIN] Wyłączanie (Ctrl+C / SIGTERM)")
    except discord.LoginFailure:
        print("[FATAL] Nieprawidłowy token")
    except Exception as e:
        print(f"[MAIN FATAL] {type(e).__name__}: {e}")
    finally:
        print("[MAIN] Kończenie...")
        # discord.py sam zamyka sesję przy client.run() – nie trzeba ręcznie
