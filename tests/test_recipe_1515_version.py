"""Runtipi must see 15.15 as newer than the installed 15.14 recipe."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Recipe1515VersionTests(unittest.TestCase):
    def test_monotonic_1515_recipe_version(self):
        recipe = json.loads((ROOT / "runtipi/config.json").read_text())
        self.assertEqual(recipe["version"], "0.2.0-unified.15.15")
        self.assertEqual(recipe["tipi_version"], 57)
        self.assertGreater(recipe["tipi_version"], 56)  # installed 15.14


if __name__ == "__main__":
    unittest.main()
