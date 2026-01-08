@tasks.loop(seconds=CHECK_INTERVAL)
async def check_logs():
    print(f"[TASK] Sprawdzam nowe logi (co {CHECK_INTERVAL}s)...")
    
    if not watcher.connect():
        print("[TASK] ❌ Brak połączenia FTP")
        return
    
    content = watcher.get_new_content()
    if not content:
        print("[TASK] Brak nowych danych")
        return
    
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    print(f"[TASK] Znaleziono {len(lines)} nowych linii")
    
    # Ochrona przed starymi logami przy pierwszym uruchomieniu
    if len(lines) > 500:
        print(f"[TASK] ⚠️ ZA DUŻO LINII ({len(lines)}) – pomijam (pierwsze uruchomienie). Następny cykl będzie OK.")
        return
    
    for line in lines:
        try:
            await process_line(bot, line)
        except Exception as e:
            print(f"[BŁĄD przetwarzania linii]: {e}")
