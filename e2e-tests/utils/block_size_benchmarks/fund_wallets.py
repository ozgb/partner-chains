#!/usr/bin/env python3
import subprocess
import json
import sys
import time
import random

# Configuration
TOOLKIT_CMD = "midnight-node-toolkit"
SRC_URL = "ws://ferdie.node.sc.iog.io:9944"
DEST_URL = "ws://ferdie.node.sc.iog.io:9944"
SOURCE_SEED = "0000000000000000000000000000000000000000000000000000000000000001"
TOKEN_TYPE = "0000000000000000000000000000000000000000000000000000000000000000"
BASE_AMOUNT = 1000000*10**6
START_INDEX = 40
END_INDEX = 99

def run_command(cmd):
    """Runs a command and returns stdout if successful, exits otherwise."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error executing command: {' '.join(cmd)}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n❌ Error: Executable '{cmd[0]}' not found. Ensure it is in your PATH.")
        sys.exit(1)

def get_wallet_address(index):
    """Creates a wallet seed and retrieves its address."""
    # Seed format: 00..xx where xx is 10-19
    # 62 zeros + 2 digits
    seed = "0" * 62 + str(index)
    
    cmd = [
        TOOLKIT_CMD, "show-address",
        "--network", "undeployed",
        "--seed", seed
    ]
    
    output = run_command(cmd)
    try:
        data = json.loads(output)
        return data["unshielded"]
    except json.JSONDecodeError:
        print(f"\n❌ Failed to parse JSON from show-address output: {output}")
        sys.exit(1)
    except KeyError:
        print(f"\n❌ JSON output does not contain 'unshielded' field: {output}")
        sys.exit(1)

def fund_address(address):
    """Funds the given address using the source seed."""
    # Randomize amount: BASE_AMOUNT +/- [1, 100]
    amount = str(BASE_AMOUNT + random.randint(-100, 100))

    cmd = [
        TOOLKIT_CMD, "generate-txs", "single-tx",
        "--source-seed", SOURCE_SEED,
        "--src-url", SRC_URL,
        "--unshielded-amount", amount,
        "--unshielded-token-type", TOKEN_TYPE,
        "--destination-address", address,
        "--dest-url", DEST_URL
    ]
    
    # Run the command (output is captured but we assume success if no error raised)
    run_command(cmd)

def main():
    print("🚀 Starting wallet creation and funding script...")
    
    new_addresses = []
    
    # 1. Create 10 wallets
    print(f"\n--- Step 1: Generating Wallets (Seeds {START_INDEX}-{END_INDEX}) ---")
    for i in range(START_INDEX, END_INDEX + 1):
        print(f"Generating wallet {i-9}/10 (Seed suffix {i})...", end=" ", flush=True)
        addr = get_wallet_address(i)
        new_addresses.append(addr)
        print(f"✅ {addr}")
        
    # 2. Fund the wallets
    print("\n--- Step 2: Funding Wallets ---")
    for i, addr in enumerate(new_addresses, 1):
        print(f"Funding wallet {i}/10 ({addr})...", end=" ", flush=True)
        fund_address(addr)
        print("✅ Sent")
        
        # Wait a bit between transactions to ensure nonce propagation
        if i < len(new_addresses):
            time.sleep(2)

    print("\n🎉 All operations completed successfully.")

if __name__ == "__main__":
    main()
