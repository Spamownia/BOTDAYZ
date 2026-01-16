from ftplib import FTP
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_file = None
        self.last_position = 0
        print("[FTP] Watcher wystartował – śledzi pozycję w pliku, unika duplikatów")

    def connect(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                self.ftp = None

        try:
            print("[FTP] Łączenie z serwerem...")
            self.ftp = FTP(timeout=25)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            print("[FTP] Połączono pomyślnie")
            return True
        except Exception as e:
            print(f"[FTP] Błąd połączenia: {e}")
            self.ftp = None
            time.sleep(3)
            return False

    def get_latest_rpt(self):
        if not self.connect():
            return None

        try:
            files = self.ftp.nlst()
            rpt_files = [f for f in files if f.startswith("DayZServer_x64_") and f.endswith(".RPT")]
            if not rpt_files:
                print("[FTP] Brak plików .RPT w katalogu")
                return None
            latest_rpt = max(rpt_files)  # alfabetycznie – w DayZ zwykle działa
            print(f"[FTP] Najnowszy plik: {latest_rpt}")
            return latest_rpt
        except Exception as e:
            print(f"[FTP] Błąd listy plików: {e}")
            self.ftp = None
            return None

    def get_new_content(self):
        latest_file = self.get_latest_rpt()
        if not latest_file:
            return ""

        try:
            if not self.connect():
                return ""

            size = self.ftp.size(latest_file)
            print(f"[FTP] Rozmiar {latest_file}: {size:,} bajtów")

            if latest_file != self.last_file:
                print(f"[FTP] Nowy plik logów! Reset → {latest_file}")
                self.last_file = latest_file
                self.last_position = max(0, size - 4_000_000)  # ~4 MB na start

            if self.last_position >= size:
                print("[FTP] Brak nowych danych")
                return ""

            print(f"[FTP] Pobieram od {self.last_position:,} bajtu → {size - self.last_position:,} nowych")

            data = bytearray()
            self.ftp.retrbinary(f'RETR {latest_file}', data.extend, rest=self.last_position)

            text = data.decode('utf-8', errors='replace')

            # Usuwamy niepełną linię na początku
            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            self.last_position = size

            lines_count = len(text.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii")

            return text

        except Exception as e:
            print(f"[FTP] Błąd pobierania: {e}")
            self.ftp = None
            return ""
