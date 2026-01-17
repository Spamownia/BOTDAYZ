from ftplib import FTP
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_file = None
        self.last_position = 0
        print("[FTP] Watcher wystartował – czyta .RPT / .ADM")

    def connect(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                self.ftp = None

        try:
            print(f"[FTP] Łączenie z {FTP_HOST}:{FTP_PORT} jako {FTP_USER} …")
            self.ftp = FTP(timeout=25)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            self.ftp.set_pasv(True)
            print(f"[FTP] Połączono – katalog: {self.ftp.pwd()}")
            return True
        except Exception as e:
            print(f"[FTP] Błąd połączenia: {e}")
            self.ftp = None
            time.sleep(3)
            return False

    def get_latest_log(self):
        if not self.connect():
            return None

        try:
            files = self.ftp.nlst()
            print(f"[FTP] Znaleziono {len(files)} elementów w katalogu")
            log_files = [f for f in files if f.lower().endswith(('.rpt', '.adm'))]
            if not log_files:
                print("[FTP] Brak plików .RPT / .ADM !")
                print("[FTP DEBUG] Przykładowe pliki:", files[:10])
                return None
            latest = max(log_files)
            print(f"[FTP] Wybrany najnowszy plik: {latest}")
            return latest
        except Exception as e:
            print(f"[FTP] Błąd listowania: {e}")
            return None

    def get_new_content(self):
        latest_file = self.get_latest_log()
        if not latest_file:
            return ""

        try:
            if not self.connect():
                return ""

            size = self.ftp.size(latest_file)
            print(f"[FTP] Plik {latest_file} → {size:,} bajtów")

            if latest_file != self.last_file:
                print(f"[FTP] Nowy plik wykryty → reset pozycji")
                self.last_file = latest_file
                self.last_position = max(0, size - 5_000_000)  # 5 MB na start

            if self.last_position >= size:
                print("[FTP] Brak nowych bajtów")
                return ""

            to_read = size - self.last_position
            print(f"[FTP] Pobieram {to_read:,} bajtów od {self.last_position:,}")

            data = bytearray()
            self.ftp.retrbinary(f'RETR {latest_file}', data.extend, rest=self.last_position)

            text = data.decode('utf-8', errors='replace')

            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            self.last_position = size

            lines = len(text.splitlines())
            print(f"[FTP] Pobrano {lines} linii")

            if text:
                preview = text[:280].replace('\n', ' ◄NL► ')
                print(f"[FTP PREVIEW] {preview}...")

            return text

        except Exception as e:
            print(f"[FTP] Błąd pobierania: {e}")
            self.ftp = None
            return ""
