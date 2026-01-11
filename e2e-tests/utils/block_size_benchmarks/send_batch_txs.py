import subprocess
import glob
import os
import re
import sys
import time
import concurrent.futures
import shutil
import tempfile

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
DB_PATH = "toolkit.db"

def submit_single_tx(i, tx_file, total_files, toolkit_path):
    relay_name = RELAYS[i % len(RELAYS)]
    dest_url = f"ws://{relay_name}.node.sc.iog.io:9944"
    
    # Ensure absolute path for the source file since we change CWD
    abs_tx_file = os.path.abspath(tx_file)

    cmd = [
        toolkit_path, "generate-txs", "send",
        "--src-file", abs_tx_file,
        "--dest-url", dest_url
    ]

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy toolkit.db to temp_dir to avoid locking
            db_copy_start = time.time()
            if os.path.exists(DB_PATH):
                shutil.copy(DB_PATH, os.path.join(temp_dir, "toolkit.db"))
            db_copy_time = time.time() - db_copy_start

            exec_start = time.time()
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, cwd=temp_dir
            )
            exec_time = time.time() - exec_start

        if result.stderr:
            print(f"⚠️  {tx_file}: {result.stderr}")
        print(f"✅ [{i}/{total_files}] Sent {tx_file} to {relay_name} [DB Copy: {db_copy_time:.4f}s, Exec: {exec_time:.4f}s]")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to submit {tx_file} to {relay_name}!")
        print("Error Output:", e.stderr)

def submit_transactions(toolkit_path="midnight-node-toolkit"):
    global DB_PATH
    if not os.path.exists(DB_PATH):
        print(f"⚠️  Warning: '{DB_PATH}' not found in current directory.")
        user_input = input("Please enter the full path to toolkit.db: ").strip()
        if not user_input:
            print("❌ No path provided. Exiting.")
            sys.exit(1)
        
        DB_PATH = user_input
        if not os.path.exists(DB_PATH):
            print(f"❌ Error: File '{DB_PATH}' not found.")
            sys.exit(1)

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