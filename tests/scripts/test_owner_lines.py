"""Tests for owner_lines.py: which edits of the scripts CLAUDE.md only add or update owner bullets."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import owner_lines
import script_utils
from owner_line_fixtures import NEW_BULLET, SCRIPTS_MD, SCRIPTS_MD_WITH_NEW_BULLET

SEPARATED_SWAP_HEAD = "# Toolkit scripts\n\n## Owners\n\n"
SEPARATED_SWAP_BEFORE = (
    f"{SEPARATED_SWAP_HEAD}- Plan text: `lib/plan_format.py`.\n- TOML files: `lib/toml_file.py` `read_toml`.\n"
    "- Plan text b: `lib/plan_format_b.py`.\n"
)
SEPARATED_SWAP_AFTER = (
    f"{SEPARATED_SWAP_HEAD}- Plan text b: `lib/plan_format_b.py` `read`.\n"
    "- TOML files: `lib/toml_file.py` `read_toml`.\n- Plan text: `lib/plan_format.py` `read`.\n"
)


class OwnerLinesOnlyTest(unittest.TestCase):
    def test_edits_that_only_add_or_update_owner_bullets_are_true(self):
        cases = {
            "bullet added": SCRIPTS_MD_WITH_NEW_BULLET,
            "bullet updated": SCRIPTS_MD.replace("`lib/plan_format.py`", "`lib/plan_format.py` `read_plan`"),
            "two bullets updated": SCRIPTS_MD.replace("Plan text", "Plan texts").replace("TOML files", "TOML"),
            "bullet updated with a new bullet beside it": SCRIPTS_MD.replace(
                "- Plan text: `lib/plan_format.py`.\n", "- Plan text: `lib/plan_format.py` `read_plan`.\n" + NEW_BULLET
            ),
        }
        for name, after in cases.items():
            with self.subTest(name):
                self.assertTrue(owner_lines.owner_lines_only(SCRIPTS_MD, after), name)

    def test_two_similar_bullets_updated_in_order_is_true(self):
        before = SCRIPTS_MD.replace(
            "- TOML files: `lib/toml_file.py` `read_toml`.\n", "- Plan text b: `lib/plan_format.py`.\n"
        )
        after = before.replace("- Plan text: `lib/plan_format.py`.", "- Plan text: `lib/plan_format.py` x.").replace(
            "- Plan text b: `lib/plan_format.py`.", "- Plan text b: `lib/plan_format.py` b."
        )

        self.assertTrue(owner_lines.owner_lines_only(before, after))

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
            "two bullets merged beside an unrelated added bullet": SCRIPTS_MD.replace(
                "- Plan text: `lib/plan_format.py`.\n- TOML files: `lib/toml_file.py` `read_toml`.\n",
                "- Plan text: `lib/plan_format.py` `lib/toml_file.py` `read_toml`.\n"
                "- Hook gates: `gates/x.py`.\n",
            ),
            "two bullets swapped and lightly reworded": "".join(
                [
                    *lines[:4],
                    lines[5].replace("TOML files", "TOML file"),
                    lines[4].replace("Plan text", "Plan texts"),
                    *lines[6:],
                ]
            ),
            "heading renamed": SCRIPTS_MD.replace("## Owners", "## Owner list"),
            "identical": SCRIPTS_MD,
            "blank line added with the bullet": SCRIPTS_MD.replace("\n## Data", NEW_BULLET + "\n\n## Data"),
        }
        for name, after in cases.items():
            with self.subTest(name):
                self.assertFalse(owner_lines.owner_lines_only(SCRIPTS_MD, after), name)

    def test_two_reworded_bullets_swapped_around_an_unchanged_bullet_is_false(self):
        self.assertFalse(owner_lines.owner_lines_only(SEPARATED_SWAP_BEFORE, SEPARATED_SWAP_AFTER))

    def test_a_bullet_updated_in_place_beside_an_untouched_look_alike_bullet_is_true(self):
        head = "# Toolkit scripts\n\n## Owners\n\n"
        first = "- Plan text: `lib/plan_format.py`."
        sibling = "- Plan text b: `lib/plan_format_b.py`."

        before = f"{head}{first}\n{sibling}\n"
        after = f"{head}{first[:-1]} and `check`.\n{sibling}\n"

        self.assertTrue(owner_lines.owner_lines_only(before, after))

    def test_a_swap_of_the_last_two_bullets_of_a_file_with_no_final_newline_is_false(self):
        head = "# Toolkit scripts\n\n## Owners\n\n"
        first = "- Plan text: `lib/plan_format.py`."
        second = "- Plan files: `lib/plan_files.py`."

        self.assertFalse(owner_lines.owner_lines_only(f"{head}{first}\n{second}", f"{head}{second}\n{first}"))

    def test_a_swap_of_resembling_bullets_each_reworded_is_false(self):
        head = "# Toolkit scripts\n\n## Owners\n\n"
        first = "- Plan text: `lib/plan_format.py`."
        second = "- Plan files: `lib/plan_files.py`."

        before = f"{head}{first}\n{second}\n"
        after = f"{head}{second} `read`\n{first} `read`\n"

        self.assertFalse(owner_lines.owner_lines_only(before, after))

    def test_each_bullet_updated_in_place_beside_an_added_bullet_is_true(self):
        head = "# Toolkit scripts\n\n## Owners\n\n"
        first = "- Plan text: `lib/plan_format.py`."
        second = "- Plan files: `lib/plan_files.py`."

        before = f"{head}{first}\n{second}\n"
        after = f"{head}{first} `read`\n{second} `read`\n{NEW_BULLET}"

        self.assertTrue(owner_lines.owner_lines_only(before, after))

    def test_a_bullet_added_right_above_an_updated_look_alike_bullet_is_true(self):
        head = "# Toolkit scripts\n\n## Owners\n\n"
        first = "- Plan text: `lib/plan_format.py`."
        added = "- Plan text sections: `lib/plan_sections.py`."

        before = f"{head}{first}\n"
        after = f"{head}{added}\n{first} `read`\n"

        self.assertTrue(owner_lines.owner_lines_only(before, after))

    def test_a_non_owner_line_in_owners_replaced_by_an_owner_bullet_is_false(self):
        before = SCRIPTS_MD.replace("\n## Data", "Some prose.\n\n## Data")
        after = SCRIPTS_MD_WITH_NEW_BULLET

        self.assertFalse(owner_lines.owner_lines_only(before, after))

    def test_a_non_bullet_line_in_owners_updated_to_the_bullet_form_is_false(self):
        before = SCRIPTS_MD.replace("- Plan text: `lib/plan_format.py`.", "- Plan text: lib/plan_format.py.")

        self.assertFalse(owner_lines.owner_lines_only(before, SCRIPTS_MD))


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
