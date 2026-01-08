from ftplib import FTP
import os
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.current_file = None
        self.last_size = 0
        print("[FTP] Inicjalizacja watcher'a – ftplib z LIST zamiast NLST")

    def connect(self):
        print(f"[FTP] Próba połączenia z {FTP_HOST}:{FTP_PORT} jako {FTP_USER}")
        try:
            self.ftp = FTP()
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT, timeout=15)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            print("[FTP] ✅ Połączono pomyślnie!")
        except Exception as e:
            print(f"[FTP] ❌ Błąd połączenia: {str(e)}")
            self.ftp = None

    def get_latest_rpt_file(self):
        if not self.ftp:
            self.connect()
            if not self.ftp:
                return None, None

        try:
            print(f"[FTP] Przechodzę do katalogu: {FTP_LOG_DIR}")
            self.ftp.cwd(FTP_LOG_DIR)

            # Używamy LIST zamiast NLST – bardziej kompatybilne
            files = []
            self.ftp.retrlines('LIST', files.append)
            print(f"[FTP] Surowa lista LIST: {files}")

            # Parsujemy linie LIST (format: prawa, liczba, user, group, rozmiar, data, nazwa)
            rpt_files = []
            for line in files:
                parts = line.split()
                if len(parts) >= 9:
                    filename = ' '.join(parts[8:])
                    if filename.startswith("DayZServer_x64_") and filename.endswith(".RPT"):
                        rpt_files.append(filename)

            print(f"[FTP] Znaleziono plików .RPT: {len(rpt_files)} → {rpt_files}")

            if not rpt_files:
                print("[FTP] ⚠️ Brak plików .RPT (lub serwer nie zwraca poprawnej listy)")
                return None, None

            # Sortujemy alfabetycznie (najnowszy zwykle ma najwyższą datę w nazwie)
            latest = sorted(rpt_files)[-1]
            print(f"[FTP] Wybrano najnowszy plik: {latest}")
            return latest, latest

        except Exception as e:
            print(f"[FTP] Błąd podczas cwd lub LIST: {str(e)}")
            self.ftp = None
            return None, None

    def get_new_content(self):
        filename, _ = self.get_latest_rpt_file()
        if not filename:
            return ""

        try:
            size = self.ftp.size(filename)
            print(f"[FTP] Rozmiar pliku {filename}: {size or 'nieznany'} bajtów (poprzednio: {self.last_size})")

            if filename != self.current_file:
                print(f"[FTP] 🔄 Nowy plik logów: {filename}")
                self.current_file = filename
                self.last_size = 0

            if size is None or size <= self.last_size:
                print("[FTP] Brak nowych danych")
                return ""

            data = bytearray()
            def append_data(block):
                data.extend(block)

            self.ftp.retrbinary(f'RETR {filename}', append_data, rest=self.last_size)
            new_text = data.decode("utf-8", errors="replace")
            lines_count = len([l for l in new_text.splitlines() if l.strip()])
            print(f"[FTP] Pobrano {len(data)} bajtów (~{lines_count} nowych linii)")
            self.last_size = size or (self.last_size + len(data))
            return new_text

        except Exception as e:
            print(f"[FTP] Błąd odczytu pliku {filename}: {str(e)}")
            self.ftp = None
            return ""
