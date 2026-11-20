import json
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import approval_asks_store
import handback
import handback_store
import plan_format
import review_loop_findings
import review_loop_packet
import review_loop_prompts
import review_loop_ruled
import review_loop_script
import review_loop_signoffs
import review_user_ruled
import ruled_change_text
from approval_ask_chain import accepted_approval_ask_text
from finding_record import parse_finding
from no_code_notes import NO_CODE_NOTES
from test_review_loop_script import APP_FIXED, CLEAN_REVIEW, CLOSED, SESSION, ReviewLoopHarness


def ruled_finding(note, location="`a/b.py:3`"):
    return parse_finding(ruled_change_text.changed_text(f"{location} [bug] Proposed change: add X.", note,
                                                          ruled_change_text.USER_CLAUSE))


def broken_entry(finding, path):
    return {"ruling": review_loop_ruled.ruling_line(finding), "file": path}


class Host(review_loop_ruled.RuledFindings):
    def __init__(self):
        self.repo = "/repo"
        self.plan = ""
        self.change = None
        self.plan_impacts = []
        self.resolved_texts = []
        self.init_ruled_state()


class ApprovalOnlyPathsTest(unittest.TestCase):
    def test_only_a_file_named_claude_md_needs_approval_whatever_its_folder(self):
        changed = ["a/b.py", "CLAUDE.md", "x/y/CLAUDE.md", "NOT_CLAUDE.md", "docs/CLAUDE.md.bak", "claude.md"]
        self.assertEqual(review_loop_ruled.approval_only_paths(changed), ["CLAUDE.md", "x/y/CLAUDE.md"])

    def test_an_agents_md_and_a_claude_local_md_edit_need_approval(self):
        changed = ["AGENTS.md", "x/CLAUDE.local.md", "a/b.py"]
        self.assertEqual(review_loop_ruled.approval_only_paths(changed), ["AGENTS.md", "x/CLAUDE.local.md"])


def approval_host(user_ruled=(), session_ruled=()):
    host = Host()
    host.asks, host.ask_gates = [], {}
    host.user_ruled, host.session_ruled = list(user_ruled), list(session_ruled)
    host.add_ask = lambda agent, item: review_loop_script.LoopRun.add_ask(host, agent, item)
    return host


class ApprovalAskFilingTest(unittest.TestCase):
    def test_two_files_are_two_asks(self):
        host = approval_host()
        host.ask_for_approval_only_edits(["CLAUDE.md", "x/CLAUDE.md"], [])
        self.assertEqual(len(host.asks), 2)

    def test_an_agents_md_and_a_claude_local_md_edit_each_file_an_ask(self):
        host = approval_host()
        host.ask_for_approval_only_edits(["AGENTS.md", "CLAUDE.local.md"], [])
        self.assertEqual(len(host.asks), 2)


class ApprovalRulingTest(unittest.TestCase):
    def ask_filed(self, finding, user_ruled=(), session_ruled=(), changed="CLAUDE.md"):
        host = approval_host(user_ruled, session_ruled)
        host.ask_for_approval_only_edits([changed], [finding])
        return len(host.asks)

    def test_a_user_ruling_on_an_absolute_path_finding_files_no_ask(self):
        finding = parse_finding("`/repo/sub/CLAUDE.md:7` [bug] Proposed change: reword the rule.")
        self.assertEqual(self.ask_filed(finding, user_ruled=[finding.text], changed="sub/CLAUDE.md"), 0)

    def test_a_session_ruling_on_a_reviewer_finding_for_claude_md_still_files_the_ask(self):
        finding = parse_finding("`CLAUDE.md:7` [bug] Proposed change: reword the rule.")
        self.assertEqual(self.ask_filed(finding, session_ruled=[finding.text]), 1)

    def test_a_user_ruling_on_a_finding_for_claude_md_files_no_ask(self):
        finding = parse_finding("`CLAUDE.md:7` [bug] Proposed change: reword the rule.")
        self.assertEqual(self.ask_filed(finding, user_ruled=[finding.text]), 0)

    def test_a_user_ruling_on_root_claude_md_leaves_a_nested_claude_md_edit_asked(self):
        finding = parse_finding("`CLAUDE.md:7` [bug] Proposed change: reword the rule.")
        self.assertEqual(self.ask_filed(finding, user_ruled=[finding.text], changed="sub/CLAUDE.md"), 1)

    def test_a_session_accepted_root_approval_ask_leaves_a_nested_claude_md_edit_asked(self):
        finding = parse_finding(accepted_approval_ask_text("CLAUDE.md"))
        host = approval_host(session_ruled=[finding.text])
        host.ask_for_approval_only_edits(["CLAUDE.md", "sub/CLAUDE.md"], [finding])
        self.assertEqual(len(host.asks), 1)
        self.assertEqual(host.asks[0].path, "sub/CLAUDE.md")

    def test_a_user_ruling_on_a_shortened_path_leaves_the_full_path_edit_asked(self):
        finding = parse_finding("`.claude/CLAUDE.md:3` [bug] Proposed change: reword the rule.")
        self.assertEqual(self.ask_filed(finding, user_ruled=[finding.text], changed="claude/.claude/CLAUDE.md"), 1)

    def test_a_session_ruling_on_the_approval_ask_itself_files_no_ask(self):
        finding = parse_finding(accepted_approval_ask_text("CLAUDE.md"))
        self.assertEqual(self.ask_filed(finding, session_ruled=[finding.text]), 0)

    def test_a_session_ruling_that_modifies_the_approval_ask_still_files_the_ask(self):
        finding = parse_finding(accepted_approval_ask_text("CLAUDE.md", "keep the edit and reword line 3", "session"))
        self.assertEqual(self.ask_filed(finding, session_ruled=[finding.text]), 1)


GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


class ApprovalAskUserOnlyTest(unittest.TestCase):
    def test_the_filed_ask_is_user_only_and_the_packet_entry_carries_the_flag(self):
        host = approval_host()
        host.ask_for_approval_only_edits(["CLAUDE.md"], [])
        outcome = {"status": "converged", "asks": host.asks, "ask_gates": host.ask_gates,
                   "user_only_asks": host.user_only_asks}

        entries = review_loop_packet.ask_entries({**review_loop_packet.EMPTY_OUTCOME, **outcome})

        self.assertEqual([entry.get("user_only") for entry in entries], [True])

    def test_a_reviewer_ask_has_no_flag(self):
        ask = parse_finding("`a/b.py:3` [bug] Should it log? Change: add a log line.")
        entry = review_loop_packet.ask_entry(ask, "code-reviewer", None)
        self.assertNotIn("user_only", entry)


class ApprovalAskResumeTest(unittest.TestCase):
    """A coder's edit to CLAUDE.md survives a run that died after it."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = str(pathlib.Path(folder.name).resolve())
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("rules\n")
        for argv in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-q", "-m", "init"]):
            self.git(*argv)
        before_coder = approval_host()
        before_coder.repo = self.repo
        before_coder.snapshot_approval_blobs()
        self.blobs_before_coder = before_coder.approval_blobs

    def git(self, *argv):
        subprocess.run(["git", *argv], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True,
                       capture_output=True)

    def host(self, rejected=()):
        host = approval_host()
        host.repo = self.repo
        host.rejected_asks = list(rejected)
        host.approval_blobs = dict(self.blobs_before_coder)
        return host

    def edit_claude_md(self):
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("rules\nnew rule\n")

    def saved_paths(self):
        return list(approval_asks_store.read_approval_paths(self.repo))

    def test_a_ruled_user_only_ask_leaves_the_saved_paths_whatever_the_outcome(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        ask = {"question": "q", "file_line": "CLAUDE.md:1", "user_only": True,
               "change": approval_asks_store.approval_change("CLAUDE.md")}
        other = {"question": "q", "file_line": "a.py:1", "change": approval_asks_store.approval_change("CLAUDE.md")}

        approval_asks_store.forget_ruled_approval_paths(self.repo, [other])
        self.assertEqual(self.saved_paths(), ["CLAUDE.md"], "an ask that is not user-only leaves the file alone")

        approval_asks_store.forget_ruled_approval_paths(self.repo, [ask])
        self.assertEqual(self.saved_paths(), [], "a ruled user-only ask leaves the saved paths")

    def test_a_second_loop_after_an_accepted_user_ruling_files_no_ask_for_the_edit(self):
        self.edit_claude_md()
        first_loop = self.host()
        first_loop.ask_for_approval_only_edits(["CLAUDE.md"], [])
        self.assertEqual([ask.path for ask in first_loop.asks], ["CLAUDE.md"])
        accepted_ask = {"question": "q", "file_line": "CLAUDE.md:1", "user_only": True,
                        "change": approval_asks_store.approval_change("CLAUDE.md")}
        before_forgetting = self.host()
        before_forgetting.resume_approval_asks([])
        self.assertEqual([ask.path for ask in before_forgetting.asks], ["CLAUDE.md"],
                         "without the forgetting, a second loop files the ask")
        approval_asks_store.forget_ruled_approval_paths(self.repo, [accepted_ask])

        second_loop = self.host()
        second_loop.resume_approval_asks([])

        self.assertEqual(second_loop.asks, [], "the ruled ask is not filed again")
        self.assertEqual(self.saved_paths(), [])

    def test_a_resumed_run_holds_the_ask_when_the_coder_committed_the_edit_before_the_crash(self):
        self.edit_claude_md()
        self.git("commit", "-q", "-am", "the coder's commit")
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual([ask.path for ask in resumed.asks], ["CLAUDE.md"])
        self.assertEqual(self.saved_paths(), ["CLAUDE.md"])

    def test_a_revert_to_a_phase_edit_the_coder_built_on_clears_the_ask_after_the_commit(self):
        phase_text = "rules\nthe phase's own rule\n"
        claude_md = pathlib.Path(self.repo) / "CLAUDE.md"
        claude_md.write_text(phase_text)
        filing = approval_host()
        filing.repo = self.repo
        filing.rejected_asks = []
        filing.snapshot_approval_blobs()
        claude_md.write_text(phase_text + "the coder's rule\n")
        filing.ask_for_approval_only_edits(["CLAUDE.md"], [])
        claude_md.write_text(phase_text)
        self.git("commit", "-q", "-am", "the phase")

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(resumed.asks, [])
        self.assertEqual(self.saved_paths(), [])

    def test_a_file_the_tree_lacked_before_the_coder_is_asked_about_while_it_exists(self):
        agents_md = pathlib.Path(self.repo) / "AGENTS.md"
        agents_md.write_text("new\n")
        self.host().ask_for_approval_only_edits(["AGENTS.md"], [])
        self.assertEqual(self.saved_paths(), ["AGENTS.md"])

        agents_md.unlink()
        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(resumed.asks, [])
        self.assertEqual(self.saved_paths(), [])

    def test_a_run_with_nothing_saved_writes_no_file(self):
        self.host().resume_approval_asks([])

        self.assertFalse(approval_asks_store.approval_paths_file(self.repo).exists())

    def test_a_resumed_run_holds_the_ask_an_earlier_run_filed(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual([ask.path for ask in resumed.asks], ["CLAUDE.md"])
        outcome = {**review_loop_packet.EMPTY_OUTCOME, "asks": resumed.asks, "ask_gates": resumed.ask_gates,
                   "user_only_asks": resumed.user_only_asks}
        entries = review_loop_packet.ask_entries(outcome)
        self.assertEqual([(entry["file_line"], entry.get("user_only")) for entry in entries], [("CLAUDE.md:1", True)])

    def test_a_path_with_a_space_in_its_folder_is_saved_whole_and_resumed(self):
        folder = pathlib.Path(self.repo) / "my dir"
        folder.mkdir()
        (folder / "CLAUDE.local.md").write_text("rules\n")
        self.host().ask_for_approval_only_edits(["my dir/CLAUDE.local.md"], [])

        self.assertEqual(self.saved_paths(), ["my dir/CLAUDE.local.md"])
        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(self.saved_paths(), ["my dir/CLAUDE.local.md"])
        self.assertEqual(len(resumed.asks), 1)

    def test_a_resumed_run_drops_an_ask_whose_edit_is_gone(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("rules\n")

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(resumed.asks, [])

    def test_a_rejected_approval_ask_is_not_resumed_and_leaves_the_saved_file(self):
        self.edit_claude_md()
        # asks-done stores the file:line and the question, the text before the ask's change
        question, _change = review_loop_findings.ask_parts(review_loop_ruled.approval_ask_text("CLAUDE.md"))
        rejected = [parse_finding(question)]
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])

        later = self.host(rejected)
        later.resume_approval_asks([])

        self.assertEqual(later.asks, [])
        self.assertEqual(later.user_only_asks, [])
        self.assertEqual(self.saved_paths(), [])
        self.assertEqual([reason for _ask, reason in later.dropped_asks],
                         [review_loop_ruled.REJECTED_ASK_REASON])

    def test_a_rejected_approval_ask_is_still_filed_for_a_coders_new_edit(self):
        self.edit_claude_md()
        question, _change = review_loop_findings.ask_parts(review_loop_ruled.approval_ask_text("CLAUDE.md"))
        host = self.host([parse_finding(question)])

        host.ask_for_approval_only_edits(["CLAUDE.md"], [])

        self.assertEqual([ask.path for ask in host.user_only_asks], ["CLAUDE.md"])

    def test_a_user_ruled_approval_ask_is_not_filed_again_on_resume(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        ruling = parse_finding(accepted_approval_ask_text("CLAUDE.md"))

        resumed = approval_host(user_ruled=[ruling.text])
        resumed.repo = self.repo
        resumed.rejected_asks = []
        resumed.resume_approval_asks([ruling])

        self.assertEqual(resumed.asks, [])
        self.assertEqual(self.saved_paths(), [])

    def test_a_ruled_path_committed_since_it_was_saved_is_not_asked_again_after_a_later_edit(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        self.git("commit", "-q", "-am", "keep the edit")
        ruling = parse_finding(accepted_approval_ask_text("CLAUDE.md"))
        resumed = approval_host(user_ruled=[ruling.text])
        resumed.repo = self.repo
        resumed.rejected_asks = []
        resumed.resume_approval_asks([ruling])
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("rules\nnew rule\nuser's own edit\n")

        later = self.host()
        later.resume_approval_asks([])

        self.assertEqual(later.asks, [])
        self.assertEqual(self.saved_paths(), [])

    def test_a_damaged_saved_file_stops_the_run_naming_the_file(self):
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        saved = approval_asks_store.approval_paths_file(self.repo)
        for damaged in ("{", "[1]"):
            saved.write_text(damaged)
            with self.assertRaises(approval_asks_store.ApprovalAsksFileError) as caught:
                self.host().resume_approval_asks([])
            self.assertIn("approval-asks.json", str(caught.exception))

    def test_an_untracked_approval_file_is_resumed(self):
        (pathlib.Path(self.repo) / "AGENTS.md").write_text("new\n")
        self.host().ask_for_approval_only_edits(["AGENTS.md"], [])

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual([ask.path for ask in resumed.asks], ["AGENTS.md"])

    def test_a_git_failure_keeps_the_ask_resumed(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        resumed = self.host()

        real_git_output = review_loop_ruled.script_utils.git_output

        def hash_fails(repo, *args):
            return None if args[0] == "hash-object" else real_git_output(repo, *args)

        with mock.patch.object(review_loop_ruled.script_utils, "git_output", side_effect=hash_fails):
            resumed.resume_approval_asks([])

        self.assertEqual([ask.path for ask in resumed.asks], ["CLAUDE.md"])

    def test_every_filed_path_is_saved_and_resumed(self):
        self.edit_claude_md()
        (pathlib.Path(self.repo) / "AGENTS.md").write_text("new\n")
        self.host().ask_for_approval_only_edits(["CLAUDE.md", "AGENTS.md"], [])
        self.assertEqual(self.saved_paths(), ["CLAUDE.md", "AGENTS.md"])

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual([ask.path for ask in resumed.asks], ["CLAUDE.md", "AGENTS.md"])


class RewordFlagTest(unittest.TestCase):
    REPORT = ("PLAN-IMPACT:\n  assumed: AC1 as worded\n  found: the cache may reuse\n  acceptance_criteria: AC1\n"
              "  cause: plan\n  kind: {kind}")

    def impact_for(self, kind):
        host = Host()
        host.record_coder_plan_impact(self.REPORT.format(kind=kind), [])
        return host.plan_impacts[0]

    def test_a_coder_impact_says_reword_only_with_kind_reword_and_a_criterion(self):
        self.assertTrue(self.impact_for("reword")["reword"])
        self.assertFalse(self.impact_for("cut")["reword"])

    def test_a_reviewer_impact_says_reword_only_with_kind_reword_and_a_criterion(self):
        for kind, expected in {"reword": True, "cut": False}.items():
            with self.subTest(kind):
                host = Host()
                item = types.SimpleNamespace(text=self.REPORT.format(kind=kind))

                host.route_plan_items("code-reviewer", [item])

                self.assertEqual(host.plan_impacts[0]["reword"], expected)

    def routed_with_plan(self, plan_text, kind="reword"):
        """(to_coder, held, impacts) of one reviewer impact, with a plan file holding plan_text (None: no plan)."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        host = Host()
        host.repo = folder.name
        if plan_text is not None:
            (pathlib.Path(folder.name) / "plan.md").write_text(plan_text)
            host.plan = "plan.md"
        item = types.SimpleNamespace(text=self.REPORT.format(kind=kind))
        to_coder, held = host.route_plan_items("code-reviewer", [item])
        return to_coder, held, host.plan_impacts

    STANDING = ('# Plan\n\n## Plan Deviations\n\n- Standing ruling by Pat at 2026-11-19: "follow one rule" '
                "covers: rewords\n")

    def test_a_standing_ruled_reword_goes_to_the_coder_adopted_and_unapplied(self):
        to_coder, held, impacts = self.routed_with_plan(self.STANDING)

        self.assertEqual((len(to_coder), held), (1, []))
        self.assertTrue(impacts[0]["adopted"])
        self.assertFalse(impacts[0]["applied"])

    def test_a_standing_ruled_reword_counts_as_applied_only_when_the_pass_changed_the_plan_or_its_criteria(self):
        cases = {"the criteria file": (["docs/plans/p/acceptance-criteria.md"], True),
                 "the plan file": (["docs/plans/p/plan.md", "app.py"], True),
                 "only code": (["app.py"], False),
                 "nothing": ([], False),
                 "another plan's criteria": (["docs/plans/q/acceptance-criteria.md"], False)}
        for name, (changed, expected) in cases.items():
            with self.subTest(name):
                folder = tempfile.TemporaryDirectory()
                self.addCleanup(folder.cleanup)
                plan_dir = pathlib.Path(folder.name) / "docs" / "plans" / "p"
                plan_dir.mkdir(parents=True)
                (plan_dir / "plan.md").write_text(self.STANDING)
                host = Host()
                host.repo = folder.name
                host.plan = "docs/plans/p/plan.md"
                host.route_plan_items("code-reviewer", [types.SimpleNamespace(text=self.REPORT.format(kind="reword"))])

                host.mark_standing_rewords_applied(changed)

                self.assertEqual(host.plan_impacts[0]["applied"], expected)

    def test_an_impact_the_standing_ruling_does_not_cover_stays_held(self):
        cases = {"a cut under a standing ruling": (self.STANDING, "cut"),
                 "a reword with no ruling in the plan": ("# Plan\n", "reword"),
                 "a reword with no plan": (None, "reword")}
        for name, (plan_text, kind) in cases.items():
            with self.subTest(name):
                to_coder, held, impacts = self.routed_with_plan(plan_text, kind)

                self.assertEqual((to_coder, len(held)), ([], 1))
                self.assertFalse(impacts[0]["adopted"])

    def test_a_malformed_standing_ruling_raises_with_the_file_line_and_form(self):
        bad_plan = '# Plan\n\n## Plan Deviations\n\n- Standing ruling by Pat at yesterday: "x" covers: rewords\n'

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            self.routed_with_plan(bad_plan)

        message = str(raised.exception)
        self.assertIn("plan.md:5:", message)
        self.assertIn("expected", message)

    def test_the_flag_reaches_the_packet_and_survives_loading_it(self):
        host = Host()
        host.record_coder_plan_impact(self.REPORT.format(kind="reword"), [])

        message = review_loop_packet.packet_message({"status": "converged", "plan_impacts": host.plan_impacts})

        self.assertTrue(handback.load(message)["plan_impacts"][0]["reword"])


class ApprovalAskTextTest(unittest.TestCase):
    def test_the_ask_is_one_unconditional_change(self):
        _question, change = review_loop_findings.ask_parts(review_loop_ruled.approval_ask_text("CLAUDE.md"))
        self.assertEqual(change, "revert the fix coder's edit to `CLAUDE.md`.")


class NoCodeRulingTest(unittest.TestCase):
    def test_the_coder_prompt_names_the_no_code_issue(self):
        findings = [parse_finding("`a/c.py:1` [bug] Proposed change: fix c."), ruled_finding(NO_CODE_NOTES[1])]
        numbers = review_loop_ruled.no_code_numbers(findings)
        self.assertEqual(numbers, [2])
        with tempfile.TemporaryDirectory() as folder:
            prompt = review_loop_prompts.coder_prompt(
                "/repo", [item.text for item in findings], [], ["a/b.py"], pathlib.Path(folder),
                no_code_numbers=numbers)
            plain = review_loop_prompts.coder_prompt(
                "/repo", [item.text for item in findings], [], ["a/b.py"], pathlib.Path(folder))
        self.assertIn("Issues ruled no code change: 2.", prompt)
        self.assertIn("SKIPPED <n>", prompt)
        self.assertNotIn("ruled no code change", plain)

    def test_a_code_edit_against_a_no_code_ruling_is_flagged_and_a_doc_edit_is_not(self):
        ruled = ruled_finding(NO_CODE_NOTES[1])
        findings = [parse_finding("`a/c.py:1` [bug] Proposed change: fix c."), ruled]
        host = Host()
        host.flag_broken_no_code_rulings(findings, ["a/c.py", "docs/changes/notes/x.md"])
        self.assertEqual(host.no_code_broken, [])
        host.flag_broken_no_code_rulings(findings, ["a/b.py", "a/c.py"])
        self.assertEqual(host.no_code_broken, [broken_entry(ruled, "a/b.py")])

    def test_any_code_file_breaks_the_ruling_when_every_finding_is_no_code(self):
        host = Host()
        ruled = ruled_finding(NO_CODE_NOTES[3])
        host.flag_broken_no_code_rulings([ruled], ["z/other.py", "docs/n.md"])
        self.assertEqual(host.no_code_broken, [broken_entry(ruled, "z/other.py")])

    def test_a_file_that_another_finding_also_names_is_not_flagged(self):
        host = Host()
        findings = [parse_finding("`a/b.py:1` [bug] Proposed change: fix b."), ruled_finding(NO_CODE_NOTES[1])]
        host.flag_broken_no_code_rulings(findings, ["a/b.py"])
        self.assertEqual(host.no_code_broken, [])

    def test_every_no_code_finding_blames_the_ruling_that_names_the_file(self):
        host = Host()
        named = ruled_finding(NO_CODE_NOTES[1], "`a/c.py:1`")
        other = ruled_finding(NO_CODE_NOTES[3])
        host.flag_broken_no_code_rulings([named, other], ["a/b.py", "z/other.py"])
        self.assertEqual(host.no_code_broken, [broken_entry(other, "a/b.py"), broken_entry(named, "z/other.py")])

    def test_a_nit_may_change_code_when_every_finding_is_no_code(self):
        host = Host()
        ruled = ruled_finding(NO_CODE_NOTES[3])
        nit = parse_finding("`z/nit.py:4` [nit] rename x.")
        host.flag_broken_no_code_rulings([ruled], ["z/nit.py", "a/b.py"], [nit])
        self.assertEqual(host.no_code_broken, [broken_entry(ruled, "a/b.py")])

    def test_an_absolute_finding_path_names_the_changed_file(self):
        host = Host()
        ruled = ruled_finding(NO_CODE_NOTES[1], "`/repo/a/b.py:3`")
        findings = [parse_finding("`a/c.py:1` [bug] Proposed change: fix c."), ruled]
        host.flag_broken_no_code_rulings(findings, ["a/c.py", "a/b.py"])
        self.assertEqual(host.no_code_broken, [broken_entry(ruled, "a/b.py")])

    def test_a_run_without_a_no_code_ruling_flags_nothing(self):
        host = Host()
        host.flag_broken_no_code_rulings([parse_finding("`a/c.py:1` [bug] Proposed change: fix c.")], ["a/c.py"])
        self.assertEqual(host.no_code_broken, [])
        self.assertEqual(host.no_code_rulings, [])

    def test_the_packet_carries_the_flag_and_defaults_it_empty(self):
        broken = {"ruling": "`a/b.py:3` Make no code change.", "file": "a/b.py"}
        flagged = review_loop_packet.packet_message({"no_code_ruling_broken": [broken]})
        self.assertEqual(json.loads(flagged)["no_code_ruling_broken"], [broken])
        self.assertNotIn("no_code_ruling_broken", json.loads(review_loop_packet.packet_message({})))

    def test_the_next_reviewer_prompt_lists_the_no_code_rulings(self):
        host = Host()
        finding = ruled_finding(NO_CODE_NOTES[3])
        host.flag_broken_no_code_rulings([finding], [])
        prompt = review_loop_prompts.reviewer_prompt(
            "/repo", "bug-reviewer", ["a/b.py"], [], no_code_rulings=tuple(host.no_code_rulings))
        plain = review_loop_prompts.reviewer_prompt("/repo", "bug-reviewer", ["a/b.py"], [])
        self.assertIn(review_loop_prompts.NO_CODE_REVIEW_RULE, prompt)
        self.assertNotIn(review_loop_prompts.NO_CODE_REVIEW_RULE, plain)
        self.assertIn("Make no code change.", prompt)

    def test_a_long_finding_keeps_its_ruling_note_in_the_reviewer_prompt(self):
        host = Host()
        long_change = "Proposed change: " + "add a guard. " * 60
        finding = parse_finding(ruled_change_text.changed_text(f"`a/b.py:3` [bug] {long_change}", NO_CODE_NOTES[1],
                                                          ruled_change_text.USER_CLAUSE))
        host.flag_broken_no_code_rulings([finding], [])
        prompt = review_loop_prompts.reviewer_prompt(
            "/repo", "bug-reviewer", ["a/b.py"], [], no_code_rulings=tuple(host.no_code_rulings))
        self.assertIn("add one Watch line to the change note", prompt)


ADOPTED_RULING = handback_store.AdoptedRuling("PLAN-IMPACT: AC2 reworded.", None, "the user", "2026-11-19 10:00")
ADOPTED_FINDING = review_user_ruled.adopted_issue("app.py:2 [plan-drift] PLAN-IMPACT: AC2 reworded. "
                                                  "acceptance_criteria: AC2", ADOPTED_RULING)


class UnappliedAdoptedBlockersTest(unittest.TestCase):
    def blockers(self, texts, skips, changed):
        findings = [parse_finding(text) for text in texts]
        adopted = {ADOPTED_FINDING: ADOPTED_RULING}
        unapplied = review_loop_ruled.unapplied_adopted(findings, adopted, skips, changed, "/repo")
        return [item.blocker for item in unapplied]

    def test_an_adopted_finding_the_coder_skipped_or_left_no_diff_for_is_a_blocker_naming_the_ruling(self):
        cases = (
            ("skipped", {1: "SKIPPED 1: no"}, ["app.py"], review_loop_ruled.SKIPPED_WHY),
            ("no diff", {}, [], review_loop_ruled.NO_FILE_DIFF_WHY),
            ("another file changed", {}, ["other.py"], review_loop_ruled.NO_FILE_DIFF_WHY),
        )
        for label, skips, changed, why in cases:
            with self.subTest(label):
                blockers = self.blockers([ADOPTED_FINDING], skips, changed)

                self.assertEqual(len(blockers), 1, label)
                self.assertIn(why, blockers[0])
                self.assertIn("ruled 2026-11-19 10:00", blockers[0])
                self.assertIn("the user", blockers[0])

    def test_an_applied_adopted_finding_and_a_plain_finding_are_no_blocker(self):
        self.assertEqual(self.blockers([ADOPTED_FINDING], {}, ["app.py"]), [])
        self.assertEqual(self.blockers(["a.py:1 [bug] plain"], {1: "SKIPPED 1: no"}, []), [])

    def test_an_adopted_finding_with_no_path_needs_only_some_diff_in_the_pass(self):
        text = review_user_ruled.adopted_issue("PLAN-IMPACT: AC2 reworded.", ADOPTED_RULING)
        findings = [parse_finding(text)]
        adopted = {text: ADOPTED_RULING}

        no_diff = review_loop_ruled.unapplied_adopted(findings, adopted, {}, [], "/repo")
        some_diff = review_loop_ruled.unapplied_adopted(findings, adopted, {}, ["x.py"], "/repo")

        self.assertIn(review_loop_ruled.NO_DIFF_WHY, no_diff[0].blocker)
        self.assertEqual(some_diff, [])

    def test_an_adopted_finding_the_loop_withheld_is_a_blocker_naming_why(self):
        finding = parse_finding(ADOPTED_FINDING)
        plain = parse_finding("a.py:1 [bug] plain")
        adopted = {ADOPTED_FINDING: ADOPTED_RULING}

        held = review_loop_ruled.withheld_adopted([finding, plain], adopted, [], [finding])
        ruled_out = review_loop_ruled.withheld_adopted([finding, plain], adopted, [], [])
        sent = review_loop_ruled.withheld_adopted([finding, plain], adopted, [finding], [])

        self.assertEqual([item.finding for item in held], [finding])
        self.assertIn(review_loop_ruled.HELD_WHY, held[0].blocker)
        self.assertIn(review_loop_ruled.RULED_OUT_WHY, ruled_out[0].blocker)
        self.assertEqual(sent, [])

    def test_an_adopted_finding_the_sign_off_put_back_undid_is_not_recorded_as_applied(self):
        finding = parse_finding(ADOPTED_FINDING)
        host = Host()
        host.adopted = {ADOPTED_FINDING: ADOPTED_RULING}
        host.session_id = "s1"
        host.put_back_findings = [finding]
        host.not_put_back = types.MethodType(review_loop_signoffs.SignoffRuns.not_put_back, host)

        with mock.patch.object(handback_store, "record_applied_ruling") as record_applied:
            host.settle_adopted_after_pass([finding], {}, ["app.py"])

        record_applied.assert_not_called()

    def test_an_adopted_finding_keeps_its_own_mark_in_the_coders_issue_list(self):
        host = Host()
        host.adopted = {ADOPTED_FINDING: ADOPTED_RULING}
        host.user_ruled = [ADOPTED_FINDING]
        host.user_ruled_at = "2026-11-13 11:32:00Z"

        self.assertEqual(host.issue_text(parse_finding(ADOPTED_FINDING)), ADOPTED_FINDING)


class AdoptedRulingRoundTest(ReviewLoopHarness, unittest.TestCase):
    """The fix-first round of a resume that adopts a plan change."""

    def run_adopted(self, coder_reply, findings=(ADOPTED_FINDING,)):
        findings_file = self.scratch / "findings.json"
        findings_file.write_text(json.dumps(list(findings)))
        row = {"number": 1, **ADOPTED_RULING._asdict()}
        header = (f"mode: fix-first\nfindings: {findings_file}\nuser-ruled: 1\n"
                  f"user-ruled-at: 2026-11-19 10:00:00Z\nadopted: {json.dumps([row])}\n")
        scenario = {"coder": [coder_reply], "code-reviewer": [{"result": CLEAN_REVIEW}] * 2,
                    "closure": [{"result": CLOSED}]}
        completed = self.run_script(scenario, header_extra=header)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        _row, packet = self.stored_packet()
        return packet

    def test_a_coder_that_changes_nothing_for_an_adopted_ruling_ends_the_round_with_a_blocker_and_no_reviewer(self):
        packet = self.run_adopted({"result": "Fixed 1."})

        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("2026-11-19 10:00", packet["blockers"][0])
        self.assertIn(review_loop_ruled.NO_DIFF_WHY, packet["blockers"][0])
        self.assertEqual([call["key"] for call in self.fake_calls()], ["coder"])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(packet["ask"], [])
        self.assertIn(ADOPTED_FINDING, json.dumps(packet["findings_remaining"]))

    def test_a_coder_that_skips_the_adopted_finding_ends_the_round_with_a_blocker_and_no_reviewer(self):
        packet = self.run_adopted({"result": "SKIPPED 1: needs a sign-off.", "edits": {"app.py": APP_FIXED}})

        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn(review_loop_ruled.SKIPPED_WHY, packet["blockers"][0])
        self.assertEqual([call["key"] for call in self.fake_calls()], ["coder"])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(packet["ask"], [])
        self.assertIn(ADOPTED_FINDING, json.dumps(packet["findings_remaining"]))

    def seed_adopt_row(self):
        """Records the adopt decision the launch reads, in the store the run writes its applied row to."""
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            handback_store.record_ruled_impact(
                SESSION, ADOPTED_RULING.text, handback_store.ruled_rows_repo(self.repo), decision="adopt",
                owner=ADOPTED_RULING.owner, ruled_at=ADOPTED_RULING.ruled_at)

    def adopted_left(self):
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            return handback_store.rulings(SESSION, handback_store.ruled_rows_repo(self.repo)).adopted

    def test_an_applied_adopted_ruling_is_recorded_as_applied(self):
        self.seed_adopt_row()
        self.assertEqual(len(self.adopted_left()), 1)

        packet = self.run_adopted({"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}})

        self.assertNotEqual(packet["status"], "critical-blocker")
        self.assertEqual(self.adopted_left(), ())

    def test_an_adopted_ruling_the_coder_left_unapplied_stays_adopted(self):
        self.seed_adopt_row()

        self.run_adopted({"result": "Fixed 1."})

        self.assertEqual(len(self.adopted_left()), 1)

    def test_a_plain_finding_the_coder_fixed_is_fixed_beside_an_unapplied_adopted_one(self):
        plain = "app.py:1 [bug] plain finding"

        packet = self.run_adopted({"result": "SKIPPED 1: needs a sign-off.\nFixed 2.", "edits": {"app.py": APP_FIXED}},
                                  findings=(ADOPTED_FINDING, plain))

        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn(plain, json.dumps(packet["fixed"]))
        self.assertIn(ADOPTED_FINDING, json.dumps(packet["findings_remaining"]))
        self.assertEqual(packet["skipped_fp"], [])


if __name__ == "__main__":
    unittest.main()
