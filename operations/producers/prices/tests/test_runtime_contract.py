import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "operations/producers/prices/run_price_snapshot.sh"


class PriceRuntimeContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_validation_precedes_all_publication(self):
        validation = self.text.index("price snapshot validation failed")
        deploy = self.text.index("deploy --prod")
        database = self.text.index("save-price-snapshot.js")
        telegram = self.text.index("sendMessage")
        self.assertLess(validation, deploy)
        self.assertLess(deploy, database)
        self.assertLess(database, telegram)

    def test_deployment_is_staged_outside_git_worktree(self):
        self.assertIn("git -C \"$ROOT\" archive HEAD", self.text)
        self.assertIn("$stage/public/fresh-food/$snapshot_date", self.text)
        self.assertNotIn("$ROOT/public/fresh-food/$snapshot_date", self.text)

    def test_dry_run_exits_before_publication(self):
        dry_run = self.text.index('if [[ "$DRY_RUN" -eq 1 ]]')
        deploy = self.text.index("deploy --prod")
        self.assertLess(dry_run, deploy)


if __name__ == "__main__":
    unittest.main()
