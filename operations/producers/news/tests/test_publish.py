import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs

from operations.producers.news.adapters.publish import (
    HttpResponse, PublishConflict, SupabasePublisher, TelegramPublisher, publish_once
)


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


class PublishTests(unittest.TestCase):
    def test_create_then_send_and_receipt_prevents_duplicate_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_http = FakeHttp([HttpResponse(200, b"[]"), HttpResponse(201), HttpResponse(200, json.dumps([{"content": "**Headline** body"}]).encode())])
            tg_http = FakeHttp([HttpResponse(200)])
            kwargs = dict(date="2026-08-25", category="news", content="**Headline** body", web_base="https://example.test",
                          chat_id="-1", receipt_dir=Path(temporary),
                          supabase=SupabasePublisher("https://db.test", "key", db_http),
                          telegram=TelegramPublisher("token", tg_http))
            self.assertEqual(publish_once(**kwargs), {"database": "created", "telegram": "sent"})
            self.assertEqual(publish_once(**kwargs), {"database": "unchanged", "telegram": "unchanged"})
            self.assertEqual(len(tg_http.requests), 1)
            sent = parse_qs(tg_http.requests[0].data.decode())
            self.assertIn("Headline", sent["text"][0])

    def test_existing_different_content_is_conflict(self):
        db_http = FakeHttp([HttpResponse(200, b'[{"content":"old"}]')])
        with self.assertRaises(PublishConflict):
            SupabasePublisher("https://db.test", "key", db_http).publish("2026-08-25", "it", "new")

    def test_existing_identical_without_receipt_recovers_telegram(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_http = FakeHttp([HttpResponse(200, b'[{"content":"same"}]')])
            tg_http = FakeHttp([HttpResponse(200)])
            result = publish_once(date="2026-08-25", category="trend", content="same", web_base="https://example.test",
                                  chat_id="-1", receipt_dir=Path(temporary),
                                  supabase=SupabasePublisher("https://db.test", "key", db_http),
                                  telegram=TelegramPublisher("token", tg_http))
            self.assertEqual(result, {"database": "unchanged", "telegram": "sent"})


if __name__ == "__main__":
    unittest.main()
