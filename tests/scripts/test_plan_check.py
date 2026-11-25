"""Tests for plan_check.py: the argument handling of the check verb. The acceptance-criteria rows of
check are tested in test_spec_ac_check.py."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import plan_format

PLAN_CHECK = toolkit_paths.CODE_DIR / "plan_check.py"
PLAN = ("## Phase Status\n\n- [ ] Phase 1: First (risk: low)\n- [x] Phase 2: Second (risk: low)\n\n"
        "## Phase 1: First\n\nx\n")


class PlanCheckCliTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        self.plan = self.folder / "spec.md"
        self.plan.write_text(PLAN)

    def run_plan_check(self, *args, env=None):
        return subprocess.run([sys.executable, str(PLAN_CHECK), *args], cwd=self.folder, capture_output=True,
                              text=True, check=False, env=env)

    def test_a_verb_it_does_not_know_prints_the_usage_and_fails(self):
        done = self.run_plan_check("run", str(self.plan))

        self.assertEqual(done.returncode, 1)
        self.assertIn("usage: plan_check.py", done.stderr)

    def test_check_with_no_plan_path_prints_the_usage_and_fails(self):
        done = self.run_plan_check("check", "--final")

        self.assertEqual(done.returncode, 1)
        self.assertIn("usage: plan_check.py", done.stderr)

    def test_owner_prints_the_owner_of_the_ticket_beside_the_plan_as_json(self):
        ticket = self.folder / "00-ticket.md"
        ticket.write_text("# T-1: Thing\n\n## Background\n\nWords.\n")

        done = self.run_plan_check("owner", str(self.plan))

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        owner = json.loads(done.stdout)
        self.assertEqual(owner["owner"], "plan")
        self.assertEqual(owner["ticket"], str(ticket))
        self.assertEqual(owner["rule"], plan_format.CRITERIA_OWNER_RULES["plan"])
        self.assertIsNone(owner["source"])

    def test_owner_prints_session_and_the_queue_source_for_a_session_written_ticket(self):
        home = self.folder / "home"
        queue_dir = home / "agent-evals" / "queue"
        queue_dir.mkdir(parents=True)
        (queue_dir / "item.md").write_text('---\ngenerated: {"by": "claude-code/x", "at": "2026-11-01"}\n---\n')
        (self.folder / "00-ticket.md").write_text(
            "# T-1: Thing\n\nSource: ~/agent-evals/queue/item.md\n\n## Acceptance Criteria\n\n- Words.\n")

        done = self.run_plan_check("owner", str(self.plan), env={**os.environ, "HOME": str(home)})

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        owner = json.loads(done.stdout)
        self.assertEqual(owner["owner"], "session")
        self.assertEqual(owner["source"], "~/agent-evals/queue/item.md")
        self.assertEqual(owner["rule"], plan_format.CRITERIA_OWNER_RULES["session"])

    def test_owner_given_the_plan_folder_reads_the_ticket_inside_it(self):
        _home, env = self.queue_home("claude-code/x")
        (self.folder / "00-ticket.md").write_text(
            "# T-1: Thing\n\nSource: ~/agent-evals/queue/item.md\n\n## Acceptance Criteria\n\n- Words.\n")

        done = self.run_plan_check("owner", str(self.folder), env=env)

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["owner"], "session")

    def test_owner_given_a_folder_with_a_ticket_and_no_plan_file_reads_the_ticket(self):
        _home, env = self.queue_home("claude-code/x")
        self.plan.unlink()
        (self.folder / "00-ticket.md").write_text(
            "# T-1: Thing\n\nSource: ~/agent-evals/queue/item.md\n\n## Acceptance Criteria\n\n- Words.\n")

        done = self.run_plan_check("owner", str(self.folder), env=env)

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["owner"], "session")

    def test_owner_given_a_folder_with_no_ticket_and_no_plan_file_names_the_expected_plan_files_and_fails(self):
        self.plan.unlink()

        done = self.run_plan_check("owner", str(self.folder))

        self.assertEqual(done.returncode, 1)
        self.assertIn("spec.md, plan.md or *-05-plan.md", done.stdout)

    def queue_home(self, author, home_name="home"):
        home = self.folder / home_name
        queue_dir = home / "agent-evals" / "queue"
        queue_dir.mkdir(parents=True, exist_ok=True)
        (queue_dir / "item.md").write_text(f'---\ngenerated: {{"by": "{author}", "at": "2026-11-01"}}\n---\n')
        return home, {**os.environ, "HOME": str(home)}

    def owner_with_source(self, author, source, home_name="home"):
        home, env = self.queue_home(author, home_name)
        source_value = source.replace("<home>", str(home))
        (self.folder / "00-ticket.md").write_text(
            f"# Lane\n\nSource: {source_value}\n\nBrief restated.\n\n## Done when\n\n- Words.\n")
        done = self.run_plan_check("owner", str(self.plan), env=env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return json.loads(done.stdout)

    def test_owner_prints_session_when_the_source_line_spells_the_queue_path_with_the_home_folder(self):
        owner = self.owner_with_source("claude-code/x", "<home>/agent-evals/queue/item.md")

        self.assertEqual(owner["owner"], "session")
        self.assertEqual(owner["source"], "~/agent-evals/queue/item.md")

    def test_owner_reads_a_home_folder_path_that_holds_an_underscore(self):
        owner = self.owner_with_source("claude-code/x", "**<home>/agent-evals/queue/item.md**", "home_dir")

        self.assertEqual(owner["owner"], "session")
        self.assertEqual(owner["source"], "~/agent-evals/queue/item.md")

    def test_owner_stays_user_for_a_human_written_queue_item_in_either_spelling(self):
        for source in ("<home>/agent-evals/queue/item.md", "~/agent-evals/queue/item.md"):
            with self.subTest(source):
                self.assertEqual(self.owner_with_source("human:brandon", source)["owner"], "user")

    def test_owner_stays_user_for_a_ticket_with_no_queue_source(self):
        self.queue_home("claude-code/x")
        (self.folder / "00-ticket.md").write_text("# Lane\n\n## Done when\n\n- The user's words.\n")

        done = self.run_plan_check("owner", str(self.plan))

        self.assertEqual(json.loads(done.stdout)["owner"], "user")

    def test_owner_with_no_path_or_two_paths_prints_the_usage_and_fails(self):
        for args in (("owner",), ("owner", str(self.plan), str(self.plan))):
            with self.subTest(args):
                done = self.run_plan_check(*args)

                self.assertNotEqual(done.returncode, 0)
                self.assertIn("usage:", done.stderr)

    def test_owner_with_no_ticket_beside_the_plan_prints_user(self):
        done = self.run_plan_check("owner", str(self.plan))

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["owner"], "user")

    def test_owner_prints_the_error_and_fails_on_a_ticket_it_cannot_read(self):
        ticket = self.folder / "00-ticket.md"
        ticket.write_text("# T-1\n\nSource: ~/agent-evals/queue/no-such-item-here.md\n")

        done = self.run_plan_check("owner", str(self.plan))

        self.assertEqual(done.returncode, 1)
        self.assertIn("no-such-item-here.md", done.stdout)

    def test_owner_prints_the_error_and_fails_when_several_tickets_sit_beside_the_plan(self):
        (self.folder / "A-00-ticket.md").write_text("# T-1\n")
        (self.folder / "B-00-ticket.md").write_text("# T-2\n")

        done = self.run_plan_check("owner", str(self.plan))

        self.assertEqual(done.returncode, 1)
        self.assertIn("B-00-ticket.md", done.stdout)

    def test_a_plan_with_an_entry_that_has_no_section_fails_the_check(self):
        done = self.run_plan_check("check", str(self.plan))

        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(f"{self.plan}:4: missing-section: Phase 2 is in Phase Status but the plan has no "
                      "'## Phase 2' section.", done.stdout)


def phase_plan(first_mark, second_mark, first_items="", second_items="", extra=""):
    return (f"## Phase Status\n\n- [{first_mark}] Phase 1: First (risk: low)\n"
            f"- [{second_mark}] Phase 2: Second (risk: low)\n\n"
            f"## Phase 1: First\n\n#### Automated Verification:\n\n{first_items}\n\n"
            f"## Phase 2: Second\n\n#### Automated Verification:\n\n{second_items}\n{extra}")


class SpecAcRowsTest(unittest.TestCase):
    STANDING = 'Standing ruling by Pat at 2026-11-19: every criterion reword follows one rule covers: rewords'
    CRITERIA = ("# Acceptance Criteria\n\n- **AC1** — The cache may reuse a stored value (Ticket #1, reworded)\n")

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        self.spec = self.folder / "spec.md"
        (self.folder / "00-ticket.md").write_text(
            "# T-1: Thing\n\nSource: https://example.com/T-1\n\n## Acceptance Criteria\n\n"
            "- The cache reuses the stored value\n")
        (self.folder / "acceptance-criteria.md").write_text(self.CRITERIA)

    def spec_rows(self, standing_line):
        self.spec.write_text(f"# Plan\n\n## Plan Deviations\n\n{standing_line}\n")
        sys.path.insert(0, str(toolkit_paths.CODE_DIR))
        import plan_check
        return plan_check.spec_ac_rows(self.spec)

    def test_a_reworded_ticket_criterion_gives_no_row_under_a_standing_reword_ruling(self):
        self.assertEqual(self.spec_rows(self.STANDING), [])

    def test_the_same_reword_gives_a_drift_row_with_no_standing_ruling(self):
        self.assertEqual(len(self.spec_rows("- none")), 1)

    def test_a_bad_standing_line_gives_one_row_naming_the_plan_file_and_line(self):
        rows = self.spec_rows('Standing ruling by Pat at yesterday: x covers: rewords')

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].startswith(f"{self.spec}:5:"), rows[0])


class PlanCheckVerdictTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "backend").mkdir()
        (self.repo / "CLAUDE.md").write_text("Quality check: `npm run lint && npx vitest run`\n")
        self.plan = self.repo / "spec.md"

    def check(self, text, cwd=None):
        self.plan.write_text(text)
        return subprocess.run([sys.executable, str(PLAN_CHECK), "check", str(self.plan)], cwd=cwd or self.repo,
                              capture_output=True, text=True, check=False)

    def test_a_clean_plan_with_any_heading_level_and_indented_notes_passes(self):
        done = self.check("## Phase Status\n\n- [ ] Phase 1: A\n  - [ ] note under one\n- [ ] Phase 2: B\n"
                          "- [ ] Phase 3.5: C\n\n## Phase 1: A\n\n### Phase 2: B\n\n#### Phase 3.5: C\n")

        self.assertEqual((0, ""), (done.returncode, done.stdout), done.stderr)

    def test_an_expected_red_line_that_holds_passes_also_from_a_repo_subfolder(self):
        text = phase_plan(" ", " ", first_items="Expected red: `npx vitest run` until Phase 2")

        for cwd in (self.repo, self.repo / "backend"):
            with self.subTest(cwd=cwd.name):
                done = self.check(text, cwd)

                self.assertEqual((0, ""), (done.returncode, done.stdout), done.stderr)

    def test_an_expected_red_line_that_does_not_hold_fails(self):
        line = "Expected red: `npx vitest run` until Phase 1"

        done = self.check(phase_plan(" ", " ", first_items=line))

        self.assertEqual(1, done.returncode, done.stdout)
        self.assertIn(": expected-red-not-later: ", done.stdout)

    def test_only_open_phases_have_their_verification_items_checked(self):
        bad_item = "- [ ] it works"
        clean_item = "- [ ] **Check**: lists - `ls -l`"

        closed_first = self.check(phase_plan("x", " ", bad_item, clean_item))
        open_first = self.check(phase_plan(" ", " ", bad_item, clean_item))

        self.assertEqual((0, ""), (closed_first.returncode, closed_first.stdout), closed_first.stderr)
        self.assertEqual(1, open_first.returncode)
        self.assertIn("Phase 1:", open_first.stdout)
        self.assertNotIn("Phase 2:", open_first.stdout)

    def test_a_closing_phase_reports_only_a_moving_base_diff(self):
        plan = ("## Phase Status\n\n- [ ] Phase 1: First (risk: low)\n"
                "- [ ] Phase 2: Refactor pass - /refactor cleanup sweep (risk: low)\n\n"
                "## Phase 1: First\n\n#### Automated Verification:\n\n- [ ] **Check**: lists - `ls -l`\n\n"
                "## Phase 2: Refactor pass\n\n")
        prose_box = "- [ ] the sweep is done\n"
        moving_box = "- [ ] diff is read - `git diff main...HEAD`\n"

        prose_only = self.check(plan + prose_box)
        moving = self.check(plan + moving_box)

        self.assertEqual((0, ""), (prose_only.returncode, prose_only.stdout), prose_only.stderr)
        self.assertEqual(1, moving.returncode)
        self.assertIn("Phase 2:", moving.stdout)
        self.assertIn("moving branch name", moving.stdout)

    def test_a_verification_heading_in_other_words_becomes_a_failure_row(self):
        text = phase_plan(" ", " ").replace("## Phase 1: First\n\n#### Automated Verification:",
                                            "## Phase 1: First\n\n#### Automated Tests Verification:", 1)

        done = self.check(text)

        self.assertEqual(1, done.returncode, done.stdout)
        self.assertIn(f"{self.plan}:8: heading `#### Automated Tests Verification:` is not a verification heading",
                      done.stdout)

    def test_a_manual_verification_section_that_does_not_parse_is_reported_with_its_line(self):
        text = phase_plan(" ", " ", extra="\n#### Manual Verification:\n\n"
                          "- [ ] **Manual-verified** (agent-verified): hit /orders\n  ```\n  curl /orders\n  ```\n")
        bad_line = text[:text.index("  ```")].count("\n") + 1

        done = self.check(text)

        self.assertEqual(1, done.returncode, done.stdout)
        self.assertIn(f"{self.plan}:{bad_line}:", done.stdout)


if __name__ == "__main__":
    unittest.main()
