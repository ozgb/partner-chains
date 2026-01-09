import subprocess
import time
import sys

def register_dust_addresses():
    # Configuration
    start_index = 40
    end_index = 99
    
    # Connection details
    node_url = "ws://ferdie.node.sc.iog.io:9944"
    toolkit_path = "midnight-node-toolkit"
    
    # The seed paying the transaction fees
    funding_seed = "0000000000000000000000000000000000000000000000000000000000000001"

    print(f"🚀 Starting dust registration for seeds ending in {start_index} to {end_index}...")

    for i in range(start_index, end_index + 1):
        # Format the seed: Pad '20' to '000...00020' (64 chars total)
        # We treat '20' as the literal suffix the user requested
        wallet_seed = f"{i:064}" 
        
        print(f"\n[{i - start_index + 1}/{(end_index - start_index) + 1}] Registering dust for seed ...{i}...", end=" ", flush=True)

        cmd = [
            toolkit_path, "generate-txs",
            "--src-url", node_url,
            "--dest-url", node_url,
            "register-dust-address",
            "--wallet-seed", wallet_seed,
            "--funding-seed", funding_seed
        ]

        try:
            # Run the command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            print("✅ Success.")
            # print(result.stdout) # Uncomment if you want to see the tx hash

        except subprocess.CalledProcessError as e:
            print(f"\n❌ Failed to register seed ...{i}!")
            print("Error Output:", e.stderr)
            # We continue to the next one even if one fails
            
        except FileNotFoundError:
            print(f"\n❌ Error: Could not find '{toolkit_path}'.")
            sys.exit(1)

        # Wait 2 seconds between registrations to ensure the funding account's 
        # previous transaction is processed/propagated (prevents nonce/dust errors)
        time.sleep(2)

    print("\n🎉 All registration commands completed.")

if __name__ == "__main__":
    register_dust_addresses()