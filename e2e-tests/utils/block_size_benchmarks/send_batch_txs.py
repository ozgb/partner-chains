import subprocess
import glob
import json
import os
import sys
import time
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
    "tom",
]

SEND_MESSAGES = [
    "SENDING",
    "SENT",
    "BEST_BLOCK",
    "FAILED_TO_REACH_BEST_BLOCK",
    "FINALIZED",
    "FAILED_TO_FINALIZE",
]


def submit_txs(dest_urls, tx_files, toolkit_path, rate=30) -> dict[str, str | int]:
    # Ensure absolute path for the source file since we change CWD

    cmd = [toolkit_path, "generate-txs", "send", "--rate", str(rate)]

    # Append the txs to the command
    for tx_file in tx_files:
        abs_tx_file = os.path.abspath(tx_file)
        cmd.extend(["--src-file", abs_tx_file])

    for dest_url in dest_urls:
        cmd.extend(["--dest-url", dest_url])

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            exec_start = time.time()
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, cwd=temp_dir
            )
            exec_time = time.time() - exec_start

        traces = {}
        if result.stderr:
            for line in result.stderr.splitlines():
                try:
                    parsed_log = json.loads(line)
                    if (
                        "message" in parsed_log
                        and parsed_log["message"] in SEND_MESSAGES
                    ):
                        midnight_tx_hash = parsed_log["midnight_tx_hash"]
                        if midnight_tx_hash not in traces:
                            traces[midnight_tx_hash] = {}
                        message_type = parsed_log["message"]
                        traces[midnight_tx_hash][message_type] = parsed_log
                except (json.JSONDecodeError, TypeError):
                    # Failed to decode line as JSON
                    pass
        print(f"✅ [Exec: {exec_time:.4f}s]")
        return traces

    except subprocess.CalledProcessError as e:
        print("\n❌ Failed to submit txs!")
        print("Error Output:", e.stderr)
        raise e


def analyze_traces(traces):
    """Analyze transaction traces for timing metrics and success rates.

    Args:
        traces: Dict mapping midnight_tx_hash to dict of message_type -> trace data

    Returns:
        Dict containing analysis results
    """
    if not traces:
        print("No traces to analyze")
        return {}

    total_txs = len(traces)

    # Counters for success/failure
    sent_count = 0
    best_block_count = 0
    finalized_count = 0
    failed_best_block_count = 0
    failed_finalize_count = 0

    # Timing metrics (in milliseconds)
    submission_latencies = []  # SENDING -> SENT
    block_latencies = []  # SENT -> BEST_BLOCK
    finalization_latencies = []  # BEST_BLOCK -> FINALIZED
    total_latencies = []  # SENDING -> FINALIZED

    # Track first/last timestamps for send rate calculation
    first_sending_ts = None
    last_sending_ts = None

    for tx_hash, events in traces.items():
        sending = events.get("SENDING")
        sent = events.get("SENT")
        best_block = events.get("BEST_BLOCK")
        finalized = events.get("FINALIZED")
        failed_best = events.get("FAILED_TO_REACH_BEST_BLOCK")
        failed_final = events.get("FAILED_TO_FINALIZE")

        # Track send timestamps for rate calculation
        if sending:
            ts = sending["timestamp"]
            if first_sending_ts is None or ts < first_sending_ts:
                first_sending_ts = ts
            if last_sending_ts is None or ts > last_sending_ts:
                last_sending_ts = ts

        # Count outcomes
        if sent:
            sent_count += 1
        if best_block:
            best_block_count += 1
        if finalized:
            finalized_count += 1
        if failed_best:
            failed_best_block_count += 1
        if failed_final:
            failed_finalize_count += 1

        # Calculate latencies
        if sending and sent:
            submission_latencies.append(sent["timestamp"] - sending["timestamp"])
        if sent and best_block:
            block_latencies.append(best_block["timestamp"] - sent["timestamp"])
        if best_block and finalized:
            finalization_latencies.append(
                finalized["timestamp"] - best_block["timestamp"]
            )
        if sending and finalized:
            total_latencies.append(finalized["timestamp"] - sending["timestamp"])

    def calc_stats(values):
        if not values:
            return None
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(sorted_vals) / n,
            "median": sorted_vals[n // 2],
            "p95": sorted_vals[int(n * 0.95)] if n >= 20 else sorted_vals[-1],
            "count": n,
        }

    # Calculate send rate (txs/second)
    send_rate = None
    if first_sending_ts and last_sending_ts and first_sending_ts != last_sending_ts:
        duration_sec = (last_sending_ts - first_sending_ts) / 1000.0
        send_rate = total_txs / duration_sec if duration_sec > 0 else None

    results = {
        "total_transactions": total_txs,
        "sent_count": sent_count,
        "best_block_count": best_block_count,
        "finalized_count": finalized_count,
        "failed_best_block_count": failed_best_block_count,
        "failed_finalize_count": failed_finalize_count,
        "send_rate_tps": send_rate,
        "submission_latency_ms": calc_stats(submission_latencies),
        "block_inclusion_latency_ms": calc_stats(block_latencies),
        "finalization_latency_ms": calc_stats(finalization_latencies),
        "total_latency_ms": calc_stats(total_latencies),
    }

    # Print summary
    print("\n" + "=" * 60)
    print("TRANSACTION ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total Transactions: {total_txs}")
    print(f"  Sent:       {sent_count} ({100 * sent_count / total_txs:.1f}%)")
    print(
        f"  In Block:   {best_block_count} ({100 * best_block_count / total_txs:.1f}%)"
    )
    print(f"  Finalized:  {finalized_count} ({100 * finalized_count / total_txs:.1f}%)")
    if failed_best_block_count or failed_finalize_count:
        print(f"  Failed Block: {failed_best_block_count}")
        print(f"  Failed Final: {failed_finalize_count}")

    if send_rate:
        print(f"\nSend Rate: {send_rate:.2f} tx/s")

    def print_latency_stats(name, stats):
        if stats:
            print(f"\n{name}:")
            print(f"  Min: {stats['min']:.0f}ms  Max: {stats['max']:.0f}ms")
            print(
                f"  Avg: {stats['avg']:.0f}ms  Median: {stats['median']:.0f}ms  P95: {stats['p95']:.0f}ms"
            )

    print_latency_stats(
        "Submission Latency (SENDING->SENT)", results["submission_latency_ms"]
    )
    print_latency_stats(
        "Block Inclusion Latency (SENT->BEST_BLOCK)",
        results["block_inclusion_latency_ms"],
    )
    print_latency_stats(
        "Finalization Latency (BEST_BLOCK->FINALIZED)",
        results["finalization_latency_ms"],
    )
    print_latency_stats(
        "Total Latency (SENDING->FINALIZED)", results["total_latency_ms"]
    )
    print("=" * 60 + "\n")

    return results


def submit_transactions(toolkit_path="midnight-node-toolkit"):
    start_time = time.time()
    # 1. Find all matching files
    files = glob.glob(os.path.join("txs", "tx_*.mn"))

    if not files:
        print("❌ No files found matching 'tx_*.mn'")
        sys.exit(1)

    print(f"🚀 Found {len(files)} transaction files to submit.")

    dest_urls = [f"ws://{relay}.node.sc.iog.io:9944" for relay in RELAYS]

    traces = submit_txs(dest_urls, files, toolkit_path)

    end_time = time.time()
    print("\n🎉 Batch submission complete.")
    print(f"⏱️ Total execution time: {end_time - start_time:.2f} seconds")

    analyze_traces(traces)


if __name__ == "__main__":
    submit_transactions()
