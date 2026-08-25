#!/usr/bin/env python3
"""Run the imported fresh-food collector in an ops-owned shadow directory."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ITEMS = ("배추", "대파", "양파", "무")


def default_template_path() -> pathlib.Path:
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    return repo_root / "public/fresh-food/index.html"


def validate_report(report: dict) -> dict:
    items = report.get("items") if isinstance(report.get("items"), list) else []
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    labels = [str(item.get("label") or "") for item in items if isinstance(item, dict)]
    covered = [name for name in ITEMS if any(name in label for label in labels)]
    return {
        "expected_items": list(ITEMS),
        "covered_items": covered,
        "missing_items": [name for name in ITEMS if name not in covered],
        "item_count": len(items),
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=pathlib.Path, required=True)
    parser.add_argument("--template", type=pathlib.Path)
    parser.add_argument("--data-key-file", type=pathlib.Path, required=True)
    parser.add_argument("--garak-password-file", type=pathlib.Path, required=True)
    args = parser.parse_args()

    template = args.template or default_template_path()
    run_date = dt.datetime.now().astimezone().strftime("%Y-%m-%d")
    output_dir = args.output_root / run_date
    output_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DATA_GO_KR_KEY_FILE"] = str(args.data_key_file)
    env["GARAK_PASSWORD_FILE"] = str(args.garak_password_file)
    command = [
        sys.executable,
        "-B",
        str(pathlib.Path(__file__).with_name("generate_price_view.py")),
        "--items",
        *ITEMS,
        "--side",
        "소매",
        "--snapshot",
        "--template",
        str(template),
        "--output-dir",
        str(output_dir),
    ]
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    report_path = output_dir / "report.json"
    if result.returncode and not report_path.exists():
        print(result.stderr, file=sys.stderr)
        return result.returncode

    report = json.loads(report_path.read_text(encoding="utf-8"))
    validation = validate_report(report)
    snapshots = sorted(output_dir.glob("snapshot-*.html"), key=lambda path: path.stat().st_mtime)
    if not snapshots:
        raise SystemExit("shadow snapshot was not generated")
    snapshot = snapshots[-1]
    status = {
        "run_date": run_date,
        "generated_at": report.get("generatedAt"),
        "model_route": "none",
        "publication": "disabled",
        "collector_exit_code": result.returncode,
        "report_path": str(report_path),
        "snapshot_path": str(snapshot),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        **validation,
    }
    (output_dir / "shadow-status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, ensure_ascii=False))
    if result.returncode:
        return result.returncode
    return 0 if validation["item_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
