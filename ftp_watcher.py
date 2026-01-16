# ftp_watcher.py – pamięta ostatnią pozycję w każdym pliku + ignoruje stare pliki

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
        print(f"[FTP] Wczytano stan dla {len(self.tracked_files)} plików")

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
                return True
            except:
                self.ftp = None

        try:
            print("[FTP] Łączenie...")
            self.ftp = FTP(timeout=30)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            print("[FTP] Połączono")
            return True
        except Exception as e:
            print(f"[FTP] Błąd połączenia: {e}")
            self.ftp = None
            time.sleep(2)
            return False

    def get_log_files(self):
        if not self.connect():
            return []

        try:
            files = []
            self.ftp.dir(files.append)
            log_files = []
            for line in files:
                parts = line.split()
                if len(parts) >= 9:
                    filename = ' '.join(parts[8:])
                    if filename.startswith("DayZServer_x64_") and filename.endswith((".RPT", ".ADM")):
                        log_files.append(filename)
            print(f"[FTP] Znaleziono {len(log_files)} plików logów")
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
                if not self.connect():
                    continue

                size = self.ftp.size(filename)
                last_pos = self.tracked_files.get(filename, 0)

                if size <= last_pos:
                    continue

                delta = size - last_pos
                print(f"[FTP] +{delta} bajtów → {filename}")

                rest = last_pos
                if delta > 100_000:
                    print(f"[FTP] Duży przyrost – pobieram ostatnie 100 KB")
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

        if new_content:
            lines_count = len([l for l in new_content.splitlines() if l.strip()])
            print(f"[FTP] Pobrano {lines_count} nowych linii")

        return new_content
