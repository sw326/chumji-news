import hashlib
import json
import unittest

from operations.producers.news.build_prompt import build_prompt


class PromptParityTests(unittest.TestCase):
    DATE = "2026.08.25 (화)"
    FIXTURE = json.dumps({"articles": [{"title": "고정 기사", "url": "https://example.test/a"}]}, ensure_ascii=False, separators=(",", ":"))

    def test_frozen_prompt_hashes_match_production_contract(self):
        expected = {
            # Frozen production prompt contract; update only with reviewed prompt changes.
            "morning": "b7de0613de7a3a9538e84cbc698ba2d790ac1f8f2ec7d8557b91ddd49c20a85c",
            "it": "0493b4c81aac9a1ff2badfdc8028e6d7005fb0de91e7bcdf14d4bd12454107b3",
            "trend": "a5a4ae72ab06c37a62c8a5ed5e637370d15488d7f2550b0b0bb92e8d484ecdae",
        }
        actual = {profile: hashlib.sha256(build_prompt(profile, self.DATE, self.FIXTURE).encode()).hexdigest() for profile in expected}
        self.assertEqual(actual, expected)

    def test_source_json_bytes_are_not_reserialized(self):
        source = '{\n  "articles": []\n}\n'
        self.assertTrue(build_prompt("morning", self.DATE, source).endswith(source))

    def test_invalid_source_is_rejected_before_gpt(self):
        with self.assertRaises(json.JSONDecodeError):
            build_prompt("it", self.DATE, "not json")
