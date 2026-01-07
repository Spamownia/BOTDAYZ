import ftputil
from datetime import datetime, timedelta
from config import FTP_HOST, FTP_USER, FTP_PASS, FTP_PORT, FTP_LOG_DIR


class DayZLogWatcher:
    """
    Klasa odpowiedzialna za połączenie z FTP i pobieranie tylko nowych linii
    z najnowszego pliku DayZServer_x64_*.RPT w katalogu /config/
    """

    def __init__(self):
        self.ftp = None
        self.current_file = None    # nazwa aktualnie czytanego pliku .RPT
        self.last_size = 0          # ile bajtów już przeczytano z bieżącego pliku

    def connect(self):
        """Nawiązuje połączenie FTP z niestandardowym portem"""
        try:
            self.ftp = ftputil.FTPHost(
                host=FTP_HOST,
                user=FTP_USER,
                passwd=FTP_PASS,
                port=FTP_PORT
            )
            print(f"[FTP] Połączono pomyślnie z {FTP_HOST}:{FTP_PORT}")
        except Exception as e:
            print(f"[FTP] Błąd połączenia z {FTP_HOST}:{FTP_PORT} – {e}")
            self.ftp = None

    def get_latest_rpt_file(self):
        """
        Zwraca pełną ścieżkę i nazwę najnowszego pliku .RPT
        w katalogu FTP_LOG_DIR (np. /config/DayZServer_x64_20260107.RPT)
        """
        if not self.ftp:
            self.connect()
            if not self.ftp:
                return None, None

        try:
            all_files = self.ftp.listdir(FTP_LOG_DIR)

            # Filtrujemy tylko pliki pasujące do wzorca DayZ
            rpt_files = [
                f for f in all_files
                if f.startswith("DayZServer_x64_") and f.endswith(".RPT")
            ]

            if not rpt_files:
                print("[FTP] Nie znaleziono plików DayZServer_x64_*.RPT w /config/")
                return None, None

            # Wybieramy najnowszy plik według czasu modyfikacji
            latest_file = max(
                rpt_files,
                key=lambda f: self.ftp.path.getmtime(FTP_LOG_DIR + f)
            )

            full_path = FTP_LOG_DIR + latest_file
            return full_path, latest_file

        except Exception as e:
            print(f"[FTP] Błąd podczas listowania katalogu: {e}")
            self.ftp = None
            return None, None

    def get_new_content(self):
        """
        Pobiera tylko nowe linie z najnowszego pliku .RPT.
        Automatycznie przechodzi na nowy plik po rotacji logów serwera.
        """
        remote_path, filename = self.get_latest_rpt_file()
        if not remote_path:
            return ""

        try:
            current_size = self.ftp.path.getsize(remote_path)

            # Wykrycie rotacji pliku (nowy plik po restarcie serwera)
            if filename != self.current_file:
                print(f"[FTP] Wykryto nowy plik logów: {filename} (poprzedni: {self.current_file})")
                self.current_file = filename
                self.last_size = 0  # zaczynamy od początku nowego pliku

            # Jeśli plik urósł – pobieramy tylko nową część
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
