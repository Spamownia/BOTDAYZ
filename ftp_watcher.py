from ftplib import FTP
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_file = None
        self.last_position = 0
        print("[FTP] Watcher wystartował – czyta .RPT i .ADM, śledzi pozycję")

    def connect(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                self.ftp = None

        try:
            print("[FTP] Łączenie...")
            self.ftp = FTP(timeout=25)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            self.ftp.set_pasv(True)  # często pomaga z połączeniami
            print("[FTP] Połączono")
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
            log_files = [f for f in files if f.startswith("DayZServer_x64_") and (f.endswith(".RPT") or f.endswith(".ADM"))]
            if not log_files:
                print("[FTP] Brak plików .RPT lub .ADM")
                return None
            latest_log = max(log_files)  # najnowszy alfabetycznie (data w nazwie)
            print(f"[FTP] Najnowszy log: {latest_log}")
            return latest_log
        except Exception as e:
            print(f"[FTP] Błąd listy plików: {e}")
            return None

    def get_new_content(self):
        latest_file = self.get_latest_log()
        if not latest_file:
            return ""

        try:
            if not self.connect():
                return ""

            size = self.ftp.size(latest_file)
            print(f"[FTP] Rozmiar {latest_file}: {size:,} bajtów")

            if latest_file != self.last_file:
                print(f"[FTP] Nowy plik: {latest_file} – start od końca (4 MB)")
                self.last_file = latest_file
                self.last_position = max(0, size - 4_000_000)

            if self.last_position >= size:
                print("[FTP] Brak nowych danych")
                return ""

            print(f"[FTP] Pobieram {size - self.last_position:,} bajtów od {self.last_position:,}")

            data = bytearray()
            self.ftp.retrbinary(f'RETR {latest_file}', data.extend, rest=self.last_position)

            text = data.decode('utf-8', errors='replace')

            # Usuwamy niepełną linię na początku
            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            self.last_position = size

            lines_count = len(text.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii")

            # DEBUG: pokaż początek
            if text:
                preview = text[:300].replace('\n', ' ◄NL► ')
                print(f"[FTP DEBUG] Początek danych: {preview}...")

            return text

        except Exception as e:
            print(f"[FTP] Błąd pobierania: {e}")
            self.ftp = None
            return ""
