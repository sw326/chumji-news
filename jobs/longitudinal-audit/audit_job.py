#!/usr/bin/env python3
"""Prepare bounded owner-conversation batches and wake an audit agent."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

OWNER_ID = "7800641846"
AGENTS = ("main", "wiki-lab", "fin", "dev", "notification", "playground")
TRANSCRIPT_RE = re.compile(r"^[0-9a-f-]+\.jsonl(?:\.(?:reset|deleted)\.\d{4}-\d{2}-\d{2}T[^/]+Z)?$")
DEFAULT_THRESHOLD_CHARS = 30_000
DEFAULT_MAX_CHARS = 45_000


@dataclass(frozen=True)
class Turn:
    order: tuple[str, str]
    agent: str
    session_id: str
    session_file: str
    message_id: str
    timestamp: str
    channel: str
    context: str
    user_text: str

    @property
    def normalized_chars(self) -> int:
        return len(self.user_text) + len(self.context)

    def as_dict(self) -> dict[str, Any]:
        return {"agent": self.agent, "session_id": self.session_id, "session_file": self.session_file,
                "message_id": self.message_id, "timestamp": self.timestamp, "channel": self.channel,
                "assistant_context": self.context, "user_text": self.user_text,
                "normalized_chars": self.normalized_chars}


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(raw, path)
    finally:
        if os.path.exists(raw):
            os.unlink(raw)


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    return "\n".join(item["text"] for item in content
                     if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)).strip()


def transcript_files(agent_root: Path) -> Iterable[tuple[str, Path]]:
    for agent in AGENTS:
        directory = agent_root / agent / "sessions"
        if directory.is_dir():
            for path in sorted(directory.iterdir()):
                if path.is_file() and TRANSCRIPT_RE.fullmatch(path.name):
                    yield agent, path


def parse_transcript(agent: str, path: Path) -> tuple[list[Turn], list[str]]:
    rows: list[dict[str, Any]] = []
    try:
        snapshot = path.read_text(encoding="utf-8")
        # JSONL is delimited by LF only. str.splitlines() also treats legacy
        # control characters embedded in tool output as record boundaries.
        lines = snapshot.split("\n")
        for number, line in enumerate(lines, 1):
            if number == len(lines) and line == "":
                break
            try:
                # Legacy OpenClaw tool-result rows can contain literal control
                # characters inside strings. They are valid transcript payloads
                # for our purposes and must be parsed rather than skipped.
                row = json.loads(line, strict=False)
            except json.JSONDecodeError:
                # An active JSONL can be observed between append writes. Only an
                # incomplete, non-newline-terminated final record is retryable.
                if number == len(lines) and not snapshot.endswith("\n"):
                    break
                return [], [f"{path.name}:{number}:invalid_json"]
            if isinstance(row, dict):
                rows.append(row)
    except OSError as exc:
        return [], [f"{path.name}:read_error:{exc.__class__.__name__}"]
    if not rows or rows[0].get("type") != "session" or not rows[0].get("timestamp"):
        return [], [f"{path.name}:invalid_session_header"]
    session_id = str(rows[0].get("id") or path.name.split(".jsonl", 1)[0])
    turns: list[Turn] = []
    last_assistant = ""
    pending: list[tuple[dict[str, Any], str]] = []
    for row in rows[1:]:
        if row.get("type") != "message" or not isinstance(row.get("message"), dict):
            continue
        message = row["message"]
        if message.get("role") == "assistant":
            value = text_content(message.get("content"))
            if value:
                last_assistant = value[-1200:]
            for user_row, context in pending:
                msg = user_row["message"]
                message_id = str(user_row.get("id") or "")
                timestamp = str(user_row.get("timestamp") or "")
                user_text = text_content(msg.get("content"))
                if message_id and timestamp and user_text:
                    key = f"{agent}:{session_id}:{message_id}"
                    turns.append(Turn((timestamp, key), agent, session_id, path.name, message_id,
                                      timestamp, str(msg.get("sourceChannel") or ""), context, user_text))
            pending.clear()
        elif message.get("role") == "user":
            meta = message.get("__openclaw")
            owner = message.get("senderId") == OWNER_ID or (
                isinstance(meta, dict) and meta.get("senderIsOwner") is True and str(meta.get("senderId")) == OWNER_ID)
            if owner and message.get("sourceChannel") == "telegram":
                pending.append((row, last_assistant))
    return turns, []


def collect(agent_root: Path, cursor: tuple[str, str]) -> tuple[list[Turn], list[str]]:
    by_key: dict[tuple[str, str], Turn] = {}
    errors: list[str] = []
    for agent, path in transcript_files(agent_root):
        turns, found = parse_transcript(agent, path)
        errors.extend(found)
        for turn in turns:
            if turn.order > cursor:
                by_key.setdefault(turn.order, turn)
    return sorted(by_key.values(), key=lambda item: item.order), errors


def make_batch(turns: list[Turn], threshold: int, maximum: int) -> list[Turn]:
    if sum(turn.normalized_chars for turn in turns) < threshold:
        return []
    batch: list[Turn] = []
    total = 0
    for turn in turns:
        if batch and total + turn.normalized_chars > maximum:
            break
        batch.append(turn)
        total += turn.normalized_chars
        if total >= threshold:
            break
    return batch


def checksum(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def status_payload(args: argparse.Namespace, state: dict[str, Any]) -> tuple[dict[str, Any], list[Turn]]:
    raw = state.get("cursor", ["", ""])
    cursor = (str(raw[0]), str(raw[1]))
    turns, errors = collect(args.agent_root, cursor)
    batch = make_batch(turns, args.threshold_chars, args.max_chars)
    return {"ready": bool(batch), "cursor": list(cursor), "unprocessed_turns": len(turns),
            "unprocessed_chars": sum(item.normalized_chars for item in turns), "batch_turns": len(batch),
            "batch_chars": sum(item.normalized_chars for item in batch), "threshold_chars": args.threshold_chars,
            "max_chars": args.max_chars, "schema_errors": errors}, batch


def run_audit(args: argparse.Namespace) -> int:
    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (args.state_dir / "audit.lock").open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('{"status":"locked"}')
            return 0
        state_path = args.state_dir / "state.json"
        state = load_json(state_path, {"version": 1, "cursor": ["", ""]})
        status, batch = status_payload(args, state)
        if status["schema_errors"]:
            print(json.dumps({"status": "rejected", **status}, ensure_ascii=False))
            return 2
        if not batch:
            print(json.dumps({"status": "not_ready", **status}, ensure_ascii=False))
            return 0
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        batch_checksum = checksum([item.as_dict() for item in batch])
        # Stable across retries so a model can reconcile a prior partial run
        # that committed durable knowledge before its result handshake.
        manifest_id = f"batch-{batch_checksum[:20]}"
        packet = {"version": 1, "manifest_id": manifest_id, "turns": [item.as_dict() for item in batch]}
        packet_checksum = checksum(packet)
        run_dir = args.state_dir / "runs" / manifest_id
        run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        packet_path, manifest_path = run_dir / "packet.json", run_dir / "manifest.json"
        result_path, prompt_path = run_dir / "result.json", run_dir / "prompt.md"
        result_path.unlink(missing_ok=True)
        atomic_json(packet_path, packet)
        atomic_json(manifest_path, {"version": 1, "manifest_id": manifest_id, "created_at": created_at,
                    "packet_checksum": packet_checksum, "start_cursor": list(batch[0].order),
                    "end_cursor": list(batch[-1].order), "turn_count": len(batch),
                    "normalized_chars": sum(item.normalized_chars for item in batch),
                    "source_files": sorted({f"{item.agent}/{item.session_file}" for item in batch}),
                    "active_and_archives": True, "schema_errors": []})
        prompt_path.write_text(
            f"Use the longitudinal-observation-audit skill for this dedicated retrospective run.\n\n"
            f"Manifest: {manifest_path}\nPacket: {packet_path}\nRequired result: {result_path}\n\n"
            f"Do not deliver routine results to Telegram. Follow maintain-personal-wiki for durable edits. "
            f"This batch identity is stable across retries: inspect existing canonical review first, and if a prior "
            f"partial run already reflected a finding, reconcile it and complete without duplicating the knowledge. "
            f"Before ending, write result JSON with manifest_id={manifest_id!r}, packet_checksum={packet_checksum!r}, "
            f"audit_status completed/rejected/failed, processed_end_cursor={list(batch[-1].order)!r}, "
            "finding_counts, wiki_paths_changed, and commit_identity. A completed no-finding result is valid.\n",
            encoding="utf-8")
        os.chmod(prompt_path, 0o600)
        if args.prepare_only:
            print(json.dumps({"status": "prepared", "manifest": str(manifest_path)}, ensure_ascii=False))
            return 0
        command = [args.openclaw_bin, "agent", "--agent", "wiki-lab", "--session-key",
                   "agent:wiki-lab:longitudinal-audit", "--message-file", str(prompt_path),
                   "--thinking", "high", "--timeout", str(args.agent_timeout), "--json"]
        completed = subprocess.run(command, text=True, capture_output=True, timeout=args.agent_timeout + 60)
        if completed.returncode != 0 or not result_path.exists():
            packet_path.unlink(missing_ok=True)
            prompt_path.unlink(missing_ok=True)
            print(json.dumps({"status": "agent_failed", "returncode": completed.returncode}))
            return 3
        result = load_json(result_path, {})
        valid = (result.get("audit_status") == "completed" and result.get("manifest_id") == manifest_id
                 and result.get("packet_checksum") == packet_checksum
                 and result.get("processed_end_cursor") == list(batch[-1].order))
        if not valid:
            packet_path.unlink(missing_ok=True)
            prompt_path.unlink(missing_ok=True)
            print('{"status":"invalid_result"}')
            return 4
        state.update({"version": 1, "cursor": list(batch[-1].order), "last_completed_manifest": manifest_id,
                      "last_completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})
        atomic_json(state_path, state)
        packet_path.unlink(missing_ok=True)
        prompt_path.unlink(missing_ok=True)
        print(json.dumps({"status": "completed", "manifest_id": manifest_id}))
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("status", "run"))
    parser.add_argument("--agent-root", type=Path, default=Path.home() / ".openclaw" / "agents")
    parser.add_argument("--state-dir", type=Path, default=Path.home() / "Library" / "Application Support" / "chumji-longitudinal-audit")
    parser.add_argument("--threshold-chars", type=int, default=DEFAULT_THRESHOLD_CHARS)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--openclaw-bin", default="openclaw")
    parser.add_argument("--agent-timeout", type=int, default=1800)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.threshold_chars <= 0 or args.max_chars < args.threshold_chars:
        parser.error("max chars must be >= positive threshold chars")
    return args


def main() -> int:
    args = parse_args()
    if args.mode == "run":
        return run_audit(args)
    state = load_json(args.state_dir / "state.json", {"version": 1, "cursor": ["", ""]})
    status, _ = status_payload(args, state)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 2 if status["schema_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
