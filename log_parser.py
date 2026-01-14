# ftp_watcher.py – TYLKO NAJNOWSZE LOGI, BEZ SPAMU Z HISTORII

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
                    return json.load(f)
            except:
                pass
        return {}

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.tracked_files, f)
        except:
            pass

    def connect(self, retries=3):
        for attempt in range(retries):
            if self.ftp:
                try:
                    self.ftp.voidcmd("NOOP")
                    return True
                except:
                    pass

            try:
                print(f"[FTP] Łączenie (próba {attempt+1})...")
                self.ftp = FTP(timeout=20)
                self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
                self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
                self.ftp.cwd(FTP_LOG_DIR)
                print("[FTP] Połączono")
                return True
            except Exception as e:
                print(f"[FTP] Błąd połączenia: {e}")
                time.sleep(2)

        print("[FTP] Nie udało się połączyć po 3 próbach")
        self.ftp = None
        return False

    def get_latest_log_files(self):
        if not self.connect():
            return None, None

        try:
            files = []
            self.ftp.retrlines('LIST', files.append)
            rpt_files = []
            adm_files = []
            for line in files:
                parts = line.split()
                if len(parts) >= 9:
                    filename = ' '.join(parts[8:])
                    if filename.startswith("DayZServer_x64_"):
                        if filename.endswith(".RPT"):
                            rpt_files.append(filename)
                        elif filename.endswith(".ADM"):
                            adm_files.append(filename)
            latest_rpt = sorted(rpt_files)[-1] if rpt_files else None
            latest_adm = sorted(adm_files)[-1] if adm_files else None
            return latest_rpt, latest_adm
        except Exception as e:
            print(f"[FTP] Błąd listy plików: {e}")
            self.ftp = None
            return None, None

    def get_new_content(self):
        latest_rpt, latest_adm = self.get_latest_log_files()
        files_to_process = [f for f in [latest_rpt, latest_adm] if f]

        if not files_to_process:
            print("[FTP] Brak najnowszych logów")
            return ""

        new_content = ""
        updated = False

        for filename in files_to_process:
            try:
                if not self.connect():
                    continue

                size = self.ftp.size(filename)
                last_size = self.tracked_files.get(filename, 0)

                print(f"[FTP DEBUG] {filename} | last: {last_size} | current: {size} | delta: {size - last_size}")

                if size <= last_size:
                    continue

                delta = size - last_size
                print(f"[FTP] +{delta} bajtów → {filename}")

                rest = last_size
                if delta > 100_000:
                    rest = size - 100_000
                    print(f"[FTP] Duży delta – pobieram ostatnie 100 KB")

                data = bytearray()
                def append_data(block):
                    data.extend(block)

                self.ftp.retrbinary(f'RETR {filename}', append_data, rest=rest)

                text = data.decode("utf-8", errors="replace")
                new_content += text

                self.tracked_files[filename] = size
                updated = True

                print(f"[FTP] Pobrano {len(text)} znaków z {filename}")

            except Exception as e:
                print(f"[FTP] Błąd przy {filename}: {e}")
                self.ftp = None
                continue

        if updated:
            self.save_state()

        if new_content:
            lines_count = len([l for l in new_content.splitlines() if l.strip()])
            print(f"[FTP] Przetworzono {lines_count} nowych linii")

        return new_content
