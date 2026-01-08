from ftplib import FTP
import os
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.current_file = None
        self.last_size = 0
        print("[FTP] Inicjalizacja watcher'a (używamy ftplib)")

    def connect(self):
        print(f"[FTP] Próba połączenia z {FTP_HOST}:{FTP_PORT} jako {FTP_USER}")
        try:
            self.ftp = FTP('')
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT, timeout=10)
            self.ftp.login(FTP_USER, FTP_PASS)
            print("[FTP] ✅ Połączono pomyślnie przez ftplib!")
        except Exception as e:
            print(f"[FTP] ❌ Błąd połączenia: {str(e)}")
            self.ftp = None

    def get_latest_rpt_file(self):
        if not self.ftp:
            self.connect()
            if not self.ftp:
                return None, None

        try:
            print(f"[FTP] Listuję pliki w katalogu: {FTP_LOG_DIR}")
            self.ftp.cwd(FTP_LOG_DIR)
            files = self.ftp.nlst()
            rpt_files = [f for f in files if f.startswith("DayZServer_x64_") and f.endswith(".RPT")]
            print(f"[FTP] Znaleziono plików .RPT: {len(rpt_files)} → {rpt_files}")

            if not rpt_files:
                print("[FTP] ⚠️ Brak plików .RPT!")
                return None, None

            # Sortujemy po czasie modyfikacji (ftplib nie daje mtime bezpośrednio, więc bierzemy ostatni alfabetycznie – zwykle działa)
            latest = sorted(rpt_files)[-1]
            full_path = os.path.join(FTP_LOG_DIR, latest).replace("\\", "/")
            print(f"[FTP] Najnowszy plik (przybliżony): {latest}")
            return full_path, latest
        except Exception as e:
            print(f"[FTP] Błąd listowania lub cwd: {str(e)}")
            self.ftp = None
            return None, None

    def get_new_content(self):
        remote_path, filename = self.get_latest_rpt_file()
        if not remote_path:
            return ""

        try:
            size = self.ftp.size(filename)  # rozmiar tylko pliku w bieżącym katalogu
            print(f"[FTP] Rozmiar pliku {filename}: {size or 'nieznany'} bajtów (poprzednio: {self.last_size})")

            if filename != self.current_file:
                print(f"[FTP] 🔄 Nowy plik logów: {filename}")
                self.current_file = filename
                self.last_size = 0

            if size is None or size <= self.last_size:
                print("[FTP] Brak nowych danych lub rozmiar nieznany")
                return ""

            # Pobieramy tylko nową część
            data = []
            def callback(line):
                data.append(line)

            self.ftp.retrbinary(f'RETR {filename}', callback, rest=self.last_size)
            new_text = b''.join(data).decode("utf-8", errors="replace")
            lines_count = len([l for l in new_text.splitlines() if l.strip()])
            print(f"[FTP] Pobrano {len(data)} bajtów (~{lines_count} nowych linii)")
            self.last_size = size or self.last_size + len(data)
            return new_text

        except Exception as e:
            print(f"[FTP] Błąd odczytu pliku: {str(e)}")
            self.ftp = None
            return ""
