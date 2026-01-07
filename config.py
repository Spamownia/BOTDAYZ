import os
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("Brak DISCORD_TOKEN w pliku .env!")

# FTP
FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", "21"))
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_LOG_DIR = os.getenv("FTP_LOG_DIR", "/config/")

if not all([FTP_HOST, FTP_USER, FTP_PASS]):
    raise ValueError("Brak wymaganych danych FTP w pliku .env!")

# ID kanałów Discord – WPISZ SWOJE ID KANAŁÓW!
CHANNEL_IDS = {
    "connections": None,  # np. 123456789012345678
    "kills":       None,
    "deaths":      None,
    "admin":       None,
    "chat":        None,
    "debug":       None,  # ustaw na ID jeśli chcesz surowe logi (pomocne przy testach)
}

# Ustawienia
INITIAL_LOOKBACK_MINUTES = 10
CHECK_INTERVAL = 15  # co ile sekund sprawdzać nowe linie
