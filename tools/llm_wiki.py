#!/usr/bin/env python3
"""Deterministic indexes and lint for the local Markdown research wiki."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
REQUIRED = ("id", "type", "title", "status", "updated_at")
AUTHORED_DIRS = ("sources", "entities", "concepts", "events", "questions", "hypotheses", "notes", "rules")


def parse_scalar(value: str):
    value = value.strip()
    if not value:
        return ""
    if value.startswith("["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    if value in {"true", "false"}:
        return value == "true"
    return value.strip('"\'')


def parse_page(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            for line in text[4:end].splitlines():
                if ":" in line and not line.startswith((" ", "\t")):
                    key, value = line.split(":", 1)
                    meta[key.strip()] = parse_scalar(value)
            body = text[end + 5 :]
    return {"path": path, "meta": meta, "body": body, "links": LINK_RE.findall(body)}


def canonical_url(raw: str) -> str:
    parts = urlsplit(raw.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def load_pages(root: Path) -> list[dict]:
    pages = []
    for directory in AUTHORED_DIRS:
        base = root / directory
        if base.exists():
            pages.extend(parse_page(path) for path in sorted(base.rglob("*.md")))
    if (root / "index.md").exists():
        pages.append(parse_page(root / "index.md"))
    return pages


def build(root: Path, write: bool = True) -> tuple[dict, list[str]]:
    pages = load_pages(root)
    errors: list[str] = []
    lookup: dict[str, str] = {}
    aliases: dict[str, str] = {}
    records: dict[str, dict] = {}

    for page in pages:
        rel = page["path"].relative_to(root).as_posix()
        meta = page["meta"]
        missing = [key for key in REQUIRED if not meta.get(key)]
        if missing:
            errors.append(f"{rel}: missing frontmatter: {', '.join(missing)}")
            continue
        page_id = str(meta["id"])
        if page_id in records:
            errors.append(f"{rel}: duplicate id: {page_id}")
            continue
        records[page_id] = {
            "id": page_id,
            "type": meta["type"],
            "title": meta["title"],
            "status": meta["status"],
            "updated_at": meta["updated_at"],
            "path": rel,
        }
        keys = [page_id, str(meta["title"]), page["path"].stem]
        page_aliases = meta.get("aliases", [])
        if isinstance(page_aliases, str):
            page_aliases = [page_aliases] if page_aliases else []
        keys.extend(str(item) for item in page_aliases)
        for key in keys:
            normalized = key.casefold().strip()
            if normalized in lookup and lookup[normalized] != page_id:
                errors.append(f"{rel}: duplicate title/alias: {key}")
            else:
                lookup[normalized] = page_id
                if key not in {page_id, str(meta["title"]), page["path"].stem}:
                    aliases[key] = page_id

    graph: dict[str, list[str]] = {}
    backlinks: dict[str, list[str]] = defaultdict(list)
    broken: list[dict] = []
    source_map: dict[str, list[str]] = defaultdict(list)
    question_gaps: dict[str, list[str]] = {}

    for page in pages:
        meta = page["meta"]
        page_id = str(meta.get("id", ""))
        if page_id not in records:
            continue
        targets = []
        for raw_target in page["links"]:
            target = lookup.get(raw_target.casefold().strip())
            if not target:
                broken.append({"page": page_id, "target": raw_target})
                errors.append(f"{records[page_id]['path']}: broken link: [[{raw_target}]]")
                continue
            targets.append(target)
            backlinks[target].append(page_id)
        graph[page_id] = sorted(set(targets))
        source_url = meta.get("source_url")
        if source_url:
            source_map[canonical_url(str(source_url))].append(page_id)
        if meta.get("type") == "question":
            required_headings = ("## 현재 답할 수 있는 범위", "## 현재 답할 수 없는 범위", "## 증거 격차")
            missing_headings = [heading[3:] for heading in required_headings if heading not in page["body"]]
            if missing_headings:
                errors.append(f"{records[page_id]['path']}: missing question sections: {', '.join(missing_headings)}")
            gaps = re.findall(r"^- \[ \] (.+)$", page["body"], flags=re.MULTILINE)
            question_gaps[page_id] = gaps

    output = {
        "pages": sorted(records.values(), key=lambda row: (str(row["type"]), str(row["title"]))),
        "aliases": dict(sorted(aliases.items())),
        "graph": dict(sorted(graph.items())),
        "backlinks": {key: sorted(set(value)) for key, value in sorted(backlinks.items())},
        "broken_links": broken,
        "source_map": {key: sorted(value) for key, value in sorted(source_map.items())},
        "question_gaps": dict(sorted(question_gaps.items())),
    }
    if write:
        index_dir = root / "indexes"
        index_dir.mkdir(parents=True, exist_ok=True)
        for name in ("aliases", "graph", "backlinks", "broken_links", "source_map", "question_gaps"):
            target = index_dir / f"_{name}.json"
            target.write_text(json.dumps(output[name], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = ["# Page index", "", "이 파일은 `tools/llm_wiki.py build`가 생성합니다.", ""]
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in output["pages"]:
            grouped[str(row["type"])].append(row)
        for page_type in sorted(grouped):
            lines.extend([f"## {page_type}", ""])
            for row in grouped[page_type]:
                lines.append(f"- [[{row['title']}]] — `{row['status']}` · {row['updated_at']}")
            lines.append("")
        (index_dir / "pages.md").write_text("\n".join(lines), encoding="utf-8")
    return output, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "lint"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "wiki")
    args = parser.parse_args()
    _, errors = build(args.root.resolve(), write=args.command == "build")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"wiki {args.command} ok ({date.today().isoformat()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
