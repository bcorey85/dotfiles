"""verify-prep with a queue item as the ticket: the item's `## Done when` bullets are the criteria, and the owner comes
from the item's own `generated.by`."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import test_verify_branch_script as branch
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import plan_format

PLAN_CHECK = toolkit_paths.CODE_DIR / "plan_check.py"
MODEL_AUTHOR = '{"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T09:45:40-06:00"}'
THREE_BULLETS = "- First thing\n- Second thing\n- Third thing\n"


def queue_item(done_when=THREE_BULLETS, generated=MODEL_AUTHOR, heading="## Done when"):
    generated_line = f"generated: {generated}\n" if generated is not None else ""
    return (f'---\ntype: "QueueItem"\ntitle: "t"\n{generated_line}kind: "live-edit"\n---\n\n## Context\n\nWhy.\n\n'
            f"{heading}\n\n{done_when}")


class QueueTicketTest(branch.VerifyBranchBase):
    def prep_ticket(self, text):
        ticket = self.temp_root / "item.md"
        ticket.write_bytes(text.encode())
        return self.prep("--ticket-file", str(ticket))

    def prepared_criteria(self):
        return self.context()["criteria"]

    def assert_ticket_lines(self, expected):
        self.assertEqual(expected, self.prepared_criteria()["ticketLines"])

    def test_a_queue_item_exits_0_with_its_done_when_bullets_and_a_session_owner(self):
        done = self.prep_ticket(queue_item())

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: First thing", "Ticket #2: Second thing", "Ticket #3: Third thing"])
        self.assertEqual("session", self.prepared_criteria()["criteriaOwner"]["owner"])
        self.assertIn("criteria owner: session", done.stdout)

    def test_a_human_author_owns_the_criteria_as_user(self):
        done = self.prep_ticket(queue_item(generated='{"by": "human:brandon", "at": "2026-11-15"}'))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual("user", self.prepared_criteria()["criteriaOwner"]["owner"])

    def test_a_process_author_owns_the_criteria_as_session(self):
        done = self.prep_ticket(queue_item(generated='{"by": "process:build-queue", "at": "2026-11-15"}'))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual("session", self.prepared_criteria()["criteriaOwner"]["owner"])

    def test_an_empty_done_when_does_not_pass_with_zero_criteria(self):
        done = self.prep_ticket(queue_item(done_when=""))

        self.assertNotEqual(done.returncode, 0)
        self.assertIn("has no criteria", done.stderr)

    def test_a_bullet_wrapped_over_two_lines_is_one_criterion(self):
        done = self.prep_ticket(queue_item(done_when="- First thing\n  wraps here\n- Second\n"))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: First thing wraps here", "Ticket #2: Second"])

    def test_a_nested_bullet_folds_into_its_parent(self):
        done = self.prep_ticket(queue_item(done_when="- First thing\n  - nested detail\n- Second\n"))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: First thing nested detail", "Ticket #2: Second"])

    def test_the_next_heading_ends_the_done_when_section(self):
        done = self.prep_ticket(queue_item(done_when="- First thing\n\n## Notes\n\n- not a criterion\n"))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: First thing"])

    def test_with_acceptance_criteria_and_done_when_the_first_one_with_items_wins(self):
        text = queue_item(done_when="- From done when\n") + "\n## Acceptance Criteria\n\n- From acceptance\n"

        done = self.prep_ticket(text)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: From done when"])

    def test_the_first_heading_with_items_wins_when_the_earlier_one_is_empty(self):
        text = queue_item(done_when="") + "\n## Acceptance Criteria\n\n- From acceptance\n"

        done = self.prep_ticket(text)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: From acceptance"])

    def test_the_heading_matches_in_any_case(self):
        for heading in ("## Done When", "## DONE WHEN", "### done when:"):
            with self.subTest(heading=heading):
                done = self.prep_ticket(queue_item(heading=heading))

                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(3, len(self.prepared_criteria()["ticketLines"]))
                for state_file in (self.temp_root / "state").glob("*.json"):
                    state_file.unlink()

    def test_one_prose_paragraph_is_one_criterion(self):
        done = self.prep_ticket(queue_item(done_when="The thing works end to end.\n"))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: The thing works end to end."])
        self.assertEqual("session", self.prepared_criteria()["criteriaOwner"]["owner"])

    def test_a_paragraph_wrapped_over_three_lines_is_joined_by_one_space_per_line_break(self):
        done = self.prep_ticket(queue_item(done_when="The thing\nworks   end\n  to end.\n"))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: The thing works   end to end."])

    def test_two_paragraphs_are_two_criteria(self):
        done = self.prep_ticket(queue_item(done_when="First thing\nwraps.\n\nSecond thing.\n"))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: First thing wraps.", "Ticket #2: Second thing."])

    def test_prose_before_bullets_stops_naming_the_line(self):
        done = self.prep_ticket(queue_item(done_when="Lead-in sentence:\n\n- First thing\n"))

        self.assertEqual(done.returncode, 2)
        self.assertIn("item.md:14:", done.stderr)
        self.assertIn("prose in the criteria section is not a list item", done.stderr)

    def test_prose_after_bullets_stops_naming_the_line(self):
        done = self.prep_ticket(queue_item(done_when="- First thing\n\nA ruling narrowed this.\n"))

        self.assertEqual(done.returncode, 2)
        self.assertIn("item.md:16:", done.stderr)
        self.assertIn("A ruling narrowed this.", done.stderr)

    def test_prose_under_acceptance_criteria_still_stops(self):
        done = self.prep_ticket(queue_item(done_when="Plain prose.\n", heading="## Acceptance Criteria"))

        self.assertEqual(done.returncode, 2)
        self.assertIn("prose in the criteria section is not a list item", done.stderr)

    def test_a_fenced_block_in_a_prose_done_when_stops(self):
        done = self.prep_ticket(queue_item(done_when="Prose.\n\n```\ncode\n```\n"))

        self.assertEqual(done.returncode, 2)
        self.assertIn("fenced block in a prose criteria section", done.stderr)

    def test_a_tilde_fenced_block_in_a_prose_done_when_stops(self):
        done = self.prep_ticket(queue_item(done_when="Prose.\n\n~~~\nfoo\n\nbar\n~~~\n"))

        self.assertEqual(done.returncode, 2)
        self.assertIn("fenced block in a prose criteria section", done.stderr)

    def test_prose_done_when_with_crlf_line_ends(self):
        done = self.prep_ticket(queue_item(done_when="First thing\nwraps.\n\nSecond thing.\n").replace("\n", "\r\n"))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: First thing wraps.", "Ticket #2: Second thing."])

    def test_crlf_line_ends_still_read_the_criteria_and_the_session_owner(self):
        done = self.prep_ticket(queue_item().replace("\n", "\r\n"))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: First thing", "Ticket #2: Second thing", "Ticket #3: Third thing"])
        self.assertEqual("session", self.prepared_criteria()["criteriaOwner"]["owner"])

    def test_done_when_without_frontmatter_is_read_and_owned_by_the_user(self):
        done = self.prep_ticket("# T\n\n## Done when\n\n" + THREE_BULLETS)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_ticket_lines(["Ticket #1: First thing", "Ticket #2: Second thing", "Ticket #3: Third thing"])
        self.assertEqual("user", self.prepared_criteria()["criteriaOwner"]["owner"])

    def test_a_broken_generated_value_stops_naming_the_file_and_line(self):
        done = self.prep_ticket(queue_item(generated="{not json"))

        self.assertEqual(done.returncode, 2)
        self.assertIn("item.md:4:", done.stderr)
        self.assertIn("`generated:` is not a JSON object", done.stderr)
        self.assertNotIn("criteria owner: user", done.stdout)

    def test_a_queue_item_with_no_generated_key_stops(self):
        done = self.prep_ticket(queue_item(generated=None))

        self.assertEqual(done.returncode, 2)
        self.assertIn("has no `generated:` frontmatter key", done.stderr)
        self.assertNotIn("criteria owner: user", done.stdout)

    def test_a_ticket_with_no_criteria_heading_still_exits_2(self):
        done = self.prep_ticket(queue_item().replace("## Done when", "## Outcome"))

        self.assertEqual(done.returncode, 2)
        self.assertIn("no criteria heading", done.stderr)


class RunRulesTmpdirTest(branch.VerifyBranchBase):
    def test_the_run_rules_keep_the_default_tmpdir_and_allow_no_tmp_redirect_ban(self):
        self.task_dir()

        done = self.prep()

        self.assertEqual(done.returncode, 0, done.stderr)
        payload = done.stdout.split("subagent_type=plan-verifier", 1)[1]
        self.assertIn("TMPDIR", payload)
        self.assertIn("keep the default TMPDIR", payload)
        self.assertIn("never set TMPDIR", payload)
        self.assertNotIn("Never write it to /tmp", payload)


class CriteriaReaderStopsTest(unittest.TestCase):
    def test_a_done_when_heading_with_a_suffix_stops_beside_a_real_criteria_heading(self):
        text = "# T\n\n## Done when (narrowed by ruling)\n\n- one\n\n## Acceptance Criteria\n\n- two\n"

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.ticket_criteria(text, "t.md")

        self.assertIn("t.md:3:", str(raised.exception))
        self.assertIn("## Done when (narrowed by ruling)", str(raised.exception))

    def test_a_sub_heading_inside_a_prose_done_when_stops_naming_the_line(self):
        text = "## Done when\n\nThe thing works.\n\n#### Detail\n\nMore.\n"

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.ticket_criteria(text, "t.md")

        self.assertIn("t.md:5:", str(raised.exception))
        self.assertIn("sub-heading", str(raised.exception))

    def test_a_blockquote_inside_a_prose_done_when_stops_naming_the_line(self):
        text = "## Done when\n\nThe thing works.\n> quoted ruling\n"

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.ticket_criteria(text, "t.md")

        self.assertIn("t.md:4:", str(raised.exception))
        self.assertIn("blockquote", str(raised.exception))

    def test_a_level_2_done_when_wins_over_an_earlier_level_3_acceptance_criteria(self):
        text = "# T\n\n### Acceptance Criteria\n\n- sub one\n\n## Done when\n\n- top one\n- top two\n"

        criteria = plan_format.ticket_criteria(text, "t.md")

        self.assertEqual([item["text"] for item in criteria], ["top one", "top two"])

    def test_a_queue_item_with_no_generated_key_names_line_1_not_a_body_line(self):
        folder_handle = tempfile.TemporaryDirectory()
        self.addCleanup(folder_handle.cleanup)
        item = pathlib.Path(folder_handle.name) / "item.md"
        item.write_text(queue_item(generated=None).replace("Why.", "generated: not frontmatter"))

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.criteria_owner(item)

        self.assertIn(f"{item}:1:", str(raised.exception))


class OrdinaryPlanOwnerTest(unittest.TestCase):
    def test_plan_check_owner_still_names_user_for_a_plan_beside_an_ordinary_ticket(self):
        folder_handle = tempfile.TemporaryDirectory()
        self.addCleanup(folder_handle.cleanup)
        folder = pathlib.Path(folder_handle.name)
        (folder / "00-ticket.md").write_text("# T\n\n## Acceptance\n\n- one\n")
        (folder / "spec.md").write_text("# Spec\n")

        done = subprocess.run([sys.executable, str(PLAN_CHECK), "owner", str(folder / "spec.md")],
                              capture_output=True, text=True, env={**os.environ})

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(plan_format.CRITERIA_OWNER_USER, json.loads(done.stdout)["owner"])


if __name__ == "__main__":
    unittest.main()
