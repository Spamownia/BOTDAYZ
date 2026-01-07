import os
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# FTP
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_LOG_DIR = os.getenv("FTP_LOG_DIR", "/logs/")

# ID kanałów – zmień na swoje!
CHANNEL_IDS = {
    "connections": 1249732031634739203,  # dołączenia / wyjścia
    "kills":       1249732031634739203,  # zabójstwa PvP i zombie
    "deaths":      1249732031634739203,  # śmierci graczy (np. od zombie, upadku)
    "admin":       1249732031634739203,  # akcje admina, kicki, bany
    "chat":        1249732031634739203,  # wiadomości w grze (jeśli logowane)
    "debug":       None                  # None = wyłączony
}

# Ile minut wstecz przeczytać przy pierwszym uruchomieniu
INITIAL_LOOKBACK_MINUTES = 10

# Częstotliwość sprawdzania FTP (sekundy)
CHECK_INTERVAL = 15
