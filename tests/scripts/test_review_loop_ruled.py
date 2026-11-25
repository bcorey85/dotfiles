import dataclasses
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
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import approval_asks_store
import approval_restore
import coder_report
import finding_record
import handback
import handback_store
import plan_format
import review_asks
import review_fix_asks
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
from owner_line_fixtures import SCRIPTS_MD, SCRIPTS_MD_WITH_NEW_BULLET
from owner_lines import SCRIPTS_CLAUDE_MD
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


class WantedTargetPathTest(unittest.TestCase):
    def test_the_path_a_change_ends_with_is_read_back_and_anything_else_is_none(self):
        target = approval_asks_store.wanted_edit_target
        cases = [
            (f"add the line. {target('a/CLAUDE.md')}", "a/CLAUDE.md", "a path ends the change"),
            (f"add the line. {target('my dir/CLAUDE.md')}", "my dir/CLAUDE.md", "a folder with a space"),
            (f"{target('old/CLAUDE.md')} then {target('new/CLAUDE.md')}", "new/CLAUDE.md", "the last target wins"),
            ("add the line.", None, "no target"),
            (f"{target('CLAUDE.md')} and more", None, "text after the target"),
            (target(""), None, "an empty path"),
            (None, None, "not a string"),
        ]
        for change, expected, message in cases:
            with self.subTest(message):
                self.assertEqual(approval_asks_store.wanted_path_of_change(change), expected)


class ApprovalOnlyPathsTest(unittest.TestCase):
    def test_only_a_file_named_claude_md_needs_approval_whatever_its_folder(self):
        changed = ["a/b.py", "CLAUDE.md", "x/y/CLAUDE.md", "NOT_CLAUDE.md", "docs/CLAUDE.md.bak", "claude.md"]
        self.assertEqual(review_loop_ruled.approval_only_paths(changed), ["CLAUDE.md", "x/y/CLAUDE.md"])

    def test_an_agents_md_and_a_claude_local_md_edit_need_approval(self):
        changed = ["AGENTS.md", "x/CLAUDE.local.md", "a/b.py"]
        self.assertEqual(review_loop_ruled.approval_only_paths(changed), ["AGENTS.md", "x/CLAUDE.local.md"])


def approval_host(user_ruled=(), session_ruled=(), reverts=False):
    """A loop host. Unless `reverts`, a coder's approval-only edit cannot be reverted, so it is filed as an ask:
    the tests of the ask path and its resume read the ask that way."""
    host = Host()
    if not reverts:
        host.revert_approval_edit = lambda path: False
    host.asks, host.ask_gates, host.ask_rounds, host.iter_count = [], {}, {}, 1
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

    def test_a_session_ruling_on_a_scripts_claude_md_wanted_change_ask_files_no_ask(self):
        target = approval_asks_store.wanted_edit_target(SCRIPTS_CLAUDE_MD)
        finding = parse_finding(f"`{SCRIPTS_CLAUDE_MD}:3` [bug] Change: add the owner line. {target}")
        self.assertEqual(self.ask_filed(finding, session_ruled=[finding.text], changed=SCRIPTS_CLAUDE_MD), 0)

    def test_a_session_ruling_on_a_wanted_change_ask_for_another_approval_file_still_files_the_ask(self):
        target = approval_asks_store.wanted_edit_target("CLAUDE.md")
        finding = parse_finding(f"`CLAUDE.md:3` [bug] Change: reword the rule. {target}")
        self.assertEqual(self.ask_filed(finding, session_ruled=[finding.text]), 1)

    def test_a_session_ruling_with_a_note_on_a_scripts_claude_md_wanted_change_ask_files_no_ask(self):
        target = approval_asks_store.wanted_edit_target(SCRIPTS_CLAUDE_MD)
        ruled = accepted_approval_ask_text(SCRIPTS_CLAUDE_MD, "keep the edit and reword line 3", "session")
        finding = parse_finding(f"{ruled} {target}")
        self.assertEqual(self.ask_filed(finding, session_ruled=[finding.text], changed=SCRIPTS_CLAUDE_MD), 0)

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

    def filed_host(self, changed):
        host = approval_host()
        host.ask_for_approval_only_edits(changed, [])
        return host

    def flags_of(self, host):
        outcome = {"status": "converged", "asks": host.asks, "ask_gates": host.ask_gates,
                   "user_only_asks": host.user_only_asks}
        entries = review_loop_packet.ask_entries({**review_loop_packet.EMPTY_OUTCOME, **outcome})
        return [(entry["file_line"], entry.get("user_only")) for entry in entries]

    def test_an_ask_for_only_the_scripts_claude_md_is_not_user_only_and_stays_saved(self):
        host = self.filed_host([SCRIPTS_CLAUDE_MD])

        self.assertEqual(self.flags_of(host), [(f"{SCRIPTS_CLAUDE_MD}:1", None)])
        self.assertEqual(host.approval_ask_paths, [SCRIPTS_CLAUDE_MD])

    def test_the_scripts_claude_md_ask_is_saved_with_its_base_for_a_resumed_run(self):
        host = self.filed_host([SCRIPTS_CLAUDE_MD])
        with tempfile.TemporaryDirectory() as folder:
            repo = pathlib.Path(folder).resolve()
            (repo / "CLAUDE.md").write_text("rules\n")
            init_repo(repo)
            host.repo = str(repo)
            host.save_approval_paths()
            saved = approval_asks_store.read_approval_paths(str(repo))

        self.assertEqual(saved, {SCRIPTS_CLAUDE_MD: host.approval_ask_bases[SCRIPTS_CLAUDE_MD]})

    def test_an_ask_for_another_approval_file_beside_the_scripts_claude_md_stays_user_only(self):
        flags = self.flags_of(self.filed_host([SCRIPTS_CLAUDE_MD, "CLAUDE.md"]))

        self.assertEqual(flags, [(f"{SCRIPTS_CLAUDE_MD}:1", None), ("CLAUDE.md:1", True)])

    def test_a_wanted_change_ask_for_the_scripts_claude_md_is_not_user_only(self):
        finding = parse_finding(f"`{SCRIPTS_CLAUDE_MD}:4` [docs] stale owner — update it")
        host = approval_host()
        host.ask_for_wanted_changes([finding], [SCRIPTS_CLAUDE_MD])
        self.assertEqual(len(host.asks), 1)
        self.assertEqual(host.user_only_asks, [])
        self.assertEqual(len(host.wanted_entries), 1)
        self.assertEqual(self.flags_of(host), [(f"{SCRIPTS_CLAUDE_MD}:4", None)])

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

    def host(self, rejected=(), reverts=False):
        host = approval_host(reverts=reverts)
        host.repo = self.repo
        host.rejected_asks = list(rejected)
        host.approval_blobs = dict(self.blobs_before_coder)
        host.approval_snapshot_ok = True
        return host

    def edit_claude_md(self):
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("rules\nnew rule\n")

    def saved_paths(self):
        return list(approval_asks_store.read_approval_paths(self.repo))

    def test_a_reverted_claude_md_edit_for_a_finding_becomes_a_user_only_ask_carrying_its_change(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        self.edit_claude_md()
        host = self.host(reverts=True)
        host.open_fixes = []

        reverted = host.ask_for_approval_only_edits(["CLAUDE.md"], [finding])
        kept_open = host.findings_on_reverted_paths([finding], reverted)

        self.assertEqual(reverted, ["CLAUDE.md"])
        self.assertEqual((pathlib.Path(self.repo) / "CLAUDE.md").read_text(), "rules\n")
        self.assertEqual(len(host.asks), 1)
        self.assertIn(host.asks[0], host.user_only_asks)
        self.assertEqual(host.asks[0].path, "CLAUDE.md")
        self.assertIn("add the new rule to the list.", host.asks[0].text)
        self.assertEqual(kept_open, [finding], "the finding is still held out of the fixed and skipped sets")
        self.assertEqual(host.open_fixes, [], "the finding is an ask, not an open fix")

    def test_a_reverted_claude_md_edit_no_finding_names_is_reported_as_dropped_and_files_no_ask(self):
        other_finding = parse_finding("`app.py:2` [bug] Proposed change: guard the limit.")
        self.edit_claude_md()
        host = self.host(reverts=True)

        host.ask_for_approval_only_edits(["CLAUDE.md"], [other_finding])

        self.assertEqual((pathlib.Path(self.repo) / "CLAUDE.md").read_text(), "rules\n")
        self.assertEqual(host.asks, [])
        self.assertEqual(host.user_only_asks, [])
        self.assertEqual([(ask.path, reason) for ask, reason in host.dropped_asks],
                         [("CLAUDE.md", review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON)])
        self.assertEqual(approval_asks_store.read_saved_asks(self.repo), ({}, []))

    def test_each_finding_on_the_file_gets_its_own_question_naming_the_file_and_the_finding(self):
        first = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        second = parse_finding("`CLAUDE.md:5` [bug] Proposed change: drop the stale rule from the list.")
        self.edit_claude_md()
        host = self.host(reverts=True)

        host.ask_for_approval_only_edits(["CLAUDE.md"], [first, second])

        questions = [review_loop_findings.ask_parts(ask.text).question for ask in host.asks]
        self.assertEqual(len(set(questions)), 2, "one distinct question per finding")
        for question, finding in zip(questions, (first, second), strict=True):
            self.assertIn("`CLAUDE.md`", question)
            self.assertIn(finding.title, question)

    def stored_rejection(self, ask):
        """The record of `ask` as asks-done stores it when the user rejects it."""
        question = review_loop_findings.ask_parts(ask.text).question
        item = {"question": question, "file_line": f"{ask.path}:{ask.line}"}
        return parse_finding(review_asks.rejected_ask_text(item))

    def filed_wanted_ask(self, finding):
        """The wanted-change ask a reverted edit for `finding` files, from a throwaway host."""
        self.edit_claude_md()
        host = self.host(reverts=True)
        host.ask_for_approval_only_edits(["CLAUDE.md"], [finding])
        return host.asks[0]

    def test_a_rejected_wanted_change_ask_is_dropped_when_it_comes_again(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        rejection = self.stored_rejection(self.filed_wanted_ask(finding))
        self.edit_claude_md()
        host = self.host(rejected=[rejection], reverts=True)

        host.ask_for_approval_only_edits(["CLAUDE.md"], [finding])

        self.assertEqual(host.asks, [])
        self.assertIn(review_loop_findings.REJECTED_ASK_REASON, [reason for _ask, reason in host.dropped_asks])

    def test_a_rejection_on_one_claude_md_leaves_the_same_finding_on_another_folders_claude_md_filed(self):
        nested = pathlib.Path(self.repo) / "sub" / "CLAUDE.md"
        nested.parent.mkdir()
        nested.write_text("sub rules\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "sub")
        root_finding = parse_finding("`CLAUDE.md:2` [docs] stale path — update it")
        sub_finding = parse_finding("`sub/CLAUDE.md:2` [docs] stale path — update it")
        rejection = self.stored_rejection(self.filed_wanted_ask(root_finding))
        host = self.host(rejected=[rejection], reverts=True)
        host.snapshot_approval_blobs()
        nested.write_text("sub rules\nnew\n")

        host.ask_for_approval_only_edits(["sub/CLAUDE.md"], [sub_finding])

        self.assertEqual([ask.path for ask in host.asks], ["sub/CLAUDE.md"])

    def test_a_rejected_revert_ask_does_not_drop_the_wanted_change_ask(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        revert_rejection = parse_finding(review_loop_ruled.approval_ask_text("CLAUDE.md"))
        self.edit_claude_md()
        host = self.host(rejected=[revert_rejection], reverts=True)

        host.ask_for_approval_only_edits(["CLAUDE.md"], [finding])

        self.assertEqual(len(host.asks), 1)

    def test_rejecting_one_wanted_ask_keeps_another_short_titled_finding_on_the_same_file(self):
        rejected_finding = parse_finding("`CLAUDE.md:3` [docs] stale path — update it")
        other_finding = parse_finding("`CLAUDE.md:9` [docs] typo — fix it")
        rejection = self.stored_rejection(self.filed_wanted_ask(rejected_finding))
        self.edit_claude_md()
        host = self.host(rejected=[rejection], reverts=True)

        host.ask_for_approval_only_edits(["CLAUDE.md"], [rejected_finding, other_finding])

        self.assertEqual([entry["title"] for entry in host.wanted_entries], [other_finding.title])
        self.assertEqual(len(host.wanted_entries), 1)

    def test_a_rejected_wanted_ask_stays_rejected_when_the_finding_comes_again_on_another_line(self):
        rejected_finding = parse_finding("`CLAUDE.md:3` [docs] stale path — update it")
        moved_finding = parse_finding("`CLAUDE.md:4` [docs] stale path — update it")
        rejection = self.stored_rejection(self.filed_wanted_ask(rejected_finding))
        self.edit_claude_md()
        host = self.host(rejected=[rejection], reverts=True)

        host.ask_for_approval_only_edits(["CLAUDE.md"], [moved_finding])

        self.assertEqual(host.asks, [], "the user already rejected this finding")

    def test_a_later_round_that_reverts_the_same_finding_files_one_ask(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        moved = parse_finding("`CLAUDE.md:7` [bug] Proposed change: add the new rule to the list.")
        host = self.host(reverts=True)
        for round_finding in (finding, moved):
            self.edit_claude_md()
            host.ask_for_approval_only_edits(["CLAUDE.md"], [round_finding])

        self.assertEqual(len(host.asks), 1)
        self.assertEqual(len(host.wanted_entries), 1)

    def test_a_finding_with_no_line_on_a_nested_claude_md_files_its_ask_at_line_one(self):
        nested = pathlib.Path(self.repo) / "docs" / "CLAUDE.md"
        nested.parent.mkdir()
        nested.write_text("docs rules\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "docs")
        host = self.host(reverts=True)
        host.snapshot_approval_blobs()
        nested.write_text("docs rules\nnew\n")
        finding = parse_finding("`docs/CLAUDE.md` [docs] missing rule — add it")

        host.ask_for_approval_only_edits(["docs/CLAUDE.md"], [finding])

        self.assertEqual([(ask.path, ask.line) for ask in host.asks], [("docs/CLAUDE.md", 1)])
        self.assertEqual(nested.read_text(), "docs rules\n")

    def test_a_conditional_branch_kept_in_a_finding_change_does_not_move_the_ask_split(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Is it needed? Change if yes: add A. Change if no: add B")
        self.edit_claude_md()
        host = self.host(reverts=True)

        host.ask_for_approval_only_edits(["CLAUDE.md"], [finding])

        change = review_loop_findings.ask_parts(host.asks[0].text).change
        target = approval_asks_store.wanted_edit_target("CLAUDE.md")
        self.assertTrue(change.startswith("add A."), change)
        self.assertIn("add B", change)
        self.assertTrue(change.endswith(target), change)
        self.assertTrue(review_asks.is_conditional_change(change), change)

    def test_an_accepted_wanted_ask_for_a_folder_with_a_space_is_not_reverted_again(self):
        folder = pathlib.Path(self.repo) / "sub dir"
        folder.mkdir()
        target = folder / "CLAUDE.local.md"
        target.write_text("mine\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "local")
        filing = self.host(reverts=True)
        filing.snapshot_approval_blobs()
        target.write_text("mine\ncoder\n")
        # The finding parser reads no path with a space, so the finding takes its location by hand.
        located_finding = parse_finding("`x.md:1` [docs] stale rule. Proposed change: drop it.")
        finding = dataclasses.replace(located_finding, path="sub dir/CLAUDE.local.md", line=1)
        filing.ask_for_approval_only_edits(["sub dir/CLAUDE.local.md"], [finding])
        item = review_loop_packet.ask_entry(filing.asks[0], "coder", None, user_only=True)
        accepted = review_fix_asks.ask_finding_text(item)

        later = approval_host(user_ruled=[accepted], reverts=True)
        later.repo = self.repo
        later.snapshot_approval_blobs()
        target.write_text("mine\ncoder\n")
        later.ask_for_approval_only_edits(["sub dir/CLAUDE.local.md"], [parse_finding(accepted)])

        self.assertEqual(target.read_text(), "mine\ncoder\n", "the user's approval keeps the edit")
        self.assertEqual(later.asks, [])

    def test_a_wanted_ask_a_kept_held_packet_waits_on_is_not_filed_again_on_resume(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        self.edit_claude_md()
        self.host(reverts=True).ask_for_approval_only_edits(["CLAUDE.md"], [finding])
        _paths, wanted = approval_asks_store.read_saved_asks(self.repo)

        resumed = self.host()
        resumed.resume_wanted_asks(wanted, {wanted[0]["change"]})

        self.assertEqual(resumed.asks, [])

    def test_a_later_pass_files_no_second_ask_for_a_wanted_ask_a_kept_held_packet_waits_on(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        self.edit_claude_md()
        self.host(reverts=True).ask_for_approval_only_edits(["CLAUDE.md"], [finding])
        _paths, wanted = approval_asks_store.read_saved_asks(self.repo)
        resumed = self.host(reverts=True)
        resumed.resume_wanted_asks(wanted, {wanted[0]["change"]})

        resumed.snapshot_approval_blobs()
        self.edit_claude_md()
        resumed.ask_for_approval_only_edits(["CLAUDE.md"], [finding])
        resumed.save_approval_paths()

        self.assertEqual(resumed.asks, [], "the held ask is not filed a second time")
        self.assertEqual(approval_asks_store.read_saved_asks(self.repo)[1], wanted,
                         "the held ask stays saved while its packet waits")

    def test_a_wanted_change_ask_survives_a_run_that_died_and_leaves_the_file_when_ruled(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        self.edit_claude_md()
        self.host(reverts=True).ask_for_approval_only_edits(["CLAUDE.md"], [finding])

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(len(resumed.asks), 1)
        self.assertIn("add the new rule to the list.", resumed.asks[0].text)
        self.assertIn(resumed.asks[0], resumed.user_only_asks)
        ruled = {"question": "q", "file_line": "CLAUDE.md:2", "user_only": True,
                 "change": review_loop_findings.ask_parts(resumed.asks[0].text).change}
        approval_asks_store.forget_ruled_approval_paths(self.repo, [ruled])
        later = self.host()
        later.resume_approval_asks([])
        self.assertEqual(later.asks, [])

    def test_a_ruled_unmarked_wanted_change_ask_leaves_the_saved_wanted_entry(self):
        target = approval_asks_store.wanted_edit_target(SCRIPTS_CLAUDE_MD)
        change = f"update the owner line {target}"
        entry = approval_asks_store.wanted_entry(
            f"`{SCRIPTS_CLAUDE_MD}:4` [docs] stale owner Change: {change}", change, SCRIPTS_CLAUDE_MD, 4, "")
        approval_asks_store.write_saved_asks(self.repo, {}, [entry])
        ruled = {"question": "q", "file_line": f"{SCRIPTS_CLAUDE_MD}:4", "change": change}

        approval_asks_store.forget_ruled_approval_paths(self.repo, [ruled])

        self.assertEqual(approval_asks_store.read_saved_asks(self.repo), ({}, []))

    def test_the_saved_file_reads_an_older_flat_object_and_round_trips_paths_and_wanted_asks(self):
        saved = approval_asks_store.approval_paths_file(self.repo)
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text('{"CLAUDE.md": null}')
        self.assertEqual(approval_asks_store.read_saved_asks(self.repo), ({"CLAUDE.md": None}, []))

        entry = {"text": "`CLAUDE.md:1` [other] q Change: c", "change": "c", "path": "CLAUDE.md", "line": 1,
                 "title": ""}
        approval_asks_store.write_saved_asks(self.repo, {"AGENTS.md": None}, [entry])

        self.assertEqual(approval_asks_store.read_saved_asks(self.repo), ({"AGENTS.md": None}, [entry]))
        saved.write_text('{"paths": {}, "wanted": [{"text": 1}]}')
        with self.assertRaises(approval_asks_store.ApprovalAsksFileError):
            approval_asks_store.read_saved_asks(self.repo)

    def test_a_merged_finding_on_a_reverted_claude_md_becomes_one_ask_carrying_every_part_change(self):
        first = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add rule A.")
        second = parse_finding("`CLAUDE.md:2` [bug] Proposed change: fix typo B.")
        merged = finding_record.combine([first, second])
        self.edit_claude_md()
        host = self.host(reverts=True)
        host.open_fixes = []

        host.ask_for_approval_only_edits(["CLAUDE.md"], [merged])

        self.assertEqual(len(host.asks), 1)
        self.assertIn("add rule A.", host.asks[0].text)
        self.assertIn("fix typo B.", host.asks[0].text)

    def test_a_ruled_approval_ask_leaves_the_saved_paths_whatever_the_outcome(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        ask = {"question": "q", "file_line": "CLAUDE.md:1", "user_only": True,
               "change": approval_asks_store.approval_change("CLAUDE.md")}
        other = {"question": "q", "file_line": "a.py:1", "change": "rename the helper."}

        approval_asks_store.forget_ruled_approval_paths(self.repo, [other])
        self.assertEqual(self.saved_paths(), ["CLAUDE.md"], "an ask that is no approval ask leaves the file alone")

        approval_asks_store.forget_ruled_approval_paths(self.repo, [ask])
        self.assertEqual(self.saved_paths(), [], "a ruled user-only ask leaves the saved paths")

    def test_a_ruled_approval_ask_without_the_user_only_mark_leaves_the_saved_paths(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        unmarked_ask = {"question": "q", "file_line": "CLAUDE.md:1",
                        "change": approval_asks_store.approval_change("CLAUDE.md")}

        approval_asks_store.forget_ruled_approval_paths(self.repo, [unmarked_ask])

        self.assertEqual(self.saved_paths(), [])

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

    def file_the_coder_edit_over_user_lines(self, snapshot_ok=True):
        """CLAUDE.md holds an uncommitted user line before the pass; the pass appends a coder line and the loop files
        its approval ask. Returns the filed ask as asks-done receives it."""
        claude_md = pathlib.Path(self.repo) / "CLAUDE.md"
        claude_md.write_text("rules\nuser line\n")
        host = approval_host()
        host.repo = self.repo
        host.snapshot_approval_blobs()
        host.approval_snapshot_ok = snapshot_ok
        claude_md.write_text("rules\nuser line\ncoder line\n")
        host.ask_for_approval_only_edits(["CLAUDE.md"], [])
        return {"question": "q", "file_line": "CLAUDE.md:1", "user_only": True,
                "change": approval_asks_store.approval_change("CLAUDE.md")}

    def test_an_accepted_approval_ask_restores_the_pre_pass_text_and_not_head(self):
        ask = self.file_the_coder_edit_over_user_lines()

        restored = approval_restore.restore_accepted_approvals(self.repo, [ask], ["accepted"])

        self.assertEqual(restored, [approval_restore.RestoredApproval(0, "CLAUDE.md")])
        self.assertEqual((pathlib.Path(self.repo) / "CLAUDE.md").read_text(), "rules\nuser line\n")

    def test_a_saved_none_base_for_a_tracked_file_is_not_deleted(self):
        ask = self.file_the_coder_edit_over_user_lines()
        approval_asks_store.write_saved_asks(self.repo, {"CLAUDE.md": None}, [])

        restored = approval_restore.restore_accepted_approvals(self.repo, [ask], ["accepted"])

        self.assertEqual(restored, [])
        self.assertTrue((pathlib.Path(self.repo) / "CLAUDE.md").exists())

    def test_a_file_the_pass_created_is_deleted_on_acceptance(self):
        agents_md = pathlib.Path(self.repo) / "AGENTS.md"
        agents_md.write_text("coder rules\n")
        approval_asks_store.write_saved_asks(self.repo, {"AGENTS.md": None}, [])
        ask = {"question": "q", "file_line": "AGENTS.md:1", "user_only": True,
               "change": approval_asks_store.approval_change("AGENTS.md")}

        restored = approval_restore.restore_accepted_approvals(self.repo, [ask], ["accepted"])

        self.assertEqual(restored, [approval_restore.RestoredApproval(0, "AGENTS.md")])
        self.assertFalse(agents_md.exists())

    def test_an_ask_matching_no_saved_path_restores_nothing_and_indexes_follow_ask_order(self):
        ask = self.file_the_coder_edit_over_user_lines()
        stranger = {"question": "q", "file_line": "x.md:1", "user_only": True,
                    "change": approval_asks_store.approval_change("x.md")}

        restored = approval_restore.restore_accepted_approvals(self.repo, [stranger, ask], ["accepted", "accepted"])

        self.assertEqual(restored, [approval_restore.RestoredApproval(1, "CLAUDE.md")])

    def test_an_approval_ask_ruled_rejected_modified_or_applied_is_not_restored(self):
        ask = self.file_the_coder_edit_over_user_lines()

        for outcome in ("rejected", "modified", "applied"):
            with self.subTest(outcome=outcome):
                restored = approval_restore.restore_accepted_approvals(self.repo, [ask], [outcome])

                self.assertEqual(restored, [])
                self.assertEqual(
                    (pathlib.Path(self.repo) / "CLAUDE.md").read_text(), "rules\nuser line\ncoder line\n")

    def test_an_unknown_base_is_saved_as_its_own_value_and_is_not_restored(self):
        ask = self.file_the_coder_edit_over_user_lines(snapshot_ok=False)

        saved = approval_asks_store.read_approval_paths(self.repo)
        restored = approval_restore.restore_accepted_approvals(self.repo, [ask], ["accepted"])

        self.assertEqual(saved, {"CLAUDE.md": approval_asks_store.UNKNOWN_BASE})
        self.assertEqual(restored, [], "the coder still reverts an ask with an unknown base")
        self.assertEqual((pathlib.Path(self.repo) / "CLAUDE.md").read_text(), "rules\nuser line\ncoder line\n")

    def test_an_unknown_base_files_the_ask_again_on_resume(self):
        self.file_the_coder_edit_over_user_lines(snapshot_ok=False)
        resumed = self.host()
        resumed.resume_approval_asks([])
        self.assertEqual([ask.path for ask in resumed.asks], ["CLAUDE.md"])

    def test_a_restore_that_fails_names_the_file_and_the_blob(self):
        ask = self.file_the_coder_edit_over_user_lines()
        missing_blob = "0123456789abcdef0123456789abcdef01234567"
        approval_asks_store.write_saved_asks(self.repo, {"CLAUDE.md": missing_blob}, [])

        with self.assertRaises(approval_restore.ApprovalRestoreError) as raised:
            approval_restore.restore_accepted_approvals(self.repo, [ask], ["accepted"])

        self.assertIn("CLAUDE.md", str(raised.exception))
        self.assertIn(missing_blob, str(raised.exception))
        self.assertIn("was pruned", str(raised.exception))
        self.assertIn("by hand", str(raised.exception))
        self.assertEqual((pathlib.Path(self.repo) / "CLAUDE.md").read_text(), "rules\nuser line\ncoder line\n")

    def hold_the_approval_ask(self):
        """Keeps the ask for CLAUDE.md in a held packet of a session whose own repo is another one, so the fix state
        is not saved under this repo; returns the held ask. Only the packet repo's approval store can tell the loop."""
        held_ask = {"question": "q", "file_line": "CLAUDE.md:1", "user_only": True,
                    "change": approval_asks_store.approval_change("CLAUDE.md")}
        state = {"packet_id": "p1", "asks": []}
        parent = {"packet_id": "p1", "relaunch_args": ["--repo", str(self.repo)]}
        held_changes = review_fix_asks.held_approval_changes(parent, [held_ask])
        review_fix_asks.keep_held_packet(state, parent, [held_ask])
        approval_asks_store.write_held_changes(held_changes.repo, held_changes.changes)
        return held_ask

    def test_a_fix_run_loop_resume_files_no_ask_for_a_path_a_kept_packet_holds(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        held_ask = self.hold_the_approval_ask()

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(resumed.asks, [], "the kept packet owns the ask, so the loop files none")
        self.assertEqual(self.saved_paths(), ["CLAUDE.md"], "the saved base stays until the user rules")

        approval_asks_store.forget_ruled_approval_paths(self.repo, [held_ask])
        self.assertEqual(self.saved_paths(), [], "the user's ruling on the kept packet drops the path")
        self.assertEqual(approval_asks_store.read_held_changes(self.repo), set(),
                         "the user's ruling on the kept packet clears the held record")

    def test_a_resumed_run_files_no_ask_for_a_saved_path_that_matches_head(self):
        self.edit_claude_md()
        self.git("commit", "-q", "-am", "the coder's commit")
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(resumed.asks, [])
        self.assertEqual(self.saved_paths(), [])

    def test_a_resumed_run_holds_the_ask_for_a_saved_path_that_differs_from_head(self):
        self.edit_claude_md()
        self.git("commit", "-q", "-am", "the coder's commit")
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("rules\nnew rule\nand one more\n")
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual([ask.path for ask in resumed.asks], ["CLAUDE.md"])
        self.assertEqual(self.saved_paths(), ["CLAUDE.md"])

    def test_a_resumed_run_files_the_wanted_ask_of_a_reverted_edit_but_no_revert_ask(self):
        finding = parse_finding("`CLAUDE.md:2` [bug] Proposed change: add the new rule to the list.")
        self.edit_claude_md()
        reverting = self.host(reverts=True)
        reverting.ask_for_approval_only_edits(["CLAUDE.md"], [finding])
        self.assertEqual(len(reverting.asks), 1)

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual([ask.text for ask in resumed.asks], [ask.text for ask in reverting.asks])
        self.assertEqual(self.saved_paths(), [])

    def test_a_saved_path_whose_file_was_reverted_to_head_by_a_session_files_no_ask(self):
        self.edit_claude_md()
        self.host().ask_for_approval_only_edits(["CLAUDE.md"], [])
        self.assertEqual(self.saved_paths(), ["CLAUDE.md"])
        self.git("checkout", "-q", "--", "CLAUDE.md")

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(resumed.asks, [])
        self.assertEqual(self.saved_paths(), [])

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

    STANDING = ('# Plan\n\n## Plan Deviations\n\n- Standing ruling by Pat at 2026-11-19: follow one rule '
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
        bad_plan = '# Plan\n\n## Plan Deviations\n\n- Standing ruling by Pat at yesterday: x covers: rewords\n'

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            self.routed_with_plan(bad_plan)

        message = str(raised.exception)
        self.assertIn("plan.md:5:", message)
        self.assertIn("expected", message)

    def test_a_malformed_standing_ruling_is_not_read_for_an_impact_that_is_not_a_reword(self):
        bad_plan = '# Plan\n\n## Plan Deviations\n\n- Standing ruling by Pat at yesterday: x covers: rewords\n'

        to_coder, held, _impacts = self.routed_with_plan(bad_plan, kind="cut")

        self.assertEqual((to_coder, len(held)), ([], 1))

    def test_the_flag_reaches_the_packet_and_survives_loading_it(self):
        host = Host()
        host.record_coder_plan_impact(self.REPORT.format(kind="reword"), [])

        message = review_loop_packet.packet_message({"status": "converged", "plan_impacts": host.plan_impacts})

        self.assertTrue(handback.load(message)["plan_impacts"][0]["reword"])


def git_in(repo, *argv):
    subprocess.run(["git", *argv], cwd=repo, env={**os.environ, **GIT_ENV}, check=True, capture_output=True)


def init_repo(repo):
    """Makes `repo` a git repo on main with every file in it committed."""
    for argv in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-q", "-m", "init"]):
        git_in(repo, *argv)


class ApprovalEditRevertTest(unittest.TestCase):
    """A fix coder's edit to an approval-only file is put back and reported, never filed as an ask."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name).resolve()
        self.claude_md = self.repo / "CLAUDE.md"
        self.claude_md.write_text("rules\n")
        init_repo(self.repo)

    def coder_pass(self, edit, changed):
        """Runs `edit` between the snapshot and the ask step, as a coder pass does. Returns the host."""
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.files_touched = set()
        host.snapshot_approval_blobs()
        edit()
        host.ask_for_approval_only_edits(changed, [])
        return host

    def git_run(self, *argv):
        git_in(self.repo, *argv)

    def staged_names(self):
        done = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.repo, capture_output=True,
                              text=True, check=True)
        return done.stdout.split()

    def test_an_edit_the_coder_staged_is_unstaged_with_the_work_tree_revert(self):
        def stage_edit():
            self.claude_md.write_text("rules\nnew rule\n")
            self.git_run("add", "CLAUDE.md")

        host = self.coder_pass(stage_edit, ["CLAUDE.md"])

        self.assertEqual(self.claude_md.read_text(), "rules\n")
        self.assertEqual(self.staged_names(), [])
        self.assertEqual(host.user_only_asks, [])
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_an_edit_staged_before_the_pass_stays_staged_as_it_was(self):
        self.claude_md.write_text("rules\nthe phase's rule\n")
        self.git_run("add", "CLAUDE.md")

        def stage_coder_edit():
            self.claude_md.write_text("rules\nthe coder's rule\n")
            self.git_run("add", "CLAUDE.md")

        self.coder_pass(stage_coder_edit, ["CLAUDE.md"])

        self.assertEqual(self.claude_md.read_text(), "rules\nthe phase's rule\n")
        self.assertEqual(self.staged_names(), ["CLAUDE.md"])
        shown = subprocess.run(["git", "show", ":CLAUDE.md"], cwd=self.repo, capture_output=True, text=True,
                               check=True)
        self.assertEqual(shown.stdout, "rules\nthe phase's rule\n")

    def test_a_created_and_staged_agents_md_leaves_the_index_too(self):
        agents_md = self.repo / "AGENTS.md"

        def create_and_stage():
            agents_md.write_text("new\n")
            self.git_run("add", "AGENTS.md")

        self.coder_pass(create_and_stage, ["AGENTS.md"])

        self.assertFalse(agents_md.exists())
        self.assertEqual(self.staged_names(), [])

    def test_an_edit_the_coder_committed_is_reverted_and_named_for_the_session_to_commit(self):
        def commit_edit():
            self.claude_md.write_text("rules\ncommitted\n")
            self.git_run("commit", "-q", "-am", "coder")

        host = self.coder_pass(commit_edit, ["CLAUDE.md"])

        self.assertEqual(self.claude_md.read_text(), "rules\n")
        self.assertEqual(host.files_touched, {"CLAUDE.md"})
        self.assertEqual(host.user_only_asks, [])
        self.assertEqual([(ask.path, reason) for ask, reason in host.dropped_asks],
                         [("CLAUDE.md", review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON)])

    def test_an_edit_to_claude_md_no_finding_names_is_reverted_and_reported_with_no_ask(self):
        host = self.coder_pass(lambda: self.claude_md.write_text("rules\nnew rule\n"), ["CLAUDE.md"])

        self.assertEqual(self.claude_md.read_text(), "rules\n")
        self.assertEqual(host.asks, [])
        self.assertEqual(host.user_only_asks, [])
        self.assertEqual([(ask.path, reason) for ask, reason in host.dropped_asks],
                         [("CLAUDE.md", review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON)])
        self.assertEqual(approval_asks_store.read_saved_asks(str(self.repo)), ({}, []))

    def test_the_packet_names_the_reverted_file_in_its_dropped_asks(self):
        host = self.coder_pass(lambda: self.claude_md.write_text("rules\nnew rule\n"), ["CLAUDE.md"])

        outcome = {**review_loop_packet.EMPTY_OUTCOME, "dropped_asks": host.dropped_asks}
        entries = review_loop_packet.ask_entries(outcome)

        self.assertEqual([(entry["file_line"], entry["drop_reason"]) for entry in entries],
                         [("CLAUDE.md:1", review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON)])

    def test_a_created_agents_md_is_removed(self):
        agents_md = self.repo / "AGENTS.md"
        host = self.coder_pass(lambda: agents_md.write_text("new\n"), ["AGENTS.md"])

        self.assertFalse(agents_md.exists())
        self.assertEqual(host.asks, [])
        self.assertEqual([ask.path for ask, _reason in host.dropped_asks], ["AGENTS.md"])

    def test_a_phase_edit_made_before_the_pass_is_restored_not_lost(self):
        self.claude_md.write_text("rules\nthe phase's rule\n")
        self.coder_pass(lambda: self.claude_md.write_text("rules\nthe coder's rule\n"), ["CLAUDE.md"])

        self.assertEqual(self.claude_md.read_text(), "rules\nthe phase's rule\n")

    def test_a_pass_that_leaves_the_content_alone_reports_nothing(self):
        host = self.coder_pass(lambda: self.claude_md.write_text("rules\n"), ["CLAUDE.md"])

        self.assertEqual(host.dropped_asks, [])
        self.assertEqual(host.asks, [])

    def test_an_edit_to_a_nested_claude_local_md_is_restored_and_reported(self):
        nested = self.repo / "sub dir" / "CLAUDE.local.md"
        nested.parent.mkdir()
        nested.write_text("mine\n")

        host = self.coder_pass(lambda: nested.write_text("coder\n"), ["sub dir/CLAUDE.local.md"])

        self.assertEqual(nested.read_text(), "mine\n")
        self.assertEqual(host.asks, [])
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_an_edit_the_coder_committed_is_still_reverted(self):
        def commit_edit():
            self.claude_md.write_text("rules\ncommitted\n")
            for argv in (["add", "."], ["commit", "-q", "-m", "coder"]):
                subprocess.run(["git", *argv], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True,
                               capture_output=True)

        host = self.coder_pass(commit_edit, ["CLAUDE.md"])

        self.assertEqual(self.claude_md.read_text(), "rules\n")
        self.assertEqual(host.asks, [])

    def test_a_tracked_file_the_coder_deleted_is_restored(self):
        host = self.coder_pass(self.claude_md.unlink, ["CLAUDE.md"])

        self.assertEqual(self.claude_md.read_text(), "rules\n")
        self.assertEqual([ask.path for ask, _reason in host.dropped_asks], ["CLAUDE.md"])

    def test_a_file_that_cannot_be_hashed_survives_and_is_filed_as_an_ask(self):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        with mock.patch.object(review_loop_ruled.script_utils, "work_tree_blob", return_value=None):
            host.snapshot_approval_blobs()
        self.claude_md.write_text("rules\nnew rule\n")

        host.ask_for_approval_only_edits(["CLAUDE.md"], [])

        self.assertEqual(self.claude_md.read_text(), "rules\nnew rule\n")
        self.assertEqual([ask.path for ask in host.user_only_asks], ["CLAUDE.md"])

    def test_a_failed_index_listing_at_the_snapshot_keeps_the_edit_and_files_an_ask(self):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        git_error = review_loop_ruled.script_utils.GitCallError("ls-files")
        with mock.patch.object(review_loop_ruled.script_utils, "index_entries", side_effect=git_error):
            host.snapshot_approval_blobs()
        self.claude_md.write_text("rules\nnew rule\n")

        host.ask_for_approval_only_edits(["CLAUDE.md"], [])

        self.assertIn("CLAUDE.md", host.approval_unhashed)
        self.assertNotIn("CLAUDE.md", host.approval_index_entries)
        self.assertEqual(self.claude_md.read_text(), "rules\nnew rule\n")
        self.assertEqual([ask.path for ask in host.user_only_asks], ["CLAUDE.md"])

    def test_a_plain_runtime_error_at_the_snapshot_index_listing_propagates(self):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        with mock.patch.object(review_loop_ruled.script_utils, "index_entries", side_effect=RuntimeError("x")), \
                self.assertRaises(RuntimeError):
            host.snapshot_approval_blobs()

    def test_a_plain_runtime_error_at_the_revert_index_read_propagates(self):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.snapshot_approval_blobs()
        self.claude_md.write_text("rules\nnew rule\n")

        with mock.patch.object(review_loop_ruled.script_utils, "index_entry", side_effect=RuntimeError("x")), \
                self.assertRaises(RuntimeError):
            host.ask_for_approval_only_edits(["CLAUDE.md"], [])

    def test_a_failed_index_listing_at_the_revert_keeps_the_index_entry_and_files_an_ask(self):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.snapshot_approval_blobs()
        self.claude_md.write_text("rules\nnew rule\n")
        subprocess.run(["git", "add", "CLAUDE.md"], cwd=self.repo, check=True, capture_output=True)

        git_error = review_loop_ruled.script_utils.GitCallError("ls-files")
        with mock.patch.object(review_loop_ruled.script_utils, "index_entry", side_effect=git_error), \
                mock.patch.object(review_loop_ruled.script_utils, "restore_index_entry") as restore:
            host.ask_for_approval_only_edits(["CLAUDE.md"], [])

        restore.assert_not_called()
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.repo, check=True,
                                capture_output=True, text=True).stdout
        self.assertEqual(staged.strip(), "CLAUDE.md")
        self.assertEqual([ask.path for ask in host.user_only_asks], ["CLAUDE.md"])

    def test_a_snapshot_that_could_not_list_files_deletes_nothing_and_files_an_ask(self):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        with mock.patch.object(review_loop_ruled.script_utils, "git_output", return_value=None):
            host.snapshot_approval_blobs()
        self.claude_md.write_text("rules\nnew rule\n")

        host.ask_for_approval_only_edits(["CLAUDE.md"], [])

        self.assertEqual(self.claude_md.read_text(), "rules\nnew rule\n")
        self.assertEqual([ask.path for ask in host.user_only_asks], ["CLAUDE.md"])

    def test_an_edit_that_cannot_be_restored_is_filed_as_an_ask(self):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.snapshot_approval_blobs()
        self.claude_md.write_text("rules\nnew rule\n")

        with mock.patch.object(review_loop_ruled.script_utils, "restore_blob", return_value=False):
            host.ask_for_approval_only_edits(["CLAUDE.md"], [])

        self.assertEqual([ask.path for ask in host.user_only_asks], ["CLAUDE.md"])
        self.assertEqual(host.dropped_asks, [])


OWNER_RULING = ("- Standing ruling by the orchestrating session at 2026-11-22: owner lines need no ask "
                "covers: owner-lines\n")
REWORDS_RULING = "- Standing ruling by Pat at 2026-11-22: one rule covers: rewords\n"
KEPT_REASON = review_loop_findings.KEPT_OWNER_LINE_EDIT_REASON.format(ruling="the orchestrating session at 2026-11-22")
OTHER_SCRIPTS_MD_PATH = "other/scripts/CLAUDE.md"
PLAN_PATH = "docs/plans/p/plan.md"


class OwnerLineEditTest(unittest.TestCase):
    """The fix coder's owner-line edit to the scripts CLAUDE.md stands under a ruling read before the pass."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name).resolve()
        self.scripts_md = self.repo / SCRIPTS_CLAUDE_MD
        self.other_md = self.repo / OTHER_SCRIPTS_MD_PATH
        self.decisions = self.repo / "docs/plans/p/03-decisions.md"
        for target in (self.scripts_md, self.other_md):
            target.parent.mkdir(parents=True)
            target.write_text(SCRIPTS_MD)
        self.decisions.parent.mkdir(parents=True)
        (self.repo / PLAN_PATH).write_text("# Plan\n")
        self.decisions.write_text(OWNER_RULING)
        init_repo(self.repo)

    def coder_pass(self, edit, findings=(), changed=SCRIPTS_CLAUDE_MD, plan=PLAN_PATH):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.plan = plan
        host.files_touched = set()
        host.snapshot_approval_blobs()
        edit()
        host.reverted = host.ask_for_approval_only_edits([changed], list(findings))
        return host

    def edit_scripts_md(self, text):
        return lambda: self.scripts_md.write_text(text)

    def test_only_an_owner_line_edit_stands_under_the_ruling(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET
        updated = SCRIPTS_MD.replace("`lib/plan_format.py`", "`lib/plan_format.py` `read_plan`")
        cases = {
            "owner bullet added": (added, True),
            "owner bullet updated": (updated, True),
            "prose bullet added under Data": (SCRIPTS_MD + "- Prose bullet.\n", False),
            "owner bullet plus prose line": (added + "- Prose bullet.\n", False),
            "owner bullet removed": (SCRIPTS_MD.replace("- Plan text: `lib/plan_format.py`.\n", ""), False),
        }
        for name, (edited, kept) in cases.items():
            with self.subTest(name):
                self.scripts_md.write_text(SCRIPTS_MD)

                host = self.coder_pass(self.edit_scripts_md(edited))

                self.assertEqual(self.scripts_md.read_text(), edited if kept else SCRIPTS_MD, name)
                self.assertEqual(host.user_only_asks, [], name)
                expected = KEPT_REASON if kept else review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON
                self.assertEqual([reason for _ask, reason in host.dropped_asks], [expected], name)

    def test_a_finding_on_the_kept_file_files_no_ask(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET
        finding = parse_finding(f"`{SCRIPTS_CLAUDE_MD}:5` [docs] missing owner — Change: add the bullet.")

        host = self.coder_pass(self.edit_scripts_md(added), [finding])
        wanted_filed = host.ask_for_wanted_changes([finding], host.reverted)

        self.assertEqual(host.reverted, [])
        self.assertFalse(wanted_filed)
        self.assertEqual(self.scripts_md.read_text(), added)
        self.assertEqual(host.user_only_asks, [])
        self.assertEqual(host.asks, [])

    def test_a_staged_mixed_edit_trimmed_to_owner_lines_in_the_work_tree_is_reverted(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET

        def stage_mixed_then_trim():
            self.scripts_md.write_text(added + "- Prose bullet.\n")
            git_in(self.repo, "add", SCRIPTS_CLAUDE_MD)
            self.scripts_md.write_text(added)

        host = self.coder_pass(stage_mixed_then_trim)

        self.assertEqual(self.scripts_md.read_text(), SCRIPTS_MD)
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_a_committed_mixed_edit_trimmed_to_owner_lines_in_the_work_tree_is_reverted(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET

        def commit_mixed_then_trim():
            self.scripts_md.write_text(added + "- Prose bullet.\n")
            git_in(self.repo, "commit", "-q", "-am", "mixed")
            # Index back to the pre-pass entry, so only HEAD holds the prose.
            git_in(self.repo, "reset", "-q", "HEAD~1", "--", SCRIPTS_CLAUDE_MD)
            self.scripts_md.write_text(added)

        host = self.coder_pass(commit_mixed_then_trim)

        self.assertEqual(self.scripts_md.read_text(), SCRIPTS_MD)
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_a_kept_owner_line_edit_beside_a_reverted_root_claude_md_edit_keeps_one_and_reverts_the_other(self):
        root_md = self.repo / "CLAUDE.md"
        root_md.write_text("# Root\n")
        git_in(self.repo, "add", "CLAUDE.md")
        git_in(self.repo, "commit", "-q", "-m", "root claude md")
        added = SCRIPTS_MD_WITH_NEW_BULLET
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.plan = PLAN_PATH
        host.files_touched = set()
        host.snapshot_approval_blobs()
        self.scripts_md.write_text(added)
        root_md.write_text("# Root\nchanged\n")

        host.reverted = host.ask_for_approval_only_edits([SCRIPTS_CLAUDE_MD, "CLAUDE.md"], [])

        self.assertEqual(self.scripts_md.read_text(), added)
        self.assertEqual(root_md.read_text(), "# Root\n")
        reasons = [reason for _ask, reason in host.dropped_asks]
        self.assertEqual(reasons, [KEPT_REASON, review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_the_snapshot_clears_a_stale_ruling_and_pre_pass_text(self):
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.plan = PLAN_PATH
        host.snapshot_approval_blobs()
        self.assertIsNotNone(host.owner_line_ruling)
        self.assertEqual(host.owner_file_before, SCRIPTS_MD)

        self.scripts_md.unlink()
        host.snapshot_approval_blobs()

        self.assertIsNone(host.owner_line_ruling)
        self.assertIsNone(host.owner_file_before)

    def test_the_packet_line_reports_the_kept_edit_and_proposes_no_revert(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET
        host = self.coder_pass(self.edit_scripts_md(added))

        message = review_loop_packet.packet_message({"status": "converged", "dropped_asks": host.dropped_asks})

        loaded = handback.load(message)
        line = ("no approval ask is needed for an owner-line edit kept under the standing ruling by the "
                f"orchestrating session at 2026-11-22, so it was dropped: '`{SCRIPTS_CLAUDE_MD}:1` [other] "
                "owner-line edit kept'")
        self.assertEqual(loaded["dropped_asks"], [line])
        self.assertEqual(loaded["ask"], [])

    def test_an_owner_line_edit_stands_under_a_ruling_by_the_user(self):
        # The reader does not check who wrote the ruling, so a ruling by the user covers owner lines too.
        self.decisions.write_text("- Standing ruling by the user at 2026-11-23: owner lines need no ask "
                                  "covers: owner-lines\n")
        git_in(self.repo, "commit", "-q", "-am", "ruling by the user")
        added = SCRIPTS_MD_WITH_NEW_BULLET

        host = self.coder_pass(self.edit_scripts_md(added))

        self.assertEqual(self.scripts_md.read_text(), added)
        self.assertEqual(host.reverted, [])
        kept_reason = review_loop_findings.KEPT_OWNER_LINE_EDIT_REASON.format(ruling="the user at 2026-11-23")
        self.assertEqual([reason for _ask, reason in host.dropped_asks], [kept_reason])

    def test_a_ruling_the_pass_adds_keeps_nothing(self):
        self.decisions.write_text("# Decisions\n")
        git_in(self.repo, "commit", "-q", "-am", "no ruling")

        def add_ruling_and_bullet():
            self.decisions.write_text(OWNER_RULING)
            self.scripts_md.write_text(SCRIPTS_MD_WITH_NEW_BULLET)

        host = self.coder_pass(add_ruling_and_bullet)

        self.assertEqual(self.scripts_md.read_text(), SCRIPTS_MD)
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_no_owner_line_ruling_reaches_the_pass_as_a_kept_edit(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET
        self.decisions.write_text(REWORDS_RULING)
        cases = {"a rewords-only ruling": PLAN_PATH, "no plan": ""}
        for name, plan in cases.items():
            with self.subTest(name):
                self.scripts_md.write_text(SCRIPTS_MD)

                host = self.coder_pass(self.edit_scripts_md(added), plan=plan)

                self.assertEqual(self.scripts_md.read_text(), SCRIPTS_MD, name)
                self.assertEqual([reason for _ask, reason in host.dropped_asks],
                                 [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON], name)

    def test_an_owner_line_edit_with_a_ruling_but_no_pre_pass_text_is_reverted(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.plan = PLAN_PATH
        host.files_touched = set()
        host.snapshot_approval_blobs()
        self.assertIsNotNone(host.owner_line_ruling)
        host.owner_file_before = None
        self.scripts_md.write_text(added)

        host.reverted = host.ask_for_approval_only_edits([SCRIPTS_CLAUDE_MD], [])

        self.assertEqual(self.scripts_md.read_text(), SCRIPTS_MD)
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_an_owner_shaped_edit_to_another_scripts_claude_md_is_reverted(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET

        host = self.coder_pass(lambda: self.other_md.write_text(added), changed=OTHER_SCRIPTS_MD_PATH)

        self.assertEqual(self.other_md.read_text(), SCRIPTS_MD)
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_a_committed_owner_line_edit_stays_committed(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET

        def commit_edit():
            self.scripts_md.write_text(added)
            git_in(self.repo, "commit", "-q", "-am", "owner line")

        host = self.coder_pass(commit_edit)

        self.assertEqual(self.scripts_md.read_text(), added)
        shown = subprocess.run(["git", "show", f"HEAD:{SCRIPTS_CLAUDE_MD}"], cwd=self.repo, capture_output=True,
                               text=True, check=True)
        self.assertEqual(shown.stdout, added)
        self.assertEqual(host.files_touched, set())
        self.assertEqual([reason for _ask, reason in host.dropped_asks], [KEPT_REASON])

    def test_a_staged_owner_line_edit_with_the_work_tree_matching_the_index_stays(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET

        def stage_edit():
            self.scripts_md.write_text(added)
            git_in(self.repo, "add", SCRIPTS_CLAUDE_MD)

        host = self.coder_pass(stage_edit)

        self.assertEqual(self.scripts_md.read_text(), added)
        self.assertEqual([reason for _ask, reason in host.dropped_asks], [KEPT_REASON])

    def test_an_owner_line_edit_whose_work_tree_blob_git_cannot_hash_is_reverted(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET
        edited = []

        def edit():
            self.scripts_md.write_text(added)
            edited.append(True)

        real_work_tree_blob = review_loop_ruled.script_utils.work_tree_blob

        def blob_unhashable_after_the_edit(*args, **kwargs):
            return None if edited else real_work_tree_blob(*args, **kwargs)

        with mock.patch.object(review_loop_ruled.script_utils, "work_tree_blob",
                               side_effect=blob_unhashable_after_the_edit):
            host = self.coder_pass(edit)

        self.assertEqual(self.scripts_md.read_text(), SCRIPTS_MD)
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_an_owner_line_edit_whose_index_entry_git_cannot_read_is_reverted(self):
        added = SCRIPTS_MD_WITH_NEW_BULLET
        real_index_entry = review_loop_ruled.script_utils.index_entry
        edited = []
        reads_after_the_edit = []

        def edit():
            self.scripts_md.write_text(added)
            edited.append(True)

        def index_entry_failing_for_the_judge(*args):
            if not edited:
                return real_index_entry(*args)
            reads_after_the_edit.append(args)
            # The first read after the edit is the owner-line judge's; the revert's own read then works.
            if len(reads_after_the_edit) == 1:
                raise review_loop_ruled.script_utils.GitCallError("ls-files")
            return real_index_entry(*args)

        with mock.patch.object(review_loop_ruled.script_utils, "index_entry",
                               side_effect=index_entry_failing_for_the_judge):
            host = self.coder_pass(edit)

        # The judge's failed read sent the edit to the revert, which reads the index again.
        self.assertGreaterEqual(len(reads_after_the_edit), 2)
        self.assertEqual(self.scripts_md.read_text(), SCRIPTS_MD)
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_a_file_unreadable_when_judged_is_reverted(self):
        host = self.coder_pass(self.scripts_md.unlink)

        self.assertEqual(self.scripts_md.read_text(), SCRIPTS_MD)
        self.assertEqual([reason for _ask, reason in host.dropped_asks],
                         [review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON])

    def test_a_malformed_ruling_stops_the_snapshot_naming_file_and_line(self):
        self.decisions.write_text("Standing ruling by x at 2026-11-22: y covers: everything\n")
        host = approval_host(reverts=True)
        host.repo = str(self.repo)
        host.plan = PLAN_PATH

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            host.snapshot_approval_blobs()

        self.assertIn("03-decisions.md:1:", str(raised.exception))


class RootClaudeMdOnlySnapshotTest(unittest.TestCase):
    def test_a_malformed_ruling_is_not_read_when_the_scripts_claude_md_is_absent(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        repo = pathlib.Path(folder.name).resolve()
        (repo / "CLAUDE.md").write_text("rules\n")
        decisions = repo / "docs/plans/p/03-decisions.md"
        decisions.parent.mkdir(parents=True)
        (repo / PLAN_PATH).write_text("# Plan\n")
        decisions.write_text("Standing ruling by x at 2026-11-22: y covers: everything\n")
        init_repo(repo)
        host = approval_host(reverts=True)
        host.repo = str(repo)
        host.plan = PLAN_PATH

        host.snapshot_approval_blobs()

        self.assertTrue(host.approval_snapshot_ok)
        self.assertIn("CLAUDE.md", host.approval_blobs)
        self.assertIsNone(host.owner_line_ruling)


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

    def test_an_adopted_finding_the_coder_reported_already_in_the_tree_is_no_blocker(self):
        findings = [parse_finding(ADOPTED_FINDING)]
        adopted = {ADOPTED_FINDING: ADOPTED_RULING}

        already_applied = coder_report.already_applied_issues("- `ALREADY APPLIED 1: app.py:2`", len(findings))
        reported = review_loop_ruled.unapplied_adopted(findings, adopted, {}, [], "/repo", already_applied)
        unreported = review_loop_ruled.unapplied_adopted(findings, adopted, {}, [], "/repo")

        self.assertEqual(reported, [])
        self.assertEqual(len(unreported), 1)

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

    def run_adopted(self, coder_reply, findings=(ADOPTED_FINDING,), extra_header=""):
        findings_file = self.scratch / "findings.json"
        findings_file.write_text(json.dumps(list(findings)))
        row = {"number": 1, **ADOPTED_RULING._asdict()}
        header = (f"mode: fix-first\nfindings: {findings_file}\nuser-ruled: 1\n"
                  f"user-ruled-at: 2026-11-19 10:00:00Z\nadopted: {json.dumps([row])}\n{extra_header}")
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

    def test_the_coder_brief_asks_for_the_already_applied_marker_only_for_the_adopted_finding(self):
        plain = "app.py:1 [bug] plain finding"

        self.run_adopted({"result": "Fixed 1.\nFixed 2.", "edits": {"app.py": APP_FIXED}},
                         findings=(ADOPTED_FINDING, plain))

        (coder_call,) = [call for call in self.fake_calls() if call["key"] == "coder"]
        self.assertIn("issue 1 asks for", coder_call["prompt"])
        self.assertIn(f"{coder_report.ALREADY_APPLIED_MARKER} <n>", coder_call["prompt"])
        # Marking the plain finding too would turn the line into "issues 1, 2 ask for".
        self.assertNotIn("issues 1, 2 ask for", coder_call["prompt"])

    def test_the_packet_lists_the_text_of_each_adopted_ruling_left_unapplied(self):
        packet = self.run_adopted({"result": "Fixed 1."})

        self.assertEqual(packet["adopted_unapplied"], [ADOPTED_RULING.text])

    def test_the_packet_lists_the_adopted_ruling_the_loop_withheld_on_a_held_file(self):
        holder = {"path": "app.py", "session": "lane-b", "claim": "dirty at the run start, unchanged now"}
        header = f"files: other.py\nheld-by: {json.dumps([holder])}\n"

        packet = self.run_adopted({"result": "Fixed 1."}, extra_header=header)

        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn(review_loop_ruled.HELD_WHY, packet["blockers"][0])
        self.assertEqual(packet["adopted_unapplied"], [ADOPTED_RULING.text])
        self.assertEqual(self.fake_calls(), [])

    def test_a_coder_that_skips_the_adopted_finding_ends_the_round_with_a_blocker_and_no_reviewer(self):
        packet = self.run_adopted({"result": "SKIPPED 1: needs a sign-off.", "edits": {"app.py": APP_FIXED}})

        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn(review_loop_ruled.SKIPPED_WHY, packet["blockers"][0])
        self.assertEqual([call["key"] for call in self.fake_calls()], ["coder", "ruling-check"])
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

    def test_an_adopted_finding_reported_already_applied_in_a_pass_with_no_diff_is_fixed(self):
        packet = self.run_adopted({"result": "ALREADY APPLIED 1: app.py:2"})

        self.assertIn(ADOPTED_FINDING, json.dumps(packet["fixed"]))
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_no_diff_pass_reporting_both_an_adopted_and_a_plain_finding_already_applied_fixes_only_the_adopted(self):
        self.seed_adopt_row()
        plain = "app.py:1 [bug] plain finding"

        packet = self.run_adopted({"result": "ALREADY APPLIED 1: app.py:2\nALREADY APPLIED 2: app.py:3"},
                                  findings=(ADOPTED_FINDING, plain))

        self.assertIn(ADOPTED_FINDING, json.dumps(packet["fixed"]))
        self.assertNotIn(plain, json.dumps(packet["fixed"]))
        (skipped,) = packet["skipped_fp"]
        self.assertIn(plain, json.dumps(skipped))
        self.assertIn("ALREADY APPLIED 2: app.py:3", json.dumps(skipped))
        self.assertEqual(self.adopted_left(), (), "the adopted ruling is recorded as applied")

    def test_an_adopted_finding_reported_both_skipped_and_already_applied_is_applied_not_skipped(self):
        self.seed_adopt_row()

        packet = self.run_adopted({"result": "SKIPPED 1: not needed.\nALREADY APPLIED 1: app.py:2"})

        self.assertIn(ADOPTED_FINDING, json.dumps(packet["fixed"]))
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(self.adopted_left(), (), "the adopted ruling is recorded as applied")

    def test_a_bulleted_bold_already_applied_marker_counts_as_applied(self):
        packet = self.run_adopted({"result": "- **ALREADY APPLIED 1:** app.py:2"})

        self.assertIn(ADOPTED_FINDING, json.dumps(packet["fixed"]))
        self.assertEqual(packet["skipped_fp"], [])

    def assert_marker_is_a_skip(self, marker):
        plain = "app.py:1 [bug] plain finding"

        packet = self.run_adopted({"result": f"ALREADY APPLIED 1: app.py:2\n{marker}"},
                                  findings=(ADOPTED_FINDING, plain))

        (skipped,) = packet["skipped_fp"]
        self.assertIn(plain, json.dumps(skipped))

    def test_a_bulleted_bold_skipped_marker_is_a_skip(self):
        self.assert_marker_is_a_skip("- **SKIPPED 2:** not a bug")

    def test_a_backticked_skipped_marker_closed_before_the_colon_is_a_skip(self):
        self.assert_marker_is_a_skip("- `SKIPPED 2`: not a bug")

    def test_a_bold_skipped_marker_closed_before_the_colon_is_a_skip(self):
        self.assert_marker_is_a_skip("**SKIPPED 2**: not a bug")

    def test_a_plain_finding_reported_already_applied_is_a_skip_with_the_coders_line_as_the_reason(self):
        plain = "app.py:1 [bug] plain finding"

        packet = self.run_adopted({"result": "ALREADY APPLIED 2: app.py:2", "edits": {"app.py": APP_FIXED}},
                                  findings=(ADOPTED_FINDING, plain))

        (skipped,) = packet["skipped_fp"]
        self.assertIn(plain, json.dumps(skipped))
        self.assertIn("ALREADY APPLIED 2: app.py:2", json.dumps(skipped))
        self.assertNotIn(plain, json.dumps(packet["fixed"]))


class AlreadyAppliedBriefTest(unittest.TestCase):
    def brief(self, **options):
        findings = [parse_finding("a.py:1 [bug] x"), parse_finding("a.py:2 [bug] y")]
        with tempfile.TemporaryDirectory() as folder:
            return review_loop_prompts.coder_prompt("/repo", findings, [], ["a.py"],
                                                    pathlib.Path(folder), **options)

    def test_the_brief_asks_for_the_marker_only_when_an_issue_is_adopted(self):
        adopted = self.brief(adopted_numbers=(2,))
        plain = self.brief()

        self.assertIn("issue 2 asks for", adopted)
        self.assertNotIn("issue 1 asks for", adopted)
        self.assertIn(f"{coder_report.ALREADY_APPLIED_MARKER} <n>", adopted)
        self.assertNotIn(coder_report.ALREADY_APPLIED_MARKER, plain)


class RepairMalformedRulingTest(unittest.TestCase):
    def test_a_malformed_standing_ruling_stops_repair_with_the_findings_still_open_and_no_coder_call(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = pathlib.Path(folder).resolve()
            (repo / "app.py").write_text("x = 1\n")
            init_repo(repo)
            loop = review_loop_script.LoopRun(str(repo), repo / "out", "", (), {"fixed": [], "files_touched": set()})
            findings = [parse_finding("`app.py:1` [bug] wrong")]
            error = plan_format.PlanFormatError("plan.md:5: a standing ruling line reads 'x'; expected `form`")
            with (
                mock.patch.object(loop, "snapshot_approval_blobs", side_effect=error),
                mock.patch.object(review_loop_script, "coder_call") as coder,
                self.assertRaises(plan_format.PlanFormatError),
            ):
                loop.repair("fix", findings)

            self.assertEqual(loop.open_fixes, findings)
            coder.assert_not_called()
            self.assertEqual(loop.last_pass, "")
            self.assertFalse(loop.untested_fix)


if __name__ == "__main__":
    unittest.main()
