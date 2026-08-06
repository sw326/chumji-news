#!/usr/bin/env python3
"""Safely refresh the cathode market board while preserving the last good copy."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from current_market_board import build_live_board, render_market_board
from customs_trade_compare import DEFAULT_KEY_FILE, load_api_key


def validate_candidate(board: dict[str, Any]) -> None:
    gate = board.get("review_gate", {})
    if not gate.get("automated_sources_complete"):
        raise RuntimeError("자동 수집 출처가 모두 완료되지 않았습니다.")
    blockers = gate.get("blockers", [])
    if blockers:
        raise RuntimeError("검수 차단: " + "; ".join(str(item) for item in blockers))
    expected = {"korea_customs", "US", "HU", "PL", "CN"}
    missing = expected - set(board.get("latest_periods", {}))
    if missing:
        raise RuntimeError("기준월 누락: " + ", ".join(sorted(missing)))


def _atomic_publish(files: list[tuple[Path, Path]], backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backups: list[tuple[Path, Path | None]] = []
    try:
        for staged, target in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / target.name if target.exists() else None
            if backup:
                shutil.copy2(target, backup)
            backups.append((target, backup))
            os.replace(staged, target)
    except Exception:
        for target, backup in reversed(backups):
            if backup and backup.exists():
                shutil.copy2(backup, target)
            elif target.exists():
                target.unlink()
        raise


def refresh(
    api_key: str,
    *,
    output: Path,
    html_output: Path,
    state_output: Path,
    lock_file: Path,
    builder: Callable[[str], dict[str, Any]] = build_live_board,
) -> dict[str, Any]:
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("다른 시장판 갱신이 실행 중입니다.") from exc

        started = datetime.now().astimezone()
        try:
            board = builder(api_key)
            validate_candidate(board)
            html = render_market_board(board)
            with tempfile.TemporaryDirectory(prefix="cathode-refresh-") as temporary:
                temp_dir = Path(temporary)
                staged_json = temp_dir / output.name
                staged_html = temp_dir / html_output.name
                staged_json.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
                staged_html.write_text(html, encoding="utf-8")
                # Parse both staged artifacts before touching the published copy.
                json.loads(staged_json.read_text(encoding="utf-8"))
                if 'id="market-data"' not in staged_html.read_text(encoding="utf-8"):
                    raise RuntimeError("생성된 HTML에 시장 데이터가 없습니다.")
                backup_dir = state_output.parent / "last-good"
                _atomic_publish([(staged_json, output), (staged_html, html_output)], backup_dir)
            status = {
                "status": "published",
                "started_at": started.isoformat(),
                "completed_at": datetime.now().astimezone().isoformat(),
                "latest_periods": board["latest_periods"],
                "china_manual_check": board["review_gate"]["china_manual_check"],
                "published": {"json": str(output), "html": str(html_output)},
            }
        except Exception as exc:
            status = {
                "status": "failed-preserved-last-good",
                "started_at": started.isoformat(),
                "completed_at": datetime.now().astimezone().isoformat(),
                "error": str(exc),
                "published": {"json": str(output), "html": str(html_output)},
            }
            _write_state(state_output, status)
            raise
        _write_state(state_output, status)
        return status


def _write_state(path: Path, status: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(status, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        staged = Path(handle.name)
    os.replace(staged, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="검증본 보존형 양극재 시장판 갱신")
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    parser.add_argument("--census-key-file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/cathode-current-market.json"))
    parser.add_argument("--html-output", type=Path, default=Path("deploy/cathode-current.html"))
    parser.add_argument("--state-output", type=Path, default=Path("output/cathode-refresh-status.json"))
    parser.add_argument("--lock-file", type=Path, default=Path("output/.cathode-refresh.lock"))
    args = parser.parse_args()
    if args.census_key_file:
        census_key = args.census_key_file.read_text(encoding="utf-8").strip()
        if not census_key:
            raise RuntimeError("Census API SecretRef가 비어 있습니다.")
        os.environ["CENSUS_API_KEY"] = census_key
    status = refresh(
        load_api_key(args.key_file), output=args.output, html_output=args.html_output,
        state_output=args.state_output, lock_file=args.lock_file,
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
