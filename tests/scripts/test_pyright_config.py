"""pyrightconfig.json lists every toolkit script folder as an extraPaths entry, so pyright resolves the scripts'
bare-name sibling imports, and names no folder that is gone."""
import json
import os
import pathlib
import unittest

from toolkit_paths import CLAUDE_DIR, REPO_ROOT, SCRIPTS_DIR

CONFIG = pathlib.Path(os.environ.get("PYRIGHT_CONFIG_PATH") or REPO_ROOT / "pyrightconfig.json")


def extra_paths():
    config = json.loads(CONFIG.read_text())
    return config["extraPaths"]


class PyrightConfigTest(unittest.TestCase):
    def test_every_script_folder_is_an_extra_path(self):
        listed = {REPO_ROOT / entry for entry in extra_paths()}
        candidates = [*SCRIPTS_DIR.iterdir(), *(CLAUDE_DIR / "skills").glob("*/scripts")]
        script_folders = {folder for folder in candidates if folder.is_dir() and any(folder.glob("*.py"))}
        self.assertEqual(sorted(script_folders - listed), [])

    def test_every_extra_path_exists(self):
        missing = [entry for entry in extra_paths() if not (REPO_ROOT / entry).is_dir()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
