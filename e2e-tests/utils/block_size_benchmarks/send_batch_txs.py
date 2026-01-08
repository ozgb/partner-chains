import subprocess
import glob
import os
import re
import sys
import time

def get_tx_number(filename):
    """
    Extracts the number from 'tx_123.json' for sorting.
    Returns 0 if no number is found, ensuring consistent sorting.
    """
    match = re.search(r'tx_(\d+)\.json', filename)
    return int(match.group(1)) if match else 0

def submit_transactions(toolkit_path="midnight-node-toolkit"):
    # 1. Find all matching files
    files = glob.glob("tx_*.json")
    
    if not files:
        print("❌ No files found matching 'tx_*.json'")
        sys.exit(1)

    # 2. Sort them numerically (Crucial for sequential nonces/dust)
    # This ensures tx_1.json -> tx_2.json -> ... -> tx_10.json
    files.sort(key=get_tx_number)

    print(f"🚀 Found {len(files)} transaction files to submit.")
    
    dest_url = "ws://ferdie.node.sc.iog.io:9944"

    # 3. Submit loop
    for i, tx_file in enumerate(files, 1):
        print(f"[{i}/{len(files)}] Submitting {tx_file}...", end=" ", flush=True)
        
        cmd = [
            toolkit_path, "generate-txs", "send",
            "--src-file", tx_file,
            "--dest-url", dest_url
        ]

        try:
            # Run the command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            # if result.stdout:
            #     print(result.stdout)
            if result.stderr:
                print(result.stderr)
            # Simple check for success in stdout if the tool doesn't use exit codes correctly
            # (Adjust based on actual tool output if needed)
            print("✅ Sent.")
            
            # Optional: Detailed debug output if needed
            # print(result.stdout)

        except subprocess.CalledProcessError as e:
            print(f"\n❌ Failed to submit {tx_file}!")
            print("Error Output:", e.stderr)
            print("Standard Output:", e.stdout)
            
            # Decide if you want to stop on error or continue
            # sys.exit(1) 
        
        # Optional: Sleep to be gentle on the node (avoids 'submit pool full' errors)
        time.sleep(0.5)

    print("\n🎉 Batch submission complete.")

if __name__ == "__main__":
    submit_transactions()