# ftp_watcher.py – OSTATECZNA WERSJA Z STATE.JSON (nigdy więcej starych logów)

from ftplib import FTP
import os
import json
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

STATE_FILE = "state.json"

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.tracked_files = self.load_state()
        print(f"[FTP] Wczytano stan dla {len(self.tracked_files)} plików logów")

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    print(f"[FTP] Odtworzono pozycję z {len(data)} plików")
                    return data
            except Exception as e:
                print(f"[FTP] Błąd odczytu state.json: {e}")
        return {}

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.tracked_files, f)
            print(f"[FTP] Zaktualizowano state.json ({len(self.tracked_files)} plików)")
        except Exception as e:
            print(f"[FTP] Nie udało się zapisać state.json: {e}")

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
            print("[FTP] Połączono z FTP")
            return True
        except Exception as e:
            print(f"[FTP] Błąd połączenia: {e}")
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
                size = self.ftp.size(filename)
                last_size = self.tracked_files.get(filename, 0)

                if size <= last_size:
                    continue

                delta = size - last_size
                print(f"[FTP] +{delta} bajtów → {filename}")

                data = bytearray()
                self.ftp.retrbinary(f'RETR {filename}', data.extend, rest=last_size)
                text = data.decode("utf-8", errors="replace")
                new_content += text

                self.tracked_files[filename] = size
                updated = True

            except Exception as e:
                print(f"[FTP] Błąd {filename}: {e}")

        if updated:
            self.save_state()

        return new_content
