# ftp_watcher.py – monitoruje TYLKO najnowszy plik .ADM (bez RPT)
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
        self.last_adm_size = 0
        self.last_rpt_filename = None
        self.last_rpt_pos = 0
        self.last_rpt_size = 0
        self._load_last_positions()
        print("[FTP WATCHER] Start – monitoruję najnowszy plik ADM i RPT w katalogu")
        self.running = False

    # ... _load_last_positions i _save_last_positions bez zmian ...

    def _connect(self):
        for attempt in range(1, 4):
            try:
                if self.ftp is not None:
                    try:
                        self.ftp.quit()
                    except:
                        pass
                    self.ftp = None

                self.ftp = FTP(timeout=20)               # ← dodany timeout
                self.ftp.connect(FTP_HOST, FTP_PORT, timeout=20)
                self.ftp.login(FTP_USER, FTP_PASS)
                self.ftp.cwd(FTP_LOG_DIR)
                print(f"[FTP] Połączono → {FTP_LOG_DIR}")
                return True
            except Exception as e:
                print(f"[FTP] Połączenie nieudane (próba {attempt}/3): {e}")
                time.sleep(4)
        print("[FTP] Nie udało się połączyć po 3 próbach")
        return False

    # ... _find_latest_adm i _find_latest_rpt bez zmian ...

    def _get_adm_content(self):
        if not self._connect():
            return ""
        filename = self._find_latest_adm()
        if not filename:
            if self.ftp:
                try: self.ftp.quit()
                except: pass
            return ""

        try:
            current_size = self.ftp.size(filename)

            if filename != self.last_adm_filename or current_size < self.last_adm_size:
                print(f"[FTP] Nowy/zrotowany ADM! {self.last_adm_filename or '(brak)'} → {filename} "
                      f"(size: {current_size:,} bajtów)")
                self.last_adm_filename = filename
                self.last_adm_pos = 0
                self.last_adm_size = current_size

            if self.last_adm_pos >= current_size:
                return ""

            start_pos = self.last_adm_pos
            data = []
            def callback(block):
                data.append(block)

            print(f"[FTP] Pobieram ADM {filename} od {start_pos:,} bajtów (rozmiar: {current_size:,})")
            self.ftp.retrbinary(f"RETR {filename}", callback, rest=start_pos)
            content_bytes = b''.join(data)

            if not content_bytes:
                return ""

            content = content_bytes.decode('utf-8', errors='replace')

            self.last_adm_pos = start_pos + len(content_bytes)
            self.last_adm_size = current_size

            lines_count = len(content.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii z ADM")

            if content:
                preview = content.replace('\n', ' │ ')[:280].rstrip() + '…'
                print(f"[PREVIEW ADM] {preview}")

            return content

        except Exception as e:
            print(f"[FTP ERROR ADM {filename}]: {type(e).__name__}: {e}")
            return ""
        finally:
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    pass
            self.ftp = None   # ← zawsze czyścimy po operacji

    def _get_rpt_content(self):
        if not self._connect():
            return ""
        filename = self._find_latest_rpt()
        if not filename:
            if self.ftp:
                try: self.ftp.quit()
                except: pass
            return ""

        try:
            current_size = self.ftp.size(filename)

            if filename != self.last_rpt_filename or current_size < self.last_rpt_size:
                print(f"[FTP] Nowy/zrotowany RPT! {self.last_rpt_filename or '(brak)'} → {filename} "
                      f"(size: {current_size:,} bajtów)")
                self.last_rpt_filename = filename
                self.last_rpt_pos = 0
                self.last_rpt_size = current_size

            if self.last_rpt_pos >= current_size:
                return ""

            start_pos = self.last_rpt_pos
            data = []
            def callback(block):
                data.append(block)

            print(f"[FTP] Pobieram RPT {filename} od {start_pos:,} bajtów (rozmiar: {current_size:,})")
            self.ftp.retrbinary(f"RETR {filename}", callback, rest=start_pos)
            content_bytes = b''.join(data)

            if not content_bytes:
                return ""

            content = content_bytes.decode('utf-8', errors='replace')

            self.last_rpt_pos = start_pos + len(content_bytes)
            self.last_rpt_size = current_size

            lines_count = len(content.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii z RPT")

            if content:
                preview = content.replace('\n', ' │ ')[:280].rstrip() + '…'
                print(f"[PREVIEW RPT] {preview}")

            return content

        except Exception as e:
            print(f"[FTP ERROR RPT {filename}]: {type(e).__name__}: {e}")
            return ""
        finally:
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    pass
            self.ftp = None   # ← zawsze czyścimy po operacji

    def get_new_content(self):
        adm_content = self._get_adm_content()
        rpt_content = self._get_rpt_content()
        content = (adm_content + "\n" + rpt_content).strip()
        if content:
            self._save_last_positions()
        return content

    # ... run() i stop() bez zmian ...
