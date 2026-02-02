# ... (cały początek bez zmian) ...

async def check_and_parse_new_content():
    content = watcher.get_new_content()
    if content:
        print(f"[DEBUG MAIN] Pobrano {len(content.splitlines())} linii – wysyłam do parsera")
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        for line in lines:
            try:
                await process_line(client, line)
            except Exception as e:
                print(f"[PARSER LINE ERROR] {e} → {line[:140]}...")
    else:
        print("[DEBUG MAIN] get_new_content() → pusty string, nic do parsowania")

def run_watcher_loop():
    print("[WATCHER THREAD] Start pętli co 30 sekund")
    while True:
        try:
            future = asyncio.run_coroutine_threadsafe(check_and_parse_new_content(), client.loop)
            future.result(timeout=15)
        except Exception as e:
            print(f"[WATCHER THREAD ERROR] {e}")
        time.sleep(30)

# ... (reszta pliku bez zmian) ...
