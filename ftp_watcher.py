from ftplib import FTP
import time
import json
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_rpt = None
        self.last_adm = None
        self.last_rpt_pos = 0
        self.last_adm_pos = 0
        self._load_last_positions()
        print("[FTP DEBUG] Inicjalizacja – czyta .RPT + .ADM")

    def _load_last_positions(self):
        try:
            with open('last_positions.json', 'r') as f:
                data = json.load(f)
                self.last_rpt = data.get('last_rpt')
                self.last_adm = data.get('last_adm')
                self.last_rpt_pos = data.get('last_rpt_pos', 0)
                self.last_adm_pos = data.get('last_adm_pos', 0)
                print("[FTP DEBUG] Załadowano ostatnie pozycje z pliku")
        except FileNotFoundError:
            print("[FTP DEBUG] Brak pliku z pozycjami – start od zera")

    def _save_last_positions(self):
        data = {
            'last_rpt': self.last_rpt,
            'last_adm': self.last_adm,
            'last_rpt_pos': self.last_rpt_pos,
            'last_adm_pos': self.last_adm_pos
        }
        with open('last_positions.json', 'w') as f:
            json.dump(data, f)
        print("[FTP DEBUG] Zapisano pozycje do pliku")

    def connect_and_debug(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                print("[FTP DEBUG] Stare połączenie padło")
                self.ftp = None

        try:
            print(f"[FTP DEBUG] Łączenie: {FTP_HOST}:{FTP_PORT} / {FTP_USER}")
            self.ftp = FTP(timeout=20)
            self.ftp.connect(host=FTP_HOST, port=FTP_PORT)
            self.ftp.login(user=FTP_USER, passwd=FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            print(f"[FTP DEBUG] cwd OK → {self.ftp.pwd()}")
            self.ftp.set_pasv(True)
            return True
        except Exception as e:
            print(f"[FTP DEBUG] Błąd połączenia: {e}")
            self.ftp = None
            return False

    def get_latest_files(self):
        if not self.connect_and_debug():
            return None, None

        try:
            files_lines = []
            self.ftp.dir(files_lines.append)

            rpt_files = []
            adm_files = []

            for line in files_lines:
                parts = line.split()
                if len(parts) >= 9:
                    filename = ' '.join(parts[8:])
                    if filename.lower().endswith('.rpt'):
                        rpt_files.append(filename)
                    elif filename.lower().endswith('.adm'):
                        adm_files.append(filename)

            latest_rpt = max(rpt_files) if rpt_files else None
            latest_adm = max(adm_files) if adm_files else None

            print(f"[FTP DEBUG] Najnowszy .RPT: {latest_rpt}")
            print(f"[FTP DEBUG] Najnowszy .ADM: {latest_adm}")

            return latest_rpt, latest_adm
        except Exception as e:
            print(f"[FTP DEBUG] Błąd listowania: {e}")
            return None, None

    def get_new_content(self):
        latest_rpt, latest_adm = self.get_latest_files()
        if not latest_rpt and not latest_adm:
            return ""

        contents = []

        if latest_rpt:
            contents.append(self._get_content(latest_rpt, 'rpt'))

        if latest_adm:
            contents.append(self._get_content(latest_adm, 'adm'))

        self._save_last_positions()  # Zapisz pozycje po odczycie

        return "\n".join(contents)

    def _get_content(self, filename, file_type):
        try:
            size = self.ftp.size(filename)
            print(f"[FTP DEBUG] {filename} → {size:,} bajtów")

            last_pos = self.last_rpt_pos if file_type == 'rpt' else self.last_adm_pos
            last_file = self.last_rpt if file_type == 'rpt' else self.last_adm

            if filename != last_file:
                print(f"[FTP DEBUG] Nowy plik {file_type.upper()} → start od końca")
                last_pos = max(0, size - 5_000_000)

            if last_pos >= size:
                return ""

            data = bytearray()
            self.ftp.retrbinary(f'RETR {filename}', data.extend, rest=last_pos)

            text = data.decode('utf-8', errors='replace')
            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            lines = len(text.splitlines())
            print(f"[FTP DEBUG] Pobrano {lines} linii z {filename}")

            if text:
                preview = text[:300].replace('\n', ' | ')
                print(f"[FTP DEBUG PREVIEW {file_type.upper()}] {preview}...")

            if file_type == 'rpt':
                self.last_rpt = filename
                self.last_rpt_pos = size
            else:
                self.last_adm = filename
                self.last_adm_pos = size

            return text
        except Exception as e:
            print(f"[FTP DEBUG] Błąd pobierania {filename}: {e}")
            return ""
