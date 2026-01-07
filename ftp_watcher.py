import ftputil
from datetime import datetime, timedelta
from config import FTP_HOST, FTP_USER, FTP_PASS, FTP_LOG_DIR, INITIAL_LOOKBACK_MINUTES
import os

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_file = None
        self.last_size = 0
        self.last_mtime = datetime.utcnow() - timedelta(minutes=INITIAL_LOOKBACK_MINUTES)

    def connect(self):
        try:
            self.ftp = ftputil.FTPHost(FTP_HOST, FTP_USER, FTP_PASS)
            print("[FTP] Połączono")
        except Exception as e:
            print(f"[FTP] Błąd połączenia: {e}")
            self.ftp = None

    def get_latest_log_file(self):
        if not self.ftp:
            self.connect()
            if not self.ftp:
                return None, None

        try:
            files = self.ftp.listdir(FTP_LOG_DIR)
            # Filtrujemy tylko pliki .log, sortujemy po czasie modyfikacji
            log_files = [f for f in files if f.endswith(".log")]
            if not log_files:
                return None, None

            latest = max(log_files, key=lambda f: self.ftp.path.getmtime(FTP_LOG_DIR + f))
            full_path = FTP_LOG_DIR + latest
            return full_path, latest
        except Exception as e:
            print(f"[FTP] Błąd listowania: {e}")
            self.ftp = None
            return None, None

    def get_new_content(self):
        remote_path, filename = self.get_latest_log_file()
        if not remote_path:
            return ""

        try:
            mtime = datetime.fromtimestamp(self.ftp.path.getmtime(remote_path))

            # Jeśli plik się zmienił (nowy lub większy)
            if filename != self.last_file:
                # Nowy plik – bierzemy tylko ostatnie X minut
                self.last_file = filename
                self.last_size = 0

            current_size = self.ftp.path.getsize(remote_path)

            with self.ftp.open(remote_path, "rb") as f:
                if current_size > self.last_size:
                    f.seek(self.last_size)
                    new_bytes = f.read()
                    self.last_size = current_size
                    return new_bytes.decode("utf-8", errors="replace")
                else:
                    # Plik ten sam, ale nie urósł – nic nowego
                    return ""

        except Exception as e:
            print(f"[FTP] Błąd odczytu: {e}")
            self.ftp = None
            return ""
