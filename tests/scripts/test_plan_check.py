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
