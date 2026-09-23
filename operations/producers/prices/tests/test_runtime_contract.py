import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[4]


class PriceRuntimeContractTest(unittest.TestCase):
    def test_publication_order_and_no_daily_deployment(self):
        text = (ROOT / 'operations/producers/prices/run_price_snapshot.sh').read_text()
        steps = ['price snapshot validation failed', 'if [[ "$DRY_RUN" -eq 1 ]]',
                 '--run "$run_root" --publish', 'verify-price-artifact.mjs',
                 'save-price-snapshot.js', 'sendMessage']
        offsets = [text.index(step) for step in steps]
        self.assertEqual(offsets, sorted(offsets))
        for obsolete in ['deploy --prod', 'git -C', '$stage', 'VERCEL_PROJECT_FILE']:
            self.assertNotIn(obsolete, text)


if __name__ == '__main__':
    unittest.main()
