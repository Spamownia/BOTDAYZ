from ftplib import FTP
import time
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_rpt = None
        self.last_adm = None
        self.last_rpt_pos = 0
        self.last_adm_pos = 0
        print("[FTP DEBUG] Inicjalizacja – czyta .RPT + .ADM")

    def connect_and_debug(self):
        if self.ftp:
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
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

        return "\n".join(contents)

    def _get_content(self, filename, file_type):
        try:
            size = self.ftp.size(filename)
            last_pos = self.last_rpt_pos if file_type == 'rpt' else self.last_adm_pos
            last_file = self.last_rpt if file_type == 'rpt' else self.last_adm

            if filename != last_file:
                print(f"[FTP DEBUG] Nowy plik {file_type.upper()}: {filename} → start od końca")
                last_pos = max(0, size - 5_000_000)

            if last_pos >= size:
                return ""

            data = bytearray()
            self.ftp.retrbinary(f'RETR {filename}', data.extend, rest=last_pos)

            text = data.decode('utf-8', errors='replace')
            if text and '\n' in text:
                text = text[text.index('\n') + 1:]

            if file_type == 'rpt':
                self.last_rpt = filename
                self.last_rpt_pos = size
            else:
                self.last_adm = filename
                self.last_adm_pos = size

            lines = len(text.splitlines())
            print(f"[FTP DEBUG] Pobrano {lines} nowych linii z {filename}")

            if text:
                preview = text[:300].replace('\n', ' | ')
                print(f"[FTP DEBUG PREVIEW {file_type.upper()}] {preview}...")

            return text
        except Exception as e:
            print(f"[FTP DEBUG] Błąd pobierania {filename}: {e}")
            return ""
