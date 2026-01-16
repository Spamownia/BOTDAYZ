def get_new_content(self):
    latest_file = self.get_latest_rpt()
    if not latest_file:
        return ""

    try:
        if not self.connect():
            return ""

        size = self.ftp.size(latest_file)
        print(f"[FTP] Aktualny rozmiar {latest_file}: {size} bajtów")

        # Zawsze pobieramy ostatnie 2 MB (bezpiecznie na nowe zdarzenia graczy)
        rest = max(0, size - 2_000_000)
        print(f"[FTP] Pobieram od bajtu {rest} (ostatnie 2 MB)")

        data = bytearray()
        def append_data(block):
            data.extend(block)

        self.ftp.retrbinary(f'RETR {latest_file}', append_data, rest=rest)

        text = data.decode("utf-8", errors="replace")

        # Odrzucamy niepełną linię na początku
        if '\n' in text:
            text = text[text.index('\n') + 1:]

        lines_count = len(text.splitlines())
        print(f"[FTP] Pobrano {lines_count} potencjalnie nowych linii z {latest_file}")

        return text

    except Exception as e:
        print(f"[FTP] Błąd przy pobieraniu {latest_file}: {e}")
        self.ftp = None
        return ""
