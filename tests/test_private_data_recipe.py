"""Keep the Messenger opt-in in source; never inspect installed owner data."""
import json
from pathlib import Path
import unittest


class PrivateDataRecipeTest(unittest.TestCase):
    def test_messenger_owns_its_data_permissions(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "runtipi/config.json").read_text())
        self.assertIs(config.get("private_data"), True)
        self.assertEqual((config["uid"], config["gid"]), (1000, 1000))


if __name__ == "__main__":
    unittest.main()
