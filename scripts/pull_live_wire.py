#!/usr/bin/env python3
"""Download live wire data from R2 for LOCAL DEVELOPMENT ONLY.

This script is NOT used in CI.  The GitHub workflows (daily.yml,
live_wire.yml) download what they need directly via ``aws s3 cp`` steps.

This is a convenience tool for developers who want to inspect live wire
data locally.  It requires your *personal* AWS/R2 credentials configured
via environment variables (never committed to the repo).

Usage:
    # Set R2 credentials first (e.g. in a .env file sourced by direnv):
    export R2_BUCKET_NAME=your-bucket
    export R2_ACCOUNT_ID=your-account-id
    export AWS_ACCESS_KEY_ID=your-key
    export AWS_SECRET_ACCESS_KEY=your-secret

    python scripts/pull_live_wire.py

Requires the AWS CLI to be installed locally (``brew install awscli`` or
``pip install awscli``).

This populates data/live_wire/ with the latest state, series, and
recent snapshots.  These files are .gitignored working copies of R2
(the source of truth).
"""

import os
import subprocess
import sys


def r2_cp(r2_path: str, local_path: str, recursive: bool = False) -> bool:
    bucket = os.environ.get("R2_BUCKET_NAME")
    account_id = os.environ.get("R2_ACCOUNT_ID")
    if not bucket or not account_id:
        print("ERROR: R2_BUCKET_NAME and R2_ACCOUNT_ID env vars required", file=sys.stderr)
        sys.exit(1)

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    cmd = ["aws", "s3", "cp", f"s3://{bucket}/{r2_path}", local_path,
           "--endpoint-url", endpoint]
    if recursive:
        cmd.append("--recursive")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  skipped {r2_path} (not in R2 yet)")
        return False
    print(f"  downloaded {r2_path} -> {local_path}")
    return True


def main() -> None:
    os.makedirs("data/live_wire/snapshots", exist_ok=True)

    print("Pulling live wire data from R2...")
    r2_cp("latest/live_wire_state.json", "data/live_wire/latest.json")
    r2_cp("latest/live_wire_series.json", "data/live_wire/series.json")
    r2_cp("state/live_wire_state.json", "data/live_wire/state.json")
    r2_cp("snapshots/", "data/live_wire/snapshots/", recursive=True)

    # Decompress any .gz snapshots
    import glob
    for gz in glob.glob("data/live_wire/snapshots/*.jsonl.gz"):
        import gzip
        out = gz.removesuffix(".gz")
        if not os.path.exists(out):
            with gzip.open(gz, "rb") as f_in:
                with open(out, "wb") as f_out:
                    f_out.write(f_in.read())
            print(f"  decompressed {gz}")

    print("Done. Files in data/live_wire/ are .gitignored working copies of R2.")


if __name__ == "__main__":
    main()
