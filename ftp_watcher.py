# ftp_watcher.py - z dodanym check mtime dla update bez change size
from ftplib import FTP
import time
import json
import os
import threading
import struct
from config import FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_LOG_DIR

LAST_POSITIONS_FILE = 'last_positions.json'

class DayZLogWatcher:
    def __init__(self):
        self.ftp = None
        self.last_rpt = None
        self.last_adm = None
        self.last_rpt_pos = 0
        self.last_adm_pos = 0
        self.last_mtime_rpt = 0
        self.last_mtime_adm = 0
        self._load_last_positions()
        print("[FTP WATCHER] Inicjalizacja – pamięć pozycji z JSON")
        self.running = False

    def _load_last_positions(self):
        if os.path.exists(LAST_POSITIONS_FILE):
            try:
                with open(LAST_POSITIONS_FILE, 'r') as f:
                    data = json.load(f)
                    self.last_rpt = data.get('last_rpt')
                    self.last_adm = data.get('last_adm')
                    self.last_rpt_pos = int(data.get('last_rpt_pos', 0))
                    self.last_adm_pos = int(data.get('last_adm_pos', 0))
                    self.last_mtime_rpt = int(data.get('last_mtime_rpt', 0))
                    self.last_mtime_adm = int(data.get('last_mtime_adm', 0))
                    print(f"[FTP WATCHER] Załadowano pozycje: RPT={self.last_rpt} @ {self.last_rpt_pos:,} bajtów mtime={self.last_mtime_rpt} | ADM={self.last_adm} @ {self.last_adm_pos:,} bajtów mtime={self.last_mtime_adm}")
            except Exception as e:
                print(f"[FTP WATCHER] Błąd ładowania pozycji: {e} – start od zera")
        else:
            print("[FTP WATCHER] Brak pliku pozycji – start od zera")

    def _save_last_positions(self):
        data = {
            'last_rpt': self.last_rpt,
            'last_adm': self.last_adm,
            'last_rpt_pos': self.last_rpt_pos,
            'last_adm_pos': self.last_adm_pos,
            'last_mtime_rpt': self.last_mtime_rpt,
            'last_mtime_adm': self.last_mtime_adm
        }
        try:
            with open(LAST_POSITIONS_FILE, 'w') as f:
                json.dump(data, f)
            print("[FTP WATCHER] Zapisano aktualne pozycje: RPT@{:,} | ADM@{:,}".format(self.last_rpt_pos, self.last_adm_pos))
        except Exception as e:
            print(f"[FTP WATCHER] Błąd zapisu pozycji: {e}")

    def _connect(self):
        for attempt in range(1, 4):
            try:
                if self.ftp:
                    self.ftp.quit()
            except:
                pass

            self.ftp = FTP()
            self.ftp.connect(FTP_HOST, FTP_PORT, timeout=30)
            self.ftp.login(FTP_USER, FTP_PASS)
            self.ftp.cwd(FTP_LOG_DIR)
            print(f"[FTP WATCHER] Połączono i cwd OK → {FTP_LOG_DIR}")
            return True

            time.sleep(5)
            print(f"[FTP WATCHER] Próba połączenia {attempt}/3: {FTP_HOST}:{FTP_PORT} / {FTP_USER}")

        print("[FTP WATCHER] Nieudane połączenie po 3 próbach")
        return False

    def get_latest_files(self):
        if not self._connect():
            return None, None

        try:
            files = self.ftp.nlst()
            rpt_files = sorted(f for f in files if f.endswith('.RPT'))
            adm_files = sorted(f for f in files if f.endswith('.ADM'))

            latest_rpt = rpt_files[-1] if rpt_files else None
            latest_adm = adm_files[-1] if adm_files else None

            print(f"[FTP WATCHER] Najnowszy .RPT: {latest_rpt}")
            print(f"[FTP WATCHER] Najnowszy .ADM: {latest_adm}")
            return latest_rpt, latest_adm
        except Exception as e:
            print(f"[FTP LATEST ERROR] {e}")
            return None, None

    def _get_mtime(self, file_name):
        try:
            mdtm_resp = self.ftp.sendcmd(f'MDTM {file_name}')
            if mdtm_resp.startswith('213 '):
                mdtm_str = mdtm_resp[4:]
                return time.mktime(time.strptime(mdtm_str, '%Y%m%d%H%M%S'))
            else:
                return 0
        except:
            return 0

    def _get_content(self, file_name, type):
        if not self._connect():
            return ""

        try:
            size = self.ftp.size(file_name)
            print(f"[FTP WATCHER] {file_name} → {size:,} bajtów")

            if type == 'rpt':
                if self.last_rpt != file_name:
                    print(f"[FTP WATCHER] Nowy plik RPT → reset pozycji na 0")
                    self.last_rpt_pos = 0
                    self.last_rpt = file_name
                    self.last_mtime_rpt = self._get_mtime(file_name)
                else:
                    current_mtime = self._get_mtime(file_name)
                    if current_mtime > self.last_mtime_rpt:
                        print(f"[FTP WATCHER] RPT updated by mtime ({self.last_mtime_rpt} -> {current_mtime}) – reread from last pos")
                        self.last_mtime_rpt = current_mtime
                    else:
                        if size <= self.last_rpt_pos:
                            print(f"[FTP WATCHER] Brak nowych danych w {file_name} (pozycja {self.last_rpt_pos:,} >= {size:,})")
                            return ""

            elif type == 'adm':
                if self.last_adm != file_name:
                    print(f"[FTP WATCHER] Nowy plik ADM → reset pozycji na 0")
                    self.last_adm_pos = 0
                    self.last_adm = file_name
                    self.last_mtime_adm = self._get_mtime(file_name)
                else:
                    current_mtime = self._get_mtime(file_name)
                    if current_mtime > self.last_mtime_adm:
                        print(f"[FTP WATCHER] ADM updated by mtime ({self.last_mtime_adm} -> {current_mtime}) – reread from last pos")
                        self.last_mtime_adm = current_mtime
                    else:
                        if size <= self.last_adm_pos:
                            print(f"[FTP WATCHER] Brak nowych danych w {file_name} (pozycja {self.last_adm_pos:,} >= {size:,})")
                            return ""

            start_pos = self.last_rpt_pos if type == 'rpt' else self.last_adm_pos
            if start_pos >= size:
                return ""

            data = bytearray()
            def callback(chunk):
                data.extend(chunk)

            self.ftp.retrbinary(f"RETR {file_name}", callback, rest=start_pos)

            content = data.decode('utf-8', errors='ignore')
            new_pos = start_pos + len(data)

            if type == 'rpt':
                self.last_rpt_pos = new_pos
            else:
                self.last_adm_pos = new_pos

            print(f"[FTP WATCHER] Pobrano {len(content.splitlines())} nowych linii z {file_name} (od {start_pos:,} do {new_pos:,} bajtów)")
            print(f"[FTP WATCHER PREVIEW {type.upper()}] {content[:200].replace('\n', ' | ')}...")

            return content
        except Exception as e:
            print(f"[FTP CONTENT ERROR {type.upper()}] {e}")
            return ""

    def get_new_content(self):
        latest_rpt, latest_adm = self.get_latest_files()
        if not latest_rpt and not latest_adm:
            return ""

        contents = []

        if latest_rpt:
            content_rpt = self._get_content(latest_rpt, 'rpt')
            if content_rpt:
                contents.append(content_rpt)

        if latest_adm:
            content_adm = self._get_content(latest_adm, 'adm')
            if content_adm:
                contents.append(content_adm)

        # Zapisujemy pozycje TYLKO jeśli coś faktycznie przeczytaliśmy
        if contents:
            self._save_last_positions()

        return "\n".join(contents)

    def run(self):
        """Uruchamia watcher w pętli co 30 sekund"""
        if self.running:
            print("[FTP WATCHER] Watcher już uruchomiony")
            return

        self.running = True
        print("[FTP WATCHER] Uruchamiam pętlę sprawdzania co 30 sekund")

        def loop():
            while self.running:
                try:
                    content = self.get_new_content()
                    if content:
                        print(f"[FTP WATCHER] Znaleziono nowe dane – {len(content.splitlines())} linii")
                        # Tutaj możesz przekazać content do parsera (np. przez kolejkę lub globalną zmienną)
                        # W Twoim przypadku – po prostu print, bo parser jest wywoływany w check_logs()
                except Exception as e:
                    print(f"[FTP WATCHER LOOP ERROR] {e}")
                
                time.sleep(30)  # ← dokładnie co 30 sekund

        threading.Thread(target=loop, daemon=True).start()
</DOCUMENT>

<DOCUMENT filename="log_parser.py">
# log_parser.py - finalna poprawiona wersja z importami + śmierć z przyczyną + try/except
import re
from datetime import datetime
import time
from collections import defaultdict
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING
# Usuń from utils jeśli nie używasz embedów, bo w tej wersji używam ansi text

last_death_time = defaultdict(float)
player_login_times = {}
guid_to_name = {}
last_hit_source = {}  # nick.lower() -> ostatni source trafienia (dodane do rozpoznawania przyczyny śmierci)

UNPARSED_LOG = "unparsed_lines.log"
SUMMARY_INTERVAL = 30
last_summary_time = time.time()
processed_count = 0
detected_events = {"join":0, "disconnect":0, "cot":0, "hit":0, "kill":0, "chat":0, "other":0, "unconscious":0}

processed_events = set()  # deduplikacja

async def process_line(bot, line: str):
    try:
        global last_summary_time, processed_count
        client = bot
        line = line.strip()
        if not line:
            return

        processed_count += 1
        now = time.time()
        if now - last_summary_time >= SUMMARY_INTERVAL:
            summary = f"[PARSER SUMMARY @ {datetime.utcnow().strftime('%H:%M:%S')}] {processed_count} linii | "
            summary += " | ".join(f"{k}: {v}" for k,v in detected_events.items() if v > 0)
            print(summary)
            last_summary_time = now
            processed_count = 0
            for k in detected_events: detected_events[k] = 0

        time_match = re.search(r'^(\d{1,2}:\d{2}:\d{2})(?:\.\d+)?', line)
        log_time = time_match.group(1) if time_match else datetime.utcnow().strftime("%H:%M:%S")
        today = datetime.utcnow()
        date_str = today.strftime("%d.%m.%Y")
        log_dt = datetime.combine(today.date(), datetime.strptime(log_time, "%H:%M:%S").time())

        def dedup_key(action, name=""):
            return (log_time, name.lower(), action)

        # 1. Połączenia
        connect_m = re.search(r'Player "(.+?)"\s*\(id=(.+?)\)\s*is connected', line)
        if connect_m:
            name = connect_m.group(1).strip()
            guid = connect_m.group(2)
            key = dedup_key("connect", name)
            if key in processed_events: return
            processed_events.add(key)
            detected_events["join"] += 1
            player_login_times[name] = log_dt
            guid_to_name[guid] = name
            msg = f"{date_str} | {log_time} 🟢 **Połączono** → {name} (ID: {guid})"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                try:
                    await ch.send(f"```ansi\n[32m{msg}[0m```")
                except Exception as e:
                    print(f"[SEND ERROR connections] {e}")
            return

        # 2. Rozłączenia
        disconnect_m = re.search(r'Player "(.+?)"\s*\(id=(Unknown|.+?)\)\s*has been disconnected', line)
        if disconnect_m:
            name = disconnect_m.group(1).strip()
            guid = disconnect_m.group(2)
            key = dedup_key("disconnect", name)
            if key in processed_events: return
            processed_events.add(key)
            detected_events["disconnect"] += 1
            time_online = "nieznany"
            if name in player_login_times:
                delta = (log_dt - player_login_times[name]).total_seconds()
                minutes = int(delta // 60)
                seconds = int(delta % 60)
                time_online = f"{minutes} min {seconds} s"
                del player_login_times[name]
            emoji = "🔴"
            color = "[31m"
            msg = f"{date_str} | {log_time} {emoji} **Rozłączono** → {name} (ID: {guid}) → {time_online}"
            ch = client.get_channel(CHANNEL_IDS["connections"])
            if ch:
                try:
                    await ch.send(f"```ansi\n{color}{msg}[0m```")
                except Exception as e:
                    print(f"[SEND ERROR connections] {e}")
            return

        # 3. Chat
        chat_m = re.search(r'\[Chat - (.+?)\]\("(.+?)"\(id=(.+?)\)\): (.*)', line)
        if chat_m:
            detected_events["chat"] += 1
            channel = chat_m.group(1).strip()
            nick = chat_m.group(2).strip()
            message = chat_m.group(4).strip() or "[brak]"
            colors = {"Global": "[34m", "Admin": "[31m", "Team": "[36m", "Direct": "[37m", "Side": "[35m"}
            col = colors.get(channel, "[33m")
            msg = f"{date_str} | {log_time} 💬 [{channel}] {nick}: {message}"
            target_id = CHAT_CHANNEL_MAPPING.get(channel, CHANNEL_IDS["chat"])
            ch = client.get_channel(target_id)
            if ch:
                try:
                    await ch.send(f"```ansi\n{col}{msg}[0m```")
                except Exception as e:
                    print(f"[SEND ERROR chat] {e}")
            return

        # 4. COT actions
        cot_m = re.search(r'\[COT\] (.+)', line)
        if cot_m:
            detected_events["cot"] += 1
            content = cot_m.group(1).strip()
            msg = f"{date_str} | {log_time} 🔧 [COT] {content}"
            ch = client.get_channel(CHANNEL_IDS.get("admin", CHANNEL_IDS["connections"]))
            if ch:
                try:
                    await ch.send(f"```ansi\n[35m{msg}[0m```")
                except Exception as e:
                    print(f"[SEND ERROR admin] {e}")
            return

        # 5. Hits / Obrażenia
        hit_m = re.search(r'Player "(.+?)" \s*\(id=(.+?)\s*pos=<.+?>\)\[HP: ([\d.]+)\] hit by (.+?) into (.+?)\((\d+)\) for ([\d.]+) damage \((.+?)\)', line)
        if hit_m:
            detected_events["hit"] += 1
            nick = hit_m.group(1)
            hp = float(hit_m.group(3))
            source = hit_m.group(4)
            part = hit_m.group(5)
            dmg = hit_m.group(7)
            ammo = hit_m.group(8)

            # Zapisz ostatnie źródło obrażeń dla gracza (pomaga przy śmierci)
            last_hit_source[nick.lower()] = source

            is_dead = hp <= 0
            emoji = "☠️" if is_dead else "🔥" if hp < 20 else "⚡"
            color = "[31m" if is_dead else "[35m" if hp < 20 else "[33m"
            extra = " (ŚMIERĆ)" if is_dead else f" (HP: {hp:.1f})"
            msg = f"{date_str} | {log_time} {emoji} {nick}{extra} trafiony przez {source} w {part} za {dmg} dmg ({ammo})"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                try:
                    await ch.send(f"```ansi\n{color}{msg}[0m```")
                except Exception as e:
                    print(f"[SEND ERROR damages] {e}")
            if is_dead:
                kill_ch = client.get_channel(CHANNEL_IDS["kills"])
                if kill_ch:
                    try:
                        await kill_ch.send(f"```ansi\n[31m{date_str} | {log_time} ☠️ {nick} zabity przez {source}[0m```")
                    except Exception as e:
                        print(f"[SEND ERROR kills] {e}")
            return

        # 6. Nieprzytomność
        uncon_m = re.search(r'Player "(.+?)" \s*\(id=(.+?)\s*pos=<.+?>\) is unconscious', line)
        if uncon_m:
            detected_events["unconscious"] += 1
            nick = uncon_m.group(1)
            msg = f"{date_str} | {log_time} 😵 {nick} jest nieprzytomny"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                try:
                    await ch.send(f"```ansi\n[31m{msg}[0m```")
                except Exception as e:
                    print(f"[SEND ERROR damages] {e}")
            return

        regain_m = re.search(r'Player "(.+?)" \s*\(id=(.+?)\s*pos=<.+?>\) regained consciousness', line)
        if regain_m:
            detected_events["unconscious"] += 1
            nick = regain_m.group(1)
            msg = f"{date_str} | {log_time} 🟢 {nick} odzyskał przytomność"
            ch = client.get_channel(CHANNEL_IDS["damages"])
            if ch:
                try:
                    await ch.send(f"```ansi\n[32m{msg}[0m```")
                except Exception as e:
                    print(f"[SEND ERROR damages] {e}")
            return

        # 7. Śmierć z rozróżnieniem powodu (dodane)
        death_m = re.search(r'Player "(.+?)" \(DEAD\) .*? died\. Stats> Water: ([\d.]+) Energy: ([\d.]+) Bleed sources: (\d+)', line)
        if death_m:
            detected_events["kill"] += 1
            nick = death_m.group(1).strip()
            water = float(death_m.group(2))
            energy = float(death_m.group(3))
            bleed = int(death_m.group(4))

            # Określ prawdopodobną przyczynę
            lower_nick = nick.lower()
            reason = "nieznana przyczyna"
            emoji_reason = "☠️"

            if lower_nick in last_hit_source:
                last_source = last_hit_source[lower_nick]
                if "Infected" in last_source or "Zombie" in last_source:
                    reason = "zainfekowany / zombie"
                    emoji_reason = "🧟"
                elif "explosion" in last_source.lower() or "LandMine" in last_source:
                    reason = "eksplozja / mina"
                    emoji_reason = "💥"
                elif "Player" in last_source:
                    reason = "zabity przez gracza"
                    emoji_reason = "🔫"
                elif "Fall" in last_source or "FallDamage" in last_source:
                    reason = "upadek z wysokości"
                    emoji_reason = "🪂"
                elif bleed > 0 and water < 100 and energy < 200:
                    reason = "wykrwawienie / wyczerpanie"
                    emoji_reason = "🩸"
                else:
                    reason = f"ostatni hit: {last_source}"

            msg = f"{date_str} | {log_time} {emoji_reason} **{nick} zmarł** ({reason})\n" \
                  f"   Stats → Water: {water:.0f} | Energy: {energy:.0f} | Bleed: {bleed}"

            ch = client.get_channel(CHANNEL_IDS["kills"])
            if ch:
                try:
                    await ch.send(f"```ansi\n[31m{msg}[0m```")
                except Exception as e:
                    print(f"[SEND ERROR kills] {e}")

            # Wyczyść po wysłaniu (zapobiega błędom przy duplikatach)
            if lower_nick in last_hit_source:
                del last_hit_source[lower_nick]

            return

        # Nierozpoznane - zapisz
        detected_events["other"] += 1
        try:
            with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
        except:
            pass
    except Exception as e:
        print(f"[PROCESS LINE ERROR] {e} → {line}")
</DOCUMENT>
