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
    "connections": 1459206440836141302,  # połączenia/rozłączenia
    "kills": 1458909797121527849,        # zabójstwa (jeśli chcesz oddzielić – zmień)
    "deaths": 1458909797121527849,       # śmierci (obecnie ten sam co kills)
    "admin": 1458909797121527849,        # akcje admina i COT
    "chat": 1458909797121527849,         # chat w grze (opcjonalnie)
    "debug": 1249732031634739203,                       # ← WPISZ TU ID KANAŁU TESTOWEGO (np. prywatny) – później ustaw na None
}

# Ustawienia
INITIAL_LOOKBACK_MINUTES = 1
CHECK_INTERVAL = 30  # co ile sekund sprawdzać nowe linie
