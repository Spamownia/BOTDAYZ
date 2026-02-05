# ftp_watcher.py – TYLKO ADM, bez RPT
from ftplib import FTP
import time
import json
import os
import threading
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

LAST_POSITIONS_FILE = 'last_positions.json'
ADM_FILENAME = "DayZServer_x64_2026-02-02_18-00-33.ADM"  # ← zmień na aktualną nazwę!

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_adm_pos = 0
        self.last_adm_mtime = 0
        self.last_adm_size = 0
        self._load_last_positions()
        print(f"[FTP WATCHER] Start – monitoruję TYLKO: {ADM_FILENAME}")
        self.running = False

    def _load_last_positions(self):
        if os.path.exists(LAST_POSITIONS_FILE):
            try:
                with open(LAST_POSITIONS_FILE, 'r') as f:
                    data = json.load(f)
                    self.last_adm_pos  = int(data.get('last_adm_pos',  0))
                    self.last_adm_mtime = int(data.get('last_adm_mtime', 0))
                    self.last_adm_size = int(data.get('last_adm_size', 0))
                print(f"[FTP] Wczytano stan ADM: pos={self.last_adm_pos:,}  size={self.last_adm_size:,}  mtime={self.last_adm_mtime}")
            except Exception as e:
                print(f"[FTP] Błąd wczytywania last_positions: {e} → start od zera")
        else:
            print("[FTP] Brak pliku last_positions → start od zera")

    def _save_last_positions(self):
        data = {
            'last_adm_pos':   self.last_adm_pos,
            'last_adm_mtime': self.last_adm_mtime,
            'last_adm_size':  self.last_adm_size,
        }
        try:
            with open(LAST_POSITIONS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            # print(f"[FTP] Zapisano stan: pos={self.last_adm_pos:,}")
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
                ts = time.strptime(resp[4:].strip(), '%Y%m%d%H%M%S')
                return int(time.mktime(ts))
        except:
            pass
        return 0

    def _get_adm_content(self):
        if not self._connect():
            return ""

        filename = ADM_FILENAME

        try:
            current_size = self.ftp.size(filename)
            current_mtime = self._get_mtime(filename)

            # Wykrywanie rotacji pliku (nowy plik = mniejszy rozmiar lub nowszy mtime)
            if current_size < self.last_adm_size or current_mtime > self.last_adm_mtime:
                print(f"[FTP] Wykryto ROTACJĘ ADM! (size: {self.last_adm_size:,} → {current_size:,} | mtime zmienił się)")
                self.last_adm_pos = 0

            if self.last_adm_pos >= current_size:
                # print(f"[FTP] Brak nowych danych ({self.last_adm_pos:,} / {current_size:,})")
                return ""

            start_pos = self.last_adm_pos
            data = []

            def callback(block):
                data.append(block)

            print(f"[FTP] Pobieram ADM od {start_pos:,} bajtów (plik ma {current_size:,})")
            self.ftp.retrbinary(f"RETR {filename}", callback, rest=start_pos)

            content_bytes = b''.join(data)
            if not content_bytes:
                return ""

            content = content_bytes.decode('utf-8', errors='replace')

            # Aktualizacja stanu – ZAWSZE po udanym odczycie
            self.last_adm_pos   = start_pos + len(content_bytes)
            self.last_adm_size  = current_size
            self.last_adm_mtime = current_mtime

            lines_count = len(content.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii ADM (od {start_pos:,})")

            # Podgląd pierwszych ~300 znaków (opcjonalnie)
            if content:
                preview = content.replace('\n', ' │ ')[:280].rstrip() + '…'
                print(f"[PREVIEW ADM] {preview}")

            return content

        except Exception as e:
            print(f"[FTP ERROR ADM] {type(e).__name__}: {e}")
            return ""

    def get_new_content(self):
        content = self._get_adm_content()
        if content:
            self._save_last_positions()
        return content

    def run(self):
        if self.running:
            print("[FTP] Watcher już działa")
            return
        self.running = True
        print("[FTP] Start monitorowania ADM co 25–35 sekund")

        def loop():
            while self.running:
                try:
                    content = self.get_new_content()
                    if content:
                        print(f"[FTP] Nowe dane ADM – {len(content.splitlines())} linii")
                        # Tutaj możesz dodać np. przetwarzanie linii, wysyłanie na Discord itp.
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
