from ftplib import FTP
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_file = None
        self.last_position = 0
        print("[FTP] Inicjalizacja – katalog docelowy:", FTP_LOG_DIR)

    def connect(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                self.ftp = None

        try:
            print(f"[FTP] Próba połączenia: {FTP_HOST}:{FTP_PORT} / user: {FTP_USER}")
            self.ftp = FTP(timeout=20)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            print("[FTP] Login OK")
            current_dir = self.ftp.pwd()
            print(f"[FTP] Aktualny katalog po login: {current_dir}")
            try:
                self.ftp.cwd(FTP_LOG_DIR)
                print(f"[FTP] Przeszedłem do: {self.ftp.pwd()}")
            except Exception as cwd_err:
                print(f"[FTP] Błąd cwd do '{FTP_LOG_DIR}': {cwd_err} – zostaje w {current_dir}")
            self.ftp.set_pasv(True)
            return True
        except Exception as e:
            print(f"[FTP] Połączenie / login / cwd ZEPSUTE: {e}")
            self.ftp = None
            return False

    def get_latest_log(self):
        if not self.connect():
            print("[FTP] Brak połączenia – nie szukam plików")
            return None

        try:
            files = self.ftp.nlst()
            print(f"[FTP] Lista plików w bieżącym katalogu ({len(files)} elementów):")
            print("   ", files[:15])  # pierwsze 15 do debugu
            log_files = [f for f in files if f.lower().endswith(('.rpt', '.adm'))]
            if not log_files:
                print("[FTP] NIE ZNALEZIONO ŻADNEGO .RPT ani .ADM!")
                return None
            latest = max(log_files)
            print(f"[FTP] Wybrano najnowszy: {latest}")
            return latest
        except Exception as e:
            print(f"[FTP] Błąd nlst / size: {e}")
            return None

    def get_new_content(self):
        latest = self.get_latest_log()
        if not latest:
            return ""

        try:
            size = self.ftp.size(latest)
            print(f"[FTP] {latest} ma {size:,} bajtów")

            if latest != self.last_file:
                print(f"[FTP] Nowy plik! Reset pozycji na ostatnie 5MB")
                self.last_file = latest
                self.last_position = max(0, size - 5_000_000)

            if self.last_position >= size:
                print("[FTP] Zero nowych bajtów")
                return ""

            data = bytearray()
            self.ftp.retrbinary(f'RETR {latest}', data.extend, rest=self.last_position)
            text = data.decode('utf-8', errors='replace')

            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            self.last_position = size

            print(f"[FTP] Pobrano {len(text.splitlines())} linii")
            if text:
                print("[FTP PREVIEW] Pierwsze 250 znaków:", text[:250].replace('\n', ' | '))
            return text
        except Exception as e:
            print(f"[FTP] Retrbinary błąd: {e}")
            return ""
