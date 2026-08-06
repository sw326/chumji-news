import tempfile
import unittest
from pathlib import Path

from tools.llm_wiki import build


PAGE = """---
id: {page_id}
type: {page_type}
title: {title}
status: draft
updated_at: 2026-08-06
aliases: {aliases}
---
{body}
"""


class WikiToolTest(unittest.TestCase):
    def test_alias_link_and_backlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "entities").mkdir()
            (root / "notes").mkdir()
            (root / "entities/poland.md").write_text(PAGE.format(page_id="country-poland", page_type="entity", title="폴란드", aliases='["Poland"]', body=""), encoding="utf-8")
            (root / "notes/test.md").write_text(PAGE.format(page_id="note-test", page_type="note", title="테스트", aliases="[]", body="[[Poland]]"), encoding="utf-8")
            output, errors = build(root, write=False)
            self.assertEqual(errors, [])
            self.assertEqual(output["graph"]["note-test"], ["country-poland"])
            self.assertEqual(output["backlinks"]["country-poland"], ["note-test"])

    def test_broken_link_fails_lint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "notes").mkdir()
            (root / "notes/test.md").write_text(PAGE.format(page_id="note-test", page_type="note", title="테스트", aliases="[]", body="[[없음]]"), encoding="utf-8")
            _, errors = build(root, write=False)
            self.assertTrue(any("broken link" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
