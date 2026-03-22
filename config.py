# config.py
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
FTP_LOG_DIR = "/config/"               # ← Zmień na właściwą ścieżkę jeśli potrzeba

if not all([FTP_HOST, FTP_USER, FTP_PASS]):
    raise ValueError("Brak danych FTP!")

CHANNEL_IDS = {
    "connections": 1477302685542645991,
    "kills":       1477302685542645991,
    "damages":     1477302685542645991,
    "admin":       1477302685542645991,
    "chat":        1477302685542645991,
    "debug":       None,   # ← Zmień na prawdziwe ID jeśli chcesz debug
}

CHAT_CHANNEL_MAPPING = {
    "Global": 1477302685542645991,
    "Admin":  1477302685542645991,
    "Team":   1477302685542645991,
    "Direct": 1477302685542645991,
    "Unknown":None
}

CHECK_INTERVAL = 30  # sekundy

# BattleMetrics – teraz bez wymuszonego błędu
BATTLEMETRICS_SERVER_ID = os.getenv("BATTLEMETRICS_SERVER_ID")
if not BATTLEMETRICS_SERVER_ID:
    print("[CONFIG] Brak BATTLEMETRICS_SERVER_ID – status online nie będzie aktualizowany")
