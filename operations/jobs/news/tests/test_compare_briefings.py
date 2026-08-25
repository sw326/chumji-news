import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compare_briefings import cited_urls, compare


class CompareBriefingsTest(unittest.TestCase):
    def test_extracts_markdown_and_html_links_with_canonicalization(self):
        text = """
        [one](https://Example.com/a?utm_source=x&id=1)
        <a href="https://example.com/b/">two</a>
        <a href="https://chumji-news.vercel.app/news/2026-08-25/news">app</a>
        """
        self.assertEqual(
            cited_urls(text),
            {"https://example.com/a?id=1", "https://example.com/b"},
        )

    def test_reports_overlap_and_differences(self):
        report = compare(
            "[a](https://example.com/a) [b](https://example.com/b)",
            '<a href="https://example.com/b">b</a><a href="https://example.com/c">c</a>',
            "morning",
        )
        self.assertEqual(report["overlap_count"], 1)
        self.assertEqual(report["shadow_overlap_ratio"], 0.5)
        self.assertEqual(report["legacy_overlap_ratio"], 0.5)
        self.assertEqual(report["jaccard_ratio"], 0.3333)
        self.assertEqual(report["shadow_only_urls"], ["https://example.com/a"])
        self.assertEqual(report["legacy_only_urls"], ["https://example.com/c"])


if __name__ == "__main__":
    unittest.main()
