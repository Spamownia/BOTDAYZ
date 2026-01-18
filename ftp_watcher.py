from ftplib import FTP
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_adm = None
        self.last_adm_pos = 0
        print("[FTP DEBUG] Inicjalizacja – czyta TYLKO .ADM")

    def connect_and_debug(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                self.ftp = None

        try:
            print(f"[FTP DEBUG] Łączenie: {FTP_HOST}:{FTP_PORT} / {FTP_USER}")
            self.ftp = FTP(timeout=20)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            print(f"[FTP DEBUG] cwd OK → {self.ftp.pwd()}")
            self.ftp.set_pasv(True)
            return True
        except Exception as e:
            print(f"[FTP DEBUG] Błąd połączenia: {e}")
            self.ftp = None
            return False

    def get_latest_adm(self):
        if not self.connect_and_debug():
            return None

        try:
            files_lines = []
            self.ftp.dir(files_lines.append)

            adm_files = []
            for line in files_lines:
                parts = line.split()
                if len(parts) >= 9:
                    filename = ' '.join(parts[8:])
                    if filename.lower().endswith('.adm'):
                        adm_files.append(filename)

            if not adm_files:
                print("[FTP DEBUG] Brak plików .ADM!")
                print("[FTP DEBUG] Przykładowe pliki:", "\n".join(files_lines[:10]))
                return None

            latest = max(adm_files)
            print(f"[FTP DEBUG] Najnowszy .ADM: {latest}")
            return latest
        except Exception as e:
            print(f"[FTP DEBUG] Błąd listowania: {e}")
            return None

    def get_new_content(self):
        latest_adm = self.get_latest_adm()
        if not latest_adm:
            return ""

        try:
            size = self.ftp.size(latest_adm)
            print(f"[FTP DEBUG] {latest_adm} → {size:,} bajtów")

            if latest_adm != self.last_adm:
                print("[FTP DEBUG] Nowy plik .ADM → start od końca")
                self.last_adm = latest_adm
                self.last_adm_pos = max(0, size - 5_000_000)

            if self.last_adm_pos >= size:
                return ""

            data = bytearray()
            self.ftp.retrbinary(f'RETR {latest_adm}', data.extend, rest=self.last_adm_pos)

            text = data.decode('utf-8', errors='replace')
            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            self.last_adm_pos = size

            lines = len(text.splitlines())
            print(f"[FTP DEBUG] Pobrano {lines} linii z .ADM")

            if text:
                preview = text[:300].replace('\n', ' | ')
                print(f"[FTP DEBUG PREVIEW ADM] {preview}...")

            return text
        except Exception as e:
            print(f"[FTP DEBUG] Błąd pobierania .ADM: {e}")
            return ""
