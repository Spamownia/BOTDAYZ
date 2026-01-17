from ftplib import FTP
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_file = None
        self.last_position = 0
        print("[FTP DEBUG] Inicjalizacja, ścieżka:", FTP_LOG_DIR)

    def connect_and_debug(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                print("[FTP DEBUG] Połączenie aktywne, katalog:", self.ftp.pwd())
                return True
            except:
                print("[FTP DEBUG] Stare połączenie padło")
                self.ftp = None

        try:
            print(f"[FTP DEBUG] Łączenie: {FTP_HOST}:{FTP_PORT} / {FTP_USER}")
            self.ftp = FTP(timeout=20)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            print("[FTP DEBUG] Login OK")
            initial_pwd = self.ftp.pwd()
            print(f"[FTP DEBUG] Domyślny katalog po login: {initial_pwd}")

            try:
                self.ftp.cwd(FTP_LOG_DIR)
                print(f"[FTP DEBUG] cwd({FTP_LOG_DIR}) OK → {self.ftp.pwd()}")
            except Exception as e:
                print(f"[FTP DEBUG] cwd({FTP_LOG_DIR}) błąd: {e}")
                print("[FTP DEBUG] Zostajemy w domyślnym:", initial_pwd)

            self.ftp.set_pasv(True)
            return True
        except Exception as e:
            print(f"[FTP DEBUG] Błąd połączenia: {e}")
            self.ftp = None
            return False

    def get_latest_log(self):
        if not self.connect_and_debug():
            return None

        try:
            # Używamy dir() zamiast nlst() – zwraca linie tekstowe jak w konsoli FTP
            files_lines = []
            self.ftp.dir(files_lines.append)
            print(f"[FTP DEBUG] dir() zwróciło {len(files_lines)} linii")

            rpt_adm_files = []
            for line in files_lines:
                parts = line.split()
                if len(parts) >= 9:
                    filename = ' '.join(parts[8:])
                    if filename.lower().endswith(('.rpt', '.adm')):
                        rpt_adm_files.append(filename)

            if not rpt_adm_files:
                print("[FTP DEBUG] Brak .RPT / .ADM w katalogu!")
                print("[FTP DEBUG] Przykładowe linie z dir():")
                print("\n".join(files_lines[:10]))
                return None

            latest = max(rpt_adm_files)
            print(f"[FTP DEBUG] Najnowszy plik: {latest}")
            return latest
        except Exception as e:
            print(f"[FTP DEBUG] Błąd w dir() / parsowaniu: {e}")
            return None

    def get_new_content(self):
        latest_file = self.get_latest_log()
        if not latest_file:
            return ""

        try:
            size = self.ftp.size(latest_file)
            print(f"[FTP DEBUG] {latest_file} → {size:,} bajtów")

            if latest_file != self.last_file:
                print("[FTP DEBUG] Nowy plik → reset na ostatnie 5 MB")
                self.last_file = latest_file
                self.last_position = max(0, size - 5_000_000)

            if self.last_position >= size:
                print("[FTP DEBUG] Zero nowych bajtów")
                return ""

            data = bytearray()
            self.ftp.retrbinary(f'RETR {latest_file}', data.extend, rest=self.last_position)

            text = data.decode('utf-8', errors='replace')

            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            self.last_position = size

            lines = len(text.splitlines())
            print(f"[FTP DEBUG] Pobrano {lines} linii")

            if text:
                preview = text[:300].replace('\n', ' | ')
                print(f"[FTP DEBUG PREVIEW] {preview}...")

            return text
        except Exception as e:
            print(f"[FTP DEBUG] Błąd pobierania: {e}")
            return ""
