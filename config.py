import os
from dotenv import load_dotenv

load_dotenv()

# Discord Token
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("Brak DISCORD_TOKEN w zmiennych środowiskowych!")

# FTP dane
FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", "21"))
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_LOG_DIR = os.getenv("FTP_LOG_DIR", "/config/")

if not all([FTP_HOST, FTP_USER, FTP_PASS]):
    raise ValueError("Brak wymaganych danych FTP!")

# Kanały Discord – ZMIEŃ ID NA SWOJE RZECZYWISTE!
CHANNEL_IDS = {
    "connections": 1459206440836141302,  # połączenia / rozłączenia
    "kills": 1458909797121527849,
    "deaths": 1458909797121527849,
    "admin": 1460000218232652071,
    "chat": 1459919995919143024,         # domyślny dla chatu (jeśli nie ma mapowania)
    "debug": None                        # wyłącz debug, żeby uniknąć rate limit
}

# Mapowanie typów chatu DayZ → konkretne kanały Discord
CHAT_CHANNEL_MAPPING = {
    "Global": 1459919525037478039,    # Główny chat globalny
    "Admin":  1459919995919143024,    # Chat admina / COT / komendy
    "Team":   1459919995919143024,    # Grupowy / team chat
    "Direct": 1459919995919143024,    # Szept / direct
    "Unknown": 1458909548935905401
}

# Ustawienia
CHECK_INTERVAL = 30  # sekundy
