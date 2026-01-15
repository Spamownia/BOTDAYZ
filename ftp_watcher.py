# ftp_watcher.py – z zapamiętywaniem pozycji w każdym pliku (state.json)

from ftplib import FTP
import os
import json
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

STATE_FILE = "state.json"

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.tracked_files = self.load_state()
        print(f"[FTP] Wczytano stan: {len(self.tracked_files)} plików")

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    print(f"[FTP] Odtworzono stan z {len(data)} plików")
                    return data
            except Exception as e:
                print(f"[FTP] Błąd odczytu state.json: {e}")
        return {}

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.tracked_files, f)
            print("[FTP] Zapisano stan")
        except Exception as e:
            print(f"[FTP] Błąd zapisu state.json: {e}")

    def connect(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return
            except:
                self.ftp = None

        try:
            print("[FTP] Łączenie...")
            self.ftp = FTP(timeout=20)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            print("[FTP] Połączono")
        except Exception as e:
            print(f"[FTP] Błąd połączenia: {e}")
            self.ftp = None
            time.sleep(2)

    def get_log_files(self):
        self.connect()
        if not self.ftp:
            return []

        try:
            files = self.ftp.nlst()
            log_files = [f for f in files if f.startswith("DayZServer_x64_") and f.endswith((".RPT", ".ADM"))]
            return sorted(log_files)
        except Exception as e:
            print(f"[FTP] Błąd listy plików: {e}")
            self.ftp = None
            return []

    def get_new_content(self):
        log_files = self.get_log_files()
        if not log_files:
            return ""

        new_content = ""
        updated = False

        for filename in log_files:
            try:
                self.connect()
                if not self.ftp:
                    continue

                size = self.ftp.size(filename)
                last_pos = self.tracked_files.get(filename, 0)

                if size <= last_pos:
                    continue

                delta = size - last_pos
                print(f"[FTP] +{delta} bajtów → {filename}")

                # Jeśli plik jest bardzo duży – pobieramy tylko ostatnie 100 KB
                rest = last_pos
                if delta > 100_000:
                    print(f"[FTP] Duży plik – pobieram ostatnie 100 KB")
                    rest = max(last_pos, size - 100_000)

                data = bytearray()
                def append_data(block):
                    data.extend(block)

                self.ftp.retrbinary(f'RETR {filename}', append_data, rest=rest)

                text = data.decode("utf-8", errors="replace")
                new_content += text

                # Zapisujemy nową pozycję
                self.tracked_files[filename] = size
                updated = True

            except Exception as e:
                print(f"[FTP] Błąd przy {filename}: {e}")
                self.ftp = None
                continue

        if updated:
            self.save_state()

        return new_content
