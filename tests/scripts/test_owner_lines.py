"""Tests for owner_lines.py: which edits of the scripts CLAUDE.md only add or update owner bullets."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import owner_lines
import script_utils

SCRIPTS_MD = (
    "# Toolkit scripts\n\n## Owners\n\n- Plan text: `lib/plan_format.py`.\n"
    "- TOML files: `lib/toml_file.py` `read_toml`.\n\n## Data between steps\n\n- Steps pass JSON to each other.\n"
)
NEW_BULLET = "- A new fact: `lib/new_fact.py`.\n"


class OwnerLinesOnlyTest(unittest.TestCase):
    def test_edits_that_only_add_or_update_owner_bullets_are_true(self):
        cases = {
            "bullet added": SCRIPTS_MD.replace("\n## Data", NEW_BULLET + "\n## Data"),
            "bullet updated": SCRIPTS_MD.replace("`lib/plan_format.py`", "`lib/plan_format.py` `read_plan`"),
            "two bullets updated": SCRIPTS_MD.replace("Plan text", "Plan texts").replace("TOML files", "TOML"),
            "bullet updated with a new bullet beside it": SCRIPTS_MD.replace(
                "- Plan text: `lib/plan_format.py`.\n", "- Plan text: `lib/plan_format.py` `read_plan`.\n" + NEW_BULLET
            ),
        }
        for name, after in cases.items():
            with self.subTest(name):
                self.assertTrue(owner_lines.owner_lines_only(SCRIPTS_MD, after), name)

    def test_every_other_edit_is_false(self):
        lines = SCRIPTS_MD.splitlines(keepends=True)
        swapped = [*lines[:4], lines[5], lines[4], *lines[6:]]
        cases = {
            "prose added in Owners": SCRIPTS_MD.replace("\n## Data", "Some prose.\n\n## Data"),
            "nested bullet": SCRIPTS_MD.replace("\n## Data", "  - x: `lib/a.py`\n\n## Data"),
            "no module path": SCRIPTS_MD.replace("\n## Data", "- A fact: nothing here.\n\n## Data"),
            "owner-shaped bullet under Data": SCRIPTS_MD + NEW_BULLET,
            "bullet removed": SCRIPTS_MD.replace("- Plan text: `lib/plan_format.py`.\n", ""),
            "two bullets merged": SCRIPTS_MD.replace(
                "- Plan text: `lib/plan_format.py`.\n- TOML files:", "- Plan text and TOML files:"
            ),
            "two bullets swapped": "".join(swapped),
            "unrelated bullet put in place of a removed one": SCRIPTS_MD.replace(
                "- Plan text: `lib/plan_format.py`.", "- Hook gates: `gates/x.py`."
            ),
            "heading renamed": SCRIPTS_MD.replace("## Owners", "## Owner list"),
            "identical": SCRIPTS_MD,
            "blank line added with the bullet": SCRIPTS_MD.replace("\n## Data", NEW_BULLET + "\n\n## Data"),
        }
        for name, after in cases.items():
            with self.subTest(name):
                self.assertFalse(owner_lines.owner_lines_only(SCRIPTS_MD, after), name)

    def test_a_non_owner_line_in_owners_replaced_by_an_owner_bullet_is_false(self):
        before = SCRIPTS_MD.replace("\n## Data", "Some prose.\n\n## Data")
        after = SCRIPTS_MD.replace("\n## Data", NEW_BULLET + "\n## Data")

        self.assertFalse(owner_lines.owner_lines_only(before, after))


class RealFileTest(unittest.TestCase):
    def setUp(self):
        self.path = toolkit_paths.REPO_ROOT / owner_lines.SCRIPTS_CLAUDE_MD
        self.assertTrue(self.path.is_file())
        self.text = self.path.read_text()

    def test_every_bullet_of_the_real_owners_section_is_an_owner_line(self):
        lines = self.text.splitlines()
        section = script_utils.heading_section_indexes(lines, owner_lines.OWNERS_HEADING)
        bullets = {index for index in section if lines[index].startswith("- ")}
        self.assertTrue(bullets)
        self.assertEqual(bullets - owner_lines.owner_line_indexes(lines), set())

    def test_the_real_text_plus_one_inserted_bullet_is_true(self):
        lines = self.text.splitlines(keepends=True)
        first = min(owner_lines.owner_line_indexes(self.text.splitlines()))
        after = "".join([*lines[:first], NEW_BULLET, *lines[first:]])
        self.assertTrue(owner_lines.owner_lines_only(self.text, after))


if __name__ == "__main__":
    unittest.main()
