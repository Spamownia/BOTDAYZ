# ftp_watcher.py – ignoruje pliki starsze niż start bota + bezpieczny reconnect

from ftplib import FTP
import os
import time
from datetime import datetime
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.start_time = time.time()  # timestamp startu bota (sekundy od epoki)
        print(f"[FTP] Start bota o {datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')}")

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
                        # Pobierz datę modyfikacji pliku
                        try:
                            mod_time_str = ' '.join(parts[5:8])  # np. Jan 15 12:34
                            mod_time = time.mktime(time.strptime(mod_time_str, "%b %d %H:%M"))
                            # Pomijamy pliki starsze niż start bota
                            if mod_time < self.start_time:
                                continue
                        except:
                            continue  # jeśli data nieczytelna – pomijamy

                        log_files.append(filename)
            print(f"[FTP] Znaleziono {len(log_files)} nowych plików logów (po starcie bota)")
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
        for filename in log_files:
            try:
                if not self.connect():
                    continue

                size = self.ftp.size(filename)

                data = bytearray()
                def append_data(block):
                    data.extend(block)

                self.ftp.retrbinary(f'RETR {filename}', append_data)

                text = data.decode("utf-8", errors="replace")
                new_content += text

                print(f"[FTP] Pobrano cały nowy plik: {filename} ({size} bajtów)")

            except Exception as e:
                print(f"[FTP] Błąd przy {filename}: {e}")
                self.ftp = None
                continue

        if new_content:
            lines_count = len([l for l in new_content.splitlines() if l.strip()])
            print(f"[FTP] Pobrano {lines_count} nowych linii")

        return new_content
