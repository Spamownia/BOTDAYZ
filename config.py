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
FTP_LOG_DIR = "config/"               # ← Zmień na właściwą ścieżkę: "/", "config/", "profiles/", "./" itp.

if not all([FTP_HOST, FTP_USER, FTP_PASS]):
    raise ValueError("Brak danych FTP!")

CHANNEL_IDS = {
    "connections": 1458909797121527849,
    "kills":       1458909797121527849,
    "deaths":      1458909797121527849,
    "admin":       1458909797121527849,
    "chat":        1458909797121527849,
    "debug":       123456789012345678,   # ← ZMIEŃ NA PRAWDZIWE ID KANAŁU DEBUG !!!
}

CHAT_CHANNEL_MAPPING = {
    "Global": 1458909548935905401,
    "Admin":  1458909548935905401,
    "Team":   1458909548935905401,
    "Direct": 1458909548935905401,
    "Unknown":1458909548935905401
}

CHECK_INTERVAL = 30  # sekundy
