import json
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
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

    def test_a_session_ruling_on_the_approval_ask_itself_files_no_ask(self):
        finding = parse_finding(accepted_approval_ask_text("CLAUDE.md"))
        self.assertEqual(self.ask_filed(finding, session_ruled=[finding.text]), 0)

    def test_a_session_ruling_that_modifies_the_approval_ask_still_files_the_ask(self):
        finding = parse_finding(accepted_approval_ask_text("CLAUDE.md", "keep the edit and reword line 3", "session"))
        self.assertEqual(self.ask_filed(finding, session_ruled=[finding.text]), 1)


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
