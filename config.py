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
    "connections": 1466846633689088082,
    "kills":       1466846633689088082,
    "damages":     1466846633689088082,
    "admin":       1466846633689088082,
    "chat":        1466846633689088082,
    "debug":       None,   # ← Zmień na prawdziwe ID jeśli chcesz debug
}

CHAT_CHANNEL_MAPPING = {
    "Global": 1466846633689088082,
    "Admin":  1466846633689088082,
    "Team":   1466846633689088082,
    "Direct": 1466846633689088082,
    "Unknown":1466846633689088082
}

CHECK_INTERVAL = 30  # sekundy

# BattleMetrics – teraz bez wymuszonego błędu
BATTLEMETRICS_SERVER_ID = os.getenv("BATTLEMETRICS_SERVER_ID")
if not BATTLEMETRICS_SERVER_ID:
    print("[CONFIG] Brak BATTLEMETRICS_SERVER_ID – status online nie będzie aktualizowany")
