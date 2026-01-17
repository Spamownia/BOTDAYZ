from ftplib import FTP
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_file = None
        self.last_position = 0
        print("[FTP DEBUG] Inicjalizacja, docelowa ścieżka:", FTP_LOG_DIR)

    def connect_and_debug(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                print("[FTP DEBUG] Połączenie nadal aktywne, katalog:", self.ftp.pwd())
                return True
            except:
                print("[FTP DEBUG] Stare połączenie padło – restartuję")
                self.ftp = None

        try:
            print(f"[FTP DEBUG] Łączenie z {FTP_HOST}:{FTP_PORT} jako {FTP_USER}")
            self.ftp = FTP(timeout=20)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            print("[FTP DEBUG] Login OK")
            initial_pwd = self.ftp.pwd()
            print(f"[FTP DEBUG] Katalog po zalogowaniu (domyślny): {initial_pwd}")

            # Próbujemy przejść do docelowej ścieżki
            try:
                self.ftp.cwd(FTP_LOG_DIR)
                print(f"[FTP DEBUG] cwd({FTP_LOG_DIR}) OK → aktualny katalog: {self.ftp.pwd()}")
            except Exception as cwd_err:
                print(f"[FTP DEBUG] cwd({FTP_LOG_DIR}) ZAWODZI: {cwd_err}")
                print("[FTP DEBUG] Zostajemy w domyślnym katalogu:", initial_pwd)

            self.ftp.set_pasv(True)
            return True
        except Exception as e:
            print(f"[FTP DEBUG] Całkowity błąd połączenia/login: {e}")
            self.ftp = None
            return False

    def get_latest_log(self):
        if not self.connect_and_debug():
            print("[FTP DEBUG] Nie udało się połączyć – pomijam wyszukiwanie plików")
            return None

        try:
            files = self.ftp.nlst()
            print(f"[FTP DEBUG] nlst zwróciło {len(files)} elementów")
            if files:
                print("[FTP DEBUG] Pierwsze 12 elementów (foldery/pliki):")
                print("  ", "\n  ".join(files[:12]))

            log_files = [f for f in files if f.lower().endswith(('.rpt', '.adm', '.log'))]
            if not log_files:
                print("[FTP DEBUG] Brak plików .RPT / .ADM / .log w bieżącym katalogu!")
                return None

            latest = max(log_files)
            print(f"[FTP DEBUG] Wybrano najnowszy plik logów: {latest}")
            return latest
        except Exception as e:
            print(f"[FTP DEBUG] Błąd podczas nlst lub filtrowania: {e}")
            return None

    def get_new_content(self):
        latest_file = self.get_latest_log()
        if not latest_file:
            print("[FTP DEBUG] Nie znaleziono pliku logów – zwracam pusty string")
            return ""

        try:
            size = self.ftp.size(latest_file)
            print(f"[FTP DEBUG] Plik {latest_file} → rozmiar {size:,} bajtów")

            if latest_file != self.last_file:
                print(f"[FTP DEBUG] Nowy plik! Resetuję pozycję na ostatnie 5 MB")
                self.last_file = latest_file
                self.last_position = max(0, size - 5_000_000)

            if self.last_position >= size:
                print("[FTP DEBUG] Brak nowych danych (pozycja >= rozmiar)")
                return ""

            to_read = size - self.last_position
            print(f"[FTP DEBUG] Pobieram {to_read:,} bajtów od pozycji {self.last_position:,}")

            data = bytearray()
            self.ftp.retrbinary(f'RETR {latest_file}', data.extend, rest=self.last_position)

            text = data.decode('utf-8', errors='replace')

            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            self.last_position = size

            lines = len(text.splitlines())
            print(f"[FTP DEBUG] Pobrano i zdekodowano {lines} linii")

            if text:
                preview = text[:300].replace('\n', ' ◄NL► ')
                print(f"[FTP DEBUG PREVIEW] Pierwsze 300 znaków: {preview}...")
            else:
                print("[FTP DEBUG] Pobrano 0 bajtów użytecznego tekstu")

            return text

        except Exception as e:
            print(f"[FTP DEBUG] Błąd podczas pobierania pliku: {e}")
            return ""
