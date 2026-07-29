#!/usr/bin/env python3
"""Collect and render one profile into a date-partitioned shadow directory."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from ailess_briefing import run
from fetch_public_feeds import fetch_profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("morning", "it", "trend"), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    destination = args.output_root / run_date / args.profile
    destination.mkdir(parents=True, exist_ok=True)
    payload = fetch_profile(args.profile)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f"{args.profile}-", suffix=".json", dir=destination
    )
    input_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        final_input = destination / f"{args.profile}-input.json"
        input_path.replace(final_input)
        report = run(args.profile, final_input, destination, run_date)
        print(json.dumps(report, ensure_ascii=False))
    finally:
        if input_path.exists():
            input_path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
