import os
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("Brak DISCORD_TOKEN w pliku .env lub w zmiennych środowiskowych Render!")

# FTP
FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", "21"))
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_LOG_DIR = os.getenv("FTP_LOG_DIR", "/config/")

if not all([FTP_HOST, FTP_USER, FTP_PASS]):
    raise ValueError("Brak wymaganych danych FTP w zmiennych środowiskowych!")

# ←←←←←← WPISZ TUTAJ SWOJE ID KANAŁÓW DISCORD ←←←←←←
CHANNEL_IDS = {
    "connections": 1458887056834040012,  # <-- ZMIEŃ NA ID KANAŁU NA POŁĄCZENIA/ROZŁĄCZENIA
    "kills":       1458909596998701128,  # <-- ZMIEŃ NA ID KANAŁU NA ZABÓJSTWA
    "deaths":      1458909596998701128,  # <-- ZMIEŃ NA ID KANAŁU NA ŚMIERCI
    "admin":       1458909797121527849,  # <-- ZMIEŃ NA ID KANAŁU NA AKCJE ADMINA
    "chat":        1458909548935905401,                # <-- opcjonalnie ID kanału na chat w grze
    "debug":       None,  # <-- NA CZAS TESTÓW WPISZ ID KANAŁU DEBUG (wszystkie linie logów)
}

# Ustawienia
INITIAL_LOOKBACK_MINUTES = 10
CHECK_INTERVAL = 15  # co ile sekund sprawdzać nowe linie
