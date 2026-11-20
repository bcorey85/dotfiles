import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import approval_asks_store
import review_fix_asks
import review_loop_findings
import review_loop_packet
import review_loop_prompts
import review_loop_ruled
import review_loop_script
import ruled_change_text
from approval_ask_chain import accepted_approval_ask_text
from finding_record import parse_finding
from no_code_notes import NO_CODE_NOTES


def ruled_finding(note, location="`a/b.py:3`"):
    return parse_finding(ruled_change_text.changed_text(f"{location} [bug] Proposed change: add X.", note,
                                                          ruled_change_text.USER_CLAUSE))


def broken_entry(finding, path):
    return {"ruling": review_loop_ruled.ruling_line(finding), "file": path}


class Host(review_loop_ruled.RuledFindings):
    def __init__(self):
        self.repo = "/repo"
        self.change = None
        self.init_ruled_state()


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

    def test_a_resumed_run_files_no_ask_for_a_reverted_edit(self):
        self.edit_claude_md()
        reverting = self.host(reverts=True)
        reverting.ask_for_approval_only_edits(["CLAUDE.md"], [])
        self.assertEqual(reverting.asks, [])

        resumed = self.host()
        resumed.resume_approval_asks([])

        self.assertEqual(resumed.asks, [])
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


class ApprovalEditRevertTest(unittest.TestCase):
    """A fix coder's edit to an approval-only file is put back and reported, never filed as an ask."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name).resolve()
        self.claude_md = self.repo / "CLAUDE.md"
        self.claude_md.write_text("rules\n")
        for argv in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-q", "-m", "init"]):
            subprocess.run(["git", *argv], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True,
                           capture_output=True)

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
        subprocess.run(["git", *argv], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True, capture_output=True)

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

    def test_an_edit_to_claude_md_is_reverted_reported_and_files_no_ask(self):
        host = self.coder_pass(lambda: self.claude_md.write_text("rules\nnew rule\n"), ["CLAUDE.md"])

        self.assertEqual(self.claude_md.read_text(), "rules\n")
        self.assertEqual(host.asks, [])
        self.assertEqual(host.user_only_asks, [])
        self.assertEqual([(ask.path, reason) for ask, reason in host.dropped_asks],
                         [("CLAUDE.md", review_loop_ruled.REVERTED_APPROVAL_EDIT_REASON)])
        self.assertFalse(approval_asks_store.approval_paths_file(str(self.repo)).exists())

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


if __name__ == "__main__":
    unittest.main()
