from ftplib import FTP
import os
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.tracked_files = {}  # {filename: last_size}
        print("[FTP] Inicjalizacja watcher'a – śledzenie .RPT i .ADM osobno")

    def connect(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                self.ftp = None

        print(f"[FTP] Próba połączenia z {FTP_HOST}:{FTP_PORT} jako {FTP_USER}")
        try:
            self.ftp = FTP()
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT, timeout=15)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            print("[FTP] ✅ Połączono pomyślnie!")
            return True
        except Exception as e:
            print(f"[FTP] ❌ Błąd połączenia: {str(e)}")
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
            print(f"[FTP] Błąd LIST: {str(e)}")
            self.ftp = None
            return []

    def get_new_content(self):
        log_files = self.get_log_files()
        if not log_files:
            return ""

        new_content = ""
        for filename in log_files:
            try:
                size = self.ftp.size(filename)
                last_size = self.tracked_files.get(filename, 0)

                if size <= last_size:
                    continue

                print(f"[FTP] Nowe dane w {filename}: +{size - last_size} bajtów")

                data = bytearray()
                def append_data(block):
                    data.extend(block)
                self.ftp.retrbinary(f'RETR {filename}', append_data, rest=last_size)

                text = data.decode("utf-8", errors="replace")
                new_content += text
                self.tracked_files[filename] = size

            except Exception as e:
                print(f"[FTP] Błąd przy {filename}: {str(e)}")
                continue

        if new_content:
            print(f"[FTP] Łącznie pobrano ~{len(new_content.splitlines())} nowych linii")
        return new_content
