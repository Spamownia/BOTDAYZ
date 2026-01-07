import os
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# FTP
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_LOG_DIR = os.getenv("FTP_LOG_DIR", "/config/")  # <-- zmienione na /config/

# ID kanałów – zmień na swoje!
CHANNEL_IDS = {
    "connections": 123456789012345678,
    "kills":       987654321098765432,
    "deaths":      111222333444555666,
    "admin":       222333444555666777,
    "chat":        333444555666777888,
    "debug":       None
}

# Ile minut wstecz przeczytać przy pierwszym uruchomieniu
INITIAL_LOOKBACK_MINUTES = 10

# Częstotliwość sprawdzania FTP (sekundy)
CHECK_INTERVAL = 15
