# config.py
# Zaktualizowany config.py – dodałem nowy kanał "damages" (zmień ID na prawdziwy)
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("Brak DISCORD_TOKEN!")

FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", "21"))
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_LOG_DIR = "/config/"               # ← Zmień na właściwą ścieżkę: "/", "config/", "profiles/", "./" itp.

if not all([FTP_HOST, FTP_USER, FTP_PASS]):
    raise ValueError("Brak danych FTP!")

CHANNEL_IDS = {
    "connections": 1464697107842863348,
    "kills":       1464697107842863348,   # ← Zmiana: stary "deaths" na "kills" dla zabójstw
    "damages":     1464697107842863348,   # ← Nowy kanał dla obrażeń (zmień ID na prawdziwy !!!)
    "admin":       1464697107842863348,
    "chat":        1464697107842863348,
    "debug":       None,   # ← ZMIEŃ NA PRAWDZIWE ID KANAŁU DEBUG !!!
}

CHAT_CHANNEL_MAPPING = {
    "Global": 1464697107842863348,
    "Admin":  1464697107842863348,
    "Team":   1464697107842863348,
    "Direct": 1464697107842863348,
    "Unknown":1464697107842863348
}

CHECK_INTERVAL = 30  # sekundy
BATTLEMETRICS_SERVER_ID = os.getenv("BATTLEMETRICS_SERVER_ID")  # Dodane – zmień na prawdziwy ID serwera BattleMetrics!
if not BATTLEMETRICS_SERVER_ID:
    raise ValueError("Brak BATTLEMETRICS_SERVER_ID w .env!")
