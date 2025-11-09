# 💰 Bitcoin Address Balance Checker (Multi-API Rotator)

> ⚠️ **For Ethical & Educational Research Only**  
> This project demonstrates a robust **Bitcoin address balance scanner**  
> that uses multiple public blockchain APIs with rotation and throttling.  
>  
> It supports **multi-threaded scanning**, **progress persistence**,  
> and **cross-API parsing** for both mainnet and testnet addresses.  
>  
> 🧠 Designed for research, auditing, or studying public Bitcoin API behaviour —  
> not for unauthorized balance tracking or exploitation.

---

## 🚀 Overview

This Python script checks the **current and historical balances** of Bitcoin addresses  
by querying multiple public APIs (Blockstream, Blockchair, BlockCypher, SoChain, BTC.com, etc.).  
It automatically rotates user-agents and API sources to bypass rate limits,  
and ensures **exactly 5 requests per second** globally.

It also:
- 🔄 **Resumes scanning** from the last saved index  
- 💾 Saves all addresses with **non-zero balances**  
- 📜 Prints history for addresses that had BTC in the past  
- ⚙️ Works with both **mainnet** and **testnet** endpoints  

---

## ✨ Features

| Feature | Description |
|----------|--------------|
| 🌐 **10 public APIs** | Queries multiple blockchain explorers with rotation |
| ⚙️ **Smart throttling** | Keeps requests at 5 per second total |
| 🧵 **ThreadPool concurrency** | Uses exactly 5 worker threads in parallel |
| 📊 **Progress tracking** | Saves progress in `progress.txt` to resume after restart |
| 💾 **Output logging** | Saves addresses with positive balance to `adresyzsaldem1.txt` |
| 🧠 **API auto-parsing** | Supports Blockstream, Blockchair, BlockCypher, SoChain, BTC.com |
| 🧍 **User-Agent rotation** | Randomizes headers to emulate different clients |
| 🧩 **Mainnet & testnet support** | Scans both BTC and BTCTEST endpoints automatically |

---

## 📂 File Structure

| File | Description |
|------|-------------|
| `main.py` | Main program file (the code above) |
| `wszystkie_adresy1.txt` | Input list of Bitcoin addresses (one per line) |
| `adresyzsaldem1.txt` | Output file with addresses that hold balance |
| `progress.txt` | Automatically saved last scanned index |
| `README.md` | Documentation (this file) |

---

## ⚙️ Configuration

| Variable | Purpose |
|-----------|----------|
| `INPUT_FILE` | Path to text file containing BTC addresses |
| `OUTPUT_FILE` | File where results (addresses with BTC) are saved |
| `PROGRESS_FILE` | File used to save last processed index |
| `MIN_BALANCE_SATOSHI` | Minimum balance threshold (default: 1000 sat = 0.00001000 BTC) |
| `MAX_WORKERS` | Number of concurrent threads (default: 5) |
| `REQUESTS_PER_SECOND` | Max total requests per second (default: 5) |
| `DELAY_BETWEEN_REQUESTS` | Auto-computed delay between requests (0.2s) |

**Dependencies**

pip install requests


---

## 🧠 How It Works

### 1️⃣ Input & Progress Recovery  
- Loads all addresses from `wszystkie_adresy1.txt`.  
- Reads last processed index from `progress.txt` to **resume scanning** after restarts.

---

### 2️⃣ Multi-API Query Logic  
Each thread tries multiple API providers **sequentially** until one responds correctly:  

| API Provider | Example URL |
|---------------|--------------|
| Blockstream | `https://blockstream.info/api/address/` |
| Blockchair | `https://api.blockchair.com/bitcoin/dashboards/address/` |
| BlockCypher | `https://api.blockcypher.com/v1/btc/main/addrs/` |
| SoChain | `https://sochain.com/api/v2/get_address_balance/BTC/` |
| BTC.com | `https://chain.api.btc.com/v3/address/` |
| ...and 5 more including testnet endpoints |

The script rotates between these to maximize availability.

---

### 3️⃣ User-Agent Randomization  
To avoid API bans or request blocking, each query uses a random **User-Agent** string:  
(Chrome, Firefox, Safari, Edge, Android, iOS, Linux, etc.)

```python
ua = random.choice(USER_AGENTS)
headers = { "User-Agent": ua, "Accept": "application/json" }

4️⃣ Rate Limiting

Every request sleeps for 0.2s (1 / 5) after a valid query,
ensuring 5 requests per second total even with multiple threads.

5️⃣ Parsing API Responses

The script supports parsing multiple formats automatically:

API	Parser Function	Format Example
Blockstream	_try_parse_blockstream()	{"chain_stats": {"funded_txo_sum": …}}
Blockchair	_try_parse_blockchair()	{"data": {"<addr>": {"address": {...}}}}
BlockCypher	_try_parse_blockcypher()	{"balance": 100000, "total_received": …}
SoChain	_try_parse_sochain()	{"data": {"balance": "0.123"}}
BTC.com	_try_parse_btccom()	{"data": {"balance": …}}
Fallback	_try_parse_generic()	Heuristic detection by key names
6️⃣ Output & Progress

If balance ≥ threshold → saves to output file

If balance = 0 but had historical transactions → prints info

Progress file (progress.txt) updates after each address

write_last_index(idx)
outfile.write(f"{addr} => {btc_amount:.8f} BTC\n")

🧾 Example Output
[🚀] Start sprawdzania sald adresów BTC (5 agentów, rotacja UA)
[ℹ️] Wznowienie od indeksu 1500 (adres: 1FfmbHfnpaZjKFvyi1okTjJJusN455paPH)

[💰][1500/5000] 1Ez69SnzzmePmZX3WpEzMKTrcBF2gpNQ55 => 0.31850000 BTC
[📜][1501/5000] 1BoatSLRHtKNngkdXEeobR76b53LETtpyT miało kiedyś 50.00000000 BTC, teraz 0 BTC
[1502/5000] 1dice8EMZmqKvrGE4Qc9bUFf9PX3xaYDp => 0 BTC (zero historii)
[✅] Zakończono. Wyniki zapisano do: adresyzsaldem1.txt

🧩 Core Functions
Function	Description
check_balance()	Queries all APIs sequentially for one BTC address
read_last_index()	Reads last scanned index from progress file
write_last_index()	Saves current index to resume later
_try_parse_*()	Dedicated parsers for each API response type
main()	Orchestrates threading, progress tracking, and logging
⚡ Performance Tips

✅ Keep MAX_WORKERS = REQUESTS_PER_SECOND for proper throttling.

🧠 Use SSD for faster I/O when scanning large address lists.

🔄 You can restart at any time — it resumes automatically from progress.txt.

💡 Adjust MIN_BALANCE_SATOSHI for higher or lower thresholds.

🧱 Add proxy rotation or API key support for larger-scale scanning.

🔒 Ethical & Legal Notice

This script is a research and monitoring tool for educational use.
It must not be used for mass-scanning, wallet tracking, or privacy violations.

You may:

Study blockchain APIs and data structure differences.

Audit your own address sets or cold storage.

Analyze address reuse and UTXO balance models.

You must not:

Perform unauthorized scans or collect others’ financial data.

Attempt to infer private information or exploit API systems.

Unauthorized use is illegal and unethical.

🧰 Suggested Improvements

🌐 Add support for Ethereum or Dogecoin API endpoints.

💾 Cache API responses locally for retry control.

🔧 Add proxy rotation and API key configuration.

📈 Build web dashboard for real-time statistics.

🧮 Add retry queue for failed requests.

🪪 License

MIT License
© 2025 — Author: [Ethicbrudhack]

💡 Summary

This project showcases:

🌍 Multi-API querying with throttling

🧵 Thread-safe file and progress handling

⚙️ Real-time blockchain balance checking

to demonstrate advanced network I/O management,
rate limiting, and multi-threaded architecture in a practical Bitcoin context.

🧠 Observe responsibly. Learn deeply. Respect the network.

BTC donation address: bc1q4nyq7kr4nwq6zw35pg0zl0k9jmdmtmadlfvqhr
