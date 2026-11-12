import argparse
import os
import random
import shutil
import sys
from src.exporter import export_all
from src.master_gen import EventTracker, generate_master_data
from src.returns_gen import generate_returns_lifecycle
from src.validator import validate_dataset

SCALE_PRESETS = {
    "starter": {"orders": 600, "returns": 100, "return_lines": 160},
    "full": {"orders": 30000, "returns": 5000, "return_lines": 8000},
}


def run_pipeline(seed: int, orders: int, returns: int, return_lines: int, output_dir: str, scale_name: str, cmd_str: str):
    rng = random.Random(seed)
    event_tracker = EventTracker()

    customers, order_rows, order_line_rows = generate_master_data(rng, orders, event_tracker)
    return_tables = generate_returns_lifecycle(rng, order_rows, order_line_rows, returns, return_lines, event_tracker)

    tables = {
        "customers": customers,
        "orders": order_rows,
        "order_lines": order_line_rows,
        **return_tables,
        "state_event_log": event_tracker.events,
    }

    report = validate_dataset(tables)
    if not report["passed"]:
        print("VALIDATION FAILED:", report["errors"])
        sys.exit(1)

    manifest = export_all(tables, report, output_dir, seed, scale_name, cmd_str)
    return report, manifest


def main():
    parser = argparse.ArgumentParser(description="Deterministic E-Commerce Returns & RMA Synthetic Data Generator")
    parser.add_argument("--seed", type=int, default=20261022, help="Fixed RNG seed (default: 20261022)")
    parser.add_argument("--scale", choices=["starter", "full"], default="full", help="Dataset scale preset")
    parser.add_argument("--orders", type=int, default=None, help="Override order count")
    parser.add_argument("--returns", type=int, default=None, help="Override return request count")
    parser.add_argument("--return-lines", type=int, default=None, help="Override return line count")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    parser.add_argument("--verify-reproducibility", action="store_true", help="Run twice with same seed and compare SHA-256 checksums")
    args = parser.parse_args()

    preset = SCALE_PRESETS[args.scale]
    num_orders = args.orders or preset["orders"]
    num_returns = args.returns or preset["returns"]
    num_return_lines = args.return_lines or preset["return_lines"]
    cmd_str = f"python generate.py --seed {args.seed} --scale {args.scale}"

    print(f"[1/2] Generating dataset (scale={args.scale}, seed={args.seed}, orders={num_orders}, returns={num_returns}, return_lines={num_return_lines})...")
    report1, manifest1 = run_pipeline(args.seed, num_orders, num_returns, num_return_lines, args.output_dir, args.scale, cmd_str)
    print(f"      Validation Passed: {report1['passed']} | Total Anomalies Labelled: {sum(report1['ground_truth_expected_counts'].values())}")

    if args.verify_reproducibility:
        tmp_dir = f"{args.output_dir}_repro_check"
        print(f"[2/2] Running second pass into '{tmp_dir}' to verify bit-for-bit reproducibility...")
        report2, manifest2 = run_pipeline(args.seed, num_orders, num_returns, num_return_lines, tmp_dir, args.scale, cmd_str)

        counts_match = manifest1["row_counts"] == manifest2["row_counts"]
        hashes_match = manifest1["sha256_checksums"] == manifest2["sha256_checksums"]
        shutil.rmtree(tmp_dir, ignore_errors=True)

        if not (counts_match and hashes_match):
            print("REPRODUCIBILITY CHECK FAILED!")
            sys.exit(1)

        print("      Reproducibility Verified: 100% identical row counts and SHA-256 checksums across all 25 exported files.")


if __name__ == "__main__":
    main()
