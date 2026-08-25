#!/usr/bin/env python3
"""Idempotent Supabase + Telegram publication adapter for news briefings."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ALLOWED_CATEGORIES = {"news", "it", "trend"}


class PublishConflict(RuntimeError):
    pass


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def first_headline(content: str) -> str:
    match = re.search(r"\*\*([^*]+)\*\*", content)
    return match.group(1).strip() if match else ""


@dataclass
class HttpResponse:
    status: int
    body: bytes = b""


class HttpClient:
    def request(self, request: urllib.request.Request) -> HttpResponse:
        with urllib.request.urlopen(request, timeout=30) as response:
            return HttpResponse(response.status, response.read())


class SupabasePublisher:
    def __init__(self, base_url: str, key: str, http: HttpClient | None = None):
        self.endpoint = base_url.rstrip("/") + "/rest/v1/news_posts"
        self.key = key
        self.http = http or HttpClient()

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}"}

    def publish(self, date: str, category: str, content: str) -> str:
        query = urllib.parse.urlencode({"date": f"eq.{date}", "category": f"eq.{category}", "select": "content"})
        req = urllib.request.Request(f"{self.endpoint}?{query}", headers=self._headers())
        response = self.http.request(req)
        rows = json.loads(response.body or b"[]")
        if rows:
            if all(row.get("content") == content for row in rows):
                return "unchanged"
            raise PublishConflict(f"existing {date}/{category} briefing differs; refusing overwrite")

        payload = json.dumps({"date": date, "category": category, "content": content}, ensure_ascii=False).encode()
        headers = self._headers() | {"Content-Type": "application/json", "Prefer": "return=minimal"}
        req = urllib.request.Request(self.endpoint, data=payload, headers=headers, method="POST")
        response = self.http.request(req)
        if response.status not in (200, 201):
            raise RuntimeError(f"Supabase returned HTTP {response.status}")
        return "created"


class TelegramPublisher:
    def __init__(self, token: str, http: HttpClient | None = None):
        self.endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
        self.http = http or HttpClient()

    def send(self, chat_id: str, text: str) -> None:
        body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(self.endpoint, data=body, method="POST")
        response = self.http.request(req)
        if response.status != 200:
            raise RuntimeError(f"Telegram returned HTTP {response.status}")


def receipt_path(receipt_dir: Path, date: str, category: str) -> Path:
    return receipt_dir / f"{date}-{category}.json"


def write_receipt(path: Path, digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    with os.fdopen(fd, "w") as handle:
        json.dump({"content_sha256": digest}, handle)
    os.replace(temporary, path)


def publish_once(*, date: str, category: str, content: str, web_base: str, chat_id: str,
                 receipt_dir: Path, supabase: SupabasePublisher, telegram: TelegramPublisher) -> dict[str, str]:
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(f"unsupported category: {category}")
    digest = content_hash(content)
    db_result = supabase.publish(date, category, content)
    receipt = receipt_path(receipt_dir, date, category)
    if receipt.exists() and json.loads(receipt.read_text()).get("content_sha256") == digest:
        return {"database": db_result, "telegram": "unchanged"}

    title = {"news": "아침 뉴스", "it": "IT·테크", "trend": "트렌드"}[category]
    message = f"📰 {title} 브리핑"
    teaser = first_headline(content)
    if teaser:
        message += f"\n\n오늘의 헤드라인: {teaser}"
    message += f"\n\n{web_base.rstrip('/')}/news/{date}/{category}"
    telegram.send(chat_id, message)
    write_receipt(receipt, digest)
    return {"database": db_result, "telegram": "sent"}


def read_secret(path: str) -> str:
    return Path(path).read_text().strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--category", required=True, choices=sorted(ALLOWED_CATEGORIES))
    parser.add_argument("--briefing-file", required=True)
    parser.add_argument("--supabase-url", required=True)
    parser.add_argument("--supabase-key-file", required=True)
    parser.add_argument("--telegram-token-file", required=True)
    parser.add_argument("--telegram-chat-id-file", required=True)
    parser.add_argument("--receipt-dir", required=True)
    parser.add_argument("--web-base", default="https://chumji-news.vercel.app")
    args = parser.parse_args()
    result = publish_once(
        date=args.date, category=args.category, content=Path(args.briefing_file).read_text(),
        web_base=args.web_base, chat_id=read_secret(args.telegram_chat_id_file),
        receipt_dir=Path(args.receipt_dir),
        supabase=SupabasePublisher(args.supabase_url, read_secret(args.supabase_key_file)),
        telegram=TelegramPublisher(read_secret(args.telegram_token_file)),
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
