# ftp_watcher.py – TYLKO ADM, bez RPT
from ftplib import FTP
import time
import json
import os
import threading
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

LAST_POSITIONS_FILE = 'last_positions.json'

# Stała nazwa pliku ADM – zmień jeśli potrzeba
ADM_FILENAME = "DayZServer_x64_2026-02-02_18-00-33.ADM"   # ← aktualna nazwa Twojego ADM

FORCE_TAIL_READ = True
TAIL_BYTES = 131072  # 128 KB

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_adm_pos = 0
        self.last_mtime_adm = 0
        self._load_last_positions()
        print(f"[FTP WATCHER] Inicjalizacja – czytam TYLKO plik: {ADM_FILENAME}")
        self.running = False

    def _load_last_positions(self):
        if os.path.exists(LAST_POSITIONS_FILE):
            try:
                with open(LAST_POSITIONS_FILE, 'r') as f:
                    data = json.load(f)
                    self.last_adm_pos = int(data.get('last_adm_pos', 0))
                    self.last_mtime_adm = int(data.get('last_mtime_adm', 0))
                    print(f"[FTP WATCHER] Załadowano pozycje ADM: @{self.last_adm_pos:,} mtime={self.last_mtime_adm}")
            except Exception as e:
                print(f"[FTP WATCHER] Błąd ładowania pozycji: {e} – start od zera")
        else:
            print("[FTP WATCHER] Brak pliku pozycji – start od zera")

    def _save_last_positions(self):
        data = {
            'last_adm_pos': self.last_adm_pos,
            'last_mtime_adm': self.last_mtime_adm
        }
        try:
            with open(LAST_POSITIONS_FILE, 'w') as f:
                json.dump(data, f)
            print(f"[FTP WATCHER] Zapisano pozycje ADM: @{self.last_adm_pos:,}")
        except Exception as e:
            print(f"[FTP WATCHER] Błąd zapisu pozycji: {e}")

    def _connect(self):
        for attempt in range(1, 4):
            try:
                if self.ftp:
                    try:
                        self.ftp.quit()
                    except:
                        pass
                self.ftp = FTP()
                self.ftp.connect(FTP_HOST, FTP_PORT, timeout=30)
                self.ftp.login(FTP_USER, FTP_PASS)
                self.ftp.cwd(FTP_LOG_DIR)
                print(f"[FTP WATCHER] Połączono i cwd OK → {FTP_LOG_DIR}")
                return True
            except Exception as e:
                print(f"[FTP CONNECT] Próba {attempt}/3 nieudana: {e}")
                time.sleep(5)
        print("[FTP WATCHER] Nie udało się połączyć po 3 próbach")
        return False

    def _get_mtime(self, filename):
        try:
            resp = self.ftp.sendcmd(f'MDTM {filename}')
            if resp.startswith('213 '):
                ts = time.strptime(resp[4:], '%Y%m%d%H%M%S')
                return time.mktime(ts)
        except:
            pass
        return 0

    def _get_adm_content(self):
        if not self._connect():
            return ""

        filename = ADM_FILENAME

        try:
            size = self.ftp.size(filename)
            print(f"[FTP WATCHER] {filename} → {size:,} bajtów")

            current_pos = self.last_adm_pos
            current_mtime = self.last_mtime_adm
            new_mtime = self._get_mtime(filename)

            force_read = False
            start_pos = current_pos

            if FORCE_TAIL_READ and current_pos >= size and new_mtime == current_mtime:
                print(f"[FTP WATCHER] Force tail read ADM (ostatnie {TAIL_BYTES:,} bajtów)")
                force_read = True
                start_pos = max(0, size - TAIL_BYTES)
            elif current_pos >= size:
                print(f"[FTP WATCHER] Brak nowych danych w {filename} (pozycja {current_pos:,} >= {size:,})")
                return ""

            data = []
            def callback(block):
                data.append(block)

            self.ftp.retrbinary(f"RETR {filename}", callback, rest=start_pos)

            content_bytes = b''.join(data)
            content = content_bytes.decode('utf-8', errors='replace')

            if not force_read:
                new_pos = start_pos + len(content_bytes)
                self.last_adm_pos = new_pos
            else:
                self.last_mtime_adm = new_mtime

            print(f"[FTP WATCHER] Pobrano {len(content.splitlines())} linii z ADM (od {start_pos:,})")
            if content:
                preview = content.replace('\n', ' | ')[:300] + '...' if len(content) > 300 else content.replace('\n', ' | ')
                print(f"[FTP WATCHER PREVIEW ADM] {preview}")

            return content
        except Exception as e:
            print(f"[FTP ADM ERROR] {e}")
            return ""

    def get_new_content(self):
        content_adm = self._get_adm_content()
        if content_adm:
            self._save_last_positions()
            return content_adm
        return ""

    def run(self):
        if self.running:
            print("[FTP WATCHER] Watcher już uruchomiony")
            return

        self.running = True
        print("[FTP WATCHER] Uruchamiam pętlę sprawdzania co 30 sekund (tylko ADM)")

        def loop():
            while self.running:
                try:
                    content = self.get_new_content()
                    if content:
                        print(f"[FTP WATCHER] Znaleziono nowe dane ADM – {len(content.splitlines())} linii")
                except Exception as e:
                    print(f"[FTP WATCHER LOOP ERROR] {e}")
                time.sleep(30)

        threading.Thread(target=loop, daemon=True).start()
