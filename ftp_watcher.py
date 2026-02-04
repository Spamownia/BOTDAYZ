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
        self.last_mtime_rpt = 0
        self.last_mtime_adm = 0
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
                    self.last_mtime_rpt = int(data.get('last_mtime_rpt', 0))
                    self.last_mtime_adm = int(data.get('last_mtime_adm', 0))
                    print(f"[FTP WATCHER] Załadowano: RPT={self.last_rpt} @ {self.last_rpt_pos:,} mtime={self.last_mtime_rpt} | ADM={self.last_adm} @ {self.last_adm_pos:,} mtime={self.last_mtime_adm}")
            except Exception as e:
                print(f"[FTP WATCHER] Błąd ładowania: {e} – start od zera")
        else:
            print("[FTP WATCHER] Brak pliku pozycji – start od zera")

    def _save_last_positions(self):
        data = {
            'last_rpt': self.last_rpt,
            'last_adm': self.last_adm,
            'last_rpt_pos': self.last_rpt_pos,
            'last_adm_pos': self.last_adm_pos,
            'last_mtime_rpt': self.last_mtime_rpt,
            'last_mtime_adm': self.last_mtime_adm
        }
        try:
            with open(LAST_POSITIONS_FILE, 'w') as f:
                json.dump(data, f)
            print(f"[FTP WATCHER] Zapisano pozycje: RPT@{self.last_rpt_pos:,} | ADM@{self.last_adm_pos:,}")
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

    def get_latest_files(self):
        if not self._connect():
            return None, None
        try:
            files = self.ftp.nlst()
            rpt_files = [f for f in files if f.endswith('.RPT')]
            adm_files = [f for f in files if f.endswith('.ADM')]
            latest_rpt = max(rpt_files) if rpt_files else None
            latest_adm = max(adm_files) if adm_files else None
            print(f"[FTP WATCHER] Najnowszy RPT: {latest_rpt}")
            print(f"[FTP WATCHER] Najnowszy ADM: {latest_adm}")
            return latest_rpt, latest_adm
        except Exception as e:
            print(f"[FTP LATEST ERROR] {e}")
            return None, None

    def _get_mtime(self, filename):
        try:
            resp = self.ftp.sendcmd(f'MDTM {filename}')
            if resp.startswith('213 '):
                timestamp_str = resp[4:]
                return time.mktime(time.strptime(timestamp_str, '%Y%m%d%H%M%S'))
        except:
            pass
        return 0

    def _get_content(self, filename, log_type):
        if not self._connect():
            return ""

        try:
            size = self.ftp.size(filename)
            print(f"[FTP WATCHER] {filename} → {size:,} bajtów")

            if log_type == 'rpt':
                current_file = self.last_rpt
                pos_var = 'last_rpt_pos'
                mtime_var = 'last_mtime_rpt'
            else:
                current_file = self.last_adm
                pos_var = 'last_adm_pos'
                mtime_var = 'last_mtime_adm'

            current_pos = getattr(self, pos_var)
            current_mtime = getattr(self, mtime_var)

            if current_file != filename:
                print(f"[FTP WATCHER] Nowy plik {log_type.upper()} → reset pozycji na 0")
                setattr(self, pos_var, 0)
                current_pos = 0
                setattr(self, f'last_{log_type}', filename)
                new_mtime = self._get_mtime(filename)
                setattr(self, mtime_var, new_mtime)
            else:
                new_mtime = self._get_mtime(filename)
                if new_mtime > current_mtime:
                    print(f"[FTP WATCHER] {log_type.upper()} zaktualizowany przez mtime → odczyt od ostatniej pozycji")
                    setattr(self, mtime_var, new_mtime)
                elif size <= current_pos:
                    print(f"[FTP WATCHER] Brak nowych danych w {filename} (pozycja {current_pos:,} >= {size:,})")
                    return ""

            if current_pos >= size:
                return ""

            data = []
            def callback(block):
                data.append(block)

            self.ftp.retrbinary(f"RETR {filename}", callback, rest=current_pos)

            content_bytes = b''.join(data)
            content = content_bytes.decode('utf-8', errors='replace')

            new_pos = current_pos + len(content_bytes)
            setattr(self, pos_var, new_pos)

            print(f"[FTP WATCHER] Pobrano {len(content.splitlines())} nowych linii z {filename} (od {current_pos:,} do {new_pos:,})")
            if content:
                preview = content.replace('\n', ' | ')[:300] + '...' if len(content) > 300 else content.replace('\n', ' | ')
                print(f"[FTP WATCHER PREVIEW {log_type.upper()}] {preview}")

            return content
        except Exception as e:
            print(f"[FTP CONTENT ERROR {log_type.upper()}] {e}")
            return ""

    def get_new_content(self):
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

        if contents:
            self._save_last_positions()

        return "\n".join(contents)

    def run(self):
        if self.running:
            print("[FTP WATCHER] Watcher już uruchomiony")
            return

        self.running = True
        print("[FTP WATCHER] Uruchamiam pętlę sprawdzania co 30 sekund")

        def loop():
            while self.running:
                try:
                    content = self.get_new_content()
                    if content:
                        print(f"[FTP WATCHER] Znaleziono nowe dane – {len(content.splitlines())} linii")
                except Exception as e:
                    print(f"[FTP WATCHER LOOP ERROR] {e}")
                time.sleep(30)

        threading.Thread(target=loop, daemon=True).start()
