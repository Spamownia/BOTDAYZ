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
                    print(f"[FTP WATCHER] Załadowano: RPT={self.last_rpt} @ {self.last_rpt_pos:,} | ADM={self.last_adm} @ {self.last_adm_pos:,}")
            except Exception as e:
                print(f"[FTP] Błąd ładowania pozycji: {e} → start od zera")
        else:
            print("[FTP] Brak pliku pozycji → start od zera")

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
            print(f"[FTP] Zapisano pozycje: RPT@{self.last_rpt_pos:,} | ADM@{self.last_adm_pos:,}")
        except Exception as e:
            print(f"[FTP] Błąd zapisu pozycji: {e}")

    def connect(self, max_retries=3):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                print("[FTP] Stare połączenie padło – reconnect")
                self.ftp = None

        for attempt in range(max_retries):
            try:
                print(f"[FTP] Próba {attempt+1}/{max_retries}")
                self.ftp = FTP(timeout=30)
                self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
                self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
                self.ftp.cwd(FTP_LOG_DIR)
                print(f"[FTP] Połączono → {self.ftp.pwd()}")
                self.ftp.set_pasv(True)
                return True
            except Exception as e:
                print(f"[FTP] Błąd połączenia (próba {attempt+1}): {e}")
                self.ftp = None
                time.sleep(3 * (attempt + 1))

        print("[FTP] Nie udało się połączyć")
        return False

    def keep_alive(self):
        def alive_loop():
            while self.running:
                if self.ftp:
                    try:
                        self.ftp.voidcmd("NOOP")
                    except:
                        print("[KEEP-ALIVE] NOOP fail – połączenie zerwane")
                        self.ftp = None
                time.sleep(10)

        threading.Thread(target=alive_loop, daemon=True).start()

    def get_latest_files(self):
        if not self.connect():
            return None, None

        try:
            files_lines = []
            self.ftp.dir(files_lines.append)
            rpt = [ln.split()[-1] for ln in files_lines if ln.lower().endswith('.rpt')]
            adm = [ln.split()[-1] for ln in files_lines if ln.lower().endswith('.adm')]
            latest_rpt = max(rpt) if rpt else None
            latest_adm = max(adm) if adm else None
            print(f"[FTP] Najnowszy RPT: {latest_rpt} | ADM: {latest_adm}")
            return latest_rpt, latest_adm
        except Exception as e:
            print(f"[FTP] Błąd listowania: {e}")
            return None, None

    def _get_content(self, filename, file_type):
        if not self.connect():
            return ""

        try:
            size = self.ftp.size(filename)
            print(f"[FTP] {filename} → {size:,} bajtów")

            last_pos = self.last_rpt_pos if file_type == 'rpt' else self.last_adm_pos
            last_file = self.last_rpt if file_type == 'rpt' else self.last_adm

            if filename != last_file or last_file is None:
                print(f"[FTP] Nowy plik {file_type.upper()} → reset pozycji (ostatnie 5 MB)")
                last_pos = max(0, size - 5_000_000)

            if last_pos >= size:
                print(f"[FTP] Brak nowych danych ({last_pos:,} >= {size:,})")
                return ""

            data = bytearray()
            self.ftp.retrbinary(f'RETR {filename}', data.extend, rest=last_pos)
            text = data.decode('utf-8', errors='replace')

            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            lines_count = len(text.splitlines())
            print(f"[FTP] Pobrano {lines_count} linii z {filename} (od {last_pos:,})")

            if text:
                preview = text[:200].replace('\n', ' | ')
                print(f"[PREVIEW {file_type.upper()}] {preview}...")

                # Aktualizacja pozycji TYLKO po pobraniu treści!
                if file_type == 'rpt':
                    self.last_rpt = filename
                    self.last_rpt_pos = size
                else:
                    self.last_adm = filename
                    self.last_adm_pos = size

                self._save_last_positions()  # zapis po każdej udanej operacji

                return text

            return ""

        except Exception as e:
            print(f"[FTP] Błąd pobierania {filename}: {e}")
            return ""

    def get_new_content(self):
        latest_rpt, latest_adm = self.get_latest_files()
        if not latest_rpt and not latest_adm:
            return ""

        contents = []
        if latest_rpt:
            c = self._get_content(latest_rpt, 'rpt')
            if c: contents.append(c)
        if latest_adm:
            c = self._get_content(latest_adm, 'adm')
            if c: contents.append(c)

        return "\n".join(contents)

    def run(self):
        if self.running:
            return
        self.running = True
        self.keep_alive()
        print("[FTP] Uruchamiam pętlę co 30 sekund")

        def loop():
            while self.running:
                try:
                    content = self.get_new_content()
                    if content:
                        print(f"[FTP] Nowe dane – {len(content.splitlines())} linii")
                except Exception as e:
                    print(f"[FTP LOOP ERROR] {e}")
                time.sleep(30)

        threading.Thread(target=loop, daemon=True).start()
