import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'history_collector', Path(__file__).parents[1] / 'fetch_trends.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
NOW = datetime(2026, 9, 9, 0, tzinfo=timezone.utc)


class PublicationHistoryTest(unittest.TestCase):
    def receipt(self, root, day, category='trend', body=None):
        (Path(root) / f'{day}-{category}.json').write_text(json.dumps(
            body if body is not None else {'content_sha256': 'a' * 64}))

    def test_kst_window_success_only_and_repository_normalization(self):
        with tempfile.TemporaryDirectory() as root:
            self.receipt(root, '2026-09-02')  # expired
            self.receipt(root, '2026-09-03')  # inclusive boundary
            self.receipt(root, '2026-09-09', 'it')  # same-day successful post
            self.receipt(root, '2026-09-10')  # future
            (Path(root) / '2026-09-08-audit.json').write_text('{}')
            html = b'<a href="https://github.com/nav/ignore">nav</a><article><a href="https://github.com/Owner/Repo.git/?utm_source=x#readme">repo</a><a href="https://github.com/OWNER/REPO/issues/1">issue</a><a href="https://github.com.evil/a/b">bad</a></article>'
            with patch.object(mod, '_request_bytes', return_value=html) as fetch:
                self.assertEqual(mod.read_recent_published_repositories(NOW, root), {'owner/repo'})
                self.assertEqual({call.args[0] for call in fetch.call_args_list}, {
                    'https://chumji-news.vercel.app/news/2026-09-03/trend',
                    'https://chumji-news.vercel.app/news/2026-09-09/it'})

    def test_kst_midnight_advances_window_not_utc_midnight(self):
        with tempfile.TemporaryDirectory() as root:
            self.receipt(root, '2026-09-03')
            self.receipt(root, '2026-09-04')
            with patch.object(mod, '_request_bytes', return_value=b'<article></article>') as fetch:
                mod.read_recent_published_repositories(datetime(2026, 9, 9, 15, tzinfo=timezone.utc), root)
                self.assertEqual(fetch.call_count, 1)
                self.assertIn('/2026-09-04/', fetch.call_args.args[0])

    def test_invalid_receipt_and_missing_public_article_fail_visibly(self):
        with tempfile.TemporaryDirectory() as root:
            self.receipt(root, '2026-09-08', body={})
            with self.assertRaises(ValueError):
                mod.read_recent_published_repositories(NOW, root)
            self.receipt(root, '2026-09-08')
            with patch.object(mod, '_request_bytes', return_value=b'<main>not found</main>'):
                with self.assertRaises(ValueError):
                    mod.read_recent_published_repositories(NOW, root)

    def test_http_failure_does_not_return_partial_history(self):
        with tempfile.TemporaryDirectory() as root:
            self.receipt(root, '2026-09-08')
            with patch.object(mod, '_request_bytes', side_effect=TimeoutError):
                with self.assertRaises(TimeoutError):
                    mod.read_recent_published_repositories(NOW, root)

    def test_unreadable_and_empty_store_are_not_silently_empty_history(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                mod.read_recent_published_repositories(NOW, root)
            with self.assertRaises(FileNotFoundError):
                mod.read_recent_published_repositories(NOW, Path(root) / 'missing')

    def test_history_failure_preserves_other_news(self):
        sources = [s for s in mod.SOURCES if s['key'] in {'github_trending', 'geeknews'}]
        rss = [{'title': 'Available story', 'article_url': 'https://example.com/new',
                'raw_summary': 'Available', 'published_at': NOW}]
        with (patch.object(mod, 'SOURCES', sources), patch.object(
            mod, 'read_recent_published_repositories', side_effect=OSError('unreadable')),
            patch.object(mod, 'discover_rss', return_value=(rss, None))):
            candidates, errors = mod.collect_candidates(NOW)
        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0]['selected'])
        self.assertIn('history unavailable: OSError', errors[0])

    def test_filter_before_limit_preserves_new_lower_ranked_candidates(self):
        source = next(s for s in mod.SOURCES if s['key'] == 'github_trending')
        html = ''.join(f'<article class="Box-row"><h2><a href="/dev/repo{i}">repo</a></h2><p>AI agent tool</p><span>{100-i} stars today</span></article>' for i in range(6)).encode()
        with (patch.object(mod, 'SOURCES', [source]),
              patch.object(mod, 'read_recent_published_repositories', return_value={'dev/repo0', 'dev/repo1', 'dev/repo2'}),
              patch.object(mod, '_request_bytes', return_value=html)):
            candidates, errors = mod.collect_candidates(NOW)
        self.assertEqual(errors, [])
        self.assertEqual([c['title'] for c in candidates if c['selected']], ['dev/repo3', 'dev/repo4', 'dev/repo5'])
        self.assertEqual(sum(c['selection_reason'] == 'published_within_7_kst_days' for c in candidates), 3)

    def test_no_duplicate_backfill_when_one_or_zero_new_candidates(self):
        source = next(s for s in mod.SOURCES if s['key'] == 'github_trending')
        items = [{'repository': f'dev/repo{i}', 'description': 'AI', 'language': '', 'stars_today': 100-i, 'rank': i+1} for i in range(4)]
        for count in (3, 4):
            with (patch.object(mod, 'SOURCES', [source]),
                  patch.object(mod, 'read_recent_published_repositories', return_value={f'dev/repo{i}' for i in range(count)}),
                  patch.object(mod, 'discover_github_trending', return_value=(items, None))):
                candidates, errors = mod.collect_candidates(NOW)
            self.assertEqual(sum(c['selected'] for c in candidates), 4-count)
            self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
