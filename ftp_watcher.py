# ftp_watcher.py – tylko najnowszy RPT + ostatnie 300 KB (bez stanu, bez spamu po restarcie)

from ftplib import FTP
import os
import time
from datetime import datetime
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        print("[FTP] Watcher zainicjowany – czyta tylko najnowszy RPT")

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

    def get_latest_rpt(self):
        if not self.connect():
            return None

        try:
            files = []
            self.ftp.dir(files.append)
            rpt_files = []
            for line in files:
                parts = line.split()
                if len(parts) >= 9:
                    filename = ' '.join(parts[8:])
                    if filename.startswith("DayZServer_x64_") and filename.endswith(".RPT"):
                        rpt_files.append(filename)

            if not rpt_files:
                print("[FTP] Nie znaleziono żadnego pliku .RPT")
                return None

            # Najnowszy RPT (największa nazwa = najnowszy)
            latest_rpt = max(rpt_files)
            print(f"[FTP] Najnowszy log: {latest_rpt}")
            return latest_rpt

        except Exception as e:
            print(f"[FTP] Błąd listy plików: {e}")
            self.ftp = None
            return None

    def get_new_content(self):
        latest_file = self.get_latest_rpt()
        if not latest_file:
            return ""

        try:
            if not self.connect():
                return ""

            size = self.ftp.size(latest_file)
            print(f"[FTP] Aktualny rozmiar {latest_file}: {size} bajtów")

            # Zawsze pobieramy ostatnie 300 KB (wystarczająco na nowe linie)
            rest = max(0, size - 300_000)
            print(f"[FTP] Pobieram od bajtu {rest} (ostatnie 300 KB)")

            data = bytearray()
            def append_data(block):
                data.extend(block)

            self.ftp.retrbinary(f'RETR {latest_file}', append_data, rest=rest)

            text = data.decode("utf-8", errors="replace")
            lines = text.splitlines()

            # Odrzucamy ewentualne niepełne linie na początku
            if lines:
                text = '\n'.join(lines[1:]) if len(lines) > 1 else lines[0]

            lines_count = len(text.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii z {latest_file}")

            return text

        except Exception as e:
            print(f"[FTP] Błąd przy pobieraniu {latest_file}: {e}")
            self.ftp = None
            return ""
