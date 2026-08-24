#!/usr/bin/env python3
"""Build a small, privacy-safe candidate index for the weekly skill audit.

The collector streams active OpenClaw transcripts and emits counts plus bounded
session references. It never emits message bodies, tool arguments, or results.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SKILL_PATH_RE = re.compile(
    r"(?:^|[/\\])skills[/\\]([a-z0-9][a-z0-9._-]*)[/\\]SKILL\.md\b",
    re.IGNORECASE,
)
STRONG_CORRECTION_RE = re.compile(
    r"(오판|잘못(?:됐|했|된|한)|과잉\s*진단|근거가\s*부족|하지\s*말|"
    r"왜\s+.*(?:이상|실패)|incorrect|wrong|overdiagnos|do not|don't)",
    re.IGNORECASE,
)
ERROR_RE = re.compile(
    r"(^|\b)(error|failed|failure|exception|traceback|timed?\s*out)(\b|:)",
    re.IGNORECASE,
)


def parse_time(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def compact_ref(agent: str, session_id: str, updated_at: datetime, path: Path) -> dict[str, str]:
    return {
        "agent": agent,
        "session_id": session_id,
        "updated_at": updated_at.isoformat().replace("+00:00", "Z"),
        "path": str(path),
    }


def string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_values(child)


def content_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    message = record.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    return [item for item in content if isinstance(item, dict)] if isinstance(content, list) else []


def record_role(record: dict[str, Any]) -> str | None:
    message = record.get("message")
    return message.get("role") if isinstance(message, dict) else None


def user_text(record: dict[str, Any]) -> str:
    if record_role(record) != "user":
        return ""
    message = record.get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    return " ".join(
        item.get("text", "")
        for item in content_blocks(record)
        if item.get("type") == "text" and isinstance(item.get("text"), str)
    )


@dataclass
class SessionSignals:
    skills: set[str] = field(default_factory=set)
    tool_calls: int = 0
    tool_errors: int = 0
    correction: bool = False
    schema_errors: int = 0


def scan_transcript(path: Path) -> SessionSignals:
    signals = SessionSignals()
    first_record = True
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    signals.schema_errors += 1
                    continue
                if first_record:
                    first_record = False
                    if record.get("type") != "session":
                        signals.schema_errors += 1
                # OpenClaw user envelopes can include a long quoted history. The
                # actual current request is at the end, so avoid treating quoted
                # corrections from earlier turns as new evidence.
                if STRONG_CORRECTION_RE.search(user_text(record)[-1200:]):
                    signals.correction = True
                for block in content_blocks(record):
                    block_type = block.get("type")
                    if block_type == "toolCall":
                        signals.tool_calls += 1
                        arguments = block.get("arguments", block.get("input", {}))
                        for text in string_values(arguments):
                            signals.skills.update(match.group(1).lower() for match in SKILL_PATH_RE.finditer(text))
                    elif block_type == "toolResult":
                        raw_error = block.get("isError") is True
                        result_text = " ".join(string_values(block.get("text", block.get("content", ""))))
                        if raw_error or ERROR_RE.search(result_text[:1000]):
                            signals.tool_errors += 1
    except OSError:
        signals.schema_errors += 1
    return signals


def active_sessions(root: Path, cutoff: datetime) -> tuple[list[tuple[str, str, datetime, Path]], dict[str, int]]:
    rows: list[tuple[str, str, datetime, Path]] = []
    coverage = {"agents": 0, "index_entries": 0, "recent_entries": 0, "missing_files": 0}
    seen: set[Path] = set()
    agents_root = root / "agents"
    for index_path in sorted(agents_root.glob("*/sessions/sessions.json")):
        coverage["agents"] += 1
        agent = index_path.parents[1].name
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(index, dict):
            continue
        coverage["index_entries"] += len(index)
        for entry in index.values():
            if not isinstance(entry, dict):
                continue
            updated_at = parse_time(entry.get("updatedAt"))
            if updated_at is None or updated_at < cutoff:
                continue
            session_id = str(entry.get("sessionId", ""))
            raw_path = entry.get("sessionFile")
            path = Path(raw_path) if isinstance(raw_path, str) else index_path.parent / f"{session_id}.jsonl"
            path = path.expanduser().resolve()
            if path.name.endswith(".trajectory.jsonl") or ".reset." in path.name or ".deleted." in path.name:
                continue
            if path in seen:
                continue
            seen.add(path)
            coverage["recent_entries"] += 1
            if not path.is_file():
                coverage["missing_files"] += 1
                continue
            rows.append((agent, session_id, updated_at, path))
    return rows, coverage


def collect(root: Path, now: datetime, days: int, max_candidates: int, max_sessions: int) -> dict[str, Any]:
    cutoff = now - timedelta(days=days)
    sessions, coverage = active_sessions(root, cutoff)
    per_skill: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"sessions": 0, "manual_loads": 0, "tool_errors": 0, "corrections": 0, "refs": []}
    )
    totals = {"transcripts_scanned": 0, "tool_calls_scanned": 0, "tool_errors_seen": 0, "schema_errors": 0}
    for agent, session_id, updated_at, path in sessions:
        signals = scan_transcript(path)
        totals["transcripts_scanned"] += 1
        totals["tool_calls_scanned"] += signals.tool_calls
        totals["tool_errors_seen"] += signals.tool_errors
        totals["schema_errors"] += signals.schema_errors
        for skill in signals.skills:
            row = per_skill[skill]
            row["sessions"] += 1
            row["manual_loads"] += 1
            # Error volume belongs to the session, not automatically to every
            # loaded skill. Use one candidate signal per affected session.
            row["tool_errors"] += int(signals.tool_errors > 0)
            row["corrections"] += int(signals.correction)
            row["refs"].append(compact_ref(agent, session_id, updated_at, path))

    candidates = []
    for skill, row in per_skill.items():
        score = row["corrections"] * 100 + min(row["tool_errors"], 20) * 5 + min(row["manual_loads"], 10)
        refs = sorted(row.pop("refs"), key=lambda item: item["updated_at"], reverse=True)[:max_sessions]
        candidates.append({"skill": skill, "score": score, **row, "session_refs": refs})
    candidates.sort(key=lambda row: (-row["score"], row["skill"]))
    return {
        "schema": "skill-health-candidates.v1",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "window_start": cutoff.isoformat().replace("+00:00", "Z"),
        "privacy": "No message bodies, tool arguments, or tool results are emitted.",
        "coverage": {**coverage, **totals},
        "candidates": candidates[:max_candidates],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openclaw-root", type=Path, default=Path.home() / ".openclaw")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--max-sessions-per-candidate", type=int, default=3)
    parser.add_argument("--now", help="ISO-8601 UTC timestamp; intended for deterministic tests")
    args = parser.parse_args()
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None or args.days < 1 or args.max_candidates < 1 or args.max_sessions_per_candidate < 1:
        parser.error("invalid time or non-positive limit")
    result = collect(args.openclaw_root.expanduser().resolve(), now, args.days, args.max_candidates, args.max_sessions_per_candidate)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
