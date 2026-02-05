# ftp_watcher.py – TYLKO ADM, bez RPT
from ftplib import FTP
import time
import json
import os
import threading
from datetime import datetime
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

LAST_POSITIONS_FILE = 'last_positions.json'

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_adm_filename = None
        self.last_adm_pos = 0
        self.last_adm_mtime = 0
        self.last_adm_size = 0
        self.last_rpt_filename = None
        self.last_rpt_pos = 0
        self.last_rpt_mtime = 0
        self.last_rpt_size = 0
        self._load_last_positions()
        print("[FTP WATCHER] Start – monitoruję najnowszy plik ADM i RPT w katalogu")
        self.running = False

    def _load_last_positions(self):
        if os.path.exists(LAST_POSITIONS_FILE):
            try:
                with open(LAST_POSITIONS_FILE, 'r') as f:
                    data = json.load(f)
                self.last_adm_filename = data.get('last_adm_filename')
                self.last_adm_pos = int(data.get('last_adm_pos', 0))
                self.last_adm_mtime = int(data.get('last_adm_mtime', 0))
                self.last_adm_size = int(data.get('last_adm_size', 0))
                self.last_rpt_filename = data.get('last_rpt_filename')
                self.last_rpt_pos = int(data.get('last_rpt_pos', 0))
                self.last_rpt_mtime = int(data.get('last_rpt_mtime', 0))
                self.last_rpt_size = int(data.get('last_rpt_size', 0))
                if self.last_adm_filename:
                    print(f"[FTP] Wczytano stan ostatniego ADM: {self.last_adm_filename} pos={self.last_adm_pos:,} size={self.last_adm_size:,} mtime={self.last_adm_mtime}")
                if self.last_rpt_filename:
                    print(f"[FTP] Wczytano stan ostatniego RPT: {self.last_rpt_filename} pos={self.last_rpt_pos:,} size={self.last_rpt_size:,} mtime={self.last_rpt_mtime}")
                else:
                    print("[FTP] Brak poprzedniego pliku ADM/RPT – start od zera")
            except Exception as e:
                print(f"[FTP] Błąd wczytywania last_positions: {e} → start od zera")
        else:
            print("[FTP] Brak pliku last_positions → start od zera")

    def _save_last_positions(self):
        data = {
            'last_adm_filename': self.last_adm_filename,
            'last_adm_pos': self.last_adm_pos,
            'last_adm_mtime': self.last_adm_mtime,
            'last_adm_size': self.last_adm_size,
            'last_rpt_filename': self.last_rpt_filename,
            'last_rpt_pos': self.last_rpt_pos,
            'last_rpt_mtime': self.last_rpt_mtime,
            'last_rpt_size': self.last_rpt_size,
        }
        try:
            with open(LAST_POSITIONS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            # print(f"[FTP] Zapisano stan: {self.last_adm_filename} pos={self.last_adm_pos:,}")
        except Exception as e:
            print(f"[FTP] Błąd zapisu pozycji: {e}")

    def _connect(self):
        for attempt in range(1, 4):
            try:
                if self.ftp:
                    try:
                        self.ftp.quit()
                    except:
                        pass
                self.ftp = FTP()
                self.ftp.connect(FTP_HOST, FTP_PORT, timeout=25)
                self.ftp.login(FTP_USER, FTP_PASS)
                self.ftp.cwd(FTP_LOG_DIR)
                print(f"[FTP] Połączono → {FTP_LOG_DIR}")
                return True
            except Exception as e:
                print(f"[FTP] Połączenie nieudane (próba {attempt}/3): {e}")
                time.sleep(4)
        print("[FTP] Nie udało się połączyć po 3 próbach")
        return False

    def _get_mtime(self, filename):
        try:
            resp = self.ftp.sendcmd(f'MDTM {filename}')
            if resp.startswith('213 '):
                ts_str = resp[4:].strip()
                ts = datetime.strptime(ts_str, '%Y%m%d%H%M%S')
                return int(ts.timestamp())
        except Exception as e:
            print(f"[FTP MTIME ERROR] Dla {filename}: {e}")
        return 0

    def _find_latest_adm(self):
        """Znajduje najnowszy plik .ADM w katalogu na podstawie nazwy (data w nazwie)"""
        try:
            # Zmienione: zamiast nlst() używamy dir() – zwraca listę stringów z LIST
            lines = []
            self.ftp.dir(lines.append)  # dir() wywołuje LIST i zbiera linie do listy
            files = []
            for line in lines:
                # Parsujemy tylko nazwę pliku z końca linii (ostatnie słowo)
                parts = line.split()
                if len(parts) > 0:
                    filename = parts[-1].strip()
                    if filename.startswith('DayZServer_x64_') and filename.endswith('.ADM'):
                        files.append(filename)
            if not files:
                print("[FTP] Brak plików ADM w katalogu (po LIST)!")
                return None
            # Parsujemy daty z nazw plików: DayZServer_x64_YYYY-MM-DD_HH-MM-SS.ADM
            def parse_date(filename):
                try:
                    date_str = filename[15:-4]  # YYYY-MM-DD_HH-MM-SS
                    return datetime.strptime(date_str, '%Y-%m-%d_%H-%M-%S')
                except:
                    return datetime.min
            latest = max(files, key=parse_date)
            print(f"[FTP] Najnowszy ADM (po LIST): {latest}")
            return latest
        except Exception as e:
            print(f"[FTP FIND ADM ERROR]: {e}")
            return None

    def _find_latest_rpt(self):
        """Znajduje najnowszy plik .RPT w katalogu na podstawie nazwy (data w nazwie)"""
        try:
            # Zmienione: zamiast nlst() używamy dir() – zwraca listę stringów z LIST
            lines = []
            self.ftp.dir(lines.append)  # dir() wywołuje LIST i zbiera linie do listy
            files = []
            for line in lines:
                # Parsujemy tylko nazwę pliku z końca linii (ostatnie słowo)
                parts = line.split()
                if len(parts) > 0:
                    filename = parts[-1].strip()
                    if filename.startswith('DayZServer_x64_') and filename.endswith('.RPT'):
                        files.append(filename)
            if not files:
                print("[FTP] Brak plików RPT w katalogu (po LIST)!")
                return None
            # Parsujemy daty z nazw plików: DayZServer_x64_YYYY-MM-DD_HH-MM-SS.RPT
            def parse_date(filename):
                try:
                    date_str = filename[15:-4]  # YYYY-MM-DD_HH-MM-SS
                    return datetime.strptime(date_str, '%Y-%m-%d_%H-%M-%S')
                except:
                    return datetime.min
            latest = max(files, key=parse_date)
            print(f"[FTP] Najnowszy RPT (po LIST): {latest}")
            return latest
        except Exception as e:
            print(f"[FTP FIND RPT ERROR]: {e}")
            return None

    def _get_adm_content(self):
        if not self._connect():
            return ""
        filename = self._find_latest_adm()
        if not filename:
            return ""
        try:
            current_size = self.ftp.size(filename)
            current_mtime = self._get_mtime(filename)
            # Jeśli to nowy plik (inna nazwa lub nowszy mtime / mniejszy rozmiar)
            if filename != self.last_adm_filename or current_size < self.last_adm_size or current_mtime > self.last_adm_mtime:
                print(f"[FTP] Nowy / zrotowany ADM! {self.last_adm_filename} → {filename} (size: {self.last_adm_size:,} → {current_size:,} | mtime: {self.last_adm_mtime} → {current_mtime})")
                self.last_adm_filename = filename
                self.last_adm_pos = 0
                self.last_adm_size = current_size
                self.last_adm_mtime = current_mtime
            if self.last_adm_pos >= current_size:
                # print(f"[FTP] Brak nowych danych w {filename} ({self.last_adm_pos:,} / {current_size:,})")
                return ""
            start_pos = self.last_adm_pos
            data = []
            def callback(block):
                data.append(block)
            print(f"[FTP] Pobieram {filename} od {start_pos:,} bajtów (plik ma {current_size:,})")
            self.ftp.retrbinary(f"RETR {filename}", callback, rest=start_pos)
            content_bytes = b''.join(data)
            if not content_bytes:
                return ""
            content = content_bytes.decode('utf-8', errors='replace')
            # Aktualizacja stanu – ZAWSZE po udanym odczycie
            self.last_adm_pos = start_pos + len(content_bytes)
            self.last_adm_size = current_size
            self.last_adm_mtime = current_mtime
            lines_count = len(content.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii z {filename} (od {start_pos:,})")
            # Podgląd pierwszych ~300 znaków (opcjonalnie)
            if content:
                preview = content.replace('\n', ' │ ')[:280].rstrip() + '…'
                print(f"[PREVIEW ADM] {preview}")
            return content
        except Exception as e:
            print(f"[FTP ERROR ADM {filename}]: {type(e).__name__}: {e}")
            return ""

    def _get_rpt_content(self):
        if not self._connect():
            return ""
        filename = self._find_latest_rpt()
        if not filename:
            return ""
        try:
            current_size = self.ftp.size(filename)
            current_mtime = self._get_mtime(filename)
            # Jeśli to nowy plik (inna nazwa lub nowszy mtime / mniejszy rozmiar)
            if filename != self.last_rpt_filename or current_size < self.last_rpt_size or current_mtime > self.last_rpt_mtime:
                print(f"[FTP] Nowy / zrotowany RPT! {self.last_rpt_filename} → {filename} (size: {self.last_rpt_size:,} → {current_size:,} | mtime: {self.last_rpt_mtime} → {current_mtime})")
                self.last_rpt_filename = filename
                self.last_rpt_pos = 0
                self.last_rpt_size = current_size
                self.last_rpt_mtime = current_mtime
            if self.last_rpt_pos >= current_size:
                # print(f"[FTP] Brak nowych danych w {filename} ({self.last_rpt_pos:,} / {current_size:,})")
                return ""
            start_pos = self.last_rpt_pos
            data = []
            def callback(block):
                data.append(block)
            print(f"[FTP] Pobieram {filename} od {start_pos:,} bajtów (plik ma {current_size:,})")
            self.ftp.retrbinary(f"RETR {filename}", callback, rest=start_pos)
            content_bytes = b''.join(data)
            if not content_bytes:
                return ""
            content = content_bytes.decode('utf-8', errors='replace')
            # Aktualizacja stanu – ZAWSZE po udanym odczycie
            self.last_rpt_pos = start_pos + len(content_bytes)
            self.last_rpt_size = current_size
            self.last_rpt_mtime = current_mtime
            lines_count = len(content.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii z {filename} (od {start_pos:,})")
            # Podgląd pierwszych ~300 znaków (opcjonalnie)
            if content:
                preview = content.replace('\n', ' │ ')[:280].rstrip() + '…'
                print(f"[PREVIEW RPT] {preview}")
            return content
        except Exception as e:
            print(f"[FTP ERROR RPT {filename}]: {type(e).__name__}: {e}")
            return ""

    def get_new_content(self):
        adm_content = self._get_adm_content()
        rpt_content = self._get_rpt_content()
        all_content = ""
        if adm_content:
            all_content += adm_content
            print(f"[FTP] Nowe dane ADM – {len(adm_content.splitlines())} linii")
        if rpt_content:
            all_content += rpt_content
            print(f"[FTP] Nowe dane RPT – {len(rpt_content.splitlines())} linii")
        if all_content:
            self._save_last_positions()
        return all_content

    def run(self):
        if self.running:
            print("[FTP] Watcher już działa")
            return
        self.running = True
        print("[FTP] Start monitorowania najnowszego ADM i RPT co 25–35 sekund")
        def loop():
            while self.running:
                try:
                    content = self.get_new_content()
                    if content:
                        # Tutaj dodaj przetwarzanie content, np. parsowanie linii, wysyłanie na Discord itp.
                        pass
                except Exception as e:
                    print(f"[FTP LOOP ERROR] {e}")
                time.sleep(28 + (time.time() % 7))  # lekkie rozproszenie 25–35 s
        threading.Thread(target=loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.ftp:
            try:
                self.ftp.quit()
            except:
                pass
        print("[FTP] Watcher zatrzymany")

# Przykład użycia:
if __name__ == '__main__':
    watcher = DayZLogWatcher()
    watcher.run()
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        watcher.stop()
