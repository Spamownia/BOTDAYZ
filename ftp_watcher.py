# ftp_watcher.py – WERSJA Z TRWAŁYM STANEM (state.json)

from ftplib import FTP
import os
import json
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

STATE_FILE = "state.json"  # plik na dysku Rendera

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.tracked_files = self.load_state()
        print(f"[FTP] Inicjalizacja watcher'a – wczytano stan dla {len(self.tracked_files)} plików")

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except:
                print("[FTP] Błąd odczytu state.json – start od zera")
        return {}

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.tracked_files, f)
            print(f"[FTP] Zapisano stan: {len(self.tracked_files)} plików")
        except Exception as e:
            print(f"[FTP] Błąd zapisu state.json: {e}")

    def connect(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                self.ftp = None

        print(f"[FTP] Łączenie z {FTP_HOST}:{FTP_PORT}...")
        try:
            self.ftp = FTP()
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT, timeout=20)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            print("[FTP] ✅ Połączono")
            return True
        except Exception as e:
            print(f"[FTP] ❌ Błąd połączenia: {e}")
            self.ftp = None
            return False

    def get_log_files(self):
        if not self.connect():
            return []
        try:
            files = []
            self.ftp.retrlines('LIST', files.append)
            log_files = []
            for line in files:
                parts = line.split()
                if len(parts) >= 9:
                    filename = ' '.join(parts[8:])
                    if filename.startswith("DayZServer_x64_") and filename.endswith((".RPT", ".ADM")):
                        log_files.append(filename)
            return sorted(log_files)
        except Exception as e:
            print(f"[FTP] Błąd LIST: {e}")
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
                size = self.ftp.size(filename)
                last_size = self.tracked_files.get(filename, 0)

                if size <= last_size:
                    continue

                delta = size - last_size
                print(f"[FTP] Nowe dane w {filename}: +{delta} bajtów")

                data = bytearray()
                def append_data(block):
                    data.extend(block)
                self.ftp.retrbinary(f'RETR {filename}', append_data, rest=last_size)

                text = data.decode("utf-8", errors="replace")
                new_content += text
                self.tracked_files[filename] = size
                updated = True

            except Exception as e:
                print(f"[FTP] Błąd przy {filename}: {e}")
                continue

        if updated:
            self.save_state()

        if new_content:
            lines_count = len([l for l in new_content.splitlines() if l.strip()])
            print(f"[FTP] Pobrano {lines_count} nowych linii")
        return new_content
