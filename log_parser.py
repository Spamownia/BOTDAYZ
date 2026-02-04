# log_parser.py - poprawiona wersja: anty-duplikaty po hashu + bezpieczne wysyłanie
import re
from datetime import datetime
import time
from collections import defaultdict
from config import CHANNEL_IDS, CHAT_CHANNEL_MAPPING

last_death_time = defaultdict(float)
player_login_times = {}
guid_to_name = {}
last_hit_source = {}  # nick.lower() -> ostatni source trafienia

UNPARSED_LOG = "unparsed_lines.log"
SUMMARY_INTERVAL = 30
last_summary_time = time.time()
processed_count = 0
detected_events = {"join":0, "disconnect":0, "cot":0, "hit":0, "kill":0, "chat":0, "other":0, "unconscious":0}

processed_events = set()           # deduplikacja po (czas, nick, akcja)
processed_lines_hash = set()       # globalny cache – hash linii, które już wysłano
MAX_HASH_CACHE = 5000              # limit pamięci – po osiągnięciu czyścimy najstarsze

async def process_line(bot, line: str):
    global last_summary_time, processed_count

    try:
        client = bot
        line = line.strip()
        if not line:
            return

        # === PROSTA DEDUPLIKACJA PO HASHU LINII ===
        line_hash = hash(line)
        if line_hash in processed_lines_hash:
            return  # linia już była wysłana wcześniej

        processed_lines_hash.add(line_hash)

        # Ograniczanie rozmiaru cache (żeby nie rosło w nieskończoność)
        if len(processed_lines_hash) > MAX_HASH_CACHE:
            processed_lines_hash.pop()  # usuwa najstarszy (FIFO)

        processed_count += 1
        now = time.time()
        if now - last_summary_time >= SUMMARY_INTERVAL:
            summary = f"[PARSER SUMMARY @ {datetime.utcnow().strftime('%H:%M:%S')}] {processed_count} linii | "
            summary += " | ".join(f"{k}: {v}" for k,v in detected_events.items() if v > 0)
            print(summary)
            last_summary_time = now
            processed_count = 0
            for k in detected_events:
                detected_events[k] = 0

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
                except Exception as send_err:
                    print(f"[SEND ERROR connections] {send_err}")
            return

        # 2. Rozłączenia (obsługuje też Unknown id)
        disconnect_m = re.search(r'Player "(.+?)"\s*\(id=(.+?)\)\s*has been disconnected', line)
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
                except Exception as send_err:
                    print(f"[SEND ERROR connections] {send_err}")
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
                except Exception as send_err:
                    print(f"[SEND ERROR chat] {send_err}")
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
                except Exception as send_err:
                    print(f"[SEND ERROR admin] {send_err}")
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
                except Exception as send_err:
                    print(f"[SEND ERROR damages] {send_err}")
            if is_dead:
                kill_ch = client.get_channel(CHANNEL_IDS["kills"])
                if kill_ch:
                    try:
                        await kill_ch.send(f"```ansi\n[31m{date_str} | {log_time} ☠️ {nick} zabity przez {source}[0m```")
                    except Exception as send_err:
                        print(f"[SEND ERROR kills] {send_err}")
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
                except Exception as send_err:
                    print(f"[SEND ERROR damages] {send_err}")
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
                except Exception as send_err:
                    print(f"[SEND ERROR damages] {send_err}")
            return

        # 7. Śmierć z rozróżnieniem powodu
        death_m = re.search(r'Player "(.+?)" \(DEAD\) .*? died\. Stats> Water: ([\d.]+) Energy: ([\d.]+) Bleed sources: (\d+)', line)
        if death_m:
            detected_events["kill"] += 1
            nick = death_m.group(1).strip()
            water = float(death_m.group(2))
            energy = float(death_m.group(3))
            bleed = int(death_m.group(4))

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
                except Exception as send_err:
                    print(f"[SEND ERROR kills] {send_err}")

            if lower_nick in last_hit_source:
                del last_hit_source[lower_nick]

            return

        # Nierozpoznane - zapisz do pliku
        detected_events["other"] += 1
        try:
            with open(UNPARSED_LOG, "a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()} | {line}\n")
        except Exception as e:
            print(f"[UNPARSED WRITE ERROR] {e}")

    except Exception as e:
        print(f"[PROCESS LINE CRITICAL ERROR] {e} → {line[:150]}...")
