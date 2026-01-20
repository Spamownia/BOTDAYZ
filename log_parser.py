    # 5. Obrażenia i śmierci – żółty/pomarańczowy dla hit, czerwony dla śmierci
    if any(keyword in line for keyword in ["hit by", "killed by", "[HP: 0]", "CHAR_DEBUG - KILL"]):
        # Najpierw pełne zabójstwo (killed by) – zawsze czerwone
        match_kill = re.search(r'Player "([^"]+)" \(DEAD\) .* killed by (Player "([^"]+)"|Infected) .* with ([\w ]+) from ([\d.]+) meters', line)
        if match_kill:
            detected_events["kill"] += 1
            victim = match_kill.group(1)
            attacker_type = match_kill.group(2)
            attacker = match_kill.group(3) if attacker_type == "Player" else "Infected"
            weapon = match_kill.group(4)
            dist = match_kill.group(5)
            
            msg = f"{date_str} | {log_time} ☠️ {victim} zabity przez {attacker} z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(f"```ansi\n[31m{msg}[0m\n```")
            return

        # Potem obrażenia (hit by)
        match_hit = re.search(r'Player "([^"]+)"(?: \(DEAD\))? .*hit by (Player "([^"]+)"|Infected) .*into (\w+)\(\d+\) for ([\d.]+) damage \(([^)]+)\)(?: with ([\w ]+) from ([\d.]+) meters)?', line)
        if match_hit:
            detected_events["hit"] += 1
            victim = match_hit.group(1)
            attacker_type = match_hit.group(2)
            attacker = match_hit.group(3) if attacker_type == "Player" else "Infected"
            part = match_hit.group(4)
            dmg = match_hit.group(5)
            ammo = match_hit.group(6)
            weapon = match_hit.group(7) or "brak"
            dist = match_hit.group(8) or "brak"

            hp_match = re.search(r'\[HP: ([\d.]+)\]', line)
            hp = float(hp_match.group(1)) if hp_match else 100.0
            is_dead = hp <= 0 or "DEAD" in line

            # Kolory:
            #   pomarańczowy dla niskiego HP (< 20)
            #   żółty dla normalnych obrażeń
            #   czerwony tylko przy śmierci
            if is_dead:
                color = "[31m"
                emoji = "☠️"
                extra = " (ŚMIERĆ)"
            elif hp < 20:
                color = "[38;5;208m"  # pomarańczowy
                emoji = "🔥"
                extra = f" (krytycznie niski HP: {hp})"
            else:
                color = "[33m"  # żółty
                emoji = "⚡"
                extra = f" (HP: {hp})"

            msg = f"{date_str} | {log_time} {emoji} {victim}{extra} trafiony przez {attacker} w {part} za {dmg} dmg ({ammo}) z {weapon} z {dist}m"
            ch = client.get_channel(CHANNEL_IDS["deaths"])
            if ch:
                await ch.send(f"```ansi\n{color}{msg}[0m\n```")
            return

        # CHAR_DEBUG - KILL (z RPT) – czerwony
        if "CHAR_DEBUG - KILL" in line:
            detected_events["kill"] += 1
            match = re.search(r'player (\w+) \(dpnid = (\d+)\)', line)
            if match:
                player = match.group(1)
                dpnid = match.group(2)
                msg = f"{date_str} | {log_time} ☠️ Śmierć: {player} (dpnid: {dpnid})"
                ch = client.get_channel(CHANNEL_IDS["deaths"])
                if ch:
                    await ch.send(f"```ansi\n[31m{msg}[0m\n```")
                return
