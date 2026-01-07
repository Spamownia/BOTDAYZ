import ftputil
from datetime import datetime, timedelta
from config import FTP_HOST, FTP_USER, FTP_PASS, FTP_LOG_DIR, INITIAL_LOOKBACK_MINUTES
import re

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.current_file = None      # nazwa aktualnego pliku .RPT
        self.last_size = 0            # rozmiar już przeczytany
        self.last_mtime = datetime.utcnow() - timedelta(minutes=INITIAL_LOOKBACK_MINUTES)

    def connect(self):
        try:
            self.ftp = ftputil.FTPHost(FTP_HOST, FTP_USER, FTP_PASS)
            print("[FTP] Połączono pomyślnie")
        except Exception as e:
            print(f"[FTP] Błąd połączenia: {e}")
            self.ftp = None

    def get_latest_rpt_file(self):
        """
        Szuka najnowszego pliku pasującego do wzorca DayZServer_x64_*.RPT
        Sortuje po czasie modyfikacji (najnowszy na górze)
        """
        if not self.ftp:
            self.connect()
            if not self.ftp:
                return None

        try:
            all_files = self.ftp.listdir(FTP_LOG_DIR)
            
            # Filtrujemy tylko pliki .RPT z odpowiednim prefiksem
            rpt_files = [
                f for f in all_files
                if f.startswith("DayZServer_x64_") and f.endswith(".RPT")
            ]

            if not rpt_files:
                print("[FTP] Nie znaleziono żadnych plików .RPT w /config/")
                return None

            # Sortujemy po czasie modyfikacji (najnowszy pierwszy)
            latest_file = max(
                rpt_files,
                key=lambda f: self.ftp.path.getmtime(FTP_LOG_DIR + f)
            )

            full_path = FTP_LOG_DIR + latest_file
            return full_path, latest_file

        except Exception as e:
            print(f"[FTP] Błąd podczas listowania plików: {e}")
            self.ftp = None
            return None

    def get_new_content(self):
        """
        Pobiera tylko nowe linie z najnowszego pliku .RPT
        Obsługuje rotację plików (gdy serwer stworzy nowy .RPT)
        """
        file_info = self.get_latest_rpt_file()
        if not file_info:
            return ""

        remote_path, filename = file_info

        try:
            current_size = self.ftp.path.getsize(remote_path)

            # Jeśli zmienił się plik (rotacja logów)
            if filename != self.current_file:
                print(f"[FTP] Wykryto nowy plik logów: {filename}")
                self.current_file = filename
                self.last_size = 0  # zaczynamy od początku nowego pliku

            # Jeśli plik urósł – pobieramy nowe dane
            if current_size > self.last_size:
                with self.ftp.open(remote_path, "rb") as f:
                    f.seek(self.last_size)
                    new_bytes = f.read()
                    self.last_size = current_size
                    return new_bytes.decode("utf-8", errors="replace")
            else:
                return ""  # nic nowego

        except Exception as e:
            print(f"[FTP] Błąd odczytu pliku {filename}: {e}")
            self.ftp = None
            return ""
