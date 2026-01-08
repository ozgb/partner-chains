import subprocess
import argparse
import sys

def generate_transactions(n_files, toolkit_path="midnight-node-toolkit"):
    """
    Generates n transaction files with increasing amounts.
    """
    
    # Configuration
    base_amount = 1_000_000  # Start at 1 million
    increment = 1_000_000    # Increase by 1 million each time
    
    # Constants from your command
    src_url = "ws://ferdie.node.sc.iog.io:9944"
    # Note: Replace this with your full 32-byte hex seed string
    source_seed = "0000000000000000000000000000000000000000000000000000000000000001" 
    token_type = "0000000000000000000000000000000000000000000000000000000000000000"
    dest_address = "mn_addr_undeployed1gkasr3z3vwyscy2jpp53nzr37v7n4r3lsfgj6v5g584dakjzt0xqun4d4r"
    proof_server = "https://lace-proof-pub.preview.midnight.network"

    print(f"🚀 Starting generation of {n_files} transaction files...")

    for i in range(1, n_files + 1):
        # Calculate amount: 1M, 2M, 3M...
        current_amount = base_amount + (i - 1) * increment
        print(f"Current amount: {current_amount}")
        # Define filename: tx_1.json, tx_2.json...
        filename = f"tx_{i}.json"
        
        # Construct the command
        cmd = [
            toolkit_path, "generate-txs", "single-tx",
            "--src-url", src_url,
            "--source-seed", source_seed,
            "--unshielded-amount", str(current_amount),
            "--unshielded-token-type", token_type,
            "--destination-address", dest_address,
            "--dest-file", filename,
            # "--proof-server", proof_server
        ]
        print(f"Executing command: {' '.join(cmd)}")
        # Execute the command
        try:
            print(f"[{i}/{n_files}] Generating {filename} with amount {current_amount}...", end=" ", flush=True)
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✅ Done.")
            # if result.stdout:
            #     print(result.stdout)
            # if result.stderr:
            #     print(result.stderr)
        except subprocess.CalledProcessError as e:
            print("\n❌ Error generating transaction!")
            print("Standard Output:", e.stdout)
            print("Standard Error:", e.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print(f"\n❌ Error: Could not find executable '{toolkit_path}'. Make sure it is in your PATH or current directory.")
            sys.exit(1)

    print("\n🎉 All transactions generated successfully.")

if __name__ == "__main__":
    # You can pass the number of files as an argument: python generate_txs.py 5
    # Default is 5 if no argument provided
    num_files = 5
    if len(sys.argv) > 1:
        try:
            num_files = int(sys.argv[1])
        except ValueError:
            print("Usage: python generate_txs.py <number_of_files>")
            sys.exit(1)

    generate_transactions(num_files)