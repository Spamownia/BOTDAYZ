# ftp_watcher.py
from ftplib import FTP
import time
import json
import os
import threading
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

LAST_POSITIONS_FILE = 'last_positions.json'

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_rpt = None
        self.last_adm = None
        self.last_rpt_pos = 0
        self.last_adm_pos = 0
        self._load_last_positions()
        print("[FTP WATCHER] Inicjalizacja – pamięć pozycji z JSON")
        self.running = False

    def _load_last_positions(self):
        if os.path.exists(LAST_POSITIONS_FILE):
            try:
                with open(LAST_POSITIONS_FILE, 'r') as f:
                    data = json.load(f)
                    self.last_rpt = data.get('last_rpt')
                    self.last_adm = data.get('last_adm')
                    self.last_rpt_pos = int(data.get('last_rpt_pos', 0))
                    self.last_adm_pos = int(data.get('last_adm_pos', 0))
                    print(f"[FTP WATCHER] Załadowano pozycje: RPT={self.last_rpt} @ {self.last_rpt_pos:,} bajtów | ADM={self.last_adm} @ {self.last_adm_pos:,} bajtów")
            except Exception as e:
                print(f"[FTP WATCHER] Błąd ładowania pozycji: {e} – start od zera")
        else:
            print("[FTP WATCHER] Brak pliku pozycji – start od zera")

    def _save_last_positions(self):
        data = {
            'last_rpt': self.last_rpt,
            'last_adm': self.last_adm,
            'last_rpt_pos': self.last_rpt_pos,
            'last_adm_pos': self.last_adm_pos
        }
        try:
            with open(LAST_POSITIONS_FILE, 'w') as f:
                json.dump(data, f)
            print(f"[FTP WATCHER] Zapisano aktualne pozycje: RPT@{self.last_rpt_pos:,} | ADM@{self.last_adm_pos:,}")
        except Exception as e:
            print(f"[FTP WATCHER] Błąd zapisu pozycji: {e}")

    def connect(self, max_retries=3):
        """Stabilne połączenie z retry i timeoutami"""
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                print("[FTP WATCHER] Połączenie nadal aktywne")
                return True
            except:
                print("[FTP WATCHER] Stare połączenie padło – reconnect")
                self.ftp = None

        for attempt in range(max_retries):
            try:
                print(f"[FTP WATCHER] Próba połączenia {attempt+1}/{max_retries}: {FTP_HOST}:{FTP_PORT} / {FTP_USER}")
                self.ftp = FTP(timeout=30)
                self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
                self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
                self.ftp.cwd(FTP_LOG_DIR)
                print(f"[FTP WATCHER] Połączono i cwd OK → {self.ftp.pwd()}")
                self.ftp.set_pasv(True)
                return True
            except Exception as e:
                print(f"[FTP WATCHER] Błąd połączenia (próba {attempt+1}): {e}")
                self.ftp = None
                time.sleep(5 * (attempt + 1))  # backoff: 5s, 10s, 15s...
        
        print(f"[FTP WATCHER] Nie udało się połączyć po {max_retries} próbach")
        return False

    def get_latest_files(self):
        """Pobiera najnowsze pliki .RPT i .ADM"""
        if not self.connect():
            return None, None
        try:
            files_lines = []
            self.ftp.dir(files_lines.append)
            rpt_files = [line.split()[-1] for line in files_lines if line.lower().endswith('.rpt')]
            adm_files = [line.split()[-1] for line in files_lines if line.lower().endswith('.adm')]
            latest_rpt = max(rpt_files, key=str, default=None) if rpt_files else None
            latest_adm = max(adm_files, key=str, default=None) if adm_files else None
            print(f"[FTP WATCHER] Najnowszy .RPT: {latest_rpt}")
            print(f"[FTP WATCHER] Najnowszy .ADM: {latest_adm}")
            return latest_rpt, latest_adm
        except Exception as e:
            print(f"[FTP WATCHER] Błąd listowania plików: {e}")
            return None, None

    def _get_content(self, filename, file_type):
        """Pobiera nowe dane z pliku z resetem pozycji przy rotacji"""
        if not self.connect():
            return ""
        try:
            size = self.ftp.size(filename)
            print(f"[FTP WATCHER] {filename} → {size:,} bajtów")
            last_pos = self.last_rpt_pos if file_type == 'rpt' else self.last_adm_pos
            last_file = self.last_rpt if file_type == 'rpt' else self.last_adm
            # Reset przy nowym pliku (rotacja logów)
            if filename != last_file or last_file is None:
                print(f"[FTP WATCHER] Nowy plik {file_type.upper()} → reset pozycji na koniec - 5MB")
                last_pos = max(0, size - 5_000_000) # ostatnie 5 MB starego pliku
            if last_pos >= size:
                print(f"[FTP WATCHER] Brak nowych danych w {filename} (pozycja {last_pos:,} >= {size:,})")
                return ""
            data = bytearray()
            self.ftp.retrbinary(f'RETR {filename}', data.extend, rest=last_pos)
            text = data.decode('utf-8', errors='replace')
            # Pomijamy niepełną linię na początku
            if text and '\n' in text:
                text = text[text.index('\n') + 1:]
            lines_count = len(text.splitlines())
            print(f"[FTP WATCHER] Pobrano {lines_count} nowych linii z {filename} (od {last_pos:,} do {size:,} bajtów)")
            if text:
                preview = text[:200].replace('\n', ' | ')
                print(f"[FTP WATCHER PREVIEW {file_type.upper()}] {preview}...")
            # Aktualizacja pozycji
            if file_type == 'rpt':
                self.last_rpt = filename
                self.last_rpt_pos = size
            else:
                self.last_adm = filename
                self.last_adm_pos = size
            return text
        except Exception as e:
            print(f"[FTP WATCHER] Błąd pobierania {filename}: {e}")
            return ""

    def get_new_content(self):
        """Główna metoda – pobiera nowe dane z najnowszych plików"""
        latest_rpt, latest_adm = self.get_latest_files()
        if not latest_rpt and not latest_adm:
            return ""
        contents = []
        if latest_rpt:
            content_rpt = self._get_content(latest_rpt, 'rpt')
            if content_rpt:
                contents.append(content_rpt)
        if latest_adm:
            content_adm = self._get_content(latest_adm, 'adm')
            if content_adm:
                contents.append(content_adm)
        # Zapisujemy pozycje TYLKO jeśli coś faktycznie przeczytaliśmy
        if contents:
            self._save_last_positions()
        return "\n".join(contents)

    def _keep_alive(self):
        """Wątek wysyłający NOOP co 30 sekund, żeby połączenie nie padło"""
        while self.running:
            if self.ftp is not None:
                try:
                    self.ftp.voidcmd("NOOP")
                    print("[FTP KEEP-ALIVE] NOOP wysłany – połączenie utrzymane")
                except Exception as e:
                    print(f"[FTP KEEP-ALIVE] Błąd NOOP: {e} → połączenie prawdopodobnie już padło")
                    self.ftp = None  # wymusimy reconnect przy następnej operacji
            time.sleep(30)

    def run(self):
        """Uruchamia watcher w pętli co 60 sekund + keep-alive co 30 sekund"""
        if self.running:
            print("[FTP WATCHER] Watcher już uruchomiony")
            return
        
        self.running = True
        print("[FTP WATCHER] Start – sprawdzanie co 60s + keep-alive NOOP co 30s")
        
        # Uruchamiamy wątek keep-alive
        threading.Thread(target=self._keep_alive, daemon=True).start()
        
        def loop():
            while self.running:
                try:
                    content = self.get_new_content()
                    if content:
                        print(f"[FTP WATCHER] Znaleziono nowe dane – {len(content.splitlines())} linii")
                        # Tutaj możesz przekazać content do parsera (np. przez kolejkę lub globalną zmienną)
                except Exception as e:
                    print(f"[FTP WATCHER LOOP ERROR] {e}")
                
                time.sleep(60)
        
        threading.Thread(target=loop, daemon=True).start()
