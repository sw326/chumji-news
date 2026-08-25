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
SYNTHESIS_BATCH_INTERVAL = 3
EXTRACTION_SCHEMA_VERSION = 2


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


def append_ledger(path: Path, manifest_id: str, packet_checksum: str,
                  extraction: dict[str, Any], packet: dict[str, Any]) -> int:
    """Validate and append claim-neutral events, deduplicated by stable id."""
    if extraction.get("stage") != "extraction" or extraction.get("manifest_id") != manifest_id:
        raise ValueError("invalid extraction identity")
    if extraction.get("packet_checksum") != packet_checksum or extraction.get("status") != "completed":
        raise ValueError("invalid extraction result")
    events = extraction.get("events")
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    turns = {(str(t["agent"]), str(t["session_id"]), str(t["message_id"]))
             for t in packet["turns"]}
    existing: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            existing[str(row["event_id"])] = row
    appended = 0
    for raw in events:
        if not isinstance(raw, dict):
            raise ValueError("event must be an object")
        pointer = raw.get("source")
        if not isinstance(pointer, dict):
            raise ValueError("event source missing")
        source_key = (str(pointer.get("agent", "")), str(pointer.get("session_id", "")),
                      str(pointer.get("message_id", "")))
        if source_key not in turns:
            raise ValueError("event source outside packet")
        observation = str(raw.get("observation", "")).strip()
        if not observation or len(observation) > 600:
            raise ValueError("invalid bounded observation")
        evidence_kind = str(raw.get("evidence_kind", ""))
        if evidence_kind not in {"explicit_statement", "observed_choice", "correction",
                                 "counterexample", "ambiguity"}:
            raise ValueError("invalid evidence kind")
        canonical = {"manifest_id": manifest_id, "source": pointer,
                     "observation": observation, "evidence_kind": evidence_kind}
        event_id = "event-" + checksum(canonical)[:24]
        row = {"schema_version": EXTRACTION_SCHEMA_VERSION, "event_id": event_id,
               "manifest_id": manifest_id, "packet_checksum": packet_checksum,
               "source": pointer, "timestamp": str(raw.get("timestamp", "")),
               "context": str(raw.get("context", ""))[:400], "observation": observation,
               "evidence_kind": evidence_kind,
               "origin": str(raw.get("origin", "unclear")),
               "alternatives": [str(x)[:300] for x in raw.get("alternatives", []) if isinstance(x, str)][:4],
               "uncertainty": str(raw.get("uncertainty", ""))[:400],
               "sensitive_excluded": bool(raw.get("sensitive_excluded", False)),
               "supersedes": raw.get("supersedes")}
        if event_id not in existing:
            existing[event_id] = row
            appended += 1
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                      for row in existing.values())
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".events.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return appended


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
        state_path = args.state_dir / "state-v2.json"
        state = load_json(state_path, {"version": 2, "cursor": ["", ""],
                                      "completed_extractions_since_synthesis": 0})
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
        result_path, prompt_path = run_dir / "extraction-result.json", run_dir / "extraction-prompt.md"
        result_path.unlink(missing_ok=True)
        atomic_json(packet_path, packet)
        atomic_json(manifest_path, {"version": 1, "manifest_id": manifest_id, "created_at": created_at,
                    "packet_checksum": packet_checksum, "start_cursor": list(batch[0].order),
                    "end_cursor": list(batch[-1].order), "turn_count": len(batch),
                    "normalized_chars": sum(item.normalized_chars for item in batch),
                    "source_files": sorted({f"{item.agent}/{item.session_file}" for item in batch}),
                    "active_and_archives": True, "schema_errors": []})
        prompt_path.write_text(
            f"Use the longitudinal-observation-audit skill Stage A blind extraction only.\n\n"
            f"Manifest: {manifest_path}\nPacket: {packet_path}\nRequired result: {result_path}\n\n"
            "Do not read the personal wiki, existing hypotheses, prior audit results, profiles, or prior extraction "
            "sessions. Do not edit or commit the wiki. Use judgment to select only claim-neutral observations that "
            "could plausibly matter across sessions, directly correct a durable interpretation, or provide useful "
            "counterevidence. Do not exhaustively code every preference, acceptance, or ordinary conversational "
            "choice. Merge nearby statements that express the same bounded choice. "
            "Each event must contain source {agent, session_id, message_id}, timestamp, bounded context, observation "
            "(max 600 chars), evidence_kind (explicit_statement, observed_choice, correction, counterexample, or "
            "ambiguity), origin (user_originated, assistant_proposed_then_accepted, or unclear), alternatives, "
            "uncertainty, and sensitive_excluded. Zero events is valid. Do not assign traits, candidates, scores, "
            f"or verdicts. Write JSON with stage='extraction', manifest_id={manifest_id!r}, "
            f"packet_checksum={packet_checksum!r}, status='completed', events=[...], and coverage.\n",
            encoding="utf-8")
        os.chmod(prompt_path, 0o600)
        if args.prepare_only:
            print(json.dumps({"status": "prepared", "manifest": str(manifest_path)}, ensure_ascii=False))
            return 0
        attempt_id = checksum({"manifest_id": manifest_id, "created_at": created_at})[:10]
        command = [args.openclaw_bin, "agent", "--agent", "wiki-lab", "--session-key",
                   f"agent:wiki-lab:longitudinal-extract:{manifest_id}:{attempt_id}", "--message-file", str(prompt_path),
                   "--thinking", "high", "--timeout", str(args.agent_timeout), "--json"]
        completed = subprocess.run(command, text=True, capture_output=True, timeout=args.agent_timeout + 60)
        if completed.returncode != 0 or not result_path.exists():
            packet_path.unlink(missing_ok=True)
            prompt_path.unlink(missing_ok=True)
            print(json.dumps({"status": "agent_failed", "returncode": completed.returncode}))
            return 3
        result = load_json(result_path, {})
        try:
            appended = append_ledger(args.state_dir / "ledger" / "events.jsonl", manifest_id,
                                     packet_checksum, result, packet)
        except (ValueError, KeyError, json.JSONDecodeError):
            packet_path.unlink(missing_ok=True)
            prompt_path.unlink(missing_ok=True)
            print('{"status":"invalid_extraction"}')
            return 4
        state.update({"version": 2, "cursor": list(batch[-1].order), "last_completed_manifest": manifest_id,
                      "last_completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                      "completed_extractions_since_synthesis":
                          int(state.get("completed_extractions_since_synthesis", 0)) + 1})
        atomic_json(state_path, state)
        packet_path.unlink(missing_ok=True)
        prompt_path.unlink(missing_ok=True)
        synthesis = "not_due"
        if int(state["completed_extractions_since_synthesis"]) >= args.synthesis_batch_interval:
            ledger_checksum = checksum((args.state_dir / "ledger" / "events.jsonl").read_text(encoding="utf-8"))
            synthesis_id = "synthesis-" + checksum({"cursor": state["cursor"],
                                                     "ledger": ledger_checksum})[:20]
            synthesis_dir = args.state_dir / "syntheses" / synthesis_id
            synthesis_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            synthesis_result = synthesis_dir / "result.json"
            synthesis_prompt = synthesis_dir / "prompt.md"
            synthesis_prompt.write_text(
                "Use the longitudinal-observation-audit skill Stage B independent synthesis.\n\n"
                f"Private observation ledger: {args.state_dir / 'ledger' / 'events.jsonl'}\n"
                f"Required result: {synthesis_result}\nSynthesis id: {synthesis_id}\n\n"
                "This run was triggered by an operational sampling cadence, not by proof that the ledger contains a "
                "pattern. Start by assembling possible relationships solely from ledger events. Use descriptive support, "
                "contradiction, ambiguity, context, date, origin, and coverage counts only when they clarify the evidence. "
                "Decide whether events form a useful bounded pattern, remain unrelated observations, contradict an earlier "
                "interpretation, or warrant no finding. Counts and three-context/two-date defaults are judgment aids, not "
                "probabilities, eligibility gates, or automatic confirmation. Only then inspect existing personal review "
                "pages for reconciliation. Include counterevidence, sampling bias, and alternatives. Behavioral hypotheses "
                "remain review. Do not edit the wiki when understanding is unchanged. Follow maintain-personal-wiki for "
                "any justified edit and validation. Write "
                "result JSON with stage='synthesis', synthesis_id, status='completed', ledger_checksum, evidence_counts, "
                "wiki_paths_changed, and commit_identity. A no-finding result is valid. Do not message Telegram.\n",
                encoding="utf-8")
            os.chmod(synthesis_prompt, 0o600)
            synthesis_command = [args.openclaw_bin, "agent", "--agent", "wiki-lab", "--session-key",
                                 f"agent:wiki-lab:longitudinal-synthesis:{synthesis_id}:{attempt_id}", "--message-file",
                                 str(synthesis_prompt), "--thinking", "high", "--timeout", str(args.agent_timeout), "--json"]
            synthesis_run = subprocess.run(synthesis_command, text=True, capture_output=True,
                                           timeout=args.agent_timeout + 60)
            if synthesis_run.returncode == 0 and synthesis_result.exists():
                synthesis_payload = load_json(synthesis_result, {})
                if (synthesis_payload.get("stage") == "synthesis" and
                        synthesis_payload.get("synthesis_id") == synthesis_id and
                        synthesis_payload.get("ledger_checksum") == ledger_checksum and
                        synthesis_payload.get("status") == "completed"):
                    state["completed_extractions_since_synthesis"] = 0
                    state["last_completed_synthesis"] = synthesis_id
                    atomic_json(state_path, state)
                    synthesis = "completed"
                else:
                    synthesis = "invalid"
            else:
                synthesis = "failed"
        print(json.dumps({"status": "completed", "manifest_id": manifest_id,
                          "events_appended": appended, "synthesis": synthesis}))
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
    parser.add_argument("--synthesis-batch-interval", type=int, default=SYNTHESIS_BATCH_INTERVAL)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.threshold_chars <= 0 or args.max_chars < args.threshold_chars or args.synthesis_batch_interval <= 0:
        parser.error("max chars must be >= positive threshold chars")
    return args


def main() -> int:
    args = parse_args()
    if args.mode == "run":
        return run_audit(args)
    state = load_json(args.state_dir / "state-v2.json", {"version": 2, "cursor": ["", ""]})
    status, _ = status_payload(args, state)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 2 if status["schema_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
