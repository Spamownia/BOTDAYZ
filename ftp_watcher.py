class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_file = None
        self.last_position = 0
        print("[FTP] Watcher zainicjowany – czyta tylko najnowszy .RPT z trackingiem stanu")

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

            latest_rpt = max(rpt_files)  # najnowsza nazwa = najnowszy plik
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

            if latest_file != self.last_file:
                # Nowy plik – reset i pobierz ostatnie 2 MB
                print(f"[FTP] Nowy plik wykryty: {latest_file}. Reset pozycji.")
                self.last_file = latest_file
                self.last_position = max(0, size - 2_000_000)
            else:
                # Ten sam plik – pobierz od ostatniej pozycji
                if self.last_position >= size:
                    print("[FTP] Brak nowych danych (pozycja >= rozmiar)")
                    return ""
                print(f"[FTP] Pobieram od bajtu {self.last_position} (ten sam plik)")

            data = bytearray()
            def append_data(block):
                data.extend(block)

            self.ftp.retrbinary(f'RETR {latest_file}', append_data, rest=self.last_position)

            text = data.decode("utf-8", errors="replace")

            # Odrzucamy niepełną linię na początku (jeśli istnieje)
            if text and text[0] != '\n' and '\n' in text:
                text = text[text.index('\n') + 1:]

            self.last_position = size  # Zaktualizuj pozycję po pobraniu

            lines_count = len(text.splitlines())
            print(f"[FTP] Pobrano {lines_count} nowych linii z {latest_file}")

            return text

        except Exception as e:
            print(f"[FTP] Błąd przy pobieraniu {latest_file}: {e}")
            self.ftp = None
            # Nie resetuj pozycji na błąd, aby nie stracić postępu
            return ""
