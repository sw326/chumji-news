import sys
import unittest
from pathlib import Path

JOB_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(JOB_DIR))

import fetch_reliefweb


class ReliefWebTest(unittest.TestCase):
    def test_terms_use_word_boundaries(self):
        self.assertTrue(fetch_reliefweb._contains_term("iran situation report", "iran"))
        self.assertFalse(fetch_reliefweb._contains_term("afghanistan situation report", "iran"))


if __name__ == "__main__":
    unittest.main()
