import os
import time
import threading
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# --------------------------------------------------------
#                   USTAWIENIA GLOBALNE
# --------------------------------------------------------

INPUT_FILE             = "wszystkie_adresy1.txt"
OUTPUT_FILE            = "adresyzsaldem1.txt"
PROGRESS_FILE          = "progress.txt"

MIN_BALANCE_SATOSHI    = 1000       # 0.00001000 BTC minimalne saldo, które zapisujemy
MAX_WORKERS            = 5          # dokładnie 5 równoległych wątków (5 req/s)
REQUESTS_PER_SECOND    = 5          # chcemy maksymalnie 5 zapytań na sekundę w sumie
DELAY_BETWEEN_REQUESTS = 1.0 / REQUESTS_PER_SECOND  # ~0.2 s pauzy po każdym zapytaniu

# 10 różnych publicznych API (każde obsługuje sprawdzanie salda BTC, 
# niektóre mogą być testnetowe – traktujemy to czysto jako przykład różnorodności).
API_URLS = [
    "https://blockstream.info/api/address/",               # Blockstream (mainnet)
    "https://api.blockchair.com/bitcoin/dashboards/address/",
    "https://api.blockcypher.com/v1/btc/main/addrs/",
    "https://sochain.com/api/v2/get_address_balance/BTC/",
    "https://chain.api.btc.com/v3/address/",
    "https://api.blockchair.com/bitcoin/testnet/dashboards/address/",
    "https://api.blockcypher.com/v1/btc/test3/addrs/",
    "https://blockstream.info/testnet/api/address/",
    "https://sochain.com/api/v2/get_address_balance/BTCTEST/",
    "https://chain.so/api/v2/get_address_balance/BTC/"
]

# Lista 10 przykładowych nagłówków „User-Agent” (różne przeglądarki/urządzenia)
USER_AGENTS = [
    # Desktop Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/115.0.0.0 Safari/537.36",
    # Desktop Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) "
    "Gecko/20100101 Firefox/115.0",
    # Desktop Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/115.0.0.0 Safari/537.36 Edg/115.0.0.0",
    # macOS Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    # Android Chrome
    "Mozilla/5.0 (Linux; Android 13; Pixel 6) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/115.0.0.0 Mobile Safari/537.36",
    # Android Firefox
    "Mozilla/5.0 (Android 13; Mobile; rv:115.0) "
    "Gecko/115.0 Firefox/115.0",
    # iPad Safari
    "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/115.0.0.0 Safari/537.36",
    # Linux Firefox
    "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) "
    "Gecko/20100101 Firefox/115.0"
]

# Semaphore ograniczający liczbę jednoczesnych wątków w sekcji zapytania
sema = threading.BoundedSemaphore(MAX_WORKERS)

# Lock do zapisu do plików (wyniki + progress)
file_lock = threading.Lock()

# --------------------------------------------------------
#                FUNKCJE POMOCNICZE I WĄTKI
# --------------------------------------------------------

def read_last_index():
    """
    Odczytuje z PROGRESS_FILE ostatnio przetworzony indeks (wiersz).
    Jeśli plik nie istnieje lub jest pusty, zwraca -1.
    """
    if not os.path.exists(PROGRESS_FILE):
        return -1
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content == "":
                return -1
            return int(content)
    except Exception:
        return -1

def write_last_index(idx):
    """
    Zapisuje aktualnie przetworzony indeks do PROGRESS_FILE.
    Zabezpieczone lockiem, by nie pisały jednocześnie dwa wątki.
    """
    with file_lock:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            f.write(str(idx))

def _try_parse_blockstream(data):
    """
    Parsuje odpowiedź Blockstream API:
    { "chain_stats": { "funded_txo_sum": <int>, "spent_txo_sum": <int>, ... }, ... }
    """
    chain = data.get("chain_stats", {})
    funded = chain.get("funded_txo_sum", 0)
    spent  = chain.get("spent_txo_sum", 0)
    return funded - spent, funded

def _try_parse_blockchair(data, address):
    """
    Parsuje odpowiedź Blockchair:
    { "data": { "<adres>": { "address": { "balance": <satoshi>, "received": <satoshi>, ... } } } }
    """
    addr_info = data.get("data", {}).get(address, {}).get("address", {})
    balance = addr_info.get("balance", 0)
    funded  = addr_info.get("received", 0)
    return balance, funded

def _try_parse_blockcypher(data):
    """
    Parsuje BlockCypher:
    { "address": "<adres>", "balance": <satoshi>, "total_received": <satoshi>, ... }
    """
    balance = data.get("balance", 0)
    funded  = data.get("total_received", 0)
    return balance, funded

def _try_parse_sochain(data):
    """
    Parsuje SoChain:
    { "status": "success", "data": { "network":"BTC", "address":"<adres>",
        "confirmed_balance":"0.00000000", "balance":"0.00000000" } }
    Koloruje liczby od BTC do satoshi mnożąc przez 1e8.
    """
    if data.get("status") != "success":
        return 0, 0
    dat = data.get("data", {})
    try:
        bal_btc       = float(dat.get("balance", "0"))
        confirmed_btc = float(dat.get("confirmed_balance", "0"))
    except Exception:
        return 0, 0
    balance_satoshi = int(round(bal_btc * 1e8))
    funded_satoshi  = int(round(confirmed_btc * 1e8))
    return balance_satoshi, funded_satoshi

def _try_parse_btccom(data):
    """
    Parsuje BTC.com API v3:
    { "data": { "address":"<adres>", "balance":<satoshi>, "received":<satoshi>, ... } }
    """
    top     = data.get("data", {})
    balance = top.get("balance", 0)
    funded  = top.get("received", 0)
    return balance, funded

def _try_parse_generic(data):
    """
    Heurystyczne parsowanie w “niespodziewanym” formacie:
    szukamy kluczy 'balance', 'balance_satoshi', 'total_received', 'funded_txo_sum', 'received'.
    """
    balance = 0
    funded  = 0
    if "balance" in data:
        b = data.get("balance")
        if isinstance(b, int):
            balance = b
    if "balance_satoshi" in data:
        balance = data.get("balance_satoshi", balance)
    if "funded_txo_sum" in data:
        funded = data.get("funded_txo_sum", funded)
    if "total_received" in data:
        funded = data.get("total_received", funded)
    if "received" in data:
        r = data.get("received")
        if isinstance(r, int):
            funded = r
    return balance, funded

def check_balance(idx, address):
    """
    Sprawdza saldo dla jednego adresu, próbując po kolei API z listy API_URLS.
    Każde zapytanie odpalone jest pod semaforem i z opóźnieniem, by nie przekroczyć 5 req/s.
    Gdy znajdzie poprawną odpowiedź (HTTP 200 + prawidłowe parsowanie), zwraca:
        (idx, address, balance_satoshi, funded_total_satoshi)
    Jeśli żadne z 10 API nie zadziała, zwraca (idx, address, 0, 0).
    """
    # 1) Losowo dobieramy “User-Agent” z listy 10 UA
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "application/json",
        # Możesz dodać też: "Connection": "keep-alive", "Accept-Language": "en-US,en;q=0.9", itp.
    }

    # 2) Wchodzimy pod semafor (max 5 wątków równocześnie “zapytuje” API)
    with sema:
        for base_url in API_URLS:
            try:
                url  = f"{base_url}{address}"
                resp = requests.get(url, headers=headers, timeout=10)

                if resp.status_code != 200:
                    # Spróbuj następne API
                    continue

                data = resp.json()
                # Wybierz parser na podstawie domeny w base_url:
                if "blockstream.info" in base_url:
                    balance, funded = _try_parse_blockstream(data)
                elif "blockchair.com" in base_url:
                    balance, funded = _try_parse_blockchair(data, address)
                elif "blockcypher.com" in base_url:
                    balance, funded = _try_parse_blockcypher(data)
                elif "sochain.com" in base_url:
                    balance, funded = _try_parse_sochain(data)
                elif "btc.com" in base_url:
                    balance, funded = _try_parse_btccom(data)
                else:
                    balance, funded = _try_parse_generic(data)

                # 3) Odpocznijmy trochę przed zwróceniem wyniku, by uzyskać ~5 req/s
                time.sleep(DELAY_BETWEEN_REQUESTS)
                return idx, address, balance, funded

            except Exception:
                # Błąd sieci/parsing → spróbuj kolejne API
                continue

        # Jeśli żadne API nie zadziałało:
        time.sleep(DELAY_BETWEEN_REQUESTS)
        return idx, address, 0, 0

def main():
    print("[🚀] Start sprawdzania sald adresów BTC (5 agentów, rotacja UA)")

    # 1) Wczytaj wszystkie adresy z pliku
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            addresses = [linia.strip() for linia in f if linia.strip()]
    except FileNotFoundError:
        print(f"[❌] Brak pliku: {INPUT_FILE}")
        return

    total = len(addresses)
    if total == 0:
        print("[❌] Brak adresów w pliku.")
        return

    # 2) Odczytaj ostatni przetworzony indeks
    last_idx = read_last_index()
    start_idx = last_idx + 1
    if start_idx >= total:
        print("[ℹ️] Wszystkie adresy zostały już wcześniej sprawdzone.")
        return

    print(f"[ℹ️] Wznowienie od indeksu {start_idx} (adres: {addresses[start_idx]})")

    # 3) Otwórz plik do dopisywania wyników
    outfile = open(OUTPUT_FILE, "a", encoding="utf-8")

    # 4) Użyj ThreadPoolExecutor z dokładnie MAX_WORKERS (5) wątkami
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for idx in range(start_idx, total):
            addr = addresses[idx]
            futures.append(executor.submit(check_balance, idx, addr))

        # 5) Gdy któryś future się ukończy, pobieramy wynik i zapisujemy
        for future in as_completed(futures):
            idx, addr, balance, funded = future.result()

            # 5.a) Jeżeli bieżące saldo ≥ MIN_BALANCE_SATOSHI
            if balance >= MIN_BALANCE_SATOSHI:
                btc_amount = balance / 100_000_000
                print(f"\033[92m[💰][{idx}/{total}] {addr} => {btc_amount:.8f} BTC\033[0m")
                with file_lock:
                    outfile.write(f"{addr} => {btc_amount:.8f} BTC\n")

            # 5.b) Jeżeli saldo = 0, ale suma otrzymanych (>0) → historyczne wpłaty
            elif funded > 0:
                ever_btc = funded / 100_000_000
                print(f"\033[93m[📜][{idx}/{total}] {addr} miało kiedyś {ever_btc:.8f} BTC, teraz 0 BTC\033[0m")
                # nie zapisujemy do OUTPUT_FILE, bo nie ma aktualnego salda

            # 5.c) W przeciwnym razie – zero
            else:
                print(f"[{idx}/{total}] {addr} => 0 BTC (zero historii)")

            # 6) Zapisujemy do progress1.txt
            write_last_index(idx)

    outfile.close()
    print("[✅] Zakończono. Wyniki zapisano do:", OUTPUT_FILE)

if __name__ == "__main__":
    main()
