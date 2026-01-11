import subprocess
import glob
import os
import re
import sys
import time
import concurrent.futures
import threading

RELAYS = [
    "ferdie",
    "george",
    "henry",
    "iris",
    "jack",
    "paul",
    "quinn",
    "rita",
    "sam",
    "tom"
]

DB_LOCK = threading.Lock()

def submit_single_tx(i, tx_file, total_files, toolkit_path):
    relay_name = RELAYS[i % len(RELAYS)]
    dest_url = f"ws://{relay_name}.node.sc.iog.io:9944"
    
    cmd = [
        toolkit_path, "generate-txs", "send",
        "--src-file", tx_file,
        "--dest-url", dest_url
    ]

    try:
        # Run the command
        with DB_LOCK:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
        if result.stderr:
            print(f"⚠️  {tx_file}: {result.stderr}")
        print(f"✅ [{i}/{total_files}] Sent {tx_file} to {relay_name}")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to submit {tx_file} to {relay_name}!")
        print("Error Output:", e.stderr)

def submit_transactions(toolkit_path="midnight-node-toolkit"):
    start_time = time.time()
    # 1. Find all matching files
    files = glob.glob(os.path.join("txs", "tx_*.json"))
    
    if not files:
        print("❌ No files found matching 'tx_*.json'")
        sys.exit(1)

    print(f"🚀 Found {len(files)} transaction files to submit.")

    max_workers = min(os.cpu_count() or 1, len(files))
    print(f"ℹ️  Using {max_workers} threads for execution.")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(submit_single_tx, i, tx_file, len(files), toolkit_path) for i, tx_file in enumerate(files, 1)]
        concurrent.futures.wait(futures)

    end_time = time.time()
    print("\n🎉 Batch submission complete.")
    print(f"⏱️ Total execution time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    submit_transactions()