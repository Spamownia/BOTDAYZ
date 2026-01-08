import ftputil
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.current_file = None
        self.last_size = 0
        print("[FTP] Inicjalizacja watcher'a")

    def connect(self):
        # Poprawne połączenie z niestandardowym portem: host:port
        host_with_port = f"{FTP_HOST}:{FTP_PORT}"
        print(f"[FTP] Próba połączenia z {host_with_port} jako {FTP_USER}")
        try:
            self.ftp = ftputil.FTPHost(host_with_port, FTP_USER, FTP_PASS)
            print("[FTP] ✅ Połączono pomyślnie!")
        except Exception as e:
            print(f"[FTP] ❌ Błąd połączenia: {str(e)}")
            self.ftp = None

    def get_latest_rpt_file(self):
        if not self.ftp:
            self.connect()
            if not self.ftp:
                return None, None

        try:
            print(f"[FTP] Listuję pliki w katalogu: {FTP_LOG_DIR}")
            files = self.ftp.listdir(FTP_LOG_DIR)
            rpt_files = [f for f in files if f.startswith("DayZServer_x64_") and f.endswith(".RPT")]
            print(f"[FTP] Znaleziono plików .RPT: {len(rpt_files)} → {rpt_files}")

            if not rpt_files:
                print("[FTP] ⚠️ Brak plików .RPT w katalogu!")
                return None, None

            latest = max(rpt_files, key=lambda f: self.ftp.path.getmtime(FTP_LOG_DIR + f))
            full_path = FTP_LOG_DIR + latest if not FTP_LOG_DIR.endswith('/') else FTP_LOG_DIR + latest
            print(f"[FTP] Najnowszy plik: {latest}")
            return full_path, latest
        except Exception as e:
            print(f"[FTP] Błąd listowania katalogu: {str(e)}")
            self.ftp = None
            return None, None

    def get_new_content(self):
        remote_path, filename = self.get_latest_rpt_file()
        if not remote_path:
            return ""

        try:
            size = self.ftp.path.getsize(remote_path)
            print(f"[FTP] Rozmiar pliku {filename}: {size} bajtów (poprzednio: {self.last_size})")

            if filename != self.current_file:
                print(f"[FTP] 🔄 Wykryto nowy plik logów: {filename}")
                self.current_file = filename
                self.last_size = 0

            if size <= self.last_size:
                print("[FTP] Brak nowych danych")
                return ""

            with self.ftp.open(remote_path, "rb") as f:
                f.seek(self.last_size)
                new_data = f.read()
                new_text = new_data.decode("utf-8", errors="replace")
                lines_count = len([l for l in new_text.splitlines() if l.strip()])
                print(f"[FTP] Pobrano {len(new_data)} bajtów (~{lines_count} nowych linii)")
                self.last_size = size
                return new_text

        except Exception as e:
            print(f"[FTP] Błąd odczytu pliku: {str(e)}")
            self.ftp = None
            return ""
