#!/usr/bin/env python3
import subprocess
import json
import sys
import os
import time

# Configuration
TOOLKIT_CMD = "midnight-node-toolkit"
NODE_URL = "ws://ferdie.node.sc.iog.io:9944"
START_INDEX = 20
END_INDEX = 25

def get_balance(index):
    """Gets the balance for a given seed index."""
    seed = f"{index:064}"
    
    cmd = [
        TOOLKIT_CMD, "show-wallet",
        "--seed", seed,
        "--src-url", NODE_URL
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        output = result.stdout
        
        # Mimic sed -n '/^{/,$p': Find lines starting from the first one that begins with '{'
        lines = output.splitlines()
        json_lines = []
        capture = False
        for line in lines:
            if line.strip().startswith('{'):
                capture = True
            if capture:
                json_lines.append(line)
        
        if not json_lines:
            print(f"⚠️  Seed {index}: No JSON output found.")
            return 0
            
        json_str = "\n".join(json_lines)
        data = json.loads(json_str)
        
        # Mimic jq '.utxos[]?.value' | jq -s 'add'
        utxos = data.get("utxos", [])
        if not utxos:
            return 0
            
        total_balance = sum(int(utxo.get("value", 0)) for utxo in utxos)
        return total_balance

    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting balance for seed {index}: {e.stderr.strip()}")
        return 0
    except json.JSONDecodeError:
        print(f"❌ Failed to parse JSON for seed {index}")
        return 0
    except Exception as e:
        print(f"❌ Unexpected error for seed {index}: {e}")
        return 0

def main():
    start_time = time.time()
    print(f"🚀 Checking balances for seeds {START_INDEX} to {END_INDEX} on {NODE_URL}...")
    
    total_sum = 0
    for i in range(START_INDEX, END_INDEX + 1):
        balance = get_balance(i)
        total_sum += balance
        print(f"Seed {i}: {balance}")

    end_time = time.time()
    print(f"\n💰 Total Balance: {total_sum}")
    print(f"⏱️ Total execution time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
