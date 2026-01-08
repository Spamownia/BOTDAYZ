import ftputil
from config import FTP_HOST, FTP_USER, FTP_PASS, FTP_PORT, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.current_file = None
        self.last_size = 0

    def connect(self):
        try:
            self.ftp = ftputil.FTPHost(FTP_HOST, FTP_USER, FTP_PASS, port=FTP_PORT)
            print(f"[FTP] Połączono z {FTP_HOST}:{FTP_PORT}")
        except Exception as e:
            print(f"[FTP] Błąd połączenia: {str(e)}")
            self.ftp = None

    def get_latest_rpt_file(self):
        if not self.ftp:
            self.connect()
            if not self.ftp:
                return None, None

        try:
            files = self.ftp.listdir(FTP_LOG_DIR)
            rpt_files = [f for f in files if f.startswith("DayZServer_x64_") and f.endswith(".RPT")]
            if not rpt_files:
                print("[FTP] Brak plików .RPT w /config/")
                return None, None

            latest = max(rpt_files, key=lambda f: self.ftp.path.getmtime(FTP_LOG_DIR + f))
            print(f"[FTP] Najnowszy plik: {latest}")
            return FTP_LOG_DIR + latest, latest
        except Exception as e:
            print(f"[FTP] Błąd listowania: {str(e)}")
            self.ftp = None
            return None, None

    def get_new_content(self):
        remote_path, filename = self.get_latest_rpt_file()
        if not remote_path:
            return ""

        try:
            size = self.ftp.path.getsize(remote_path)
            print(f"[FTP] Plik {filename} rozmiar: {size} (ostatni: {self.last_size})")

            if filename != self.current_file:
                print(f"[FTP] Nowy plik: {filename}")
                self.current_file = filename
                self.last_size = 0

            if size <= self.last_size:
                print("[FTP] Nic nowego w pliku")
                return ""

            with self.ftp.open(remote_path, "rb") as f:
                f.seek(self.last_size)
                new_data = f.read()
                self.last_size = size
                print(f"[FTP] Pobrano {len(new_data)} nowych bajtów")
                return new_data.decode("utf-8", errors="replace")

        except Exception as e:
            print(f"[FTP] Błąd odczytu: {str(e)}")
            self.ftp = None
            return ""
