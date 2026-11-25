"""Checks for review_loop_script.py, the scripted review loop.

A stand-in `claude` on PATH answers each call with a canned reply chosen by the agent of the call. Set
REVIEW_LOOP_SCRIPT to run against another copy, such as a staged one."""
import collections
import importlib.util
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
import typing
import unittest
from unittest import mock

import fake_ledger
import toolkit_paths
from approval_ask_chain import accepted_approval_ask_text

sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import coder_report
import file_backup
import finding_record
import handback
import handback_store
import plan_format
import protected_lines
import review_asks
import review_loop_calls
import review_loop_closure
import review_loop_coder
import review_loop_comment_removal
import review_loop_findings
import review_loop_held
import review_loop_packet
import review_loop_plan
import review_loop_post_cap
import review_loop_prompts
import review_loop_ruled
import review_loop_ruling_check
import review_loop_scoped_tests
import review_loop_signoffs
import ruled_change_text
from review_asks import REJECTED

SCRIPT = pathlib.Path(os.environ.get("REVIEW_LOOP_SCRIPT") or toolkit_paths.REVIEW_DIR / "review_loop_script.py")
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
SESSION = "session-1"
AGENT_ID = "agent-1"
FINDING_ID = re.compile(r"[0-9a-f]{16}")
PLAN_CHANGE_STATUS = handback.STATUSES[2]

FAKE_CLAUDE = '''#!/usr/bin/env python3
import fcntl
import json
import os
import subprocess
import sys
import time

args = sys.argv[1:]
prompt = sys.stdin.read()
if "-p" not in args:
    sys.exit("fake claude: called without -p")
agent = args[args.index("--agent") + 1] if "--agent" in args else None
key = agent or ("closure" if "class-shaped" in prompt
                else "ruling-check" if "ruling-check judge" in prompt
                else "check-finder" if "full quality check" in prompt else "disposition")
fake_dir = os.environ["FAKE_CLAUDE_DIR"]

with open(os.path.join(fake_dir, "calls.jsonl"), "a") as handle:
    pane_names = ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH", "TUIOS_SOCKET")
    pane_env = {name: os.environ.get(name) for name in pane_names}
    record = {"key": key, "hook_off": os.environ.get("CLAUDE_FORMAT_HOOK_OFF"), "prompt": prompt,
              "pane_env": pane_env, "name": args[args.index("--name") + 1] if "--name" in args else None,
              "model": args[args.index("--model") + 1] if "--model" in args else None}
    handle.write(json.dumps(record) + "\\n")

if os.environ.get("FAKE_CLAUDE_HANG"):
    grandchild = subprocess.Popen(["sleep", "60"])
    with open(os.path.join(fake_dir, "grandchild.pid"), "w") as handle:
        handle.write(str(grandchild.pid))
    time.sleep(60)

with open(os.path.join(fake_dir, "counters.lock"), "w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    counters_path = os.path.join(fake_dir, "counters.json")
    counters = json.load(open(counters_path)) if os.path.exists(counters_path) else {}
    position = counters.get(key, 0)
    counters[key] = position + 1
    json.dump(counters, open(counters_path, "w"))

# Every ruling-check call answers one "kept" verdict per ruling line of its prompt unless a test gives replies; 20 caps
# the calls one run may make.
ruling_lines = [line for line in prompt.splitlines() if line.startswith("- [")]
kept_verdicts = [{"ruling": line, "verdict": "kept"} for line in ruling_lines]
all_kept = [{"result": json.dumps({"verdicts": kept_verdicts})}] * 20 if key == "ruling-check" else []
replies = json.load(open(os.path.join(fake_dir, "scenario.json"))).get(key, all_kept)
if position >= len(replies):
    print("no canned reply for " + key, file=sys.stderr)
    sys.exit(3)
reply = replies[position]

for old_path, new_path in reply.get("renames", {}).items():
    os.rename(old_path, new_path)

for path in reply.get("deletes", []):
    os.remove(path)

edits = dict(reply.get("edits", {}))
if os.environ.get("CLAUDE_FORMAT_HOOK_OFF") != "1":
    edits.update(reply.get("edits_when_format_hook_on", {}))
# A coder that follows its prompt: it edits a file only when one of its issues names that file.
issues = prompt.partition("## Issues")[2].partition("Files in scope:")[0]
edits.update({path: text for path, text in reply.get("edits_when_named", {}).items() if f"`{path}:" in issues})
# An outside edit is another session's, written during the call.
edits.update(reply.get("outside_edits", {}))
for path, text in edits.items():
    with open(path, "w") as handle:
        handle.write(text)

if reply.get("commit_all"):
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "mid-loop"],
                   check=True)

usage = {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 3, "cache_read_input_tokens": 2}
print(json.dumps({"result": reply.get("result", ""), "session_id": "fake-session", "usage": usage}))
sys.exit(reply.get("exit", 0))
'''

APP_BEFORE = "limit = 1\nlimit = 2\nlimit = 3\nlimit = 4\nlimit = 5\n"
APP_AFTER_EDIT = "limit = 1\nlimit = 2\nlimit = 3\nlimit = 4\nlimit = 6\n"
APP_FIXED = "limit = 1\nlimit = 20\nlimit = 3\nlimit = 4\nlimit = 5\n"
NOTES_BEFORE = "value = {'a': 1, 'b': 2}\n"
NOTES_REFLOWED = 'value = {\n    "a": 1,\n    "b": 2,\n}\n'

CLEAN_REVIEW = "## Fix\nNone\n\n## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: PASS\n"
NOTES_HOLDER = {"path": "notes.py", "session": "lane-b", "claim": "dirty at the run start, unchanged now"}
SCRATCH_HOLDER = {"path": "held_scratch.txt", "session": "lane-b", "claim": "dirty at the run start, unchanged now"}
HELD_FILE_REASON = review_loop_held.held_reason(NOTES_HOLDER)
SCOPED_WITH_NOTES_HELD = "files: app.py\n" + f"held-by: {json.dumps([NOTES_HOLDER])}\n"
FIX_REVIEW = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
              "Overall Assessment: NEEDS CHANGES\n")
# A check starts with this to fail only with the diff: the base run on HEAD has no diff and passes.
FAILS_ONLY_WITH_THE_DIFF = "git diff --quiet HEAD -- app.py && exit 0; "
CLOSED = '{"receipt": "one exit, all re-read", "open": []}'
OPEN_MEMBER = {"receipt": "one member still open", "open": ["`app.py:4` the same limit is wrong here too"]}
LATE_FIX = ("## Fix\n- `app.py:5` the last limit skips the unit\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
            "Overall Assessment: NEEDS CHANGES\n")
FIX_THEN_CLEAN = {
    "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
    "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
    "closure": [{"result": CLOSED}],
}


# A stand-in for the stale-prose script, written under its real name: it prints a hit line and exits with the code
# the test gives it (1 is a hit, 2 a fault of the script).
STALE_PROSE_STAND_IN = "import sys\nprint('STALE app.py:1 names a changed symbol')\nsys.exit(int(sys.argv[1]))\n"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class SkipHeldItemsTest(unittest.TestCase):
    def test_a_held_item_is_recorded_once_however_many_times_it_is_met(self):
        held_item = finding_record.parse_finding("`notes.py:1` the keys are out of order")
        real_item = finding_record.parse_finding("`app.py:2` the limit is wrong for `limit`")
        held_unfixed = []
        holders = {"notes.py": NOTES_HOLDER}

        repo = pathlib.Path("/work/repo")
        first_kept, first_held = review_loop_held.skip_held_items(
            [held_item, real_item], {"notes.py"}, {"app.py"}, held_unfixed, repo, holders)
        second_kept, second_held = review_loop_held.skip_held_items(
            [held_item], {"notes.py"}, {"app.py"}, held_unfixed, repo, holders)

        self.assertEqual((first_kept, first_held), ([real_item], [held_item]))
        self.assertEqual((second_kept, second_held), ([], [held_item]))
        self.assertEqual(held_unfixed, [{"item": held_item, "reason": HELD_FILE_REASON}])

    def test_a_finding_on_a_held_file_with_no_holder_row_stays_with_the_items_the_coder_gets(self):
        held_item = finding_record.parse_finding("`notes.py:1` the keys are out of order")
        held_unfixed = []

        kept, held_items = review_loop_held.skip_held_items(
            [held_item], {"notes.py"}, set(), held_unfixed, pathlib.Path("/work/repo"), {})

        self.assertEqual((kept, held_items, held_unfixed), ([held_item], [], []))


class PriorIssueEntriesTest(unittest.TestCase):
    def test_a_put_back_finding_is_partial_with_the_put_back_reason_not_fixed(self):
        put_back = finding_record.parse_finding("`notes.py:1` the keys are out of order")
        fixed = finding_record.parse_finding("`app.py:2` the limit is wrong for `limit`")
        skipped = finding_record.parse_finding("`lib.py:3` the name is bad")

        entries = load_script_module().prior_issue_entries(
            [put_back, fixed, skipped], {3: "not a bug"}, [put_back])

        self.assertEqual([entry["status"] for entry in entries], ["partial", "fixed", "skipped"])
        self.assertEqual(entries[0]["reason"], "the loop put the file back to keep a recorded ruling")
        self.assertNotIn("reason", entries[1])


class SplitHeldFindingsTest(unittest.TestCase):
    def test_a_finding_matches_a_held_file_only_by_the_file_itself_or_a_tail_of_it(self):
        repo = pathlib.Path("/work/repo")
        cases = [
            ("sub/notes.py", False, "a longer relative path is another file than the held root file"),
            ("notes.py", True, "the exact path"),
            ("/work/repo/notes.py", True, "an absolute path under the repo"),
            ("/work/repo/sub/notes.py", False, "an absolute path to a nested file of the same name"),
        ]
        for path, is_held, message in cases:
            with self.subTest(message):
                item = finding_record.parse_finding(f"`{path}:1` the keys are out of order")
                kept, held_items = review_loop_held.split_held_findings([item], {"notes.py"}, set(), repo)
                self.assertEqual((kept, held_items), ([], [item]) if is_held else ([item], []))

    def test_a_tail_only_path_is_held_only_when_it_names_one_held_file_and_no_owned_file(self):
        repo = pathlib.Path("/work/repo")
        cases = [
            ("notes.py", {"a/notes.py"}, set(), True, "one held file, no owned file"),
            ("notes.py", {"a/notes.py"}, {"b/notes.py"}, False, "an owned file has the same tail"),
            ("notes.py", {"a/notes.py", "c/notes.py"}, set(), False, "two held files have the same tail"),
        ]
        for path, held, owned, is_held, message in cases:
            with self.subTest(message):
                item = finding_record.parse_finding(f"`{path}:1` the keys are out of order")
                kept, held_items = review_loop_held.split_held_findings([item], held, owned, repo)
                self.assertEqual((kept, held_items), ([], [item]) if is_held else ([item], []))


    def test_an_exact_path_to_an_owned_root_file_is_kept_beside_a_held_nested_file_of_the_same_name(self):
        with tempfile.TemporaryDirectory() as directory:
            (pathlib.Path(directory) / "notes.py").write_text("a = 1\n")
            item = finding_record.parse_finding("`notes.py:1` the keys are out of order")

            kept, held_items = review_loop_held.split_held_findings([item], {"sub/notes.py"}, {"notes.py"}, directory)

            self.assertEqual((kept, held_items), ([item], []))


class ImplicitHoldersTest(unittest.TestCase):
    OTHER: typing.ClassVar[dict] = {"pid": 77, "sessionId": "other-id", "name": "lane-b", "cwd": "/repo"}

    def holders(self, live_row, only_files=("app.py",), known=None):
        with mock.patch.object(review_loop_held.session_registry, "other_live_session_in",
                               return_value=live_row) as lookup:
            result = review_loop_held.implicit_holders(
                "/repo", {"theirs.py", "named.py"}, known or {"named.py": {}}, list(only_files), "own-id")
        return result, lookup

    def test_a_dirty_file_outside_the_file_scope_is_held_by_the_live_other_session(self):
        result, lookup = self.holders(self.OTHER)

        lookup.assert_called_once_with("/repo", "own-id")
        self.assertEqual(result, {"theirs.py": review_loop_held.holder_row(
            "theirs.py", "lane-b", "dirty, outside the run's --file scope")})

    def test_with_no_live_other_session_nothing_is_held(self):
        result, _lookup = self.holders(None)

        self.assertEqual(result, {})

    def test_without_file_scoping_there_are_no_implicit_holders(self):
        result, lookup = self.holders(self.OTHER, only_files=())

        self.assertEqual(result, {})
        lookup.assert_not_called()


class HeldDigestsTest(unittest.TestCase):
    def test_a_held_file_deleted_during_the_call_is_named_and_an_unchanged_one_is_not(self):
        self.addCleanup(review_loop_held.HELD_FAULTS.clear)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "gone.py").write_text("a = 1\n")
            (root / "same.py").write_text("b = 2\n")
            before = review_loop_held.digests(root, {"gone.py", "same.py"})
            (root / "gone.py").unlink()
            review_loop_held.HELD_FAULTS.clear()

            review_loop_held.note_changed("coder1", root, before)

            self.assertEqual(len(review_loop_held.HELD_FAULTS), 1)
            self.assertIn("gone.py", review_loop_held.HELD_FAULTS[0])
            self.assertNotIn("same.py", review_loop_held.HELD_FAULTS[0])


class RulingCheckHost(review_loop_ruling_check.RulingCheck):
    """The host surface RulingCheck needs: keep_open records `kept_open`; drop_open removes findings from
    `open_fixes`; coder_held_files returns `held`; findings_on_reverted_paths returns the findings listed in
    `reverted_findings`; keep_unreverted_open is the real one."""
    reverted_findings = ()
    held = frozenset()
    open_fixes: typing.ClassVar[list] = ["on-claude-md"]
    # Tuples, so a test that does not set them cannot share a mutable default.
    no_code_broken = ()
    user_only_paths = ()

    def __init__(self):
        self.files_touched = set()

    keep_unreverted_open = review_loop_ruled.RuledFindings.keep_unreverted_open
    ruled_texts = review_loop_ruled.RuledFindings.ruled_texts
    drop_approval_asks = review_loop_ruled.RuledFindings.drop_approval_asks

    def keep_open(self, findings):
        self.kept_open = findings

    def drop_open(self, findings):
        self.open_fixes = [item for item in self.open_fixes if item not in findings]

    def coder_held_files(self):
        return self.held

    def findings_on_reverted_paths(self, findings, reverted):
        return [finding for finding in findings if finding in self.reverted_findings]


class RepeatFilterHost(review_loop_ruled.RuledFindings):
    def __init__(self, asks=()):
        self.asks = list(asks)
        self.plan_impacts = []
        self.resolved_texts = []
        self.init_ruled_state()


class WithoutRepeatsTest(unittest.TestCase):
    PLAN_ITEM = "PLAN-IMPACT: the reword is narrower than the ticket. acceptance_criteria: AC2"
    PLAIN_ASK = "`app.py:3` [bug] should the window be pinned?"

    def test_a_plan_change_item_stays_even_when_an_earlier_item_repeats_it(self):
        first = finding_record.parse_finding(self.PLAN_ITEM)
        second = finding_record.parse_finding(self.PLAN_ITEM + " Second sentence.")
        host = RepeatFilterHost()

        kept = host.without_repeats([first, second])

        self.assertEqual(kept, [first, second])
        self.assertEqual(host.dropped_asks, [])

    def test_a_plan_change_item_the_session_rejected_is_dropped_when_raised_again(self):
        rejected = finding_record.parse_finding(self.PLAN_ITEM)
        again = finding_record.parse_finding(self.PLAN_ITEM + " Second sentence.")
        host = RepeatFilterHost()
        host.rejected_asks = [rejected]

        kept = host.without_repeats([again])

        self.assertEqual(kept, [])
        self.assertEqual(host.dropped_asks, [(again, review_loop_findings.REJECTED_ASK_REASON)])

    def test_a_design_item_the_session_rejected_is_dropped_when_raised_again(self):
        rejected = finding_record.parse_finding(self.PLAN_ITEM)
        again = finding_record.parse_finding(self.PLAN_ITEM + " Second sentence.")
        other = finding_record.parse_finding("`other.py:1` [design-decision] pick a layout")
        host = RepeatFilterHost()
        host.rejected_asks = [rejected]

        kept = host.without_rejected([again, other])

        self.assertEqual(kept, [other])
        self.assertEqual(host.dropped_asks, [(again, review_loop_findings.REJECTED_ASK_REASON)])

    def test_a_plain_ask_that_repeats_an_earlier_one_of_the_same_batch_is_dropped(self):
        first = finding_record.parse_finding(self.PLAIN_ASK)
        second = finding_record.parse_finding(self.PLAIN_ASK.replace("app.py:3", "app.py:9"))
        host = RepeatFilterHost()

        kept = host.without_repeats([first, second])

        self.assertEqual(kept, [first])
        self.assertEqual([ask for ask, _reason in host.dropped_asks], [second])

    def test_an_ask_already_on_the_loop_s_list_word_for_word_stays_for_add_ask(self):
        ask = finding_record.parse_finding(self.PLAIN_ASK)
        host = RepeatFilterHost(asks=[ask])

        kept = host.without_repeats([ask])

        self.assertEqual(kept, [ask])
        self.assertEqual(host.dropped_asks, [])

    def test_an_ask_that_only_matches_the_loop_s_list_by_claim_is_dropped(self):
        listed = finding_record.parse_finding(self.PLAIN_ASK)
        reworded_line = finding_record.parse_finding(self.PLAIN_ASK.replace("app.py:3", "app.py:9"))
        host = RepeatFilterHost(asks=[listed])

        kept = host.without_repeats([reworded_line])

        self.assertEqual(kept, [])
        self.assertEqual([ask for ask, _reason in host.dropped_asks], [reworded_line])

    def test_a_re_filed_plan_drift_a_session_accepted_is_not_held_for_a_ruling_again(self):
        accepted = "README.md:1 [plan-drift] Proposed change: keep the narrower AC2 acceptance_criteria: AC2"
        refiled = finding_record.parse_finding(
            "README.md:1 [plan-drift] the narrower AC2 wording drops deletes. acceptance_criteria: AC2")
        host = RepeatFilterHost()
        host.session_ruled = [accepted]

        to_coder, ruling_held = host.route_plan_items("code-reviewer", [refiled])

        self.assertEqual(to_coder, [refiled])
        self.assertEqual(ruling_held, [])
        self.assertEqual(host.plan_impacts, [])

    def test_a_plan_drift_ask_re_filed_after_a_session_accepted_it_is_dropped(self):
        accepted = "README.md:1 [plan-drift] Proposed change: keep the narrower AC2 acceptance_criteria: AC2"
        refiled = finding_record.parse_finding(
            "`README.md:1` [plan-drift] the narrower AC2 wording drops deletes. acceptance_criteria: AC2")
        host = RepeatFilterHost()
        host.session_ruled = [accepted]

        dropped = host.drops_repeated_ask(refiled)

        self.assertTrue(dropped)
        self.assertEqual([ask for ask, _reason in host.dropped_asks], [refiled])

    def test_a_coder_plan_impact_a_session_accepted_is_recorded_adopted_and_settled(self):
        accepted = "README.md:1 [plan-drift] Proposed change: keep the narrower AC2 acceptance_criteria: AC2"
        report = ("PLAN-IMPACT:\n  assumed: the wording is kept\n  found: README.md:1 [plan-drift] it drops deletes\n"
                  "  changes: the wording\n  acceptance_criteria: AC2\n  cause: plan\nPLAN-IMPACT: yes")
        host = RepeatFilterHost()
        host.session_ruled = [accepted]

        held = host.record_coder_plan_impact(report, ["README.md"])

        self.assertFalse(held)
        self.assertTrue(host.plan_impacts[0]["settled"])
        self.assertTrue(host.plan_impacts[0]["adopted"])


class ClosureCheckTest(unittest.TestCase):
    def closure(self, reply):
        def claude_call(*_args, **_kwargs):
            return reply

        return review_loop_closure.closure_check(pathlib.Path("/repo"), pathlib.Path("/out"), ["app.py:3 - limit"],
                                                 claude_call)

    def test_a_receipt_with_a_raw_quote_still_reads_its_open_list(self):
        cases = [
            ("empty open list", 'Done.\n{"receipt": "load_state(repo)["stage"] re-read", "open": []}', [],
             'load_state(repo)["stage"] re-read'),
            ("one open member", '{"receipt": "a "b" c", "open": ["app.py:4 - same limit - fix it"]}',
             ["app.py:4 - same limit - fix it"], 'a "b" c'),
            ("receipt ending in an escaped quote", '{"receipt": "a "b" and \\"c\\"", "open": []}', [],
             'a "b" and \\"c\\"'),
            ("no receipt key", 'Done.\n{"open": [], "note": "a "b""}', [], ""),
        ]
        for message, reply, expected, expected_receipt in cases:
            with self.subTest(message):
                closure = self.closure(reply)

                self.assertEqual(expected, closure["open"])
                self.assertEqual(expected_receipt, closure["receipt"])

    def test_an_open_list_that_does_not_decode_still_raises(self):
        with self.assertRaises(review_loop_findings.ReplyShapeError):
            self.closure('{"receipt": "a "b" c", "open": ["app.py:4 - unclosed]}')

    def test_the_prompt_tells_the_model_to_escape_quotes_in_the_receipt(self):
        prompts = []

        def claude_call(_label, prompt, *_args, **_kwargs):
            prompts.append(prompt)
            return '{"receipt": "none", "open": []}'

        review_loop_closure.closure_check(pathlib.Path("/repo"), pathlib.Path("/out"), ["app.py:3 - limit"],
                                          claude_call)

        self.assertIn('escape every double quote inside the receipt as \\"', prompts[0])


def load_script_module(script=SCRIPT):
    loader = importlib.util.spec_from_file_location(f"{script.stem}_under_test", script)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


class SkipLabelsTest(unittest.TestCase):
    def test_which_report_lines_record_an_issue_skip(self):
        cases = [
            ("SKIPPED 2: needs the user", {2}, "an issue skip names its issue"),
            ("SKIPPED small 2: a nit", set(), "a small-item skip is no issue skip"),
            ("SKIPPED 3: fixed with issue 1", set(), "a skip covered by another listed issue is fixed"),
            ("SKIPPED 3: same as #1", set(), "a #<m> reference covers too"),
            ("SKIPPED 3: covered by issue 5", {3}, "an issue the list does not hold covers nothing"),
            ("SKIPPED 3: same as issue 3", {3}, "an issue never covers itself"),
            ("SKIPPED 3: the guard was already addressed in 2 places upstream", {3}, "a count is no issue number"),
            ("SKIPPED 2: false positive, the check is done in 1 pass", {2}, "a count after a verb is no cover"),
            ("SKIPPED 3: conflicts with issue 1, applying both breaks parse", {3}, "a bare mention is no cover"),
            ("SKIPPED 3: false positive; see #2", {3}, "a see-reference is no cover"),
        ]
        for report, skipped_numbers, message in cases:
            with self.subTest(message):
                number = int(re.search(r"SKIPPED (?:small )?(\d+)", report).group(1))
                skips = coder_report.skipped_issues(report, 3)

                self.assertEqual(set(skips), skipped_numbers)
                if skipped_numbers:
                    self.assertEqual(skips[number], report)

    def test_a_skip_covered_by_a_skipped_issue_stays_a_skip(self):
        report = "SKIPPED 1: false positive\nSKIPPED 3: same as 1"

        skips = coder_report.skipped_issues(report, 3)

        self.assertEqual(set(skips), {1, 3})

    def test_a_cover_chain_gives_the_same_skips_in_any_line_order(self):
        lines = ["SKIPPED 2: same as 3", "SKIPPED 3: same as 4"]

        for ordered in (lines, lines[::-1]):
            with self.subTest(order=ordered):
                skips = coder_report.skipped_issues("\n".join(ordered), 4)

                self.assertEqual(set(skips), set())

    def test_a_skip_covered_by_a_fixed_skip_is_fixed_too(self):
        report = "SKIPPED 1: fixed with issue 2\nSKIPPED 3: same as 1"

        skips = coder_report.skipped_issues(report, 3)

        self.assertEqual(set(skips), set())

    def test_a_main_session_reviewer_round_gets_a_deleted_untracked_file_back(self):
        module = load_script_module()
        repo = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / "mine.py").write_text("mine\n")

        def request_round(*_args, **_kwargs):
            (repo / "mine.py").unlink()
            return []

        loop = types.SimpleNamespace(repo=repo, out=repo / "out", iter_count=1, dispatches=[], reviewer_model="",
                                     review_request=mock.Mock())
        with mock.patch.object(module.reviewer_dispatch, "request_round", request_round):
            self.addCleanup(module.review_loop_untracked.UNTRACKED_FAULTS.clear)
            module.LoopRun.reviews_from_main(loop)

        self.assertEqual((repo / "mine.py").read_text(), "mine\n")
        self.assertIn("review1-main deleted untracked files", module.review_loop_untracked.UNTRACKED_FAULTS[0])

    def test_a_concurrent_reviewer_batch_blames_the_batch_for_a_deleted_untracked_file(self):
        module = load_script_module()
        repo = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / "mine.py").write_text("mine\n")
        (repo / "out").mkdir()
        fast_done = threading.Event()

        def run_process(command, _cwd, **_kwargs):
            if "(review1-slow)" in " ".join(command):
                fast_done.wait(timeout=10)
                (repo / "mine.py").unlink()
                return 0, '{"result": "ok"}', ""
            fast_done.set()
            return 0, '{"result": "ok"}', ""

        requests = [module.ReviewRequest("review1-slow", "slow", "p"),
                    module.ReviewRequest("review1-fast", "fast", "p")]
        loop = types.SimpleNamespace(repo=repo, out=repo / "out", iter_count=1, dispatches=["slow", "fast"],
                                     reviewer_model="", reviewers="", read_review=lambda text: text)
        loop.review_request = lambda dispatch: requests[loop.dispatches.index(dispatch)]
        loop.review_one = lambda request: module.LoopRun.review_one(loop, request)
        self.addCleanup(module.review_loop_untracked.UNTRACKED_FAULTS.clear)
        with mock.patch.object(module.script_utils, "run_process", run_process):
            module.LoopRun.run_reviewers(loop)

        faults = module.review_loop_untracked.UNTRACKED_FAULTS
        self.assertEqual((repo / "mine.py").read_text(), "mine\n")
        self.assertEqual(len(faults), 1, faults)
        self.assertIn("review1-reviewers(review1-slow, review1-fast) deleted untracked files", faults[0])

    def test_two_issues_covering_each_other_both_stay_skips(self):
        skips = coder_report.skipped_issues("SKIPPED 1: same as 3\nSKIPPED 3: same as 1", 3)

        self.assertEqual(set(skips), {1, 3})

    def test_a_short_finding_text_inside_a_longer_one_keeps_its_own_status(self):
        module = load_script_module()
        short = finding_record.parse_finding("`app.py:2` the limit")
        long_skipped = finding_record.parse_finding("`app.py:2` the limit is wrong for `limit`")
        host = types.SimpleNamespace(round_fixes=[{"finding": short}])

        module.LoopRun.mark_round_fixes(host, [], [long_skipped])

        self.assertEqual(host.round_fixes[0]["actioned"], "fixed")

    def test_a_finding_folded_into_a_merged_skipped_item_takes_its_status(self):
        module = load_script_module()
        first = finding_record.parse_finding("`app.py:2` the limit is wrong for `limit`")
        second = finding_record.parse_finding("`app.py:3` the limit is wrong again for `limit`")
        merged = finding_record.combine([first, second])
        host = types.SimpleNamespace(round_fixes=[{"finding": first}, {"finding": second}])

        module.LoopRun.mark_round_fixes(host, [], [merged])

        self.assertEqual([entry["actioned"] for entry in host.round_fixes], ["skipped_fp", "skipped_fp"])


class WithoutRevertedTest(unittest.TestCase):
    def test_a_mixed_pass_loses_only_the_reverted_path_and_its_fix_diff_stat(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        diff_files = {}
        for name in ("app.py", "CLAUDE.md"):
            diff_files[name] = pathlib.Path(folder.name) / f"{name}.diff"
            diff_files[name].write_text("diff")
            review_loop_closure.FIX_DIFF_STATS.append(
                {"path": name, "added": 1, "removed": 0, "diff_file": str(diff_files[name])})
        self.addCleanup(review_loop_closure.FIX_DIFF_STATS.clear)
        result = review_loop_coder.CoderResult(
            "Fixed 1.", ["--- a/app.py\n+++ b/app.py", "--- a/CLAUDE.md\n+++ b/CLAUDE.md"], ["app.py", "CLAUDE.md"])

        kept = review_loop_coder.without_reverted(result, ["CLAUDE.md"], 0)

        self.assertEqual(kept.changed, ["app.py"])
        self.assertEqual(kept.diffs, ["--- a/app.py\n+++ b/app.py"])
        self.assertEqual([stat["path"] for stat in review_loop_closure.FIX_DIFF_STATS], ["app.py"])
        self.assertTrue(diff_files["app.py"].exists())
        self.assertFalse(diff_files["CLAUDE.md"].exists())

    def test_an_earlier_rounds_kept_stat_for_a_reverted_path_stays(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(review_loop_closure.FIX_DIFF_STATS.clear)
        diff_files = [pathlib.Path(folder.name) / "kept.diff", pathlib.Path(folder.name) / "reverted.diff"]
        for diff_file in diff_files:
            diff_file.write_text("diff")
            review_loop_closure.FIX_DIFF_STATS.append(
                {"path": "CLAUDE.md", "added": 1, "removed": 0, "diff_file": str(diff_file)})
        result = review_loop_coder.CoderResult("Fixed 1.", ["--- a/CLAUDE.md\n+++ b/CLAUDE.md"], ["CLAUDE.md"])

        review_loop_coder.without_reverted(result, ["CLAUDE.md"], 1)

        self.assertEqual([stat["diff_file"] for stat in review_loop_closure.FIX_DIFF_STATS], [str(diff_files[0])])
        self.assertTrue(diff_files[0].exists())
        self.assertFalse(diff_files[1].exists())


class ReviewLoopHarness:
    """Mixin with no tests: the scratch repo, the stand-in `claude` and the readers of what a run stored."""

    def setUp(self):
        review_loop_ruling_check.RULING_CHECK_FAULTS.clear()
        self.addCleanup(review_loop_ruling_check.RULING_CHECK_FAULTS.clear)
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name)
        self.repo = self.scratch / "shop-api"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "T")
        self.commit_files({"app.py": APP_BEFORE, "notes.py": NOTES_BEFORE, "CLAUDE.md": "Quality check: `true`\n"})
        (self.repo / "app.py").write_text(APP_AFTER_EDIT)

        self.fake_dir = self.scratch / "fake-claude"
        self.fake_dir.mkdir()
        claude = self.fake_dir / "bin" / "claude"
        claude.parent.mkdir()
        claude.write_text(FAKE_CLAUDE)
        claude.chmod(0o755)
        self.fake_ruff = claude.parent / "ruff"
        self.fake_ruff.write_text("#!/bin/sh\nexit 0\n")
        self.fake_ruff.chmod(0o755)
        self.env = {
            **os.environ,
            **fake_ledger.install(self.scratch),
            "HOME": str(self.scratch / "home"),
            "HANDBACK_STORE_DIR": str(self.scratch / "handback"),
            "AGENT_USAGE_FILE": str(self.scratch / "agent-usage.jsonl"),
            "CLAUDE_TOOLKIT_TELEMETRY": "1",
            "FAKE_CLAUDE_DIR": str(self.fake_dir),
        }
        self.env.pop("CLAUDE_SKIP_HOOKS", None)
        self.env.pop("CLAUDE_FORMAT_HOOK_OFF", None)
        self.env["PATH"] = f"{claude.parent}{os.pathsep}{self.env['PATH']}"
        # /code starts the loop with its own state folder.
        self.state_dir = pathlib.Path(git(self.repo, "rev-parse", "--path-format=absolute", "--git-path", "code-step"))

    def commit_files(self, files):
        for name, text in files.items():
            (self.repo / name).write_text(text)
        git(self.repo, "add", *files)
        git(self.repo, "commit", "-q", "-m", "files")

    def prompt_file_text(self, header_extra="", footer=""):
        return ("mode: review-first\ncaller: code\nlane: code\nplan: plan.md\nphase: 2\n"
                f"{header_extra}\nhandoff:\n  files:\n    - path: app.py\n{footer}")

    def script_command(self, prompt, session=SESSION):
        gate_flags = [flag for command in getattr(self, "gate_commands", []) for flag in ("--gate-command", command)]
        if getattr(self, "gates_every_run", False):
            gate_flags.append("--gates-every-run")
        return [sys.executable, str(SCRIPT), str(self.repo), "--state-dir", str(self.state_dir), "--session", session,
                "--agent-id", AGENT_ID, "--prompt-file", str(prompt), *gate_flags]

    def run_script(self, scenario, header_extra="", quality_check=None, claude_md=None, footer="", session=SESSION):
        if quality_check:
            self.commit_files({"CLAUDE.md": f"Quality check: `{quality_check}`\n"})
        if claude_md:
            self.commit_files({"CLAUDE.md": claude_md})
        (self.fake_dir / "scenario.json").write_text(json.dumps(scenario))
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text(header_extra, footer))
        return subprocess.run(self.script_command(prompt, session), capture_output=True, text=True, env=self.env)

    def fake_calls(self):
        path = self.fake_dir / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def reset_fake_run(self):
        """Forget the fake agent's calls, counters and stored hand-backs, so one test can run the script again."""
        (self.fake_dir / "calls.jsonl").unlink(missing_ok=True)
        (self.fake_dir / "counters.json").unlink(missing_ok=True)
        (self.scratch / "handback").mkdir(exist_ok=True)
        for stored in (self.scratch / "handback").iterdir():
            stored.unlink()

    def store_rows(self):
        path = self.scratch / "handback" / f"{SESSION}.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def usage_rows(self):
        path = self.scratch / "agent-usage.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def stored_packet(self):
        handbacks = [row for row in self.store_rows() if row["kind"] == "handback"]
        self.assertEqual(len(handbacks), 1)
        return handbacks[0], handback.load(handbacks[0]["message"])

    def finding_rows(self):
        return fake_ledger.recorded_rows(self.env, "review_finding")


class ReviewLoopScriptTest(ReviewLoopHarness, unittest.TestCase):
    def test_converged_two_round_run_writes_packet_and_rows(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["iter"]), ("converged", 2))
        self.assertEqual(packet["fixed"][0]["file_line"], "app.py:2")
        self.assertEqual(packet["files_touched"], ["app.py"])
        self.assertIn("one exit, all re-read", packet["class_closure"])
        self.assertEqual((row["agent_id"], row["status"], row["no_reviewer"]), (AGENT_ID, "converged", False))
        self.assertFalse(row["unreviewed_fix"])

        kinds = [stored["kind"] for stored in self.store_rows()]
        self.assertEqual(kinds, ["handback", "stop"])
        stop = self.store_rows()[1]
        self.assertEqual((stop["agent_id"], stop["ask_rows"]), (AGENT_ID, []))
        self.assertNotIn("open_dispatches", stop)
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            latest_stop = handback_store.latest(SESSION)["stop"]
        self.assertEqual(latest_stop["ask_rows"], [])

        runs = fake_ledger.recorded_rows(self.env, "review_run")
        self.assertEqual([run["scope"] for run in runs], ["phase", "phase"])

        usage = self.usage_rows()
        self.assertEqual(len(usage), 1)
        self.assertEqual((usage[0]["agent"], usage[0]["model"], usage[0]["driver"]),
                         ("review-loop", "script", "script"))
        self.assertEqual((usage[0]["calls"], usage[0]["tokens"]), (4, 80))

    def answer_round(self, round_number, text, process):
        """Plays the main session for one review round: waits for the round's manifest, writes `text` as every
        report. Returns the round's requests."""
        manifest = self.state_dir / "loop-script" / AGENT_ID / "reviewer-requests" / f"round-{round_number}.json"
        deadline = time.time() + 60
        while not manifest.is_file():
            if process.poll() is not None:
                self.fail(f"loop exited {process.returncode}: {process.stderr.read()}")
            self.assertLess(time.time(), deadline, f"no {manifest}")
            time.sleep(0.05)
        requests = json.loads(manifest.read_text())["requests"]
        for request in requests:
            pathlib.Path(request["report_file"]).write_text(text)
        return requests

    def test_main_mode_hands_each_round_to_the_main_session_and_reads_its_reports(self):
        (self.fake_dir / "scenario.json").write_text(json.dumps(FIX_THEN_CLEAN))
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text())
        process = subprocess.Popen([*self.script_command(prompt), "--reviewers", "main"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=self.env)
        self.addCleanup(process.kill)

        first = self.answer_round(1, FIX_REVIEW, process)
        second = self.answer_round(2, CLEAN_REVIEW, process)
        _stdout, stderr = process.communicate(timeout=120)

        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual([(request["role"], request["agent"]) for request in first + second],
                         [("review1-code-reviewer", "code-reviewer"), ("review2-code-reviewer", "code-reviewer")])
        self.assertIn("app.py", pathlib.Path(first[0]["prompt_file"]).read_text())
        self.assertNotIn("code-reviewer", [call["key"] for call in self.fake_calls()])
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["iter"]), ("converged", 2))
        self.assertEqual(packet["fixed"][0]["file_line"], "app.py:2")
        calls = [json.loads(line)
                 for line in (self.state_dir / "loop-script" / AGENT_ID / "calls.jsonl").read_text().splitlines()]
        main_rows = [call for call in calls if call.get("via") == "main"]
        self.assertEqual([(call["role"], call["tokens"]) for call in main_rows],
                         [("review1-code-reviewer", 0), ("review2-code-reviewer", 0)])

    def findings_header(self, *findings):
        findings_file = self.scratch / "findings.json"
        findings_file.write_text(json.dumps(list(findings)))
        return f"mode: fix-first\nfindings: {findings_file}\n"

    def test_a_fix_first_run_sends_the_given_findings_to_the_coder_before_any_reviewer(self):
        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:2 the limit is wrong for `limit`"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        keys = [call["key"] for call in self.fake_calls()]
        self.assertEqual(keys[:2], ["coder", "code-reviewer"])
        self.assertIn("the limit is wrong", self.fake_calls()[0]["prompt"])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["files_touched"], ["app.py"])

    def test_a_fix_first_run_marks_only_the_callers_skip_as_given_in_the_packet(self):
        completed = self.run_script({
            "coder": [{"result": "SKIPPED 1: the caller's wording is off", "edits": {"app.py": APP_FIXED}},
                      {"result": "SKIPPED 1: the limit is meant to be 5", "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:3 the caller's finding [bug]"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(len(packet["skipped_fp"]), 2)
        callers = [entry for entry in packet["skipped_fp"] if "wording is off" in entry["reason"]]
        reviewers = [entry for entry in packet["skipped_fp"] if "meant to be 5" in entry["reason"]]
        self.assertEqual([entry.get("given") for entry in callers], [True])
        self.assertEqual([entry.get("given") for entry in reviewers], [None])

    def test_a_fix_first_finding_the_coder_re_asks_in_open_questions_is_skipped_not_fixed(self):
        report = 'Reworded the message.\nOPEN QUESTIONS: ["app.py:2 should the limit be denied instead?"]'
        completed = self.run_script({
            "coder": [{"result": report, "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:2 Proposed change: deny the limit") + self.USER_RULED_HEADER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["fixed"], [])
        self.assertEqual(len(packet["skipped_fp"]), 1)
        self.assertEqual([entry.get("given") for entry in packet["skipped_fp"]], [True])
        reason = packet["skipped_fp"][0]["reason"]
        self.assertIn("re-asked", reason)
        self.assertIn("app.py:2 should the limit be denied instead?", reason)

    def test_a_fix_first_finding_a_session_ruled_and_the_coder_re_asks_is_skipped_not_fixed(self):
        report = 'Reworded the message.\nOPEN QUESTIONS: ["app.py:2 should the limit be denied instead?"]'
        completed = self.run_script({
            "coder": [{"result": report, "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:2 Proposed change: deny the limit") + "session-ruled: 1\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["fixed"], [])
        self.assertEqual(len(packet["skipped_fp"]), 1)
        reason = packet["skipped_fp"][0]["reason"]
        self.assertIn("SKIPPED 1:", reason)
        self.assertIn("re-asked", reason)
        self.assertEqual(packet["ask"], [])

    def ruled_run(self, judge_replies, header_extra="", edits=None, ruled_header="session-ruled: 1\n"):
        """A fix-first run whose one finding a session ruled on, the coder editing app.py. `ruled_header` holds the
        ruling lines (a session ruling by default)."""
        ruling = "app.py:2 Proposed change: drop the prefix strip"
        scenario = {
            "coder": [{"result": "Fixed 1.", "edits": edits or {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }
        if judge_replies is not None:
            scenario["ruling-check"] = [{"result": reply} for reply in judge_replies]
        header = self.findings_header(ruling) + ruled_header + header_extra
        return self.run_script(scenario, header_extra=header)

    def test_a_fix_pass_that_keeps_what_a_ruling_dropped_is_put_back_and_stops_the_run(self):
        against = json.dumps({"verdicts": [
            {"ruling": "app.py:2 drop the prefix strip", "verdict": "against", "file": "app.py",
             "kept": "the prefix strip"},
            {"ruling": "app.py:2 other ruling", "verdict": "kept"},
            {"ruling": "notes.py:1 second ruling", "verdict": "against", "file": "notes.py", "kept": "the dict"}]})
        completed = self.ruled_run([against], header_extra="held files: notes.py\n",
                                   edits={"app.py": APP_FIXED, "notes.py": NOTES_REFLOWED,
                                          "new_helper.py": "value = 1\n"})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual(packet["against_ruling"],
                         [{"ruling": "app.py:2 drop the prefix strip", "file": "app.py", "kept": "the prefix strip"},
                          {"ruling": "notes.py:1 second ruling", "file": "notes.py", "kept": "the dict"}])
        self.assertIn("went against the accepted ruling on app.py: app.py:2 drop the prefix strip; it kept: the "
                      "prefix strip. The pass was put back. fix pass", packet["blockers"][0])
        self.assertIn("on notes.py: notes.py:1 second ruling; it kept: the dict.", packet["blockers"][0])
        printed = self.review_fix_packet_output()
        self.assertIn("went against the accepted ruling on app.py: app.py:2 drop the prefix strip", printed)
        self.assertNotIn("other ruling", packet["blockers"][0])
        self.assertIn("drop the prefix strip", json.dumps(packet["findings_remaining"]), "the finding stays open")
        self.assertFalse((self.repo / "new_helper.py").exists(), "a file the pass created is deleted")
        self.assertEqual((self.repo / "app.py").read_text(), APP_AFTER_EDIT)
        self.assertEqual((self.repo / "notes.py").read_text(), NOTES_REFLOWED,
                         "a held file with a holder row is not in the backup, so the put-back leaves it")
        self.assertNotIn("code-reviewer", [call["key"] for call in self.fake_calls()])
        self.assertEqual(list(self.scratch.rglob("ruling-check/*/files")), [], "the backup is discarded")

    def test_a_fix_pass_the_judge_finds_kept_moves_on_with_its_changes(self):
        kept = json.dumps({"verdicts": [{"ruling": "app.py:2 drop the prefix strip", "verdict": "kept"}]})
        completed = self.ruled_run([kept])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["against_ruling"], [])
        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED)
        self.assertEqual(list(self.scratch.rglob("ruling-check/*/files")), [], "the backup is discarded")
        self.assertIn("ruling-check", [call["key"] for call in self.fake_calls()])

    def test_a_run_with_no_ruling_makes_no_ruling_check_call(self):
        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:2 Proposed change: drop the prefix strip"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("ruling-check", [call["key"] for call in self.fake_calls()])
        self.assertEqual(self.stored_packet()[1]["against_ruling"], [])

    def test_a_judge_reply_that_does_not_parse_stops_as_a_tool_fault_and_leaves_the_pass_in_place(self):
        completed = self.ruled_run(["no verdicts here", "still none"])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("the ruling check of fix pass", packet["blockers"][0])
        self.assertIn("stay in the tree", packet["blockers"][0])
        self.assertIn("the ruling check of fix pass", packet["tool_fault"])
        self.assertEqual(packet["against_ruling"], [])
        self.assertIn("app.py", packet["files_touched"])
        self.assertTrue(packet["findings_remaining"], "the pass's findings stay open")
        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED)
        self.assertNotIn("code-reviewer", [call["key"] for call in self.fake_calls()])

    def judge_calls(self):
        return [call for call in self.fake_calls() if call["key"] == "ruling-check"]

    def test_a_user_ruling_alone_makes_a_ruling_check_call(self):
        completed = self.ruled_run(None, ruled_header="user-ruled: 1\nuser-ruled-at: 2026-11-13 11:32:00Z\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(self.judge_calls()), 1)

    def test_an_adopted_ruling_alone_makes_a_ruling_check_call(self):
        row = {"number": 1, "text": "drop the prefix strip", "finding_text": None, "owner": "session",
               "ruled_at": "2026-11-13 11:32:00Z"}
        completed = self.ruled_run(None, ruled_header=f"adopted: {json.dumps([row])}\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(self.judge_calls()), 1)

    def test_an_existing_file_a_ruled_finding_names_outside_the_pass_scope_is_put_back(self):
        helper_before = "helper = 1\n"
        self.commit_files({"helper.py": helper_before})
        against = json.dumps({"verdicts": [
            {"ruling": "helper.py:1 drop the helper", "verdict": "against", "file": "helper.py", "kept": "helper"}]})
        scenario = {
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "helper.py": "helper = 2\n"}}],
            "ruling-check": [{"result": against}],
        }
        ruling = "app.py:2 Proposed change: drop the prefix strip and the helper in helper.py"
        completed = self.run_script(scenario, header_extra=self.findings_header(ruling) + "session-ruled: 1\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "helper.py").read_text(), helper_before)

    def test_a_held_file_with_no_holder_row_that_no_finding_names_is_put_back_byte_for_byte(self):
        self.commit_files({"held_extra.py": "held = 1\n"})
        held_before = "held = 5\n"
        (self.repo / "held_extra.py").write_text(held_before)
        against = json.dumps({"verdicts": [
            {"ruling": "app.py:2 drop the prefix strip", "verdict": "against", "file": "app.py",
             "kept": "the prefix strip"}]})
        # A run scoped to app.py holds the dirty held_extra.py; with no other live session it has no holder row.
        completed = self.ruled_run([against], header_extra="files: app.py\n",
                                   edits={"app.py": APP_FIXED, "held_extra.py": "held = 2\n"})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "held_extra.py").read_bytes(), held_before.encode())
        self.assertEqual((self.repo / "app.py").read_text(), APP_AFTER_EDIT)

    def assert_claude_md_finding_in_ask_after_ruling_check(self, replies):
        """A ruled run whose coder edits CLAUDE.md and app.py, the judge answering `replies`."""
        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "CLAUDE.md": "# Rules\n"}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
            "ruling-check": [{"result": reply} for reply in replies],
        }, header_extra=self.findings_header("CLAUDE.md:1 Proposed change: reword the rule",
                                             "app.py:2 Proposed change: drop the prefix strip")
                        + "session-ruled: 1, 2\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual([entry["file_line"] for entry in packet["ask"]], ["CLAUDE.md:1"])
        self.assertNotIn("CLAUDE.md", json.dumps(packet["findings_remaining"]))
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), "Quality check: `true`\n")

    def test_a_claude_md_finding_lands_in_ask_when_the_judge_finds_the_pass_against_a_ruling(self):
        against = json.dumps({"verdicts": [
            {"ruling": "app.py:2 drop the prefix strip", "verdict": "against", "file": "app.py", "kept": "k"}]})
        self.assert_claude_md_finding_in_ask_after_ruling_check([against])

    def test_a_claude_md_finding_lands_in_ask_when_the_judge_reply_cannot_be_read(self):
        self.assert_claude_md_finding_in_ask_after_ruling_check(["no verdicts", "still none"])

    def test_the_judge_prompt_tags_each_ruling_source_once_and_names_no_outcome(self):
        header = "user-ruled: 1\nuser-ruled-at: 2026-11-13 11:32:00Z\n"
        completed = self.ruled_run(None, ruled_header=header + "session-ruled: 1\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        prompt = self.judge_calls()[0]["prompt"]
        ruling_lines = [line for line in prompt.splitlines() if line.startswith("- [")]
        self.assertEqual(len(ruling_lines), 1, "a text held as user_ruled and session_ruled shows once")
        self.assertTrue(ruling_lines[0].startswith("- [user_ruled] "), ruling_lines[0])
        marked = review_loop_prompts.user_ruled_issue("app.py:2 Proposed change: drop the prefix strip",
                                                      "2026-11-13 11:32:00Z")
        self.assertEqual(ruling_lines[0], f"- [user_ruled] {marked}", "the judge sees the mark the coder saw")
        self.assertNotIn("[accepted]", prompt)
        self.assertNotIn("[rejected]", prompt)
        self.assertIn("carries no outcome mark: judge it as accepted only when its text says so", prompt)

    def test_the_judge_prompt_tags_a_session_only_ruling_as_session_ruled(self):
        completed = self.ruled_run(None)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        ruling_lines = [line for line in self.judge_calls()[0]["prompt"].splitlines() if line.startswith("- [")]
        self.assertEqual(len(ruling_lines), 1)
        self.assertTrue(ruling_lines[0].startswith("- [session_ruled] "), ruling_lines[0])

    def test_the_judge_prompt_tags_an_adopted_ruling_as_adopted(self):
        row = {"number": 1, "text": "drop the prefix strip", "finding_text": None, "owner": "session",
               "ruled_at": "2026-11-13 11:32:00Z"}
        completed = self.ruled_run(None, ruled_header=f"adopted: {json.dumps([row])}\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        ruling_lines = [line for line in self.judge_calls()[0]["prompt"].splitlines() if line.startswith("- [")]
        self.assertEqual(len(ruling_lines), 1)
        self.assertTrue(ruling_lines[0].startswith("- [adopted] "), ruling_lines[0])

    def test_the_judge_reads_a_pass_diff_file_holding_the_edit_and_the_prompt_names_it(self):
        completed = self.ruled_run(None)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        diff_files = list(self.scratch.rglob("ruling-check/*/pass.diff"))
        self.assertEqual(len(diff_files), 1)
        self.assertIn("+limit = 20", diff_files[0].read_text())
        self.assertIn(str(diff_files[0]), self.judge_calls()[0]["prompt"])

    def test_a_ruled_run_whose_coder_changes_nothing_makes_no_ruling_check_call_and_keeps_no_backup(self):
        completed = self.ruled_run(None, edits={"app.py": APP_AFTER_EDIT})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.judge_calls(), [])
        self.assertEqual(list(self.scratch.rglob("ruling-check/*/files")), [])

    def test_a_judge_reply_with_a_bad_verdict_value_is_asked_again(self):
        bad = json.dumps({"verdicts": [{"ruling": "r", "verdict": "maybe"}]})
        good = json.dumps({"verdicts": [{"ruling": "r", "verdict": "kept"}]})
        completed = self.ruled_run([bad, good])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(len(self.judge_calls()), 2)
        self.assertIn("each verdict must be 'kept' or 'against'", self.judge_calls()[1]["prompt"])

    def test_a_judge_reply_with_no_verdicts_is_asked_again_and_then_stops_as_a_tool_fault(self):
        empty = json.dumps({"verdicts": []})
        completed = self.ruled_run([empty, empty])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("the ruling check of fix pass", packet["blockers"][0])
        self.assertIn("one verdict for each of the 1 rulings", self.judge_calls()[1]["prompt"])
        self.assertEqual(len(self.judge_calls()), 2)

    def test_a_failed_coder_pass_discards_the_ruling_backup(self):
        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "exit": 1}],
        }, header_extra=self.findings_header("app.py:2 Proposed change: drop the prefix strip")
                        + "session-ruled: 1\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coder_calls = [call for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coder_calls), 1, "the pass ran, so the ruling check had made its backup first")
        self.assertEqual(list(self.scratch.rglob("ruling-check/*/files")), [])

    def test_an_against_verdict_with_no_file_is_asked_again_and_then_stops_as_a_tool_fault(self):
        no_file = json.dumps({"verdicts": [{"ruling": "r", "verdict": "against", "kept": "x"}]})
        completed = self.ruled_run([no_file, no_file])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual(packet["against_ruling"], [])
        self.assertIn("the ruling check of fix pass", packet["blockers"][0])
        self.assertEqual(len(self.judge_calls()), 2)

    def test_a_judge_call_that_fails_stops_as_a_tool_fault_and_leaves_the_pass_in_place(self):
        completed = self.ruled_run([])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("stay in the tree", packet["blockers"][0])
        self.assertIn("the ruling check of fix pass", packet["tool_fault"])
        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED)

    def test_a_repo_git_cannot_list_stops_the_pass_as_a_ruling_check_fault_that_reaches_the_packet_notes(self):
        host = RulingCheckHost()
        host.repo = str(self.scratch / "no-repo-here")
        host.user_ruled = ["a ruling"]
        host.session_ruled = []
        host.adopted = {}
        faults_before = len(review_loop_ruling_check.RULING_CHECK_FAULTS)

        no_listing = mock.patch.object(review_loop_ruling_check.script_utils, "repo_file_paths", return_value=None)
        with no_listing, self.assertRaises(review_loop_ruling_check.RulingCheckFaultError) as raised:
            host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])

        self.assertIn("git could not list the files", str(raised.exception))
        self.assertEqual(host.kept_open, ["finding"])
        self.assertEqual(len(review_loop_ruling_check.RULING_CHECK_FAULTS), faults_before + 1)
        self.assertIn(str(raised.exception), review_loop_coder.coder_fault_notes())

    def ruled_host(self):
        host = RulingCheckHost()
        host.repo = str(self.repo)
        host.out = self.scratch / "out"
        host.user_ruled = ["a ruling"]
        host.session_ruled = []
        host.adopted = {}
        return host

    def test_an_index_git_cannot_read_stops_the_pass_as_a_ruling_check_fault_and_drops_the_backup(self):
        host = self.ruled_host()
        faults_before = len(review_loop_ruling_check.RULING_CHECK_FAULTS)
        index_fails = mock.patch.object(review_loop_ruling_check.script_utils, "index_entries",
                                        side_effect=review_loop_ruling_check.script_utils.GitCallError("no index"))

        with index_fails, self.assertRaises(review_loop_ruling_check.RulingCheckFaultError) as raised:
            host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])

        self.assertIn("no index", str(raised.exception))
        self.assertEqual(host.kept_open, ["finding"])
        self.assertEqual(len(review_loop_ruling_check.RULING_CHECK_FAULTS), faults_before + 1)
        self.assertEqual(list((self.scratch / "out").rglob("app.py")), [], "the backup folder is gone")

    def test_a_put_back_pass_puts_the_index_back_for_a_changed_a_new_and_a_created_path(self):
        host = self.ruled_host()
        backup = host.begin_ruling_check("fix-1", ["app.py", "in_scope_new.py"], ["finding"], [])
        stage_before = git(self.repo, "ls-files", "--stage")
        (self.repo / "app.py").write_text("changed by the pass\n")
        (self.repo / "in_scope_new.py").write_text("new\n")
        (self.repo / "stray.py").write_text("stray\n")
        git(self.repo, "add", "app.py", "in_scope_new.py", "stray.py")
        result = types.SimpleNamespace(changed=["app.py", "in_scope_new.py", "stray.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertEqual(git(self.repo, "ls-files", "--stage"), stage_before)
        self.assertNotIn("Not put back", str(raised.exception))

    def test_a_coder_commit_made_during_the_pass_stays_in_head_and_is_named(self):
        host = self.ruled_host()
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        (self.repo / "app.py").write_text("committed by the coder\n")
        git(self.repo, "add", "app.py")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "coder fix")
        short_hash = git(self.repo, "rev-parse", "--short", "HEAD")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        blocker = str(raised.exception)
        self.assertIn(f"Commits the coder made during the pass stay in HEAD: {short_hash} coder fix.", blocker)
        self.assertIn("The work tree and index were put back; the coder's commit stays.", blocker)
        self.assertNotIn("The pass was put back.", blocker)
        self.assertIn("app.py", host.files_touched, "the session commits the revert")

    def test_a_coder_commit_in_a_repo_that_had_no_commit_is_named(self):
        unborn = self.scratch / "unborn"
        unborn.mkdir()
        git(unborn, "init", "-q", "-b", "main")
        (unborn / "app.py").write_text("old\n")
        host = self.ruled_host()
        host.repo = str(unborn)
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        self.assertIsNone(host.ruling_head_before)
        (unborn / "app.py").write_text("committed by the coder\n")
        git(unborn, "add", "app.py")
        git(unborn, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "first commit")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertIn("stay in HEAD:", str(raised.exception))
        self.assertIn("first commit", str(raised.exception))

    def test_a_commit_list_git_cannot_read_is_reported_and_the_pass_is_not_called_put_back(self):
        host = self.ruled_host()
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        (self.repo / "app.py").write_text("changed by the pass\n")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]
        log_fails = mock.patch.object(review_loop_ruling_check.script_utils, "commits_since", return_value=None)

        with log_fails, self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertIn("could not tell whether the coder committed during the pass", str(raised.exception))
        self.assertNotIn("The pass was put back.", str(raised.exception))
        self.assertIn("app.py", host.files_touched)

    def test_a_head_git_cannot_name_before_the_pass_stops_it_as_a_ruling_check_fault(self):
        host = self.ruled_host()
        head_fails = mock.patch.object(review_loop_ruling_check.script_utils, "head_commit_or_unborn",
                                       side_effect=review_loop_ruling_check.script_utils.GitCallError("no head"))

        with head_fails, self.assertRaises(review_loop_ruling_check.RulingCheckFaultError) as raised:
            host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])

        self.assertIn("no head", str(raised.exception))
        self.assertEqual(host.kept_open, ["finding"])

    def test_a_path_not_put_back_is_recorded_in_files_touched(self):
        host = RulingCheckHost()
        host.repo = str(self.repo)
        host.files_touched = set()
        host.ruling_files_before = frozenset({"big.bin"})
        backup = file_backup.Backup(self.repo, self.scratch / "copies", [], ["big.bin"])
        result = types.SimpleNamespace(changed=["big.bin"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError):
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertEqual(host.files_touched, {"big.bin"})

    def test_a_pass_with_no_coder_commit_keeps_the_put_back_text(self):
        host = self.ruled_host()
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        (self.repo / "app.py").write_text("changed by the pass\n")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertIn("it kept: k. The pass was put back.", str(raised.exception))
        self.assertNotIn("Commits the coder made", str(raised.exception))

    def test_an_index_entry_git_cannot_restore_is_named_as_not_put_back(self):
        host = self.ruled_host()
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        (self.repo / "app.py").write_text("changed by the pass\n")
        git(self.repo, "add", "app.py")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]
        restore_fails = mock.patch.object(review_loop_ruling_check.script_utils, "restore_index_entry",
                                          return_value=False)

        with restore_fails, self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertIn("or an index entry git could not restore: app.py.", str(raised.exception))

    def test_a_path_the_backup_could_not_save_is_named_as_not_put_back(self):
        host = RulingCheckHost()
        host.repo = str(self.repo)
        host.ruling_files_before = frozenset({"big.bin", "stray.txt"})
        backup = file_backup.Backup(self.repo, self.scratch / "copies", [], ["big.bin", "idle.bin"])
        result = types.SimpleNamespace(changed=["big.bin", "stray.txt"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertIn("Not put back, over the size cap, unreadable, outside the saved files, a directory left in "
                      "place or an index entry git could not restore: big.bin, stray.txt.", str(raised.exception))
        self.assertNotIn("The pass was put back.", str(raised.exception))
        self.assertIn("Part of the pass was put back.", str(raised.exception))
        self.assertNotIn("idle.bin", str(raised.exception), "an unsaved file the pass did not change is not named")

    def test_a_directory_the_pass_made_at_an_absent_path_is_named_as_not_put_back(self):
        (self.repo / "made_dir").mkdir()
        host = RulingCheckHost()
        host.repo = str(self.repo)
        host.ruling_files_before = frozenset()
        backup = file_backup.Backup(self.repo, self.scratch / "copies", [], [])
        result = types.SimpleNamespace(changed=["made_dir"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertIn("a directory left in place or an index entry git could not restore: made_dir.",
                      str(raised.exception))

    def test_a_put_back_pass_keeps_open_only_the_findings_not_on_a_reverted_approval_path(self):
        host = RulingCheckHost()
        host.repo = str(self.repo)
        host.ruling_files_before = frozenset()
        host.reverted_findings = ["on-claude-md"]
        backup = file_backup.Backup(self.repo, self.scratch / "copies", [], [])
        result = types.SimpleNamespace(changed=[], reverted=["CLAUDE.md"])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError):
            host.put_back_pass("fix-1", ["on-claude-md", "on-app"], result, backup, against)

        self.assertEqual(host.kept_open, ["on-app"])
        self.assertEqual(host.open_fixes, [], "a reverted finding kept open by an earlier round is dropped")

    def test_a_held_file_a_finding_text_names_is_left_out_of_the_ruling_backup(self):
        (self.repo / "notes.py").write_text("n = 1\n")
        host = self.ruled_host()
        host.held = frozenset({"notes.py"})
        listing = ["app.py", "notes.py"]

        with mock.patch.object(review_loop_ruling_check.script_utils, "repo_file_paths", return_value=listing):
            backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], ["app.py:3 same as notes.py"])

        self.assertNotIn("notes.py", backup.saved)
        self.assertIn("app.py", backup.saved)

    def test_a_ruling_check_that_cannot_reach_the_judge_keeps_the_unreverted_findings_open(self):
        host = RulingCheckHost()
        host.repo = str(self.repo)
        host.out = self.scratch / "out"
        host.reverted_findings = ["on-claude-md"]
        host.files_touched = set()
        host.ruling_texts = lambda findings: []
        host.issue_text = lambda finding: finding
        result = types.SimpleNamespace(changed=["app.py"], reverted=["CLAUDE.md"], diffs=["d"])
        backup = file_backup.Backup(self.repo, self.scratch / "copies", [], [])

        failing = mock.patch.object(review_loop_ruling_check, "reply_with_one_retry",
                                    side_effect=review_loop_ruling_check.ModelCallError("down"))
        with failing, self.assertRaises(review_loop_ruling_check.RulingCheckFaultError):
            host.check_rulings_kept("fix-1", ["on-claude-md", "on-app"], result, backup)

        self.assertEqual(host.kept_open, ["on-app"])
        self.assertEqual(host.open_fixes, [])

    def test_a_code_edit_against_a_no_code_ruling_reaches_the_packet_and_the_next_reviewer_prompt(self):
        ruled = ruled_change_text.changed_text("app.py:2 [bug] Proposed change: deny the limit",
                                               "Make no code change.", ruled_change_text.USER_CLAUSE)
        completed = self.run_script({
            "coder": [{"result": "Reworded the message.", "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header(ruled))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["no_code_ruling_broken"],
                         [{"ruling": "app.py:2 Make no code change.", "file": "app.py"}])
        reviewer_prompt = [call for call in self.fake_calls() if call["key"] == "code-reviewer"][-1]["prompt"]
        self.assertIn(review_loop_prompts.NO_CODE_REVIEW_RULE, reviewer_prompt)
        self.assertIn("Make no code change.", reviewer_prompt)

    def test_a_coder_that_dies_after_editing_against_a_no_code_ruling_still_reaches_the_packet(self):
        ruled = ruled_change_text.changed_text("app.py:2 [bug] Proposed change: deny the limit",
                                               "Make no code change.", ruled_change_text.USER_CLAUSE)
        completed = self.run_script({
            "coder": [{"result": "Prompt is too long", "edits": {"app.py": APP_FIXED}, "exit": 1}],
        }, header_extra=self.findings_header(ruled))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        ruling = review_loop_ruled.ruling_line(finding_record.parse_finding(ruled))
        self.assertEqual(packet["no_code_ruling_broken"], [{"ruling": ruling, "file": "app.py"}])

    def test_a_no_code_ruling_edit_the_judge_puts_back_leaves_no_broken_entry_in_the_packet(self):
        ruled = ruled_change_text.changed_text("app.py:2 [bug] Proposed change: deny the limit",
                                               "Make no code change.", ruled_change_text.USER_CLAUSE)
        against = json.dumps({"verdicts": [
            {"ruling": "app.py:2 Make no code change.", "verdict": "against", "file": "app.py", "kept": "the edit"}]})
        completed = self.run_script({
            "coder": [{"result": "Reworded the message.", "edits": {"app.py": APP_FIXED}}],
            "ruling-check": [{"result": against}],
        }, header_extra=self.findings_header(ruled) + "user-ruled: 1\nuser-ruled-at: 2026-11-13 11:32:00Z\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual((self.repo / "app.py").read_text(), APP_AFTER_EDIT)
        self.assertEqual(packet["no_code_ruling_broken"], [])

    def test_a_put_back_pass_drops_the_approval_ask_and_no_code_entry_it_filed_for_a_restored_path(self):
        host = self.ruled_host()
        host.no_code_broken = [{"ruling": "earlier", "file": "old.py"}]
        host.user_only_paths = ["old_approval.md"]
        wanted_ask = finding_record.parse_finding("`app.py:1` [other] A fix coder wants to edit `app.py`: earlier ask")
        host.user_only_asks = [finding_record.parse_finding("`old_approval.md:1` [other] earlier ask"), wanted_ask]
        host.asks = list(host.user_only_asks)
        host.ask_gates = {}
        host.user_only_bases = {"old_approval.md": "b0"}
        saved = []
        host.save_approval_paths = lambda: saved.append(list(host.user_only_paths))
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        ask = finding_record.parse_finding(review_loop_ruled.approval_ask_text("app.py"))
        host.no_code_broken.append({"ruling": "r", "file": "app.py"})
        host.no_code_broken.append({"ruling": "r", "file": "kept_edit.py"})
        host.user_only_paths.append("app.py")
        host.user_only_asks.append(ask)
        host.asks.append(ask)
        host.ask_gates[ask] = "coder"
        host.user_only_bases["app.py"] = "b1"
        (self.repo / "app.py").write_text("changed by the pass\n")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError):
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertEqual([entry["file"] for entry in host.no_code_broken], ["old.py", "kept_edit.py"])
        self.assertEqual(host.user_only_paths, ["old_approval.md"])
        self.assertEqual([item.path for item in host.asks], ["old_approval.md", "app.py"])
        self.assertIn(wanted_ask, host.user_only_asks, "a wanted-change ask on the same path at line 1 survives")
        self.assertNotIn(ask, host.user_only_asks)
        self.assertNotIn("app.py", host.user_only_bases)
        self.assertEqual(saved, [["old_approval.md"]])

    def test_a_put_back_pass_drops_an_approval_ask_it_filed_for_a_path_it_did_not_restore(self):
        host = self.ruled_host()
        host.no_code_broken = []
        host.user_only_paths = []
        host.user_only_asks = []
        host.asks = []
        host.ask_gates = {}
        host.user_only_bases = {}
        saved = []
        host.save_approval_paths = lambda: saved.append(list(host.user_only_paths))
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        for filed_path in ("CLAUDE.md", "app.py"):
            ask = finding_record.parse_finding(review_loop_ruled.approval_ask_text(filed_path))
            host.user_only_paths.append(filed_path)
            host.user_only_asks.append(ask)
            host.asks.append(ask)
            host.ask_gates[ask] = "coder"
            host.user_only_bases[filed_path] = "b1"
        (self.repo / "app.py").write_text("changed by the pass\n")
        result = types.SimpleNamespace(changed=["app.py"], reverted=["CLAUDE.md"])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError):
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertEqual(host.user_only_paths, [], "the reverted CLAUDE.md ask goes with the put-back pass")
        self.assertEqual(host.user_only_asks, [])
        self.assertEqual(host.asks, [])
        self.assertEqual(host.user_only_bases, {})

    def test_a_put_back_pass_leaves_the_index_entry_of_a_path_the_backup_could_not_save(self):
        host = self.ruled_host()
        backup = file_backup.Backup(self.repo, self.scratch / "copies", [], ["app.py"])
        host.ruling_index_entries = review_loop_ruling_check.script_utils.index_entries(self.repo, ["app.py"])
        host.ruling_files_before = frozenset({"app.py"})
        (self.repo / "app.py").write_text("changed by the pass\n")
        git(self.repo, "add", "app.py")
        stage_after_pass = git(self.repo, "ls-files", "--stage")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertEqual(git(self.repo, "ls-files", "--stage"), stage_after_pass)
        self.assertIn("app.py", str(raised.exception), "the path is still named as not put back")

    def test_an_index_git_cannot_read_at_put_back_names_every_path_as_not_put_back(self):
        host = self.ruled_host()
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        (self.repo / "app.py").write_text("changed by the pass\n")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]
        index_fails = mock.patch.object(review_loop_ruling_check.script_utils, "index_entries",
                                        side_effect=review_loop_ruling_check.script_utils.GitCallError("no index"))

        with index_fails, self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertIn("or an index entry git could not restore: app.py.", str(raised.exception))

    def test_a_tracked_file_deleted_in_the_work_tree_has_its_index_entry_put_back_after_the_pass_recreates_it(self):
        (self.repo / "app.py").unlink()
        host = self.ruled_host()
        backup = host.begin_ruling_check("fix-1", ["app.py"], ["finding"], [])
        stage_before = git(self.repo, "ls-files", "--stage")
        (self.repo / "app.py").write_text("recreated by the pass\n")
        git(self.repo, "add", "app.py")
        result = types.SimpleNamespace(changed=["app.py"], reverted=[])
        against = [{"ruling": "r", "verdict": "against", "file": "app.py", "kept": "k"}]

        with self.assertRaises(review_loop_ruling_check.RulingBrokenError) as raised:
            host.put_back_pass("fix-1", ["finding"], result, backup, against)

        self.assertFalse((self.repo / "app.py").exists())
        self.assertEqual(git(self.repo, "ls-files", "--stage"), stage_before)
        self.assertNotIn("Not put back", str(raised.exception))
        self.assertTrue(str(raised.exception).endswith("The pass was put back."), str(raised.exception))
        self.assertEqual(host.files_touched, set(), "a path the loop put back is not progress to commit")

    def test_verdict_problem_names_each_malformed_reply_shape(self):
        against_blank = {"ruling": "r", "verdict": "against", "file": "  ", "kept": "k"}
        cases = {"verdicts not a list": ({"verdicts": "x"}, "'verdicts' must be a list"),
                 "verdict not an object": ({"verdicts": ["x"]}, "each verdict must be an object"),
                 "whitespace-only file": ({"verdicts": [against_blank]}, "non-empty text for 'file'"),
                 "whitespace-only kept": ({"verdicts": [{**against_blank, "file": "a.py", "kept": " "}]},
                                          "non-empty text for 'kept'"),
                 }
        for name, (parsed, expected) in cases.items():
            with self.subTest(name):
                problem = review_loop_ruling_check.verdict_problem(parsed, 1)
                self.assertIsNotNone(problem, name)
                self.assertIn(expected, problem, name)

    def test_verdict_problem_refuses_a_reply_that_repeats_one_rulings_verdict(self):
        kept = {"ruling": "first", "verdict": "kept"}
        parsed = {"verdicts": [kept, dict(kept)]}

        problem = review_loop_ruling_check.verdict_problem(parsed, 2)

        self.assertIn("one verdict for each of the 2 rulings", problem)
        two_rulings = {"verdicts": [kept, {"ruling": "second", "verdict": "kept"}]}
        self.assertIsNone(review_loop_ruling_check.verdict_problem(two_rulings, 2))

    def assert_reverted_and_reported(self, packet, path):
        """The reverted edit no finding names is reported once as dropped, and files no ask."""
        self.assertEqual(packet["ask"], [])
        self.assertEqual(len(packet["dropped_asks"]), 1, packet["dropped_asks"])
        self.assertIn(review_loop_findings.REVERTED_APPROVAL_EDIT_REASON, packet["dropped_asks"][0])
        self.assertIn(path, packet["dropped_asks"][0])

    def test_a_coder_edit_to_a_claude_md_file_is_reverted_and_reported_as_a_dropped_ask(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "CLAUDE.md": "# Rules\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assert_reverted_and_reported(packet, "CLAUDE.md")
        self.assertEqual(len(packet["fixed"]), 1)
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), "Quality check: `true`\n")

    def test_a_finding_whose_only_edit_was_a_reverted_claude_md_is_skipped_not_fixed(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"CLAUDE.md": "# Rules\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["fixed"], [])
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]],
                         ["the coder made no change"])

    CLAUDE_MD_FIX_REVIEW = FIX_REVIEW.replace("`app.py:2` the limit is wrong for `limit`",
                                              "`CLAUDE.md:1` the rule is wrong for `limit`")

    def assert_one_user_only_ask_on_claude_md(self, packet):
        """The reverted approval-file edit is one user-only ask carrying the finding's change, never an open fix."""
        self.assertEqual([(entry["file_line"], entry.get("user_only")) for entry in packet["ask"]],
                         [("CLAUDE.md:1", True)])
        self.assertIn("the rule is wrong for `limit`", packet["ask"][0]["change"])
        self.assertEqual(packet["findings_remaining"], [])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(packet["fixed"], [])
        claude_md_rows = [row for row in self.finding_rows() if "CLAUDE.md" in json.dumps(row)]
        self.assertEqual([row["actioned"] for row in claude_md_rows[:1]], ["none"])
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), "Quality check: `true`\n")

    def test_a_coder_failure_that_edited_claude_md_leaves_one_user_only_ask_not_an_open_fix(self):
        completed = self.run_script({
            "code-reviewer": [{"result": self.CLAUDE_MD_FIX_REVIEW}],
            "coder": [{"result": "Prompt is too long", "edits": {"CLAUDE.md": "# Rules\n"}, "exit": 1}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assert_one_user_only_ask_on_claude_md(packet)

    def test_a_claude_md_finding_left_open_by_a_plan_held_skip_leaves_no_open_fix_when_a_later_coder_failure_reverts_it(
            self):
        plan_held_skip = ("Skipped 1: needs the user's sign-off.\nPLAN-IMPACT:\n  assumed: AC2 as written\n"
                          "  found: the rule is wrong for `limit`\n  changes: the wording\n"
                          "  acceptance_criteria: AC2\n  cause: plan\nPLAN-IMPACT: yes")
        completed = self.run_script({
            "code-reviewer": [{"result": self.CLAUDE_MD_FIX_REVIEW}, {"result": self.CLAUDE_MD_FIX_REVIEW}],
            "coder": [{"result": plan_held_skip},
                      {"result": "Prompt is too long", "edits": {"CLAUDE.md": "# Rules\n"}, "exit": 1}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["findings_remaining"], [])
        self.assertEqual([(entry["file_line"], entry.get("user_only")) for entry in packet["ask"]],
                         [("CLAUDE.md:1", True)])

    def test_a_finding_on_a_reverted_claude_md_becomes_a_user_only_ask_when_the_coder_also_changed_another_file(self):
        completed = self.run_script({
            "code-reviewer": [{"result": self.CLAUDE_MD_FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "CLAUDE.md": "# Rules\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assert_one_user_only_ask_on_claude_md(packet)
        self.assertEqual(len(packet["dropped_asks"]), 1, packet["dropped_asks"])
        self.assertIn(review_loop_findings.REVERTED_APPROVAL_EDIT_REASON, packet["dropped_asks"][0])

    def test_a_finding_on_a_reverted_claude_md_is_a_user_only_ask_not_skipped_when_it_was_the_only_edit(self):
        completed = self.run_script({
            "code-reviewer": [{"result": self.CLAUDE_MD_FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"CLAUDE.md": "# Rules\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assert_one_user_only_ask_on_claude_md(packet)

    def test_a_coder_created_agents_md_file_is_removed_and_reported_as_a_dropped_ask(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "AGENTS.md": "# Rules\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assert_reverted_and_reported(packet, "AGENTS.md")

    def test_a_coder_that_dies_after_editing_a_claude_md_file_still_reports_the_reverted_edit(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Prompt is too long", "edits": {"CLAUDE.md": "# Rules\n"}, "exit": 1}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assert_reverted_and_reported(packet, "CLAUDE.md")
        self.assertNotIn("CLAUDE.md", packet["files_touched"])

    def test_the_blocker_of_a_failed_coder_call_names_no_path_that_was_reverted(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Prompt is too long", "edits": {"CLAUDE.md": "# Rules\n"}, "exit": 1}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertNotIn("CLAUDE.md", packet["blockers"][0])
        self.assertIn("Prompt is too long", packet["blockers"][0])

    def test_a_claude_md_file_edited_in_two_rounds_is_reported_once(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "CLAUDE.md": "# Rules\n"}},
                      {"result": "Fixed 1.", "edits": {"CLAUDE.md": "# Rules 2\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assert_reverted_and_reported(packet, "CLAUDE.md")

    def test_a_coder_edit_to_a_claude_md_file_the_user_accepted_the_ask_for_files_no_new_ask(self):
        ask_text = accepted_approval_ask_text("CLAUDE.md")
        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "CLAUDE.md": "# Rules\n"}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header(ask_text) + self.USER_RULED_HEADER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])

    def test_a_session_accepted_approval_ask_whose_fix_run_reverts_claude_md_files_no_new_ask(self):
        ask_text = accepted_approval_ask_text("CLAUDE.md")
        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"CLAUDE.md": "# Reverted\n"}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header(ask_text) + "session-ruled: 1\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])

    def test_a_coder_edit_to_a_file_that_only_ends_in_claude_md_files_no_ask(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "NOT_CLAUDE.md": "# Notes\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])

    def test_a_coders_own_skip_line_beats_the_re_ask_text_for_a_user_ruled_finding(self):
        report = ('SKIPPED 1: the limit is meant to be 5\n'
                  'OPEN QUESTIONS: ["app.py:2 should the limit be denied instead?"]')
        completed = self.run_script({
            "coder": [{"result": report, "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:2 Proposed change: deny the limit") + self.USER_RULED_HEADER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        reason = packet["skipped_fp"][0]["reason"]
        self.assertIn("the limit is meant to be 5", reason)
        self.assertNotIn("re-asked", reason)

    def test_a_fix_first_finding_the_user_did_not_rule_on_stays_fixed_when_open_questions_name_it(self):
        report = 'Reworded the message.\nOPEN QUESTIONS: ["app.py:2 should the limit be denied instead?"]'
        completed = self.run_script({
            "coder": [{"result": report, "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:2 Proposed change: deny the limit"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual([entry["finding"] for entry in packet["fixed"]], ["app.py:2 Proposed change: deny the limit"])

    def test_a_fix_first_run_marks_a_no_change_skip_as_given_in_the_packet(self):
        completed = self.run_script({
            "coder": [{"result": "Fixed 1."}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:2 the limit is wrong for `limit`"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], ["the coder made no change"])
        self.assertEqual([entry.get("given") for entry in packet["skipped_fp"]], [True])

    def test_a_fix_first_run_rejects_a_blank_finding_text(self):
        completed = self.run_script({}, header_extra=self.findings_header("a.py:1 - x", " "))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("expected a JSON list of non-empty finding texts", completed.stderr + completed.stdout)

    def test_a_fix_first_run_with_no_review_calls_no_reviewer(self):
        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header("app.py:2 the limit is wrong") + "no-review: yes\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        keys = [call["key"] for call in self.fake_calls()]
        self.assertIn("coder", keys)
        self.assertNotIn("code-reviewer", keys)

    def test_a_base_line_reviews_the_commits_since_that_ref(self):
        base = git(self.repo, "rev-parse", "HEAD")
        self.commit_files({"app.py": APP_AFTER_EDIT})
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}], "closure": [{"result": CLOSED}]},
                                    header_extra=f"base: {base}\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        reviews = [call for call in self.fake_calls() if call["key"] == "code-reviewer"]
        self.assertEqual(len(reviews), 1)
        self.assertIn(f"Review every change since {base}", reviews[0]["prompt"])
        self.assertIn("app.py", reviews[0]["prompt"])

    def test_a_fix_the_coder_commits_on_a_clean_tree_counts_as_fixed_and_is_reviewed(self):
        base = git(self.repo, "rev-parse", "HEAD")
        self.commit_files({"app.py": APP_AFTER_EDIT})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "commit_all": True}],
            "closure": [{"result": CLOSED}],
        }, header_extra=f"base: {base}\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s"), "mid-loop")
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["iter"]), ("converged", 2))
        self.assertEqual([entry["file_line"] for entry in packet["fixed"]], ["app.py:2"])
        self.assertEqual(packet["skipped_fp"], [])
        reviews = [call for call in self.fake_calls() if call["key"] == "code-reviewer"]
        self.assertEqual(len(reviews), 2)
        self.assertIn("+limit = 20", reviews[1]["prompt"] + self.round_fix_diff_text())

    def test_a_fix_the_coder_commits_on_a_dirty_tree_is_reviewed_as_its_own_diff(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "commit_all": True}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["iter"]), ("converged", 2))
        self.assertEqual([entry["file_line"] for entry in packet["fixed"]], ["app.py:2"])
        reviews = [call for call in self.fake_calls() if call["key"] == "code-reviewer"]
        self.assertEqual(len(reviews), 2)
        self.assertIn("app.py", reviews[1]["prompt"])
        fix_diff = self.round_fix_diff_text()
        self.assertIn("+limit = 20", fix_diff)
        self.assertNotIn("-limit = 1\n", fix_diff)

    def round_fix_diff_text(self):
        """The text of every round fix diff the loop wrote under its run folder."""
        diffs = sorted(self.state_dir.rglob("round*-fix.diff"))
        return "\n".join(diff.read_text() for diff in diffs)

    def test_a_files_line_scopes_the_review_to_those_files(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}], "closure": [{"result": CLOSED}]},
                                    header_extra="files: notes.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        reviews = [call for call in self.fake_calls() if call["key"] == "code-reviewer"]
        self.assertEqual(len(reviews), 1)
        self.assertIn("owned files:\n    - notes.py\nYour scope", reviews[0]["prompt"])

    def test_a_files_line_holds_every_other_dirty_file_from_the_fix_coder(self):
        """notes.py holds another session's uncommitted edit; the reviewer flags it and the coder edits each file
        its issues name."""
        theirs = "value = {'a': 1, 'b': 3}  # another session's edit\n"
        (self.repo / "notes.py").write_text(theirs)
        review = FIX_REVIEW.replace("## Ask", "- `notes.py:1` the keys are out of order\n\n## Ask", 1)
        completed = self.run_script({
            "code-reviewer": [{"result": review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits_when_named": {"app.py": APP_FIXED, "notes.py": NOTES_REFLOWED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_bytes(), theirs.encode())
        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED)
        reviews = [call for call in self.fake_calls() if call["key"] == "code-reviewer"]
        self.assertTrue(reviews)
        for review_call in reviews:
            self.assertNotIn("notes.py", review_call["prompt"])
        coder = next(call for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("Never edit these files: another session holds uncommitted edits in them. When an issue needs "
                      "one of them, skip it and say so: notes.py", coder["prompt"])
        self.assertNotIn("notes.py", coder["prompt"].partition("Files in scope: ")[2].splitlines()[0])
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["files_touched"]), ("converged", ["app.py"]))
        self.assertEqual([entry["file_line"] for entry in packet["held_unfixed"]], ["notes.py:1"])
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(packet["tool_fault"], "")

    def test_a_held_files_line_with_no_files_line_keeps_that_file_out_of_the_review_and_the_fix(self):
        """A /code phase passes no files line: it names the files dirty before the phase as held."""
        theirs = "value = {'a': 1, 'b': 3}  # another session's edit\n"
        (self.repo / "notes.py").write_text(theirs)
        review = FIX_REVIEW.replace("## Ask", "- `notes.py:1` the keys are out of order\n\n## Ask", 1)
        completed = self.run_script({
            "code-reviewer": [{"result": review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits_when_named": {"app.py": APP_FIXED, "notes.py": NOTES_REFLOWED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra="held files: notes.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_bytes(), theirs.encode())
        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED)
        reviews = [call for call in self.fake_calls() if call["key"] == "code-reviewer"]
        self.assertTrue(reviews)
        for review_call in reviews:
            self.assertNotIn("notes.py", review_call["prompt"])
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["files_touched"]), ("converged", ["app.py"]))
        self.assertEqual([entry["file_line"] for entry in packet["held_unfixed"]], ["notes.py:1"])
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]],
                         ["held by the caller: named held by the caller"])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_held_file_that_changes_during_the_coder_call_is_left_and_named_in_the_hand_back(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        later = "value = {'a': 1, 'b': 4}  # the other session's edit made during the coder call\n"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "outside_edits": {"notes.py": later}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), later)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["files_touched"]), ("converged", ["app.py"]))
        self.assertIn("the loop left them as they are, so check them: notes.py", packet["tool_fault"])
        rendered = handback.render(packet, "review")
        self.assertIn("Tool fault: held files changed while coder1 ran", rendered)
        self.assertIn("notes.py", rendered)

    def test_a_held_file_that_changes_during_a_failed_coder_call_is_left_and_named_in_the_hand_back(self):
        theirs = "value = {'a': 1, 'b': 3}  # another session's edit\n"
        (self.repo / "notes.py").write_text(theirs)
        later = "value = {'a': 1, 'b': 4}  # the other session's edit made during the coder call\n"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "boom", "exit": 1, "outside_edits": {"notes.py": later}}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), later)
        _row, packet = self.stored_packet()
        self.assertIn("boom", packet["blockers"][0])
        self.assertEqual(len(packet["findings_remaining"]), 1)
        self.assertIn("held files changed while coder1 ran", packet["tool_fault"])
        self.assertIn("notes.py", packet["tool_fault"])

    def test_a_finding_that_names_a_held_file_by_absolute_path_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_review = (f"## Fix\n- `{self.repo / 'notes.py'}:1` the keys are out of order\n\n## Ask\nNone\n\n"
                       "## Nit\nNone\n")
        completed = self.run_script({
            "code-reviewer": [{"result": held_review}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_finding_on_a_held_file_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_review = "## Fix\n- `notes.py:1` the keys are out of order\n\n## Ask\nNone\n\n## Nit\nNone\n"
        completed = self.run_script({
            "code-reviewer": [{"result": held_review}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_finding_on_a_file_with_no_named_holder_is_sent_to_the_coder_not_held_unfixed(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # edited, no session proven\n")
        review = "## Fix\n- `notes.py:1` the keys are out of order\n\n## Ask\nNone\n\n## Nit\nNone\n"
        completed = self.run_script({
            "code-reviewer": [{"result": review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"notes.py": "value = {'a': 1, 'b': 2}\n"}}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coders = [call for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coders), 1)
        self.assertIn("the keys are out of order", coders[0]["prompt"])
        self.assertNotIn(review_loop_prompts.HELD_FILES_RULE, coders[0]["prompt"])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["held_unfixed"], [])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(len(packet["fixed"]), 1)

    def test_a_held_finding_beside_a_real_one_is_skipped_and_only_the_real_one_is_fixed(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        mixed = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n- `notes.py:1` the keys are out of order\n\n"
                 "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")
        completed = self.run_script({
            "code-reviewer": [{"result": mixed}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(packet["held_unfixed"][0]["file_line"], "notes.py:1")
        self.assertEqual([entry["file_line"] for entry in packet["fixed"]], ["app.py:2"])
        coder = next(call for call in self.fake_calls() if call["key"] == "coder")
        self.assertNotIn("keys are out of order", coder["prompt"])

    def test_a_plan_routed_design_decision_on_a_held_file_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_design = ("## Fix\n- `notes.py:1` [design-decision] plan-impact: the owner moves to a new table\n\n"
                       "## Ask\nNone\n\n## Nit\nNone\n")
        completed = self.run_script({
            "code-reviewer": [{"result": held_design}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_plan_ask_on_a_held_file_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_ask = ("## Fix\nNone\n\n## Ask\n- `notes.py:1` [plan-drift] "
                    f"{PLAN_CHANGE_STATUS}: the owner moves to a new table; acceptance_criteria: none\n\n"
                    "## Nit\nNone\n")
        completed = self.run_script({
            "code-reviewer": [{"result": held_ask}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(packet["plan_impacts"], [])

    def test_a_tail_path_that_an_owned_file_and_a_held_file_share_reaches_the_coder(self):
        (self.repo / "pkg/deep").mkdir(parents=True)
        (self.repo / "sub/deep").mkdir(parents=True)
        self.commit_files({"pkg/deep/lib.py": "a = 1\n", "sub/deep/lib.py": "b = 1\n"})
        (self.repo / "pkg/deep/lib.py").write_text("a = 2\n")
        (self.repo / "sub/deep/lib.py").write_text("b = 2  # another session's edit\n")
        tail_review = "## Fix\n- `deep/lib.py:1` the value is wrong\n\n## Ask\nNone\n\n## Nit\nNone\n"
        completed = self.run_script({
            "code-reviewer": [{"result": tail_review}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py, pkg/deep/lib.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coder = next(call for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("the value is wrong", coder["prompt"])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_tail_path_of_a_file_the_coder_created_and_a_held_file_reaches_the_coder_in_a_later_round(self):
        (self.repo / "pkg/deep").mkdir(parents=True)
        (self.repo / "sub/deep").mkdir(parents=True)
        self.commit_files({"sub/deep/lib.py": "b = 1\n"})
        (self.repo / "sub/deep/lib.py").write_text("b = 2  # another session's edit\n")
        app_review = "## Fix\n- `app.py:2` the limit is wrong for `limit`\n\n## Ask\nNone\n\n## Nit\nNone\n"
        tail_review = "## Fix\n- `deep/lib.py:1` the value is wrong\n\n## Ask\nNone\n\n## Nit\nNone\n"
        completed = self.run_script({
            "code-reviewer": [{"result": app_review}, {"result": tail_review}, {"result": CLEAN_REVIEW},
                              {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "pkg/deep/lib.py": "a = 1\n"}},
                      {"result": "Fixed 1.", "edits": {"pkg/deep/lib.py": "a = 2\n"}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coders = [call for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coders), 2)
        self.assertIn("the value is wrong", coders[1]["prompt"])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_design_ask_on_a_held_file_is_skipped_and_never_reaches_the_packet_asks(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_ask = ("## Fix\nNone\n\n## Ask\n- `notes.py:1` [design] should the keys be sorted? "
                    "Proposed change: sort them\n\n## Nit\nNone\n")
        completed = self.run_script({
            "code-reviewer": [{"result": held_ask}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_given_finding_on_a_held_file_is_skipped_and_no_coder_runs(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD + self.findings_header("notes.py:1 the keys are out of order"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["held_unfixed"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_given_finding_on_a_held_file_stays_a_plain_skip_in_the_packet(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD + self.findings_header("notes.py:1 the keys are out of order"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual([entry.get("given") for entry in packet["held_unfixed"]], [None])

    def test_a_class_member_open_in_a_held_file_is_only_skipped_and_no_class_coder_runs(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        open_member = "`notes.py:1` the same limit is wrong here too"
        closure = json.dumps({"receipt": "one member still open", "open": [open_member]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": closure}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder-class"], [])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["open_classes"], [])
        self.assertEqual([(entry["file_line"], entry["reason"]) for entry in packet["held_unfixed"]],
                         [("notes.py:1", HELD_FILE_REASON)])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertIn("held by another session", packet["class_closure"])
        self.assertIn("notes.py:1", packet["class_closure"])
        self.assertNotIn("one member still open", packet["class_closure"])

    def assert_packet_carries_the_member_left_alone(self, closure, class_coder, branch_text=None):
        left_alone = "`log.py:2` prints the limit, not a bound"
        closure_reply = json.dumps({**closure, "left_alone": [left_alone]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, *class_coder],
            "closure": [{"result": closure_reply}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["left_alone"], [left_alone])
        self.assertIn("Left alone, read for another purpose: " + left_alone, handback.render(packet, "review"))
        self.assertNotIn("left alone", packet["class_closure"])
        if branch_text:
            self.assertIn(branch_text, packet["class_closure"])

    def test_a_closed_class_packet_carries_the_members_left_alone(self):
        self.assert_packet_carries_the_member_left_alone({"receipt": "all readers re-read", "open": []}, [])

    def test_an_empty_receipt_with_members_left_alone_still_renders_the_missing_receipt_line(self):
        closure_reply = json.dumps({"receipt": "", "open": [], "left_alone": ["`log.py:2` prints the limit"]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": closure_reply}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertTrue(handback.receipt_is_missing(packet["class_closure"]))
        self.assertEqual(packet["left_alone"], ["`log.py:2` prints the limit"])
        rendered = handback.render(packet, "review")
        self.assertIn("The class-closure receipt is missing", rendered)
        self.assertIn("`log.py:2` prints the limit", rendered)

    def test_a_closed_class_without_left_alone_leaves_no_left_alone_text(self):
        closure_reply = json.dumps({"receipt": "all readers re-read", "open": []})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": closure_reply}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertNotIn("left alone", packet["class_closure"])
        self.assertEqual(packet["left_alone"], [])

    def test_a_still_open_class_packet_carries_the_members_left_alone(self):
        still_open = {"receipt": "one member still open", "open": ["`app.py:4` the same limit is wrong here too"]}
        class_coder = [{"result": "Nothing to change."}]
        self.assert_packet_carries_the_member_left_alone(
            still_open, class_coder, "class members still open, the class repair changed nothing")

    def test_a_held_class_packet_carries_the_members_left_alone(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held = {"receipt": "one member still open", "open": ["`notes.py:1` the same limit is wrong here too"]}
        self.assert_packet_carries_the_member_left_alone(held, [], "none went to a coder")

    def test_a_repaired_class_packet_carries_the_members_left_alone(self):
        repaired = {"receipt": "one member still open", "open": ["`app.py:4` the same limit is wrong here too"]}
        class_coder = [{"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT}}]
        self.assert_packet_carries_the_member_left_alone(
            repaired, class_coder, "the class repair fixed these class members")

    def test_a_held_class_member_beside_a_sendable_one_is_named_apart_from_the_fixed_one(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_member = "`notes.py:1` the same limit is wrong here too"
        sent_member = "`app.py:4` the same limit is wrong here too"
        closure = json.dumps({"receipt": "two members still open", "open": [held_member, sent_member]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": closure}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        fixed_part, _sep, held_part = packet["class_closure"].partition("; skipped, held by another session: ")
        self.assertIn("the class repair fixed these class members", fixed_part)
        self.assertNotIn("every", packet["class_closure"])
        self.assertIn(sent_member, fixed_part)
        self.assertNotIn(held_member, fixed_part)
        self.assertIn(held_member, held_part)

    def test_a_class_repair_that_changes_nothing_keeps_the_sendable_member_open_and_names_the_held_one(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_member = "`notes.py:1` the same limit is wrong here too"
        sent_member = "`app.py:4` the same limit is wrong here too"
        closure = json.dumps({"receipt": "two members still open", "open": [held_member, sent_member]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Nothing to change."}],
            "closure": [{"result": closure}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["open_classes"], [sent_member])
        _open_part, _sep, held_part = packet["class_closure"].partition("; skipped, held by another session: ")
        self.assertIn(held_member, held_part)
        self.assertTrue(
            packet["class_closure"].startswith("class members still open, the class repair changed nothing"))

    def test_a_class_member_whose_repair_was_a_reverted_claude_md_edit_is_a_user_only_ask_never_open(self):
        member = "`CLAUDE.md:1` the same limit is wrong here too"
        closure = json.dumps({"receipt": "one member still open", "open": [member]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 1.", "edits": {"CLAUDE.md": "# Rules\n"}}],
            "closure": [{"result": closure}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["open_classes"], [], "the reverted member is a user-only ask, not an open class")
        self.assertEqual([(entry["file_line"], entry.get("user_only")) for entry in packet["ask"]],
                         [("CLAUDE.md:1", True)])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual(len(packet["fixed"]), 1, "only the app.py finding is fixed")
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), "Quality check: `true`\n")
        self.assertEqual(
            packet["class_closure"],
            "the class repair fixed none of the class members the closure check found open"
            "; filed as a user-only ask unless it repeats one the session rejected, their fix was an approval-only "
            "edit the loop reverted: " + member)

    def test_a_class_repair_that_changes_other_files_but_reverts_every_member_claims_no_fix(self):
        member = "`CLAUDE.md:1` the same limit is wrong here too"
        closure = json.dumps({"receipt": "one member still open", "open": [member]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED + "# again\n", "CLAUDE.md": "# Rules\n"}}],
            "closure": [{"result": closure}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["open_classes"], [], "the reverted member is a user-only ask, not an open class")
        self.assertTrue(packet["class_closure"].startswith("the class repair fixed none of the class members"),
                        packet["class_closure"])
        self.assertIn("filed as a user-only ask unless it repeats one the session rejected, their fix was an "
                      "approval-only edit the loop reverted: " + member, packet["class_closure"])
        self.assertNotIn("fixed these class members", packet["class_closure"])

    def test_a_gate_or_lint_repair_that_only_reverted_a_claude_md_edit_leaves_its_finding_to_the_user_ask(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        on_claude_md = finding_record.parse_finding("`CLAUDE.md:1` the rule is wrong")
        on_code = finding_record.parse_finding("`app.py:2` the limit is wrong")

        first = loop.mark_repaired([on_claude_md, on_code], ["app.py"], ["CLAUDE.md"])
        second = loop.mark_repaired([on_claude_md], [], ["CLAUDE.md"])

        self.assertEqual(first, [on_claude_md], "handed back for the user-only ask")
        self.assertEqual(second, [on_claude_md])
        self.assertEqual(loop.open_fixes, [], "an ask, never an open fix")
        self.assertEqual(loop.fixed, [on_code])
        self.assertEqual(loop.skipped_fp, [])

    def test_a_class_repair_that_changes_one_member_and_reverts_another_names_both_outcomes(self):
        reverted_member = "`CLAUDE.md:1` the same limit is wrong here too"
        fixed_member = "`app.py:4` the same limit is wrong here too"
        closure = json.dumps({"receipt": "two members open", "open": [fixed_member, reverted_member]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_FIXED + "# again\n", "CLAUDE.md": "# Rules\n"}}],
            "closure": [{"result": closure}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["open_classes"], [], "the reverted member is a user-only ask, not an open class")
        self.assertTrue(packet["class_closure"].endswith(
            "filed as a user-only ask unless it repeats one the session rejected, their fix was an approval-only "
            "edit the loop reverted: " + reverted_member),
            packet["class_closure"])
        fixed_lines = [item["file_line"] for item in packet["fixed"]]
        self.assertNotIn("CLAUDE.md:1", fixed_lines)
        self.assertEqual(fixed_lines, ["app.py:2", "app.py:4"])

    def test_a_prose_repair_that_only_reverted_a_claude_md_edit_leaves_its_finding_to_the_user_ask(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        on_claude_md = finding_record.parse_finding("`CLAUDE.md:1` the rule is wrong")

        reverted_findings = loop.mark_repaired([on_claude_md], [], ["CLAUDE.md"], records_skip=False)

        self.assertEqual(reverted_findings, [on_claude_md])
        self.assertEqual(loop.open_fixes, [])
        self.assertEqual(loop.fixed, [])
        self.assertEqual(loop.skipped_fp, [])

    def test_record_skips_leaves_a_reverted_finding_the_coder_skipped_out_of_the_skipped_list(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        on_claude_md = finding_record.parse_finding("`CLAUDE.md:1` the rule is wrong")
        on_app = finding_record.parse_finding("`app.py:2` the limit is wrong")
        skips = {1: "Skipped 1: not needed", 2: "Skipped 2: not needed"}

        skipped, open_fixes = loop.record_skips([on_claude_md, on_app], skips, ["app.py"], False, [on_claude_md])

        self.assertEqual(skipped, [on_app], "a reverted finding is excluded from the list the second round plans on")
        self.assertEqual(open_fixes, [])
        self.assertEqual([entry["item"] for entry in loop.skipped_fp], [on_app])

    def test_record_skips_keeps_a_reverted_finding_out_of_every_list_with_no_change_and_with_a_plan_held(self):
        cases = [
            ("a pass that changed nothing", [], False, [], [{"item": "app"}]),
            ("a plan impact held", ["app.py"], True, ["app"], []),
        ]
        for label, changed, plan_held, expected_open, expected_fp in cases:
            with self.subTest(label):
                loop_script = self.load_script_module()
                loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
                on_claude_md = finding_record.parse_finding("`CLAUDE.md:1` the rule is wrong")
                on_app = finding_record.parse_finding("`app.py:2` the limit is wrong")
                skips = {1: "Skipped 1: not needed", 2: "Skipped 2: not needed"}

                skipped, open_fixes = loop.record_skips([on_claude_md, on_app], skips, changed, plan_held,
                                                        [on_claude_md])

                self.assertEqual(skipped, [on_app], f"{label}: the reverted finding is not in the skipped list")
                self.assertEqual(open_fixes, [on_app] if expected_open else [], f"{label}: open fixes")
                skipped_items = [entry["item"] for entry in loop.skipped_fp]
                self.assertEqual(skipped_items, [on_app] if expected_fp else [], f"{label}: skipped_fp")

    def test_the_gate_and_lint_repairs_pass_the_reverted_paths_to_mark_repaired(self):
        reverted_result = review_loop_coder.CoderResult("", [], ["c.py"], ["CLAUDE.md"])
        loop_script = self.load_script_module()
        gate = loop_script.full_check_gate
        problem = [("ruff check app.py", "app.py:1:1: N802 bad name")]

        lint_loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        with mock.patch.object(gate.format_files, "lint_problems", side_effect=[problem, []]), \
                mock.patch.object(loop_script.format_files, "run_formatters", return_value=[]), \
                mock.patch.object(lint_loop, "review_scope", return_value=["a.py"]), \
                mock.patch.object(lint_loop, "repair", return_value=reverted_result), \
                mock.patch.object(lint_loop, "mark_repaired") as lint_marked, \
                mock.patch.object(lint_loop, "run_check", return_value=""):
            lint_loop.full_check_pass("true")
        self.assertEqual(lint_marked.call_args.args[2:], (["CLAUDE.md"],), "the lint repair")

        gate_loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})

        def failing_check(_command):
            gate_loop.full_check = "failed (exit 1)"
            return "boom"

        with mock.patch.object(gate.format_files, "lint_problems", return_value=[]), \
                mock.patch.object(gate_loop, "review_scope", return_value=["a.py"]), \
                mock.patch.object(gate_loop, "repair", return_value=reverted_result), \
                mock.patch.object(gate_loop, "mark_repaired") as gate_marked, \
                mock.patch.object(gate_loop, "recheck_full_check"), \
                mock.patch.object(gate_loop, "run_check", side_effect=failing_check):
            gate_loop.full_check_pass("true")
        self.assertEqual(gate_marked.call_args.args[2:], (["CLAUDE.md"],), "the gate repair")

    def test_a_finding_on_a_reverted_claude_md_over_two_rounds_files_one_user_only_ask(self):
        completed = self.run_script({
            "code-reviewer": [{"result": self.CLAUDE_MD_FIX_REVIEW}, {"result": self.CLAUDE_MD_FIX_REVIEW},
                              {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"CLAUDE.md": "# Rules\n"}},
                      {"result": "Fixed 1.", "edits": {"CLAUDE.md": "# Rules two\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assert_one_user_only_ask_on_claude_md(packet)
        reviewer_calls = [call for call in self.fake_calls() if call["key"] == "code-reviewer"]
        self.assertEqual(len(reviewer_calls), 1, "a reverted file does not send a second-round reviewer back to it")

    def coder_models_of_a_fix_run(self, header_extra):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=header_extra)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        return [call["model"] for call in self.fake_calls() if call["key"] == "coder"]

    def test_a_coder_model_line_runs_the_fix_coder_on_that_model(self):
        self.assertEqual(self.coder_models_of_a_fix_run("coder-model: haiku\n"), ["haiku"])

    def test_no_coder_model_line_leaves_the_fix_coder_on_its_agents_own_model(self):
        self.assertEqual(self.coder_models_of_a_fix_run(""), [None])

    def test_a_nit_on_a_held_file_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        nit_review = FIX_REVIEW.replace("## Nit\nNone", "## Nit\n- `notes.py:1` rename the value")
        completed = self.run_script({
            "code-reviewer": [{"result": nit_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coder_calls = [call for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coder_calls), 1)
        self.assertNotIn("notes.py", coder_calls[0]["prompt"].partition("Files in scope: ")[2].splitlines()[0])
        self.assertNotIn("rename the value", coder_calls[0]["prompt"])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual([entry["file_line"] for entry in packet["nit"]], ["notes.py:1"])

    def test_the_same_held_nit_in_two_rounds_is_kept_once_and_tallied_once(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        nit_text = "## Nit\n- `notes.py:1` rename the value"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW.replace("## Nit\nNone", nit_text)},
                              {"result": CLEAN_REVIEW.replace("## Nit\nNone", nit_text)}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual([entry["file_line"] for entry in packet["nit"]], ["notes.py:1"])
        metrics = fake_ledger.recorded_rows(self.env, "review_metrics")
        self.assertEqual(metrics[0]["nit"], "1")

    def test_an_iter_line_counts_the_rounds_an_earlier_run_used(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}], "closure": [{"result": CLOSED}]},
                                    header_extra="iter: 1\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["iter"], 2)

    def test_a_reviewer_model_line_names_the_model_on_each_main_session_request(self):
        (self.fake_dir / "scenario.json").write_text(json.dumps({"closure": [{"result": CLOSED}]}))
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text("reviewer-model: haiku\n"))
        process = subprocess.Popen([*self.script_command(prompt), "--reviewers", "main"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=self.env)
        self.addCleanup(process.kill)

        requests = self.answer_round(1, CLEAN_REVIEW, process)
        _stdout, stderr = process.communicate(timeout=120)

        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual([request["model"] for request in requests], ["haiku"])

    def test_a_finding_open_after_round_two_dispatches_no_third_round(self):
        (self.fake_dir / "scenario.json").write_text(json.dumps({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}] * 3,
            "closure": [{"result": CLOSED}] * 3,
        }))
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text())
        process = subprocess.Popen([*self.script_command(prompt), "--reviewers", "main"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=self.env)
        self.addCleanup(process.kill)

        self.answer_round(1, FIX_REVIEW, process)
        self.answer_round(2, FIX_REVIEW, process)
        _stdout, stderr = process.communicate(timeout=120)

        self.assertEqual(process.returncode, 0, stderr)
        requests_dir = self.state_dir / "loop-script" / AGENT_ID / "reviewer-requests"
        self.assertEqual(sorted(manifest.name for manifest in requests_dir.glob("round-*.json")),
                         ["round-1.json", "round-2.json"])
        runs = fake_ledger.recorded_rows(self.env, "review_run")
        self.assertEqual(len(runs), 2)

    def test_a_review_prompt_with_no_phase_logs_a_standalone_scope(self):
        self.prompt_file_text = lambda header_extra="", footer="": (
            "mode: review-first\ncaller: review\nlane: none\n\nhandoff:\n  files:\n    - path: app.py\n")
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        runs = fake_ledger.recorded_rows(self.env, "review_run")
        self.assertEqual([run["scope"] for run in runs], ["standalone"])
        scope_rows = fake_ledger.recorded_rows(self.env, "review_scope")
        self.assertEqual([row["caller"] for row in scope_rows], ["review"])

    def test_a_code_prompt_with_no_phase_logs_a_phase_scope(self):
        self.prompt_file_text = lambda header_extra="", footer="": (
            "mode: review-first\ncaller: code\nlane: code\n\nhandoff:\n  files:\n    - path: app.py\n")
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        runs = fake_ledger.recorded_rows(self.env, "review_run")
        self.assertEqual([run["scope"] for run in runs], ["phase"])

    def start_with_a_twelve_line_change(self):
        added = "".join(f"mechanism = {number}\n" for number in range(12))
        (self.repo / "app.py").write_text(APP_BEFORE + added)
        return added

    def test_a_fix_coder_that_removes_the_mechanism_the_change_added_stops_the_loop(self):
        self.start_with_a_twelve_line_change()
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_BEFORE}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], handback.FIX_REMOVED_CHANGE)
        self.assertEqual(["the fix passes removed 12 of the 12 source lines the change under review adds; "
                          "most lost in app.py (12)"], packet["blockers"])
        keys = [call["key"] for call in self.fake_calls()]
        self.assertNotIn("closure", keys)
        self.assertEqual(1, keys.count("code-reviewer"))
        self.assertEqual("", packet["scoped_tests"])
        self.assertEqual(packet["files_touched"], ["app.py"])

    def test_a_commit_of_the_change_while_reviewers_run_does_not_read_as_a_fix_that_removed_it(self):
        added = self.start_with_a_twelve_line_change()
        fixed = APP_BEFORE + added.replace("mechanism = 0", "mechanism = 100")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW, "commit_all": True}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": fixed}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s"), "mid-loop")
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))

    def test_a_fix_coder_that_deletes_an_untracked_file_it_did_not_make_finds_it_restored_and_noted(self):
        scratch = self.repo / "scratch.txt"
        scratch.write_text("select 1;\n")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}] * 2 + [{"result": CLEAN_REVIEW}] * 2,
            "smell-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "deletes": [str(scratch)]}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(scratch.read_text(), "select 1;\n")
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertIn("scratch.txt", packet["tool_fault"])
        self.assertIn("restored", packet["tool_fault"])

    def test_a_held_untracked_file_the_coder_deletes_is_put_back_too(self):
        held_file = self.repo / "held_scratch.txt"
        held_file.write_text("select 1;\n")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "deletes": [str(held_file)]}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n" + f"held-by: {json.dumps([NOTES_HOLDER, SCRATCH_HOLDER])}\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(held_file.read_text(), "select 1;\n")
        _row, packet = self.stored_packet()
        self.assertIn("held_scratch.txt", packet["tool_fault"])
        self.assertIn("restored", packet["tool_fault"])

    def test_a_held_untracked_file_with_no_holder_row_the_coder_deletes_is_put_back(self):
        held_file = self.repo / "held_scratch.txt"
        held_file.write_text("select 1;\n")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "deletes": [str(held_file)]}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(held_file.read_text(), "select 1;\n")
        _row, packet = self.stored_packet()
        self.assertIn("held_scratch.txt", packet["tool_fault"])
        self.assertIn("restored", packet["tool_fault"])

    def test_a_fix_that_moves_the_added_lines_into_a_new_file_converges(self):
        added = self.start_with_a_twelve_line_change()
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_BEFORE, "lib_helper.py": added}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))

    def test_a_fix_that_moves_the_added_lines_into_a_test_file_stops_the_loop(self):
        added = self.start_with_a_twelve_line_change()
        (self.repo / "tests").mkdir()
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_BEFORE, "tests/test_mechanism.py": added}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], handback.FIX_REMOVED_CHANGE)
        self.assertIn("12 of the 12", packet["blockers"][0])

    def test_a_fix_that_edits_half_of_a_renamed_file_it_did_not_add_converges(self):
        original = "".join(f"constant_{number} = {number}\n" for number in range(12))
        self.commit_files({"old_name.py": original})
        (self.repo / "app.py").write_text(APP_BEFORE)
        git(self.repo, "mv", "old_name.py", "new_name.py")
        edited = "".join(f"constant_{number} = {number + 100}\n" if number < 6 else f"constant_{number} = {number}\n"
                         for number in range(12))
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"new_name.py": edited}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))

    def test_a_fix_that_cuts_most_of_a_file_moved_with_a_plain_mv_stops_the_loop(self):
        original = "".join(f"constant_{number} = {number}\n" for number in range(24))
        self.commit_files({"old_name.py": original})
        (self.repo / "app.py").write_text(APP_BEFORE)
        (self.repo / "old_name.py").rename(self.repo / "new_name.py")
        trimmed = "".join(f"constant_{number} = {number}\n" for number in range(8))
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "smell-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"new_name.py": trimmed}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], handback.FIX_REMOVED_CHANGE)
        self.assertIn("16 of the 24", packet["blockers"][0])

    def test_a_fix_that_renames_a_file_and_removes_the_added_lines_elsewhere_stops_the_loop(self):
        self.start_with_a_twelve_line_change()
        original = "".join(f"constant_{number} = {number}\n" for number in range(12))
        self.commit_files({"old_name.py": original})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "renames": {"old_name.py": "new_name.py"},
                       "edits": {"app.py": APP_BEFORE}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], handback.FIX_REMOVED_CHANGE)
        self.assertIn("12 of the 12", packet["blockers"][0])

    def test_a_fix_that_edits_a_few_of_the_added_lines_still_converges(self):
        added = self.start_with_a_twelve_line_change()
        fixed = APP_BEFORE + added.replace("mechanism = 0", "mechanism = 100").replace("mechanism = 1\n",
                                                                                         "mechanism = 101\n")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": fixed}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))

    def test_a_class_coder_that_removes_the_mechanism_the_change_added_stops_the_loop(self):
        added = self.start_with_a_twelve_line_change()
        closure = json.dumps({"receipt": "one member still open", "open": ["`app.py:4` the same limit is wrong here"]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_BEFORE + added.replace("mechanism = 0",
                                                                                            "mechanism = 100")}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_BEFORE}}],
            "closure": [{"result": closure}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], handback.FIX_REMOVED_CHANGE)
        self.assertIn("12 of the 12", packet["blockers"][0])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 2)

    def test_a_gate_repair_coder_that_removes_the_mechanism_the_change_added_stops_the_loop(self):
        added = self.start_with_a_twelve_line_change()
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_BEFORE + added, "broken.flag": "x\n"}},
                      {"result": "Repaired.", "edits": {"app.py": APP_BEFORE}}],
            "closure": [{"result": CLOSED}],
        }, quality_check="test ! -f broken.flag")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], handback.FIX_REMOVED_CHANGE)
        self.assertIn("12 of the 12", packet["blockers"][0])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 2)

    def test_a_fix_that_removes_added_test_lines_does_not_count_as_removing_the_change(self):
        added = "".join(f"def test_case_{number}(): pass\n" for number in range(12))
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_app.py").write_text(added)
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}] * 2 + [{"result": CLEAN_REVIEW}] * 2,
            "coder": [{"result": "Fixed 1.", "edits": {"tests/test_app.py": ""}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))

    def test_a_fix_that_empties_an_untracked_new_file_the_change_added_stops_the_loop(self):
        (self.repo / "feature.py").write_text("".join(f"mechanism = {number}\n" for number in range(12)))
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "smell-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"feature.py": ""}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], handback.FIX_REMOVED_CHANGE)
        self.assertIn("feature.py (12)", packet["blockers"][0])

    def save_gate_commands(self, gate_commands):
        # The gate commands the caller passes with --gate-command.
        self.gate_commands = gate_commands

    def run_with_scoped_tests(self, gate_commands, scenario):
        self.save_gate_commands(gate_commands)
        return self.run_script(scenario)

    def test_a_fix_the_full_check_did_not_verify_reruns_the_scoped_tests_before_the_hand_back(self):
        completed = self.run_with_scoped_tests(["grep -q 'limit = 20' app.py"], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["scoped_tests"], "passed")
        self.assertIn("Scoped tests: passed", handback.render(packet, "review"))

    def test_a_scoped_test_left_red_by_the_last_fix_stops_the_loop(self):
        completed = self.run_with_scoped_tests(["grep -q 'limit = 99' app.py"], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        log_path = self.state_dir / "loop-script" / AGENT_ID / "scoped-tests.log"
        self.assertEqual(packet["scoped_tests"], f"failed: grep -q 'limit = 99' app.py; full output: {log_path}")
        self.assertIn("grep -q 'limit = 99' app.py", packet["blockers"][0])

    def run_clean_review_with_gates(self, gate_commands, every_run, quality_check=None):
        self.gates_every_run = every_run
        return self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}], "closure": [{"result": CLOSED}]},
                               quality_check=quality_check)

    def test_gate_commands_run_on_a_converged_run_with_no_fix_when_the_loop_gates_every_run(self):
        marker = self.scratch / "ran.txt"
        self.save_gate_commands([f"echo ran >> {marker}"])
        completed = self.run_clean_review_with_gates(self.gate_commands, True)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["scoped_tests"], f"passed; counts: echo ran >> {marker}: no runner summary")
        self.assertEqual(marker.read_text(), "ran\n")

    def test_a_red_gate_command_on_a_converged_run_with_no_fix_stops_the_loop_before_credit(self):
        self.save_gate_commands(["echo boom >&2; exit 1"])
        completed = self.run_clean_review_with_gates(self.gate_commands, True)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("boom", packet["blockers"][0])
        self.assertNotIn(packet["status"], handback.CLEAN_STATUSES, "a red gate command must withhold credit")

    def test_a_gate_command_failing_the_same_way_on_head_leaves_a_converged_run_converged(self):
        self.commit_files({"failing.txt": "FAIL: test_old (shop.tests.OldTest)\n"})
        self.save_gate_commands(["cat failing.txt; exit 1"])
        completed = self.run_clean_review_with_gates(self.gate_commands, True)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertTrue(packet["scoped_tests"].startswith("pre-existing failure"), packet["scoped_tests"])

    def test_a_stop_before_the_gate_commands_ran_says_they_did_not_run(self):
        self.save_gate_commands(["echo ran"])
        self.gates_every_run = True
        completed = self.run_script(
            {"code-reviewer": [{"result": CLEAN_REVIEW}]},
            quality_check="echo 'ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND No package.json found'; exit 1")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "setup-fault")
        self.assertEqual(packet["scoped_tests"], "not run: loop stopped as setup-fault before the scoped tests")

    def use_named_tests_budget(self, seconds):
        patcher = mock.patch.object(review_loop_scoped_tests, "NAMED_TESTS_BUDGET_SECONDS", seconds)
        patcher.start()
        self.addCleanup(patcher.stop)

    def loop_main_module(self):
        return self.load_script_module(SCRIPT.parent / "review_loop_main.py")

    def gate_command_request(self, command, gates_every_run, header_extra=""):
        """The review_loop_main module and a LoopRequest that gates on `command`."""
        loop_main = self.loop_main_module()
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text(header_extra))
        header, handoff = loop_main.read_prompt(str(prompt))
        request = loop_main.LoopRequest(str(self.repo), self.scratch, SESSION, header, handoff,
                                        {"fixed": [], "files_touched": set()}, [command],
                                        gates_every_run=gates_every_run)
        return loop_main, request

    def built_loop_for_gate_command(self, command, gates_every_run):
        loop_main, request = self.gate_command_request(command, gates_every_run)
        loop, _check_command = loop_main.build_loop(request)
        return loop

    def test_the_loop_brief_names_the_plan_lines_of_the_phase(self):
        plan = self.repo / "docs" / "plans" / "p" / "spec.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("# Plan\n\n## Phase 1: First\n\none\n")
        loop_main, request = self.gate_command_request(
            "echo scoped", False, header_extra="plan: docs/plans/p/spec.md\nphase: 1\n")

        loop, _check_command = loop_main.build_loop(request)

        self.assertIn("Phase 1 is the `## Phase 1: First` section of the plan, lines 3-5", loop.brief)

    @staticmethod
    def fake_check_run(_repo, _check_command, log, _timeout, _env, _on_start):
        """A check run that exits 0 and leaves an empty log, so no real command starts."""
        pathlib.Path(log).write_text("")
        return 0

    def test_the_loop_narrows_a_discovered_full_check_to_the_parts_the_diff_touches(self):
        self.commit_files({"CLAUDE.md": "", "package.json": '{"scripts": {"lint": "eslint ."}}',
                           "pytest.ini": "[pytest]\naddopts = -q\n"})
        (self.repo / "app.py").write_text(APP_BEFORE)
        (self.repo / "app.js").write_text("1\n")
        loop_main, request = self.gate_command_request("echo scoped", False)

        loop, check_command = loop_main.build_loop(request)
        with mock.patch.object(loop_main.full_check, "run_check_command_retrying_collision",
                               side_effect=self.fake_check_run):
            loop.run_check(check_command)

        self.assertEqual("npm run lint", loop.full_check_command)

    def test_the_loop_runs_a_part_whose_files_the_diff_touches_after_the_loop_was_built(self):
        self.commit_files({"CLAUDE.md": "", "package.json": '{"scripts": {"lint": "eslint ."}}',
                           "pytest.ini": "[pytest]\naddopts = -q\n"})
        (self.repo / "app.py").write_text(APP_BEFORE)
        (self.repo / "app.js").write_text("1\n")
        loop_main, request = self.gate_command_request("echo scoped", False)
        loop, check_command = loop_main.build_loop(request)

        (self.repo / "app.py").write_text(APP_BEFORE + "limit = 6\n")
        with mock.patch.object(loop_main.full_check, "run_check_command_retrying_collision",
                               side_effect=self.fake_check_run):
            loop.run_check(check_command)

        self.assertIn("npm run lint", loop.full_check_command)
        self.assertIn("pytest", loop.full_check_command)

    def test_the_named_tests_budget_stops_a_command_that_cannot_start_when_the_loop_gates_every_run(self):
        marker = self.scratch / "ran.txt"
        command = f"echo ran >> {marker}"
        self.use_named_tests_budget(0)
        loop = self.built_loop_for_gate_command(command, True)

        passed = loop.run_test_commands([command], budgeted=True, stop_when_unrun=True)

        self.assertFalse(marker.exists())
        self.assertTrue(loop.scoped_tests.startswith("not run (time budget used up):"), loop.scoped_tests)
        self.assertFalse(passed)
        self.assertEqual(loop.status, "critical-blocker")

    def test_a_red_named_run_with_no_time_left_does_not_run_the_autofix_formatters(self):
        loop_script = self.load_script_module()
        self.use_named_tests_budget(0)
        loop = self.built_loop_for_gate_command("cmd", True)
        red = loop_script.coder_gate.ScopedRun("failed: cmd", ["tail"], [("cmd", "exit 1", "out")], [], [], False)

        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=red), \
                mock.patch.object(loop, "autofix_touched_files") as autofix:
            passed = loop.run_test_commands(["cmd"], budgeted=True, stop_when_unrun=True)

        self.assertFalse(passed)
        autofix.assert_not_called()

    def test_the_named_tests_budget_does_not_cap_the_post_fix_scoped_run(self):
        marker = self.scratch / "ran.txt"
        command = f"echo ran >> {marker}"
        self.use_named_tests_budget(0)
        loop = self.built_loop_for_gate_command(command, True)

        passed = loop.run_test_commands([command])

        self.assertTrue(passed)
        self.assertEqual(marker.read_text(), "ran\n")

    def test_the_named_tests_budget_does_not_apply_when_the_loop_does_not_gate_every_run(self):
        marker = self.scratch / "ran.txt"
        command = f"echo ran >> {marker}"
        self.use_named_tests_budget(0)
        loop = self.built_loop_for_gate_command(command, False)

        loop.run_test_commands([command])

        self.assertEqual(marker.read_text(), "ran\n")
        self.assertEqual(loop.scoped_tests, "passed")

    def test_the_review_scope_leaves_out_the_plan_folder_unless_the_caller_names_its_files(self):
        loop_script = self.load_script_module()
        plan = "docs/plans/p/spec.md"
        (self.repo / plan).parent.mkdir(parents=True)
        (self.repo / plan).write_text("# Plan\n")
        (self.repo / "docs/plans/p/research.md").write_text("notes\n")
        progress = {"fixed": [], "files_touched": set()}

        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), progress, plan)
        self.assertEqual(["app.py"], sorted(loop.review_scope()))

        no_plan_loop = loop_script.LoopRun(self.repo, self.scratch, "", (), progress)
        self.assertEqual(["app.py", "docs/plans/p/research.md", plan], sorted(no_plan_loop.review_scope()))

        loop.only_files = [plan]
        self.assertEqual([plan], sorted(loop.review_scope()))

    def test_a_loop_that_does_not_gate_every_run_leaves_the_runner_counts_off_the_line(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        passed_run = loop_script.coder_gate.ScopedRun("passed", [], [], [("cmd", ["2 passed"])], [], False)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=passed_run):
            loop.run_test_commands(["cmd"])

        self.assertEqual(loop.scoped_tests, "passed")

    def test_gate_commands_stay_unrun_on_a_converged_run_with_no_fix_unless_the_loop_gates_every_run(self):
        marker = self.scratch / "ran.txt"
        self.save_gate_commands([f"echo ran >> {marker}"])
        completed = self.run_clean_review_with_gates(self.gate_commands, False)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(marker.exists())

    def stale_prose_command(self, exit_code):
        script = self.scratch / "stale_prose.py"
        script.write_text(STALE_PROSE_STAND_IN)
        return f"python3 {script} {exit_code}"

    def run_with_a_stale_prose_hit(self, prose_coder_reply, test_commands=(), **script_options):
        scenario = {**FIX_THEN_CLEAN, "coder": [*FIX_THEN_CLEAN["coder"], prose_coder_reply]}
        self.save_gate_commands([*test_commands, self.stale_prose_command(1)])
        return self.run_script(scenario, **script_options)

    def test_a_stale_prose_check_stops_the_loop_when_the_script_itself_fails(self):
        completed = self.run_with_scoped_tests([self.stale_prose_command(2)], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("stale-prose check failing", packet["blockers"][0])
        self.assertEqual(1, [call["key"] for call in self.fake_calls()].count("coder"))

    def test_a_stale_prose_check_that_cannot_run_is_named_in_the_scoped_tests_line(self):
        completed = self.run_with_scoped_tests(["grep -q 'limit = 20' app.py", self.stale_prose_command(127)],
                                               FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertIn("stale-prose check setup fault", packet["scoped_tests"])

    def test_a_clean_stale_prose_check_leaves_the_scoped_tests_line_at_passed(self):
        completed = self.run_with_scoped_tests(["grep -q 'limit = 20' app.py", self.stale_prose_command(0)],
                                               FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual("passed", packet["scoped_tests"])

    def test_a_prose_repair_that_breaks_the_full_check_stops_the_loop(self):
        reply = {"result": "Fixed.", "edits": {"broken.flag": "x\n"}}

        completed = self.run_with_a_stale_prose_hit(reply, quality_check="test ! -f broken.flag")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("failing after the stale-prose check repair", packet["blockers"][0])

    def test_a_prose_repair_in_a_ci_repo_is_followed_by_the_scoped_tests(self):
        reply = {"result": "Fixed the claim.", "edits": {"app.py": APP_FIXED + "# corrected claim\n"}}

        completed = self.run_with_a_stale_prose_hit(reply, ["! grep -q 'corrected claim' app.py"],
                                                    claude_md="Quality check: `true`\nFull suite: CI\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("scoped tests failing", packet["blockers"][0])
        self.assertIn("corrected claim", packet["blockers"][0])
        self.assertIn(f"If a test needs an env var the repo's CI sets, add it under {self.repo.name!r} in ",
                      packet["blockers"][0])
        self.assertIn("gate-env.json.", packet["blockers"][0])

    def test_the_scoped_test_stop_hint_names_the_gate_env_file_the_variable_sets(self):
        personal_file = self.scratch / "my-gate-env.json"
        self.env["CLAUDE_GATE_ENV_FILE"] = str(personal_file)

        completed = self.run_with_scoped_tests(["grep -q 'limit = 99' app.py"], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertIn(f"in {personal_file}.", packet["blockers"][0])

    def test_a_stale_prose_hit_the_coder_fixes_converges_and_gets_one_final_read(self):
        reply = {"result": "Fixed the claim.", "edits": {"app.py": APP_FIXED + "# corrected claim\n"}}

        completed = self.run_with_a_stale_prose_hit(reply)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))
        self.assertEqual(2, len(packet["fixed"]))
        self.assertEqual(4, packet["iter"])
        self.assertEqual(4, packet["review_round"])
        self.assertFalse(row["unreviewed_fix"])
        self.assertIn("STALE app.py:1", json.dumps(self.fake_calls()))

    def test_a_stale_prose_hit_whose_claims_hold_converges_with_no_unreviewed_fix(self):
        completed = self.run_with_a_stale_prose_hit({"result": "Every claim still holds."})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))
        self.assertEqual((1, 0), (len(packet["fixed"]), len(packet["skipped_fp"])))
        self.assertEqual(2, packet["iter"])
        self.assertFalse(row["unreviewed_fix"])

    def test_a_packet_with_no_full_check_found_carries_a_tool_fault_and_still_converges(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="Run make ci before you push.\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertIn("no full check ran", packet["tool_fault"])
        self.assertIn("CLAUDE.local.md", packet["tool_fault"])

    def test_a_packet_whose_full_check_timed_out_carries_a_tool_fault_naming_the_faster_command_fix(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.full_check = loop_script.full_check.NOT_RUN_TIMEOUT

        packet = loop.outcome([], [])

        self.assertIn("did not finish", packet["tool_fault"])
        self.assertIn("Quality check (<repo name>)", packet["tool_fault"])
        self.assertIn("CLAUDE.local.md", packet["tool_fault"])

    def test_a_repo_with_a_makefile_check_target_runs_make_check(self):
        (self.repo / "Makefile").write_text("check:\n\t@echo '3 passed in 0.1s'\n")
        git(self.repo, "add", "Makefile")
        git(self.repo, "commit", "-q", "-m", "make")

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="Run make ci before you push.\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual((packet["full_check"], packet["full_check_command"]), ("passed", "make check"))
        self.assertEqual("", packet["tool_fault"])

    def test_a_stale_prose_hit_report_over_the_tail_limit_reaches_the_coder_whole_in_its_issues_file(self):
        script = self.scratch / "stale_prose.py"
        script.write_text("import sys\nprint('HEADER-OF-THE-REPORT')\nprint('x' * 13000)\nprint('LAST-HIT-LINE')\n"
                          "sys.exit(1)\n")
        self.save_gate_commands([f"python3 {script}"])
        scenario = {**FIX_THEN_CLEAN, "coder": [*FIX_THEN_CLEAN["coder"], {"result": "Every claim still holds."}]}

        completed = self.run_script(scenario)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        issues_file = self.state_dir / "loop-script" / AGENT_ID / "coder-briefs" / "coder-prose" / "issues.txt"
        self.assertIn("HEADER-OF-THE-REPORT", json.dumps(self.fake_calls()))
        self.assertIn("LAST-HIT-LINE", issues_file.read_text())

    def test_a_red_scoped_test_stops_the_loop_before_a_stale_prose_hit_reaches_the_coder(self):
        completed = self.run_with_scoped_tests(["grep -q 'limit = 99' app.py", self.stale_prose_command(1)],
                                               FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertNotIn("STALE", packet["blockers"][0])
        self.assertEqual(1, [call["key"] for call in self.fake_calls()].count("coder"))

    def test_a_red_scoped_test_names_the_failing_test_and_its_panic_text_and_keeps_the_full_output(self):
        fixture = pathlib.Path(__file__).resolve().parent / "fixtures" / "cargo_test_failed_assertion.txt"
        # Red only with the diff: the base run on HEAD passes, so the failure is not pre-existing.
        failing_run = f"git diff --quiet HEAD || {{ echo 'early line' && seq 1 3000 && cat {fixture} && false; }}"
        completed = self.run_with_scoped_tests([failing_run], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        log_path = self.state_dir / "loop-script" / AGENT_ID / "scoped-tests.log"
        self.assertIn("early line", log_path.read_text())
        self.assertEqual(f"failed: {failing_run}; failing tests: test tests::x_total ... FAILED | "
                         f"thread 'tests::x_total' (2268265) panicked at src/lib.rs:8:9:; full output: {log_path}",
                         packet["scoped_tests"])
        self.assertIn("  left: 3\n right: 4", packet["blockers"][0])
        self.assertIn(str(log_path), packet["blockers"][0])

    def test_a_scoped_test_that_cannot_run_names_the_log_that_keeps_its_output(self):
        completed = self.run_with_scoped_tests(["echo no runner here && exit 127"], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        log_path = self.state_dir / "loop-script" / AGENT_ID / "scoped-tests.log"
        self.assertIn("no runner here", log_path.read_text())
        self.assertTrue(packet["scoped_tests"].startswith("setup fault: "), packet["scoped_tests"])
        self.assertIn(f"full output: {log_path}", packet["scoped_tests"])

    def test_a_loop_that_made_no_fix_runs_no_scoped_tests(self):
        completed = self.run_with_scoped_tests(["false"], {"code-reviewer": [{"result": CLEAN_REVIEW}],
                                                           "smell-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["scoped_tests"]), ("converged", ""))

    def test_a_fix_with_no_scoped_test_commands_says_why_none_derive(self):
        completed = self.run_with_scoped_tests([], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["scoped_tests"], "not run (no test command derives for the changed files)")

    def test_a_fix_with_no_scoped_test_commands_runs_the_derived_command_of_the_changed_test_file(self):
        (self.repo / "tests").mkdir()
        (self.repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        # A stand-in runner: `python3 -m pytest` run from the repo finds it first.
        runner = "import sys\nprint('argv:', ' '.join(sys.argv[1:]))\nprint('1 passed in 0.01s')\nsys.exit(0)\n"
        self.commit_files({"tests/test_app.py": "def test_one():\n    assert True\n", "pytest.py": runner})
        (self.repo / "tests" / "test_app.py").write_text("def test_one():\n    assert 1 == 1\n")

        clean = [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}]
        scenario = {**FIX_THEN_CLEAN, "test-reviewer": clean, "smell-reviewer": clean,
                    "code-reviewer": [{"result": FIX_REVIEW}, *clean, *clean]}

        completed = self.run_with_scoped_tests([], scenario)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertRegex(packet["scoped_tests"], r"passed.*counts: ")
        self.assertIn("tests/test_app.py", packet["scoped_tests"])

    def test_a_finding_on_a_file_absent_from_the_tree_is_skipped_and_never_sent_to_the_coder(self):
        ghost_review = FIX_REVIEW.replace("app.py:2", "ghost.py:2")

        completed = self.run_script({"code-reviewer": [{"result": ghost_review}],
                                     "smell-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["fixed"]), ("converged", []))
        self.assertEqual(packet["skipped_fp"][0]["file_line"], "ghost.py:2")
        self.assertEqual(packet["skipped_fp"][0]["reason"], "the file is not in the tree")
        self.assertNotIn("coder", [call["key"] for call in self.fake_calls()])

    def test_a_finding_on_an_untracked_file_reaches_the_coder(self):
        (self.repo / "fresh.py").write_text(APP_BEFORE)
        fresh_review = FIX_REVIEW.replace("app.py:2", "fresh.py:2")

        completed = self.run_script({
            "code-reviewer": [{"result": fresh_review}] * 2 + [{"result": CLEAN_REVIEW}] * 2,
            "smell-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {str(self.repo / "fresh.py"): APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["fixed"][0]["file_line"], "fresh.py:2")

    def test_a_fix_the_coder_made_no_change_for_is_skipped_not_listed_as_fixed(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1."}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["fixed"], [])
        self.assertEqual(packet["skipped_fp"][0]["file_line"], "app.py:2")
        self.assertEqual(packet["skipped_fp"][0]["reason"], "the coder made no change")

    def test_a_round_two_fix_diff_over_one_argument_limit_reaches_the_reviewer_whole(self):
        long_fix = "".join(f"limit_{line} = {line}\n" for line in range(12000))

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": long_fix}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["iter"]), ("converged", 2))
        round_two_prompt = [call["prompt"] for call in self.fake_calls() if call["key"] == "code-reviewer"][1]
        diff_path = re.search(r"^Round-one fix diff.*: (\S+)$", round_two_prompt, re.M).group(1)
        fix_diff = pathlib.Path(diff_path).read_text()
        self.assertGreater(len(fix_diff.encode()), 131072)
        self.assertIn("+limit_11999 = 11999", fix_diff)

    def test_untracked_binary_file_does_not_stop_a_clean_review(self):
        (self.repo / "logo.png").write_bytes(b"\x89PNG\xff\xfe\x00")

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}] * 2,
                                     "smell-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")

    def launch_after_dispatch(self):
        # What /code leaves behind when it launches the loop: the dispatch row. Nothing else runs after the script,
        # as when the /code run ended before the loop handed back.
        store = self.scratch / "handback"
        store.mkdir()
        (store / f"{SESSION}.jsonl").write_text(json.dumps({"kind": "dispatch", "session_id": SESSION,
                                                                 "repo": str(self.repo)}) + "\n")

    def reviewed_repos(self):
        # The repos the shared reviewed-tree record credits, which the push check reads.
        record = self.scratch / "home" / ".claude" / "state" / "review-gate" / "reviewed-trees.json"
        if not record.exists():
            return set()
        return {os.path.realpath(top) for top in json.loads(record.read_text())}

    def test_converged_loop_records_its_tree_when_its_code_run_ended_first(self):
        self.launch_after_dispatch()

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(os.path.realpath(self.repo), self.reviewed_repos())

    def test_failed_loop_records_no_reviewed_tree(self):
        self.launch_after_dispatch()

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
        })

        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn(os.path.realpath(self.repo), self.reviewed_repos())

    def test_the_packet_the_script_hands_back_is_one_json_object(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        sent = json.loads(row["message"])
        self.assertIsInstance(sent, dict)
        self.assertEqual((sent["status"], sent["iter"], sent["files_touched"]), ("converged", 2, ["app.py"]))
        self.assertEqual(sent["fixed"][0]["file_line"], "app.py:2")
        self.assertEqual(handback.load(row["message"]), packet)

    def test_the_crash_packet_is_one_json_object_with_its_blocker_and_tool_fault(self):
        progress = {"iter": 1, "fixed": [], "files_touched": {"app.py"}}
        message = review_loop_packet.packet_message(review_loop_packet.crash_outcome(progress, "boom:\n- line two"))

        sent = json.loads(message)
        self.assertEqual((sent["status"], sent["blockers"], sent["tool_fault"]),
                         ("critical-blocker", ["boom:\n- line two"], "boom:\n- line two"))
        self.assertEqual(handback.load(message)["blockers"], ["boom:\n- line two"])

    def test_the_crash_outcome_has_every_key_a_finished_loop_outcome_has(self):
        loop_script = self.load_script_module()
        progress = {"iter": 0, "fixed": [], "files_touched": set()}
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), progress)

        finished = loop.outcome({}, [])
        crashed = review_loop_packet.crash_outcome(progress, "boom")

        self.assertEqual(set(), set(finished) - set(crashed))

    def test_failed_reviewer_call_is_a_critical_blocker_not_a_clean_review(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
        })

        self.assertNotEqual(completed.returncode, 0)
        row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("review2-code-reviewer call failed", packet["blockers"][0])
        self.assertFalse(row["no_reviewer"])

    def test_the_second_reviewer_reads_the_fix_diff_from_a_file_not_from_its_prompt(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        second_prompt = [call["prompt"] for call in self.fake_calls() if call["key"] == "code-reviewer"][1]
        self.assertNotIn("+limit = 20", second_prompt)
        diff_path = re.search(r"^Round-one fix diff.*: (\S+)$", second_prompt, re.M).group(1)
        self.assertIn("+limit = 20", pathlib.Path(diff_path).read_text())

    def test_a_too_long_reviewer_prompt_is_a_tool_fault_not_a_finding(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": "Prompt is too long", "exit": 1}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
        })

        self.assertNotEqual(completed.returncode, 0)
        _, packet = self.stored_packet()
        self.assertIn("Prompt is too long", packet["tool_fault"])
        self.assertIn("review2-code-reviewer call failed", packet["tool_fault"])

    def test_coder_that_dies_after_editing_reports_its_files_and_its_reply(self):
        limit_hit = "You've hit your usage limit"

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": limit_hit, "edits": {"app.py": APP_FIXED}, "exit": 1}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual(packet["files_touched"], ["app.py"])
        self.assertIn(limit_hit, packet["blockers"][0])
        self.assertIn("changed app.py before it died", packet["blockers"][0])
        self.assertEqual(len(packet["findings_remaining"]), 1)

    def test_a_coder_call_that_fails_stops_loudly_and_keeps_the_findings_in_the_packet(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Prompt is too long", "exit": 1}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual(len(packet["findings_remaining"]), 1)
        self.assertIn("`app.py:2` the limit is wrong", packet["findings_remaining"][0]["finding"])
        blocker = packet["blockers"][0]
        self.assertIn("Prompt is too long", blocker)
        self.assertRegex(blocker, r"reply \S+/call-\d+-coder1\.json, stderr \S+/call-\d+-coder1\.err\.")
        self.assertIn("Never apply them outside the review loop", blocker)

    def test_an_error_after_a_successful_coder_call_is_a_crash_not_a_failed_coder_call(self):
        loop = self.built_loop_for_gate_command("echo ran", False)
        loop_script = sys.modules["review_loop_script"]
        coder_module = sys.modules["review_loop_coder"]

        with mock.patch.object(coder_module, "claude_call", return_value="Fixed."), \
                mock.patch.object(coder_module, "write_fix_diffs", side_effect=RuntimeError("diff write broke")), \
                self.assertRaises(RuntimeError) as raised:
            loop.repair("coder1", [])

        self.assertNotIsInstance(raised.exception, loop_script.CoderFailedError)
        self.assertNotIsInstance(raised.exception, coder_module.CoderCallError)
        self.assertNotIn("coder call failed", str(raised.exception))
        self.assertIn("diff write broke", str(raised.exception))

    def test_a_git_failure_at_the_scope_guard_is_a_failed_coder_call_that_keeps_the_findings_open(self):
        loop = self.built_loop_for_gate_command("echo ran", False)
        loop_script = sys.modules["review_loop_script"]
        scope_guard_module = sys.modules["review_loop_scope_guard"]
        ruled_out_module = sys.modules["review_loop_ruled_out"]
        finding = mock.MagicMock(path="", text="`app.py:2` the limit is wrong")

        git_error = sys.modules["script_utils"].GitCallError("scope guard: git failed")
        with mock.patch.object(scope_guard_module, "guard_pass", side_effect=git_error), \
                mock.patch.object(ruled_out_module, "begin_pass") as begin_pass, \
                mock.patch.object(loop, "issue_text", return_value="issue"), \
                self.assertRaises(loop_script.CoderFailedError) as raised:
            loop.repair("coder1", [finding])

        self.assertIn("the coder1 pass could not start: the scope guard could not read the repo: "
                      "scope guard: git failed", str(raised.exception))
        self.assertIn(finding, loop.open_fixes)
        begin_pass.assert_not_called()

    def test_an_undo_failure_after_a_finished_coder_call_is_a_blocker_saying_the_pass_finished(self):
        loop = self.built_loop_for_gate_command("echo ran", False)
        loop_script = sys.modules["review_loop_script"]
        coder_module = sys.modules["review_loop_coder"]
        scope_guard_module = sys.modules["review_loop_scope_guard"]
        finding = mock.MagicMock(path="", text="`app.py:2` the limit is wrong")
        scope_guard = mock.MagicMock()
        scope_guard.undo.side_effect = RuntimeError("restore failed")

        with mock.patch.object(scope_guard_module, "guard_pass", return_value=scope_guard), \
                mock.patch.object(coder_module, "claude_call", return_value="Fixed."), \
                mock.patch.object(loop, "issue_text", return_value="issue"), \
                self.assertRaises(loop_script.CoderFailedError) as raised:
            loop.repair("coder1", [finding])

        message = str(raised.exception)
        self.assertIn("coder1 coder pass finished but the loop could not undo all of it", message)
        self.assertIn("restore failed", message)
        self.assertNotIn("coder call failed", message)

    def test_an_absolute_finding_path_reaches_the_scope_guard_as_a_repo_relative_path(self):
        loop = self.built_loop_for_gate_command("echo ran", False)
        scope_guard_module = sys.modules["review_loop_scope_guard"]
        finding = mock.MagicMock(path=str(pathlib.Path(loop.repo) / "pkg" / "app.py"), text="`app.py:2` wrong")
        stop = RuntimeError("stop after the guard call")

        with mock.patch.object(scope_guard_module, "guard_pass", side_effect=stop) as guard_pass, \
                mock.patch.object(loop, "issue_text", return_value="issue"), \
                self.assertRaises(RuntimeError):
            loop.repair("coder1", [finding])

        allowed = guard_pass.call_args.args[3]
        self.assertIn("pkg/app.py", str(allowed))
        self.assertNotIn(str(loop.repo), str(allowed))

    def test_a_plain_runtime_error_at_the_scope_guard_is_not_a_failed_coder_call(self):
        loop = self.built_loop_for_gate_command("echo ran", False)
        loop_script = sys.modules["review_loop_script"]
        scope_guard_module = sys.modules["review_loop_scope_guard"]
        finding = mock.MagicMock(path="", text="`app.py:2` the limit is wrong")

        with mock.patch.object(scope_guard_module, "guard_pass", side_effect=RuntimeError("x")), \
                mock.patch.object(loop, "issue_text", return_value="issue"), \
                self.assertRaises(RuntimeError) as raised:
            loop.repair("coder1", [finding])

        self.assertNotIsInstance(raised.exception, loop_script.CoderFailedError)

    def test_the_fix_coder_prompt_stays_small_with_a_huge_finding_set_and_held_file_list(self):
        many_findings = "".join(f"- `app.py:2` [bug] finding {index} " + "the value is wrong " * 100 + "\n"
                                for index in range(200))
        review = f"## Fix\n{many_findings}\n## Ask\nNone\n\n## Nit\nNone\n"
        held_names = [f"evalset/blind/cache/intent/{index:040x}.json" for index in range(7000)]
        held_names.reverse()

        completed = self.run_script({"code-reviewer": [{"result": review}, {"result": CLEAN_REVIEW}],
                                     "coder": [{"result": "Fixed."}], "closure": [{"result": CLOSED}]},
                                    header_extra=f"held files: {', '.join(held_names)}\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertLess(len(prompt), 20000)
        self.assertIn("evalset/blind/cache/intent/ (7000 files)", prompt)
        brief_dir = next((self.state_dir / "loop-script" / AGENT_ID / "coder-briefs").iterdir())
        self.assertEqual((brief_dir / "held-files.txt").read_text().split(), sorted(held_names))
        issues_text = (brief_dir / "issues.txt").read_text()
        self.assertEqual(issues_text.count("the value is wrong"), 200 * 100)
        self.assertIn(str(brief_dir / "issues.txt"), prompt)
        self.assertIn("Issues 51 to 200 are only in", prompt)

    def test_the_coder_prompt_files_every_long_list_and_cuts_the_small_items(self):
        loop_script = self.load_script_module()
        briefs = self.scratch / "briefs"
        files = [f"src/mod{index}/file.py" for index in range(60)]
        later_phase = {f"later/part{index}/file.py" for index in range(60)}
        small_items = [f"nit {index} " + "long " * 200 for index in range(60)]

        prompt = loop_script.coder_prompt(str(self.repo), ["`app.py:2` wrong limit"], small_items, files, briefs,
                                          later_phase_files=later_phase)

        self.assertLess(len(prompt), 30000)
        self.assertIn(str(briefs / "files-in-scope.txt"), prompt)
        self.assertIn("src/ (60 files)", prompt)
        self.assertIn("later/ (60 files)", prompt)
        self.assertEqual((briefs / "files-in-scope.txt").read_text().split(), files)
        self.assertIn(str(briefs / "later-phase-files.txt"), prompt)
        self.assertEqual((briefs / "later-phase-files.txt").read_text().split(), sorted(later_phase))
        self.assertIn(str(briefs / "small-items.txt"), prompt)
        self.assertEqual((briefs / "small-items.txt").read_text().count("long "), 60 * 200)
        self.assertIn("Small items 51 to 60 are only in", prompt)
        listed = [line for line in prompt.splitlines() if re.match(r"\d+\. nit ", line)]
        self.assertEqual(len(listed), 50)
        self.assertTrue(all(len(line) <= 245 for line in listed), "a small item was not cut")

    def test_later_phase_and_held_files_beside_an_in_scope_file_are_not_folded_into_its_directory(self):
        loop_script = self.load_script_module()
        briefs = self.scratch / "briefs"
        others = {f"a/f{index}.py" for index in range(45)}

        prompt = loop_script.coder_prompt(str(self.repo), ["`app.py:2` wrong limit"], [], ["a/z.py"], briefs,
                                          later_phase_files=others, held_files=others)

        self.assertNotIn("a/ (45 files)", prompt)
        self.assertIn("a/f0.py", prompt)
        self.assertIn("and 5 more", prompt)

    def test_a_multi_line_issue_is_listed_on_one_line_cut_to_the_limit_and_filed_in_full(self):
        loop_script = self.load_script_module()
        briefs = self.scratch / "briefs"
        issue = "`app.py:2` first line\nsecond line " + "word " * 100

        prompt = loop_script.coder_prompt(str(self.repo), [issue], [], ["app.py"], briefs)

        listed = next(line for line in prompt.splitlines() if line.startswith("1. "))
        self.assertLessEqual(len(listed), 245)
        self.assertIn("first line second line", listed)
        self.assertEqual((briefs / "issues.txt").read_text(), f"1. {issue}\n")
        self.assertIn(f"Full text of every issue, in the same numbers: {briefs / 'issues.txt'}", prompt)

    def test_a_short_multi_line_issue_adds_no_file_and_no_full_text_line(self):
        loop_script = self.load_script_module()
        briefs = self.scratch / "briefs"

        prompt = loop_script.coder_prompt(str(self.repo), ["`app.py:2` first line\n  second line"], [],
                                          ["app.py"], briefs)

        self.assertIn("1. `app.py:2` first line second line", prompt)
        self.assertNotIn("Full text of every", prompt)
        self.assertFalse((briefs / "issues.txt").exists())

    def test_an_issue_over_the_limit_raw_that_fits_once_its_whitespace_collapses_adds_no_file(self):
        loop_script = self.load_script_module()
        briefs = self.scratch / "briefs"
        issue = "`app.py:2` first" + " " * 300 + "second"

        prompt = loop_script.coder_prompt(str(self.repo), [issue], [], ["app.py"], briefs)

        self.assertIn("1. `app.py:2` first second", prompt)
        self.assertNotIn("Full text of every", prompt)
        self.assertFalse((briefs / "issues.txt").exists())

    def test_a_short_issue_and_small_item_list_adds_no_file_and_no_full_text_line(self):
        loop_script = self.load_script_module()
        briefs = self.scratch / "briefs"

        prompt = loop_script.coder_prompt(str(self.repo), ["`app.py:2` wrong limit"], ["tidy the name"],
                                          ["app.py"], briefs)

        self.assertNotIn("Full text of every", prompt)
        self.assertFalse((briefs / "issues.txt").exists())
        self.assertFalse((briefs / "small-items.txt").exists())

    def test_the_overflow_line_appears_at_one_over_the_listed_limit_and_not_at_the_limit(self):
        loop_script = self.load_script_module()
        briefs = self.scratch / "briefs"
        at_limit = [f"`app.py:2` issue {index}" for index in range(50)]

        at_prompt = loop_script.coder_prompt(str(self.repo), at_limit, [], ["app.py"], briefs)

        self.assertNotIn("Issues 51 to", at_prompt)
        self.assertNotIn("Full text of every", at_prompt)
        self.assertFalse((briefs / "issues.txt").exists())
        over_prompt = loop_script.coder_prompt(str(self.repo), [*at_limit, "`app.py:2` issue 50"], [], ["app.py"],
                                               briefs)
        self.assertIn("Issues 51 to 51 are only in", over_prompt)

    def test_sixty_files_each_alone_in_its_own_directory_are_capped_in_the_prompt_and_filed_in_full(self):
        loop_script = self.load_script_module()
        briefs = self.scratch / "briefs"
        files = [f"dir{index}/file.py" for index in range(60)]

        prompt = loop_script.coder_prompt(str(self.repo), ["`app.py:2` wrong limit"], [], files, briefs)

        self.assertIn(", ".join(files[:40]) + ", and 20 more", prompt)
        self.assertNotIn("dir40/file.py,", prompt)
        self.assertIn(str(briefs / "files-in-scope.txt"), prompt)
        self.assertEqual((briefs / "files-in-scope.txt").read_text().split(), files)

    def test_a_repo_with_no_declared_check_is_reviewed_and_its_packet_says_no_full_check_ran(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="Run make ci before you push.\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check"], "not run (no check found; the coder's scoped tests stand)")
        self.assertNotIn("check-finder", [call["key"] for call in self.fake_calls()])
        self.assertIn("code-reviewer", [call["key"] for call in self.fake_calls()])

    def test_a_plan_change_ask_is_a_plan_impact_bare_tagged_or_opening_with_its_file_line(self):
        asks = {
            "bare": f"- {PLAN_CHANGE_STATUS}: the fix needs a new column the plan rules out",
            "tagged": f"- `src/a.py:12` [plan-drift] — {PLAN_CHANGE_STATUS}: the fix needs a new column the plan "
                      "rules out",
            "opening with its file line": f"- `app.py:3` [plan-drift] {PLAN_CHANGE_STATUS}: the fix needs a new "
                                          "column the plan rules out",
        }

        for name, ask in asks.items():
            with self.subTest(name):
                self.reset_fake_run()
                ask_review = f"## Fix\nNone\n\n## Ask\n{ask}\n\n## Nit\nNone\n"

                completed = self.run_script({"code-reviewer": [{"result": ask_review}]})

                self.assertEqual(completed.returncode, 0, completed.stderr)
                _, packet = self.stored_packet()
                self.assertEqual(packet["status"], "converged")
                self.assertIn("needs a new column", packet["plan_impacts"][0]["text"])
                self.assertEqual([call["key"] for call in self.fake_calls()], ["code-reviewer"])

    def test_full_check_failing_after_one_repair_maps_to_critical_blocker(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
        }, quality_check="false")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("still failing after one repair", packet["blockers"][0])
        self.assertFalse(self.stored_packet()[0]["unreviewed_fix"])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 2)

    def test_a_full_check_failure_that_also_happens_on_head_is_pre_existing_and_gets_no_repair(self):
        check = "echo \"FAIL: test_old ($$ms)\"; exit 1"

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertTrue(packet["full_check"].startswith("pre-existing failure"), packet["full_check"])
        self.assertEqual(self.call_keys().count("coder"), 1)

    def test_a_pre_existing_lint_failure_says_the_check_did_not_verify_the_diff(self):
        check = "echo 'E501 x'; echo '  --> old.py:3:1'; exit 1"

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertTrue(packet["full_check"].startswith("pre-existing failure"), packet["full_check"])
        self.assertIn("did not verify this diff", packet["full_check"])

    def run_scoped_tests_with_autofix(self, scoped_results):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": {"app.py"}})
        runs = [loop_script.coder_gate.ScopedRun(*result, [], [], False)
                for result in scoped_results]
        with mock.patch.object(loop_script.coder_gate, "scoped_run", side_effect=runs) as scoped, \
                mock.patch.object(loop, "autofix_touched_files", return_value=True) as autofix:
            passed = loop.run_test_commands(["npm run lint"])
        return loop, passed, scoped.call_count, autofix.call_count

    def run_scoped_tests_red(self, failing_output, unrun=(), named_tests=False):
        """run_test_commands with one red scoped command, `cat failing.txt; exit 1`, whose head output is
        `failing_output`; the commit holds failing.txt with one old failing test, so the base run is real."""
        self.commit_files({"failing.txt": "FAIL: test_old (shop.tests.OldTest)\n"})
        command = "cat failing.txt; exit 1"
        red = (f"failed: {command}", [f"`{command}` (exit 1):\n{failing_output}"],
               [(command, "exit 1", failing_output)])
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": {"app.py"}})
        loop.gates_every_run = named_tests
        unnamed_lines = [f"not run: {command}" for command in unrun]
        run = loop_script.coder_gate.ScopedRun(*red, [], unnamed_lines, bool(unrun))
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=run), \
                mock.patch.object(loop, "autofix_touched_files", return_value=False):
            passed = loop.run_test_commands([command], budgeted=named_tests, stop_when_unrun=named_tests)
        return loop, passed

    LINT_STEPS: typing.ClassVar[dict] = {
        "full_check_pass": ("true",),
        "recheck_full_check": ("true", "full check failing after the class repair")}

    def run_full_check_pass_with_lint(self, lint_results, formatted=(), step="full_check_pass"):
        """The loop method `step` (a key of LINT_STEPS) with lint_problems returning each of `lint_results` in turn;
        returns the loop and the mocks of the repair, of the check, of lint_problems, of run_formatters and of
        mark_repaired. The review scope is a.py and the touched files are b.py, so a lint of both shows each source
        is read."""
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": {"b.py"}})
        gate = loop_script.full_check_gate
        with mock.patch.object(gate.format_files, "lint_problems", side_effect=lint_results) as lint, \
                mock.patch.object(loop_script.format_files, "run_formatters",
                                  return_value=list(formatted)) as formatters, \
                mock.patch.object(loop, "review_scope", return_value=["a.py"]), \
                mock.patch.object(loop, "repair",
                                  return_value=review_loop_coder.CoderResult("", [], ["c.py"])) as repair, \
                mock.patch.object(loop, "mark_repaired") as mark_repaired, \
                mock.patch.object(loop, "run_check", return_value="") as run_check:
            getattr(loop, step)(*self.LINT_STEPS[step])
        return loop, repair, run_check, lint, formatters, mark_repaired

    def test_lint_left_after_one_repair_stops_critical_blocker_and_the_check_never_runs(self):
        problem = [("ruff check app.py", "app.py:1:1: N802 bad name")]

        loop, repair, run_check, lint, _formatters, _marked = self.run_full_check_pass_with_lint([problem, problem])

        self.assertEqual(lint.call_args_list[0].args[1], ["a.py", "b.py"])
        self.assertEqual(loop.status, "critical-blocker")
        self.assertIn("N802 bad name", "\n".join(loop.remaining))
        self.assertEqual(repair.call_count, 1)
        self.assertEqual(repair.call_args.args[0], "coder-lint")
        run_check.assert_not_called()

    def test_every_linter_output_and_command_reaches_the_stop_message(self):
        problems = [("ruff check app.py", "app.py:1:1: N802 bad name"),
                    ("oxlint a.ts", "a.ts: no-debugger found")]

        loop, _repair, _run_check, _lint, _formatters, _marked = self.run_full_check_pass_with_lint(
            [problems, problems])

        remaining = "\n".join(loop.remaining)
        for expected in ("ruff check app.py", "N802 bad name", "oxlint a.ts", "no-debugger found"):
            self.assertIn(expected, remaining)

    def test_lint_fixed_by_the_one_repair_lets_the_check_run(self):
        problem = [("ruff check app.py", "app.py:1:1: N802 bad name")]

        loop, repair, run_check, lint, formatters, mark_repaired = self.run_full_check_pass_with_lint(
            [problem, []], formatted=["c.py"])

        self.assertEqual(formatters.call_args.args[1], ["a.py", "b.py"])
        self.assertEqual(lint.call_args_list[1].args[1], ["a.py", "b.py", "c.py"])
        self.assertTrue(formatters.call_args.kwargs["configured_only"])
        self.assertTrue(formatters.call_args.kwargs["include_python"])
        self.assertEqual(mark_repaired.call_args.args[1], ["c.py"])
        self.assertNotEqual(loop.status, "critical-blocker")
        self.assertEqual(repair.call_count, 1)
        run_check.assert_called_once()

    def test_lint_left_by_a_class_or_scoped_test_repair_stops_critical_blocker_and_the_recheck_never_runs(self):
        problem = [("ruff check app.py", "app.py:1:1: N802 bad name")]

        loop, repair, run_check, *_ = self.run_full_check_pass_with_lint(
            [problem, problem], step="recheck_full_check")

        self.assertEqual(loop.status, "critical-blocker")
        self.assertIn("N802 bad name", "\n".join(loop.remaining))
        self.assertEqual(repair.call_count, 1)
        self.assertEqual(repair.call_args.args[0], "coder-lint")
        run_check.assert_not_called()

    def test_clean_lint_after_a_class_or_scoped_test_repair_lets_the_recheck_run(self):
        loop, repair, run_check, *_ = self.run_full_check_pass_with_lint([[]], step="recheck_full_check")

        self.assertNotEqual(loop.status, "critical-blocker")
        repair.assert_not_called()
        run_check.assert_called_once()

    def test_a_scoped_failure_that_fails_the_same_way_on_head_without_the_diff_does_not_stop_the_loop(self):
        loop, passed = self.run_scoped_tests_red("FAIL: test_old (shop.tests.OldTest)\n")

        self.assertTrue(passed)
        self.assertNotEqual(loop.status, "critical-blocker")
        self.assertTrue(loop.scoped_tests.startswith("pre-existing failure"), loop.scoped_tests)

    def test_a_named_run_with_a_pre_existing_failure_and_an_unrun_command_stops_the_loop(self):
        loop, passed = self.run_scoped_tests_red("FAIL: test_old (shop.tests.OldTest)\n",
                                                 unrun=["slow command"], named_tests=True)

        self.assertFalse(passed)
        self.assertEqual(loop.status, "critical-blocker")
        (blocker,) = loop.remaining
        self.assertIn("not run: slow command", blocker)
        self.assertIn("FAIL: test_old", blocker)

    def test_a_loop_that_gates_every_run_names_the_runner_counts_of_a_post_fix_run(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.gates_every_run = True
        passed_run = loop_script.coder_gate.ScopedRun("passed", [], [], [("cmd", ["2 passed"])], [], False)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=passed_run):
            loop.run_test_commands(["cmd"])

        self.assertEqual(loop.scoped_tests, "passed; counts: cmd: 2 passed")

    def test_a_loop_stopped_by_a_later_phase_edit_says_why_the_named_tests_did_not_run(self):
        loop_main, request = self.gate_command_request("echo ran", True)
        error = loop_main.LaterPhaseEditError("edited a later phase file")
        with mock.patch.object(loop_main, "walk", side_effect=error), \
                mock.patch.object(loop_main, "first_pass"), \
                mock.patch.object(loop_main, "write_telemetry", return_value=([], [])):
            outcome = loop_main.run_loop(request)

        self.assertEqual(outcome["status"], "critical-blocker")
        self.assertEqual(outcome["scoped_tests"],
                         loop_main.full_check.SCOPED_NOT_RUN_STOPPED.format(status="critical-blocker"))

    def test_a_standing_ruling_that_does_not_parse_stops_the_loop_naming_the_file_and_line(self):
        loop_main, request = self.gate_command_request("echo ran", True)
        error = loop_main.plan_format.PlanFormatError("plan.md:5: a standing ruling line reads 'x'; expected `form`")
        with mock.patch.object(loop_main, "walk", side_effect=error), \
                mock.patch.object(loop_main, "first_pass"), \
                mock.patch.object(loop_main, "write_telemetry", return_value=([], [])):
            outcome = loop_main.run_loop(request)

        self.assertEqual(outcome["status"], "critical-blocker")
        self.assertIn("plan.md:5:", " ".join(outcome["blockers"]))

    def test_run_loop_resumes_the_approval_asks_with_the_runs_findings_before_the_first_pass(self):
        findings_file = self.scratch / "findings.json"
        finding_text = "`CLAUDE.md:1` [bug] Should the rule stay? Proposed change: keep it."
        findings_file.write_text(json.dumps([finding_text]))
        loop_main, request = self.gate_command_request("echo ran", True, f"findings: {findings_file}")
        calls = []
        with mock.patch.object(loop_main.LoopRun, "resume_approval_asks",
                               side_effect=lambda findings: calls.append("resume")) as resume, \
                mock.patch.object(loop_main, "first_pass", side_effect=lambda *args: calls.append("first_pass")), \
                mock.patch.object(loop_main, "walk"), \
                mock.patch.object(loop_main, "write_telemetry", return_value=([], [])):
            loop_main.run_loop(request)

        self.assertEqual(calls, ["resume", "first_pass"])
        resume.assert_called_once()
        resumed_texts = [finding.text for finding in resume.call_args.args[0]]
        self.assertEqual(resumed_texts, [finding_text])

    def test_the_outcome_keeps_the_user_only_asks(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.user_only_asks = ["the approval ask"]

        outcome = loop.outcome([], [])

        self.assertEqual(outcome["user_only_asks"], ["the approval ask"])

    def test_a_post_fix_run_with_an_unrun_command_does_not_stop_the_loop(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        timed_out = loop_script.coder_gate.ScopedRun("not run (timeout): cmd", [], [], [], [], True)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=timed_out):
            passed = loop.run_test_commands(["cmd"])

        self.assertTrue(passed)
        self.assertEqual(loop.status, "converged")

    def test_a_post_fix_run_of_a_loop_that_gates_every_run_stops_on_a_timed_out_command(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.gates_every_run = True
        timed_out = loop_script.coder_gate.ScopedRun("not run (timeout): cmd", [], [], [], [], True)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=timed_out) as scoped:
            loop.scoped_tests_pass("check", ["cmd"])

        self.assertEqual(loop.status, "critical-blocker")
        self.assertIsNone(scoped.call_args.args[4], "the post-fix run is not capped by the named-tests budget")

    def test_a_named_run_with_a_timed_out_command_stops_the_loop(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.gates_every_run = True
        timed_out = loop_script.coder_gate.ScopedRun("not run (timeout): cmd", [], [], [], [], True)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=timed_out):
            passed = loop.run_test_commands(["cmd"], budgeted=True, stop_when_unrun=True)

        self.assertFalse(passed)
        self.assertEqual(loop.status, "critical-blocker")
        self.assertEqual(["not run (timeout): cmd"], loop.remaining)

    def test_a_named_run_with_a_command_error_or_setup_fault_stops_the_loop(self):
        loop_script = self.load_script_module()
        cases = [("command error: cmd (no such file)", loop_script.coder_gate.RESULT_COMMAND_ERROR),
                 ("setup fault: cmd", loop_script.coder_gate.RESULT_SETUP_FAULT)]
        for result, outcome in cases:
            with self.subTest(outcome=outcome):
                loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
                loop.gates_every_run = True
                run = loop_script.coder_gate.ScopedRun(result, [], [], [], ["no result line: cmd"], True)
                with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=run):
                    passed = loop.run_test_commands(["cmd"], budgeted=True, stop_when_unrun=True)

                self.assertFalse(passed, f"{outcome} must block credit")
                self.assertEqual(loop.status, "critical-blocker")
                self.assertEqual(1, len(loop.remaining))
                self.assertTrue(loop.remaining[0].startswith(result), "the blocker leads with the run's result")

    def test_a_command_error_run_with_a_setup_fault_names_the_setup_fault(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.gates_every_run = True
        result = "command error: cmd-a (no such file)"
        run = loop_script.coder_gate.ScopedRun(result, [], [], [], ["setup fault: cmd-b"], True)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=run):
            passed = loop.run_test_commands(["cmd-a", "cmd-b"], budgeted=True, stop_when_unrun=True)

        self.assertFalse(passed)
        self.assertIn("setup fault: cmd-b", loop.remaining[0])
        self.assertEqual(1, loop.remaining[0].count("command error: cmd-a"))

    def test_a_post_fix_command_error_or_setup_fault_stops_only_a_loop_that_gates_every_run(self):
        loop_script = self.load_script_module()
        labels = ["command error", "setup fault"]
        for gates_every_run, expected_status in ((True, "critical-blocker"), (False, "converged")):
            for label in labels:
                with self.subTest(label=label, gates_every_run=gates_every_run):
                    loop = loop_script.LoopRun(self.repo, self.scratch, "", (),
                                               {"fixed": [], "files_touched": set()})
                    loop.gates_every_run = gates_every_run
                    run = loop_script.coder_gate.ScopedRun(f"{label}: cmd", [], [], [], [f"{label}: cmd"], True)
                    with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=run), \
                            mock.patch.object(loop, "stale_prose_pass", return_value=False):
                        loop.scoped_tests_pass("check", ["cmd"])

                    self.assertEqual(loop.status, expected_status)

    def test_a_command_error_stops_a_named_run_even_when_another_command_fails_as_it_does_on_head(self):
        self.commit_files({"failing.txt": "FAIL: test_old (shop.tests.OldTest)\n"})
        failing = "cat failing.txt; exit 1"
        wrong = "pytest missing/test_x.py"
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.gates_every_run = True
        ran = loop_script.coder_gate.CommandRun(
            [loop_script.coder_gate.GateFailure(failing, "exit 1", "FAIL: test_old (shop.tests.OldTest)\n"),
             loop_script.coder_gate.GateFailure(
                 wrong, "exit 4", "ERROR: file or directory not found: missing/test_x.py")],
            [], [], [], [])
        with mock.patch.object(loop_script.coder_gate, "run_commands", return_value=ran), \
                mock.patch.object(loop, "autofix_touched_files", return_value=False):
            passed = loop.run_test_commands([failing, wrong], budgeted=True, stop_when_unrun=True)

        self.assertFalse(passed)
        self.assertEqual(loop.status, "critical-blocker")
        self.assertIn(f"command error: {wrong}", loop.remaining[0])

    def test_a_named_run_names_the_runner_counts_in_the_scoped_tests_line(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.gates_every_run = True
        passed_run = loop_script.coder_gate.ScopedRun("passed", [], [], [("cmd", ["2 passed"])], [], False)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=passed_run):
            loop.run_test_commands(["cmd"], budgeted=True, stop_when_unrun=True)

        self.assertEqual(loop.scoped_tests, "passed; counts: cmd: 2 passed")

    def test_the_named_tests_budget_counts_from_the_named_run_not_from_the_loop_build(self):
        marker = self.scratch / "ran.txt"
        command = f"echo ran >> {marker}"
        loop = self.built_loop_for_gate_command(command, True)
        built_at = time.monotonic()

        with mock.patch.object(review_loop_scoped_tests.time, "monotonic", return_value=built_at + 10 * 60):
            passed = loop.run_test_commands([command], budgeted=True, stop_when_unrun=True)

        self.assertTrue(passed)
        self.assertEqual(marker.read_text(), "ran\n")

    def test_the_autofix_rerun_of_a_named_run_gets_the_budget_left(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": {"app.py"}})
        loop.gates_every_run = True
        red = loop_script.coder_gate.ScopedRun("failed: cmd", ["tail"], [("cmd", "exit 1", "out")], [], [], False)
        clock = iter([0.0, 0.0])

        def monotonic():
            # The first two reads are the deadline and the first run's budget; every later read is 100 s in.
            return next(clock, 100.0)

        with mock.patch.object(loop_script.coder_gate, "scoped_run", side_effect=[red, red]) as scoped, \
                mock.patch.object(loop, "autofix_touched_files", return_value=True), \
                mock.patch.object(review_loop_scoped_tests.time, "monotonic", side_effect=monotonic), \
                mock.patch.object(loop, "scoped_failures_pre_existing", return_value=False):
            loop.run_test_commands(["cmd"], budgeted=True, stop_when_unrun=True)

        budgets = [call.args[4] for call in scoped.call_args_list]
        self.assertEqual(budgets, [review_loop_scoped_tests.NAMED_TESTS_BUDGET_SECONDS,
                                   review_loop_scoped_tests.NAMED_TESTS_BUDGET_SECONDS - 100])

    def test_a_scoped_failure_new_to_the_diff_on_top_of_a_pre_existing_one_stops_the_loop(self):
        loop, passed = self.run_scoped_tests_red("FAIL: test_old (shop.tests.OldTest)\n"
                                                 "FAIL: test_new (shop.tests.NewTest)\n")

        self.assertFalse(passed)
        self.assertEqual(loop.status, "critical-blocker")
        self.assertIn("test_new", loop.remaining[0])

    def test_a_scoped_run_red_only_on_format_errors_the_autofix_clears_does_not_stop_the_loop(self):
        red = ("failed: npm run lint", ["app.ts: Insert `;` prettier/prettier"], [])
        loop, passed, scoped_runs, autofix_runs = self.run_scoped_tests_with_autofix([red, ("passed", [], [])])

        self.assertTrue(passed)
        self.assertEqual((scoped_runs, autofix_runs), (2, 1))
        self.assertNotEqual(loop.status, "critical-blocker")
        self.assertEqual(loop.scoped_tests, "passed")

    def test_a_scoped_run_still_red_after_the_autofix_stops_the_loop(self):
        red = ("failed: npm test", ["FAIL app.test.ts: expected 20, got 99"], [])
        loop, passed, scoped_runs, autofix_runs = self.run_scoped_tests_with_autofix([red, red])

        self.assertFalse(passed)
        self.assertEqual((scoped_runs, autofix_runs), (2, 1))
        self.assertEqual(loop.status, "critical-blocker")
        self.assertIn("expected 20, got 99", loop.remaining[0])

    def test_a_red_named_run_keeps_its_failure_when_no_budget_is_left_for_the_autofix_rerun(self):
        self.use_named_tests_budget(0)
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": {"app.py"}})
        red = loop_script.coder_gate.ScopedRun("failed: npm test", ["FAIL app.test.ts: expected 20, got 99"],
                                               [("npm test", "exit 1", "x")], [], [], False)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=red) as scoped, \
                mock.patch.object(loop, "autofix_touched_files", return_value=True):
            passed = loop.run_test_commands(["npm test"], budgeted=True, stop_when_unrun=True)

        self.assertFalse(passed)
        self.assertEqual(scoped.call_count, 1)
        self.assertIn("expected 20, got 99", loop.remaining[0])

    def test_a_failed_named_run_names_a_setup_fault_beside_the_failure_in_the_blocker(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        failed = loop_script.coder_gate.ScopedRun("failed: a", ["tail"], [("a", "exit 1", "x")], [],
                                                  ["setup fault: b"], True)
        with mock.patch.object(loop_script.coder_gate, "scoped_run", return_value=failed), \
                mock.patch.object(loop, "autofix_touched_files", return_value=False):
            passed = loop.run_test_commands(["a", "b"], stop_when_unrun=True)

        self.assertFalse(passed)
        self.assertIn("setup fault: b", loop.remaining[0])

    def test_the_loop_base_run_gets_the_module_live_base_trees_and_the_gate_environment_assignments(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", ("APP_DIR=/x",), {"fixed": [], "files_touched": set()})
        loop.full_check = "failed (exit 1)"
        runners = []

        def capture_runner(repo, out, check_command, gate_env=(), runner=None, log_name=None):
            runners.append(runner)
            return None

        with mock.patch.object(loop_script.full_check, "base_run") as base_run, \
                mock.patch.object(loop_script.full_check_gate, "run_full_check", side_effect=capture_runner):
            loop.fails_without_the_diff("exit 1")
            runners[0]("repo", "check", "log", 1)

        self.assertIs(base_run.call_args.kwargs["live_trees"], loop_script.full_check_gate.LIVE_BASE_TREES)
        self.assertEqual(base_run.call_args.kwargs["gate_assignments"], {"APP_DIR": "/x"})

    def test_a_wider_check_command_gets_its_own_base_run_and_the_same_command_reuses_it(self):
        loop_script = self.load_script_module()
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": set()})
        loop.full_check = "failed (exit 1)"
        commands = []

        def record_command(repo, out, check_command, gate_env=(), runner=None, log_name=None):
            commands.append(check_command)
            return None

        with mock.patch.object(loop_script.full_check_gate, "run_full_check", side_effect=record_command), \
                mock.patch.object(loop_script.full_check, "is_pre_existing", return_value=True):
            loop.fails_without_the_diff("narrow")
            loop.fails_without_the_diff("narrow")
            loop.fails_without_the_diff("wide")

        self.assertEqual(commands, ["narrow", "wide"])

    def test_sigterm_during_the_base_run_removes_the_base_worktree(self):
        loop_main = self.loop_main_module()
        temp = self.scratch / "base-temp"
        temp.mkdir()
        tree = temp / "base"
        git(self.repo, "worktree", "add", "--detach", str(tree), "HEAD")
        loop_main.full_check_gate.LIVE_BASE_TREES.add((self.repo, tree))
        self.addCleanup(loop_main.full_check_gate.LIVE_BASE_TREES.discard, (self.repo, tree))

        with mock.patch.object(loop_main.os, "_exit") as exit_now:
            loop_main.stop_on_sigterm(signal.SIGTERM, None)

        exit_now.assert_called_once_with(128 + signal.SIGTERM)
        self.assertFalse(temp.exists())
        self.assertNotIn(str(tree), git(self.repo, "worktree", "list", "--porcelain"))

    def test_a_full_check_failure_with_a_new_line_on_top_of_a_pre_existing_one_is_a_blocker(self):
        check = ("echo 'FAIL: test_old'; "
                 "test -z \"$(git diff HEAD --name-only)\" || echo 'FAIL: test_new'; exit 1")

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Repaired."}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual(self.call_keys().count("coder"), 1)

    def test_the_base_check_runs_once_per_loop_and_its_lines_serve_the_recheck_after_the_class_repair(self):
        runs = self.scratch / "runs.log"
        check = f"echo run >> {runs}; echo 'FAIL: test_old'; exit 1"

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_FIXED + "limit = 7\n"}}],
            "closure": [{"result": '{"receipt": "one site left", "open": ["app.py:4 - same limit - fix it"]}'}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertTrue(packet["full_check"].startswith("pre-existing failure"), packet["full_check"])
        # The first check, the one base run, and the recheck after the class repair.
        self.assertEqual(len(runs.read_text().splitlines()), 3)

    def test_a_check_that_fails_only_while_the_diff_holds_a_new_failure_is_pre_existing_after_the_repair(self):
        runs = self.scratch / "runs.log"
        check = (f"echo run >> {runs}; echo 'FAIL: test_old'; "
                 "grep -q 'limit = 6' app.py && echo 'FAIL: test_new'; exit 1")

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Repaired.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertTrue(packet["full_check"].startswith("pre-existing failure"), packet["full_check"])
        self.assertEqual(self.call_keys().count("coder"), 1)
        # The first check, the one base run, and the recheck after the repair.
        self.assertEqual(len(runs.read_text().splitlines()), 3)

    def test_the_autofix_formatters_skip_ruff_format_and_unconfigured_prettier_on_a_lint_only_repo(self):
        recorder = ("#!/bin/sh\necho \"$(basename $0) $*\" >> \"$FAKE_CLAUDE_DIR/tools.log\"\n"
                    "[ \"$1\" = format ] || exit 0\nshift\nfor f in \"$@\"; do echo '# formatted' >> \"$f\"; done\n")
        for tool in (self.fake_ruff, self.fake_ruff.parent / "npx"):
            tool.write_text(recorder)
            tool.chmod(0o755)
        self.commit_files({"pyproject.toml": "[tool.ruff]\nline-length = 100\n", "notes.md": "# notes\n"})
        check = f"{FAILS_ONLY_WITH_THE_DIFF}grep -q '# formatted' app.py || {{ echo 'FAIL: unformatted'; exit 1; }}"

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "notes.md": "# notes\nmore\n"}},
                      {"result": "Repaired."}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        tool_calls = (self.fake_dir / "tools.log").read_text().splitlines()
        self.assertIn("ruff check --fix --force-exclude app.py", tool_calls)
        self.assertEqual([call for call in tool_calls if call.startswith(("npx", "ruff format"))], [])

    def write_fake_ruff_that_appends_a_formatted_marker(self):
        self.fake_ruff.write_text("#!/bin/sh\n[ \"$1\" = format ] || exit 0\nshift\n"
                                  "for a in \"$@\"; do [ \"$a\" = --check ] && exit 0; done\n"
                                  "for f in \"$@\"; do echo '# formatted' >> \"$f\"; done\n")

    def test_a_formatter_fix_clears_the_failure(self):
        self.write_fake_ruff_that_appends_a_formatted_marker()
        self.commit_files({"ruff.toml": "[format]\n"})
        check = (f"{FAILS_ONLY_WITH_THE_DIFF}grep -q '# formatted' app.py || {{ echo 'FAIL: unformatted'; exit 1; }}; "
                 "echo '2 passed in 1s'")

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check"], "passed")
        self.assertIn("app.py", packet["files_touched"])
        self.assertTrue((self.repo / "app.py").read_text().endswith("# formatted\n"))

    def test_a_formatter_the_check_command_turns_on_fixes_a_touched_file_before_the_failure_blocks(self):
        self.write_fake_ruff_that_appends_a_formatted_marker()
        self.commit_files({"ruff.toml": ""})
        check = (f"ruff format --check . ; {FAILS_ONLY_WITH_THE_DIFF}"
                 "grep -q '# formatted' app.py || { echo 'FAIL: unformatted'; exit 1; }; echo '2 passed in 1s'")

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check"], "passed")
        self.assertTrue((self.repo / "app.py").read_text().endswith("# formatted\n"))

    def test_a_converged_loop_formats_the_reviewed_files_before_its_full_check_so_a_later_format_changes_nothing(self):
        self.write_fake_ruff_that_appends_a_formatted_marker()
        self.commit_files({"ruff.toml": "[format]\n"})
        check = "grep -q '# formatted' app.py || { echo 'FAIL: unformatted'; exit 1; }; echo '2 passed in 1s'"

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["full_check"]), ("converged", "passed"))
        self.assertNotIn("coder", self.call_keys())
        self.assertIn("app.py", packet["files_touched"])
        self.assertTrue((self.repo / "app.py").read_text().endswith("# formatted\n"))

    def test_a_formatter_that_changes_nothing_leaves_the_failure_a_blocker_with_no_third_check_run(self):
        runs = self.scratch / "runs.log"
        check = f"{FAILS_ONLY_WITH_THE_DIFF}echo run >> {runs}; echo 'FAIL: test_x'; exit 1"

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        # The first check and the recheck after the repair; the base run exits before it writes.
        self.assertEqual(len(runs.read_text().splitlines()), 2)

    def test_a_formatter_that_changes_a_file_but_leaves_the_failure_blocks_with_the_rechecks_failure_lines(self):
        self.write_fake_ruff_that_appends_a_formatted_marker()
        self.commit_files({"ruff.toml": "[format]\n"})
        runs = self.scratch / "runs.log"
        check = (f"{FAILS_ONLY_WITH_THE_DIFF}echo run >> {runs}; "
                 "echo \"FAIL: test_x $(grep -c formatted app.py)\"; exit 1")

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        # The first check, the recheck after the repair and the recheck after the formatter.
        self.assertEqual(len(runs.read_text().splitlines()), 3)
        # One marker from the format before the first check, one from the formatter after the repair.
        self.assertIn("FAIL: test_x 2", packet["blockers"][0])

    def test_every_coder_prompt_tells_the_coder_to_run_only_the_tests_for_its_changed_files(self):
        loop_script = self.load_script_module()

        prompt = loop_script.coder_prompt(str(self.repo), ["`app.py:2` wrong limit"], ["a small item"], ["app.py"],
                                          self.scratch / "briefs")

        self.assertIn("Run only the tests for the files you changed.", prompt)
        self.assertIn("Do not run lint suites, the full test suite or other repo-wide checks", prompt)

    def test_a_full_check_missing_a_declared_module_converges_with_the_environment_gap(self):
        self.commit_files({"requirements.txt": "ruff==0.6.9\n"})

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
        }, quality_check="echo \"No module named 'ruff'\"; exit 1")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check"], "not run (environment gap: No module named 'ruff')")
        self.assertNotIn("coder", [call["key"] for call in self.fake_calls()])

    def test_a_full_check_that_fails_lint_names_the_lint_error_in_its_blocker(self):
        self.commit_files({"run.sh": f"{FAILS_ONLY_WITH_THE_DIFF}\n"
                                     "printf 'C901 `command_asks_done` is too complex (12 > 10)\\n'\n"
                                     "printf '  --> app.py:3:1\\n'\n"
                                     "for n in $(seq 1 60); do echo \"test_$n.py OK\"; done\n"
                                     "echo '60 tests, 0 failed'\nexit 1\n"})

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
        }, quality_check="bash run.sh")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("C901 `command_asks_done` is too complex", packet["blockers"][0])
        self.assertIn("--> app.py:3:1", packet["blockers"][0])
        self.assertNotIn("0 failed", packet["blockers"][0])

    def test_a_full_check_step_on_a_missing_path_is_a_check_command_error_not_a_blocker(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}],
                                     "smell-reviewer": [{"result": CLEAN_REVIEW}]},
                                    quality_check="git diff --exit-code missing/schema.json")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertTrue(packet["full_check"].startswith("not run (check-command error: "), packet["full_check"])
        self.assertNotIn("coder", [call["key"] for call in self.fake_calls()])

    def test_a_failing_full_check_keeps_the_failing_test_name_that_the_tail_cut_off(self):
        failing_line = "FAIL: test_x (app.tests.T)"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
        }, quality_check=f"{FAILS_ONLY_WITH_THE_DIFF}echo '{failing_line}'; seq 1 200; exit 1")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn(f"Failing tests:\n{failing_line}", packet["blockers"][0])

    def test_a_full_check_that_finds_no_package_manifest_stops_as_a_setup_fault_with_no_coder_repair(self):
        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
        }, quality_check="echo 'ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND No package.json found'; exit 1")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "setup-fault")
        blocker = packet["blockers"][0]
        self.assertIn("could not run in this environment", blocker)
        self.assertIn("ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND", blocker)
        self.assertNotIn("toolkit or environment fault", blocker)
        self.assertNotIn("coder", [call["key"] for call in self.fake_calls()])

    SETUP_FAULT_CHECK = "echo 'ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND No package.json found'; exit 1"

    def run_clean_review_after_a_dispatch(self, quality_check, gate_commands=(), every_run=None):
        """One more clean review of the same session, after the dispatch row that a launch writes. A `quality_check`
        of None keeps the repo's committed one. `every_run` None gates every run exactly when gate commands are given,
        as a `--test` launch does; False is a launch whose gate commands are not `--test` commands."""
        (self.fake_dir / "counters.json").unlink(missing_ok=True)
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            handback_store.record(SESSION, "dispatch", repo=str(self.repo.resolve()))
        self.save_gate_commands(list(gate_commands))
        if every_run is None:
            every_run = bool(gate_commands)
        return self.run_clean_review_with_gates(self.gate_commands, every_run, quality_check=quality_check)

    def last_stored_packet(self):
        handbacks = [row for row in self.store_rows() if row["kind"] == "handback"]
        return handback.load(handbacks[-1]["message"])

    def test_a_test_command_on_a_resume_after_a_setup_fault_replaces_the_default_full_check(self):
        first = self.run_clean_review_after_a_dispatch(self.SETUP_FAULT_CHECK)
        self.assertEqual(self.last_stored_packet()["status"], "setup-fault", first.stderr)

        marker = self.scratch / "override-ran.txt"
        command = f"echo ran >> {marker}"
        resumed = self.run_clean_review_after_a_dispatch(None, [command])

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check_command"], command)
        # `echo` shows no test result, so the check is `unverified` and the command also runs once more as a gate.
        self.assertEqual(packet["full_check"], "unverified (exit 0, no test result shown)")
        self.assertEqual(marker.read_text().splitlines(), ["ran", "ran"])
        self.assertIs(packet["check_overridden"], True)

    def test_a_test_command_on_a_resume_after_an_environment_gap_replaces_the_default_full_check(self):
        self.run_clean_review_after_a_dispatch("echo 'bash: pipenv: command not found'; exit 127")
        gap_result = self.last_stored_packet()["full_check"]
        self.assertTrue(gap_result.startswith("not run (environment gap"), gap_result)

        command = "echo override"
        resumed = self.run_clean_review_after_a_dispatch(None, [command])

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["full_check_command"], command)
        self.assertIs(packet["check_overridden"], True)

    def test_an_earlier_hand_back_that_does_not_parse_keeps_the_configured_full_check_on_a_test_launch(self):
        self.run_clean_review_after_a_dispatch("echo '2 tests, 0 failed'")
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            handback_store.record(SESSION, "dispatch", repo=str(self.repo.resolve()))
            handback_store.record(SESSION, "handback", status="converged", message="not a packet")

        resumed = self.run_clean_review_after_a_dispatch(None, ["echo scoped"], every_run=True)

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["full_check_command"], "echo '2 tests, 0 failed'")
        self.assertFalse(packet["check_overridden"])

    def test_several_test_commands_after_a_setup_fault_all_run_in_the_check_and_leave_out_stale_prose(self):
        self.run_clean_review_after_a_dispatch(self.SETUP_FAULT_CHECK)
        marker = self.scratch / "second-ran.txt"
        commands = ["echo 'FAILED: first'; exit 1", f"echo ran >> {marker}", self.stale_prose_command(0)]

        resumed = self.run_clean_review_after_a_dispatch(None, commands)

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertTrue(marker.is_file())
        self.assertNotIn("stale_prose", packet["full_check_command"])
        self.assertIn("test-1", packet["full_check_command"])
        self.assertIn("test-2", packet["full_check_command"])

    def test_an_invalid_earlier_hand_back_keeps_the_configured_full_check_on_a_test_launch(self):
        self.run_clean_review_after_a_dispatch("echo '2 tests, 0 failed'")
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            handback_store.record(SESSION, "dispatch", repo=str(self.repo.resolve()))
            handback_store.record(SESSION, "handback", status="invalid", message="not a packet")

        resumed = self.run_clean_review_after_a_dispatch(None, ["echo scoped"], every_run=True)

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check_command"], "echo '2 tests, 0 failed'")

    def test_a_setup_fault_hand_back_of_another_session_does_not_override_the_full_check(self):
        self.run_clean_review_after_a_dispatch("echo '2 tests, 0 failed'")
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            handback_store.record("another-session", "dispatch", repo=str(self.repo.resolve()))
            handback_store.record("another-session", "handback", status=handback.SETUP_FAULT_STATUS,
                                  message=json.dumps({"status": handback.SETUP_FAULT_STATUS}))

        resumed = self.run_clean_review_after_a_dispatch(None, ["echo scoped"])

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["full_check_command"], "echo '2 tests, 0 failed'")
        self.assertFalse(packet["check_overridden"])

    def test_a_test_command_on_a_launch_with_no_earlier_setup_fault_keeps_the_configured_full_check(self):
        completed = self.run_clean_review_after_a_dispatch(self.SETUP_FAULT_CHECK, ["echo scoped"])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.last_stored_packet()["status"], "setup-fault")

    def test_a_test_command_on_a_resume_after_a_run_with_no_setup_fault_keeps_the_configured_full_check(self):
        self.run_clean_review_after_a_dispatch("echo '2 tests, 0 failed'")
        self.assertEqual(self.last_stored_packet()["status"], "converged")

        resumed = self.run_clean_review_after_a_dispatch(None, ["echo scoped"])

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check_command"], "echo '2 tests, 0 failed'")
        self.assertIn("echo scoped", packet["scoped_tests"])
        self.assertFalse(packet["check_overridden"])

    def test_gate_commands_that_are_not_a_test_launch_keep_the_configured_full_check_after_a_setup_fault(self):
        self.run_clean_review_after_a_dispatch(self.SETUP_FAULT_CHECK)
        self.assertEqual(self.last_stored_packet()["status"], "setup-fault")

        resumed = self.run_clean_review_after_a_dispatch(None, ["echo scoped"], every_run=False)

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["status"], "setup-fault")
        self.assertFalse(packet["check_overridden"])

    def test_an_overriding_test_command_that_hits_a_setup_fault_stops_as_a_setup_fault(self):
        self.run_clean_review_after_a_dispatch(self.SETUP_FAULT_CHECK)

        resumed = self.run_clean_review_after_a_dispatch(None, [self.SETUP_FAULT_CHECK])

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["status"], "setup-fault")
        self.assertTrue(packet["check_overridden"])

    def test_a_test_command_keeps_overriding_after_an_overridden_run_that_did_not_stop_as_a_setup_fault(self):
        self.run_clean_review_after_a_dispatch(self.SETUP_FAULT_CHECK)
        command = "echo override"
        self.run_clean_review_after_a_dispatch(None, [command])
        self.assertTrue(self.last_stored_packet()["check_overridden"])

        resumed = self.run_clean_review_after_a_dispatch(None, [command])

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(self.last_stored_packet()["full_check_command"], command)

    def test_a_setup_fault_hand_back_for_another_repo_does_not_override_the_full_check(self):
        self.run_clean_review_after_a_dispatch("echo '2 tests, 0 failed'")
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            handback_store.record(SESSION, "dispatch", repo=str(self.scratch / "other-repo"))
            handback_store.record(SESSION, "handback", status=handback.SETUP_FAULT_STATUS,
                                  message=json.dumps({"status": handback.SETUP_FAULT_STATUS}))

        resumed = self.run_clean_review_after_a_dispatch(None, ["echo scoped"])

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        packet = self.last_stored_packet()
        self.assertEqual(packet["full_check_command"], "echo '2 tests, 0 failed'")
        self.assertFalse(packet["check_overridden"])

    def test_a_full_check_that_misses_a_module_from_outside_the_repo_gets_one_coder_repair(self):
        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Repaired."}],
        }, quality_check="echo \"ModuleNotFoundError: No module named 'requests'\"; exit 1")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("still failing after one repair", packet["blockers"][0])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 1)

    def test_a_setup_fault_in_the_full_check_after_the_coder_repair_stops_as_a_setup_fault(self):
        check = (f"{FAILS_ONLY_WITH_THE_DIFF}"
                 "if test -f .git/check-ran; then echo ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND; "
                 "else touch .git/check-ran; echo 'FAIL: test_x'; fi; exit 1")

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1."}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "setup-fault")
        coder_calls = [call for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coder_calls), 1)

    RED_CHECK = f"{FAILS_ONLY_WITH_THE_DIFF}echo 'FAIL: test_x'; exit 1"
    EXPECTED_RED_PLAN = ("## Phase Status\n\n- [x] Phase 1: Skeleton (risk: low)\n- [ ] Phase 2: Limits (risk: low)\n"
                         "- [ ] Phase 3: Notes (risk: low)\n\n## Phase 1: Skeleton\n\n## Phase 2: Limits\n\n"
                         f"Expected red: `{RED_CHECK}` until Phase 3\n\n## Phase 3: Notes\n")

    def test_a_check_the_phase_declares_expected_red_converges_with_no_repair(self):
        self.commit_files({"plan.md": self.EXPECTED_RED_PLAN})

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]}, quality_check=self.RED_CHECK)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check"], "not run (expected red until Phase 3)")
        self.assertNotIn("coder", [call["key"] for call in self.fake_calls()])

    def test_a_check_the_phase_declares_expected_red_whole_runs_the_scoped_tests(self):
        self.commit_files({"plan.md": self.EXPECTED_RED_PLAN})
        self.save_gate_commands(["grep -q 'limit = 99' app.py"])

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]}, quality_check=self.RED_CHECK)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        scoped_tests = packet["scoped_tests"]
        self.assertTrue(scoped_tests.startswith("failed: grep -q 'limit = 99' app.py"), scoped_tests)

    def test_once_the_named_phase_is_done_the_failing_check_is_a_blocker_again(self):
        self.commit_files({"plan.md": self.EXPECTED_RED_PLAN.replace("- [ ] Phase 3:", "- [x] Phase 3:")})

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}], "coder": [{"result": "Repaired."}]},
                                    quality_check=self.RED_CHECK)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("coder", [call["key"] for call in self.fake_calls()])

    def test_a_coder_pass_that_edits_a_later_phase_file_stops_the_loop(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "notes.py": NOTES_REFLOWED}}],
        }, header_extra="later-phase files: notes.py")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("edited files the plan gives to a later phase: notes.py", packet["blockers"][0])
        self.assertEqual(1, [call["key"] for call in self.fake_calls()].count("code-reviewer"))

    def test_the_coder_prompt_carries_the_later_phase_files_and_the_guidance(self):
        completed = self.run_script(FIX_THEN_CLEAN,
                                    header_extra="later-phase files: notes.py, lib/audit.py\nguidance: keep ints")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coder_prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("the plan gives them to a later phase", coder_prompt)
        self.assertIn("lib/audit.py, notes.py", coder_prompt)
        self.assertIn("it changes neither: keep ints", coder_prompt)

    RULED_PLAN = ("# Plan\n\n## Automated Verification\n\n- [ ] **Build-verified**: `CARGO_BUILD_JOBS=4 cargo build`\n"
                  "- [ ] **Lint-clean**: `cargo clippy`\n\n## Constraints\n\n"
                  "- C1: run builds with `CARGO_BUILD_JOBS=4` while the timing slice runs.\n")

    def test_a_fix_on_a_plan_line_a_ruling_covers_becomes_an_ask(self):
        self.commit_files({"plan.md": self.RULED_PLAN})
        drift_review = FIX_REVIEW.replace("`app.py:2` the limit is wrong for `limit`",
                                          "`plan.md:5` the build line drifted from the plan; restore `cargo build`")

        completed = self.run_script({"code-reviewer": [{"result": drift_review}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([entry["file_line"] for entry in packet["ask"]], ["plan.md:5"])
        self.assertIn("ruling", packet["ask"][0]["question"])
        self.assertEqual(packet["fixed"], [])
        self.assertNotIn("coder", [call["key"] for call in self.fake_calls()])

    def test_a_ruled_plan_fix_raised_again_after_a_rejection_logs_no_finding_row_and_is_not_counted(self):
        self.commit_files({"plan.md": self.RULED_PLAN})
        drift_review = FIX_REVIEW.replace("`app.py:2` the limit is wrong for `limit`",
                                          "`plan.md:5` the build line drifted from the plan; restore `cargo build`")
        first = self.run_script({"code-reviewer": [{"result": drift_review}]})
        self.assertEqual(first.returncode, 0, first.stderr)
        _, first_packet = self.stored_packet()
        self.assertEqual(len(first_packet["ask"]), 1)
        self.reset_fake_run()
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"],
                                          "CLAUDE_CODE_SESSION_ID": SESSION}):
            review_asks.record_rejected_asks([SESSION], os.path.realpath(self.repo), first_packet["ask"], [REJECTED])
        first_finding_count = len(self.finding_rows())
        first_run_count = len(fake_ledger.recorded_rows(self.env, "review_run"))

        second = self.run_script({"code-reviewer": [{"result": drift_review}]})

        self.assertEqual(second.returncode, 0, second.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])
        second_findings = self.finding_rows()[first_finding_count:]
        self.assertEqual([row for row in second_findings if row["disposition"] == "ask"], [])
        run = fake_ledger.recorded_rows(self.env, "review_run")[first_run_count]
        self.assertEqual(run["n_findings"], "0")

    def test_a_fix_on_an_unruled_plan_line_still_goes_to_the_coder(self):
        self.commit_files({"plan.md": self.RULED_PLAN})
        lint_review = FIX_REVIEW.replace("`app.py:2` the limit is wrong for `limit`",
                                         "`plan.md:6` the lint line names the wrong command")

        completed = self.run_script({
            "code-reviewer": [{"result": lint_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1."}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 1)

    def test_ask_finding_id_reaches_packet_and_stop_row(self):
        ask_review = "## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit be configurable?\n\n## Nit\nNone\n"

        completed = self.run_script({"code-reviewer": [{"result": ask_review}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(len(packet["ask"]), 1)
        finding_id = packet["ask"][0]["finding_id"]
        self.assertRegex(finding_id, FINDING_ID)
        self.assertEqual(packet["ask"][0]["file_line"], "app.py:3")
        self.assertEqual(packet["ask"][0]["question"], "`app.py:3` should the limit be configurable?")
        self.assertEqual(packet["ask"][0]["change"], packet["ask"][0]["question"])
        stop = self.store_rows()[-1]
        self.assertEqual(stop["ask_rows"], [{"file": "app.py", "line": 3, "finding_id": finding_id}])

    def test_a_design_decision_fix_counts_as_an_ask_in_the_metrics_row(self):
        design_review = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                         "- `app.py:4` [design-decision] pick one owner for the limits\n\n"
                         "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": design_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual((len(packet["fixed"]), len(packet["ask"])), (1, 1))
        metrics = fake_ledger.recorded_rows(self.env, "review_metrics")
        self.assertEqual(len(metrics), 1)
        self.assertEqual((metrics[0]["fix"], metrics[0]["ask"], metrics[0]["fixed"]), ("1", "1", "1"))

    def test_a_finding_row_takes_the_class_its_reviewer_tagged_and_other_when_untagged(self):
        tagged_review = ("## Fix\n- [bug] `app.py:2` the docstring promises 20 but `limit` is 2\n\n"
                         "## Ask\n- [perf] `app.py:3` should the limit be cached?\n\n"
                         "## Nit\n- `app.py:5` [smell] the docs could name the unit\n\n"
                         "Overall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": tagged_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        classes = {row["disposition"]: row["class"] for row in self.finding_rows()}
        self.assertEqual(classes, {"fix": "bug", "ask": "perf", "nit": "smell"})
        metrics = fake_ledger.recorded_rows(self.env, "review_metrics")
        self.assertEqual(metrics[0]["smells"], "1")
        _, packet = self.stored_packet()
        self.assertEqual(packet["ask"][0]["class"], "perf")
        first_review_prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "code-reviewer")
        for finding_class in handback.CLASSES:
            self.assertIn(f"[{finding_class}]", first_review_prompt)

    def test_run_and_finding_rows_count_rounds_from_one(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        run_iters = [row["iter"] for row in fake_ledger.recorded_rows(self.env, "review_run")]
        self.assertEqual(run_iters, ["1", "2"])
        self.assertEqual([row["iter"] for row in self.finding_rows()], ["1"])

    def test_a_refiled_long_finding_reworded_lightly_is_one_row(self):
        long_title = "the limit is wrong for `limit` because " + "the caller passes a stale value " * 8
        first = (f"## Fix\n- `app.py:2` {long_title}\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                 "Overall Assessment: NEEDS CHANGES\n")
        reworded = first.replace("stale value", "old value", 2)

        completed = self.run_script({
            "code-reviewer": [{"result": first}, {"result": reworded}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertGreater(len(long_title), 200)
        self.assertEqual([row["iter"] for row in self.finding_rows()], ["1"])

    def test_a_refile_with_a_new_title_does_not_take_the_spot_of_a_later_same_title_finding(self):
        original = "the limit is wrong for `limit` in the first caller"
        reworded = "the limit is wrong for `limit` in the first caller of the module"
        round_one = (f"## Fix\n- `app.py:2` {original}\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                     "Overall Assessment: NEEDS CHANGES\n")
        round_two = (f"## Fix\n- `app.py:2` {reworded}\n- `app.py:2` {original}\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                     "Overall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": round_one}, {"result": round_two}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 1 and 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        findings = self.finding_rows()
        self.assertEqual(len(findings), 2)
        self.assertEqual(len({row["finding_id"] for row in findings}), 2)

    def test_a_finding_the_second_round_files_again_is_one_row(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        findings = self.finding_rows()
        self.assertEqual([(row["iter"], row["actioned"]) for row in findings], [("1", "fixed")])
        runs = fake_ledger.recorded_rows(self.env, "review_run")
        self.assertEqual(sum(int(row["n_findings"]) for row in runs), len(findings))

    def test_a_rerun_of_the_review_logs_the_same_finding_under_the_same_id(self):
        ask_review = ("## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit be configurable?\n"
                      "- `app.py:4` should the limit be cached?\n\n## Nit\nNone\n")
        scenario = {"code-reviewer": [{"result": ask_review}, {"result": ask_review}]}

        for _run in range(2):
            completed = self.run_script(scenario)
            self.assertEqual(completed.returncode, 0, completed.stderr)

        finding_ids = collections.Counter(row["finding_id"] for row in self.finding_rows())
        self.assertEqual(sum(finding_ids.values()), 4)
        self.assertEqual(list(finding_ids.values()), [2, 2])

    def test_a_rerun_in_another_session_logs_other_finding_ids(self):
        ask_review = "## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit be configurable?\n\n## Nit\nNone\n"
        scenario = {"code-reviewer": [{"result": ask_review}, {"result": ask_review}]}
        ids_by_session = []

        for session in ("session-1", "session-2"):
            before = {row["finding_id"] for row in self.finding_rows()}
            completed = self.run_script(scenario, session=session)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            ids_by_session.append({row["finding_id"] for row in self.finding_rows()} - before)

        self.assertEqual(len(ids_by_session[0]), 1)
        self.assertEqual(len(ids_by_session[1]), 1)
        self.assertFalse(ids_by_session[0] & ids_by_session[1])

    def load_script_module(self, script=SCRIPT):
        return load_script_module(script)

    def test_a_fix_coder_command_carries_the_body_of_the_skills_its_agent_preloads(self):
        module = self.load_script_module()
        claude_home = self.scratch / "home" / ".claude"
        (claude_home / "agents").mkdir(parents=True)
        (claude_home / "agents" / "coder.md").write_text("---\nname: coder\nskills:\n  - coder-core\n---\n\nBody.\n")
        (claude_home / "skills" / "coder-core").mkdir(parents=True)
        (claude_home / "skills" / "coder-core" / "SKILL.md").write_text(
            "---\nname: coder-core\n---\n\n# Coder Core\nRule one.\n")
        commands = []

        def run_process(command, *args, **kwargs):
            commands.append(command)
            return 0, json.dumps({"result": "ok", "usage": {}}), ""

        out = self.scratch / "out"
        out.mkdir()
        preloaded_skills_prompt = module.script_utils.preloaded_skills_prompt
        with mock.patch.object(module.script_utils, "run_process", run_process), \
                mock.patch.object(module.script_utils, "preloaded_skills_prompt",
                                  lambda agent: preloaded_skills_prompt(agent, claude_home)):
            module.claude_call("fix", "prompt", self.repo, out, agent="coder")

        command = commands[0]
        appended = command[command.index("--append-system-prompt") + 1]
        self.assertIn("# Coder Core\nRule one.", appended)
        self.assertNotIn("name: coder-core", appended)

    def test_a_multi_line_ask_with_a_blank_line_paragraph_parses_as_one_located_ask(self):
        module = self.load_script_module()
        review = ("## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit be configurable?\n"
                  "  It is fixed at 10 today.\n\n  Change if accepted: read it from settings\n\n## Nit\nNone\n")

        asks = module.parse_review(review)["ask"]

        self.assertEqual(len(asks), 1)
        self.assertEqual(review_loop_packet.located(asks[0]), "app.py:3")

    def test_two_ask_bullets_stay_two_items(self):
        module = self.load_script_module()
        review = ("## Fix\nNone\n\n## Ask\n- `app.py:3` first question?\n  more on the first\n"
                  "2. `app.py:4` second question?\n\n## Nit\nNone\n")

        asks = module.parse_review(review)["ask"]

        self.assertEqual(len(asks), 2)
        self.assertTrue(asks[1].text.startswith("`app.py:4` second"))

    def test_a_reviewer_line_that_states_no_findings_is_not_an_ask(self):
        module = self.load_script_module()
        for line in ("No new findings.", "- No new findings", "No findings found", "None"):
            with self.subTest(line=line):
                review = f"## Fix\nNone\n\n## Ask\n{line}\n\n## Nit\nNone\n"

                self.assertEqual([], module.parse_review(review)["ask"])

    def test_an_ask_with_nested_bullets_and_a_trailing_paragraph_parses_as_one_ask(self):
        module = self.load_script_module()
        review = ("## Fix\nNone\n\n## Ask\n- `app.py:3` the limit is fixed in two places:\n"
                  "  - the list endpoint caps at 10\n  - the export caps at 10\n\n"
                  "  Should both read one setting? Change if accepted: read both from settings\n\n## Nit\nNone\n")

        asks = module.parse_review(review)["ask"]
        entry = review_loop_packet.ask_entry(asks[0], "code-reviewer", None)

        self.assertEqual(len(asks), 1)
        self.assertEqual(entry["change"], "read both from settings")
        self.assertIn("the export caps at 10", entry["question"])
        self.assertTrue(entry["question"].endswith("Should both read one setting?"))

    def test_asks_indented_alike_under_the_heading_stay_separate(self):
        module = self.load_script_module()
        review = ("## Fix\nNone\n\n## Ask\n  - `app.py:3` first question?\n  - `app.py:4` second question?\n\n"
                  "## Nit\nNone\n")

        asks = module.parse_review(review)["ask"]

        self.assertEqual(len(asks), 2)

    def test_an_ask_followed_by_a_list_of_claims_that_check_out_parses_as_one_ask(self):
        module = self.load_script_module()
        review = ("## Fix\nNone\n\n## Ask\n- notes/change.md:15 [docs] — Should the early push stay? Change: if yes, "
                  "add the push after `git worktree add`.\n\nThe other claims check out:\n"
                  "- The deny messages in both gates match the removed text (`gate.py:194`, `write_gate.py:394`).\n"
                  "- The token counts match the finding.\n\n## Nit\nNone\n")

        asks = module.parse_review(review)["ask"]

        self.assertEqual(len(asks), 1)
        self.assertEqual(review_loop_packet.located(asks[0]), "notes/change.md:15")

    def test_a_located_bullet_after_a_lead_in_list_still_starts_its_own_ask(self):
        module = self.load_script_module()
        review = ("## Fix\nNone\n\n## Ask\n- `app.py:3` first question?\n\nThese hold:\n- The counts agree.\n"
                  "- `app.py:9` second question?\n\n## Nit\nNone\n")

        asks = module.parse_review(review)["ask"]

        self.assertEqual(len(asks), 2)
        self.assertTrue(asks[1].text.startswith("`app.py:9` second"))

    def test_the_notes_after_a_sections_none_line_are_no_findings(self):
        module = self.load_script_module()
        review = ("### Fix\nNone. The four owned files match spec.md:76-145:\n- Every column matches the plan.\n"
                  "- `drizzle-kit check` passes.\n\n### Ask\nNone.\n\n"
                  "The new `find*` helpers repeat `matters/repository.ts:17`, so I did not flag it.\n\n"
                  "### Nit\nNone.\n\nAll four owned files match spec Phase 0:\n"
                  "- **Journal:** the new `when` is later than the previous entry's.\n"
                  "- **Seed:** the truncate list is complete.\n")

        parsed = module.parse_review(review)

        self.assertEqual((parsed["fix"], parsed["ask"], parsed["nit"]), ([], [], []))

    def test_a_finding_that_opens_with_a_bare_file_line_keeps_its_bullets(self):
        module = self.load_script_module()
        review = ("### Fix\nsrc/invoices/schema.ts:111 — [smell] Three places name the rate-source values:\n"
                  "- The column type is the inline union `'general' | 'override'`.\n"
                  "- `BillingRateSource` defines the same values at src/timekeepers/schema.ts:5-6.\n\n"
                  "Nothing keeps them in step. The fix:\n- Type the column `.$type<BillingRateSource>()`.\n\n"
                  "src/invoices/schema.ts:120 — [bug] The index predicate names its table.\n")

        fixes = module.parse_review(review)["fix"]

        self.assertEqual([(fix.path, fix.line) for fix in fixes],
                         [("src/invoices/schema.ts", 111), ("src/invoices/schema.ts", 120)])
        self.assertIn("defines the same values", fixes[0].text)
        self.assertTrue(fixes[0].text.endswith("Type the column `.$type<BillingRateSource>()`."))

    def test_a_section_that_opens_with_a_sentence_about_none_keeps_its_findings(self):
        module = self.load_script_module()
        review = ("### Fix\nNone of the three changed queries filters by tenant:\n"
                  "- src/matters/repository.ts:12 — `findMatters` reads every tenant's rows.\n"
                  "- src/entries/repository.ts:40 — `findEntries` reads every tenant's rows.\n")

        fixes = module.parse_review(review)["fix"]

        self.assertEqual([(fix.path, fix.line) for fix in fixes],
                         [("src/matters/repository.ts", 12), ("src/entries/repository.ts", 40)])

    def test_bullets_under_a_colon_line_that_opens_a_section_stay_separate_findings(self):
        module = self.load_script_module()
        review = "## Fix\nTwo problems:\n- The cache never expires.\n- The lock leaks.\n"

        fixes = module.parse_review(review)["fix"]

        self.assertEqual([fix.text for fix in fixes],
                         ["Two problems:", "The cache never expires.", "The lock leaks."])

    def test_a_line_that_opens_with_a_none_word_after_the_first_finding_is_finding_text(self):
        module = self.load_script_module()
        review = ("### Fix\n- a.py:3 [bug] the loop never ends when the list is empty\n"
                  "  Empty input reaches `walk` and spins forever\n"
                  "- b.py:9 [bug] crash on the second call\n"
                  "  None of the callers reset `state`, so it crashes\n\n"
                  "- Empty catch in c.py:4 swallows the error\n- None.\n\n### Ask\nNone.\n")

        fixes = module.parse_review(review)["fix"]

        self.assertEqual([fix.text for fix in fixes], [
            "a.py:3 [bug] the loop never ends when the list is empty Empty input reaches `walk` and spins forever",
            "b.py:9 [bug] crash on the second call None of the callers reset `state`, so it crashes",
            "Empty catch in c.py:4 swallows the error",
        ])

    def test_a_reply_of_bold_head_items_with_a_tagged_sub_bullet_falls_back_to_the_disposition_call(self):
        module = self.load_script_module()
        for sub_bullet_indent in ("", "  "):
            with self.subTest(sub_bullet_indent=sub_bullet_indent):
                review = ("### Coverage Gaps in Business Logic\n\n"
                          "**19 of 21 check constraints have no test.**\n"
                          "`backend/src/modules/invoices/schema.ts:58-101`. Add one rejection test per check.\n\n"
                          "**The draft test sets one field.**\n"
                          "`backend/src/modules/invoices/schema.test.ts:63` only sets one finalize field.\n"
                          f"{sub_bullet_indent}- Fix: set all 12 finalize fields in the draft test.\n")

                self.assertIsNone(module.parse_review(review))

    def test_a_tagged_bullet_indented_deeper_than_the_other_list_items_falls_back(self):
        module = self.load_script_module()
        review = "- fix: `app.py:3` the limit is 5\n  - fix: raise it to 20\n"

        self.assertIsNone(module.parse_review(review))

    def test_an_untagged_bold_head_line_beside_tagged_bullets_falls_back(self):
        module = self.load_script_module()
        for head in ("**Big finding.**", "1. __Big finding.__", "- **Big finding.** no test"):
            with self.subTest(head=head):
                review = f"{head}\n- fix: `app.py:3` the limit is 5\n"

                self.assertIsNone(module.parse_review(review))

    def test_an_untagged_top_level_item_naming_a_file_line_beside_tagged_bullets_falls_back(self):
        module = self.load_script_module()
        review = "- fix: `app.py:3` the limit is 5\n- `util.py:9` the retry has no test\n"

        self.assertIsNone(module.parse_review(review))

    def test_a_disposition_tag_on_a_line_the_tagged_parser_did_not_take_falls_back(self):
        module = self.load_script_module()
        for stray in ("- rename the helper (nit)", "- rename the helper `nit`", "Pin the limit **ask**"):
            with self.subTest(stray=stray):
                review = f"- fix: `app.py:3` the limit is 5\n{stray}\n"

                self.assertIsNone(module.parse_review(review))

    def test_a_fully_tagged_reply_with_a_bold_report_header_field_still_parses(self):
        module = self.load_script_module()
        review = ("**Scope**: the invoice tests\n\n"
                  "- fix: `app.py:3` the limit is 5\n"
                  "- ask: `app.py:4` should the limit be configurable?\n"
                  "- nit: `app.py:5` name the test for the limit\n")

        parsed = module.parse_review(review)

        self.assertEqual([len(parsed[key]) for key in ("fix", "ask", "nit")], [1, 1, 1])

    def test_a_report_in_the_test_reviewer_template_form_parses_with_no_disposition_call(self):
        module = self.load_script_module()
        review = ("## Test Review Report\n\n"
                  "**Scope**: the invoice tests\n\n"
                  "---\n\n"
                  "### Coverage Gaps in Business Logic\n\n"
                  "- fix: `src/invoices/finalize.ts:40` — `finalize` has no test for the voided state.\n\n"
                  "### Assertions the Spec Does Not Support\n\n"
                  "- ask: `src/invoices/finalize.test.ts:12` — pins status `open`; the criteria are silent — "
                  "change: keep it.\n\n"
                  "### Test Hygiene Issues\n\n"
                  "- nit: `src/invoices/finalize.test.ts:3` — name the test for its outcome.\n")

        parsed = module.parse_review(review)

        self.assertEqual([len(parsed[key]) for key in ("fix", "ask", "nit")], [1, 1, 1])

    def test_change_if_accepted_marker_splits_question_from_change(self):
        ask = "`app.py:3` should it be configurable? Change if accepted: read from settings"

        entry = review_loop_packet.ask_entry(finding_record.parse_finding(ask), "code-reviewer", None)

        self.assertEqual(entry["change"], "read from settings")
        self.assertEqual(entry["question"], "`app.py:3` should it be configurable?")

    def test_an_ask_that_opens_with_its_change_marker_asks_its_change(self):
        for ask in ("Change if accepted: read from settings", "change: read from settings"):
            with self.subTest(ask=ask):
                entry = review_loop_packet.ask_entry(finding_record.parse_finding(ask), "code-reviewer", None)

                self.assertEqual((entry["question"], entry["change"]), ("read from settings", "read from settings"))

    def test_test_files_in_every_convention_go_to_the_test_reviewer(self):
        module = self.load_script_module()
        test_paths = ["web/__tests__/cart.js", "svc/test_cart.py", "svc/cart_test.go", "svc/tests/unit/helpers.py"]
        files = {"svc/cart.py": [5, "M"]}
        files.update({path: [5, "M"] for path in test_paths})
        files["svc/big.py"] = [review_loop_plan.LARGE_ADDED_LINES, "M"]

        dispatches = dict(module.first_round_plan(files))

        self.assertEqual(sorted(dispatches["test-reviewer"]), sorted(test_paths))
        self.assertEqual(sorted(dispatches["code-reviewer"]), ["svc/big.py", "svc/cart.py"])

    def test_added_lines_of_tests_and_any_lockfile_stay_out_of_the_size_bar(self):
        module = self.load_script_module()
        uncounted = ["web/__tests__/cart.js", "svc/test_cart.py", "svc/cart_test.go", "svc/tests/unit/helpers.py",
                     "yarn.lock", "svc/poetry.lock", "pnpm-lock.yaml"]

        for path in uncounted:
            with self.subTest(path=path):
                files = {"svc/cart.py": [5, "M"], path: [review_loop_plan.LARGE_ADDED_LINES, "M"]}
                agents = {agent for agent, _ in module.first_round_plan(files)}
                self.assertEqual(agents, {"code-reviewer"})

    def test_a_multi_file_change_sends_two_code_reviewers_each_over_every_file_with_its_own_lens(self):
        module = self.load_script_module()
        files = {"a.py": [5, "M"], "b.py": [5, "M"]}

        dispatches = module.first_round_plan(files)

        self.assertEqual([agent for agent, _ in dispatches], ["code-reviewer", "code-reviewer"])
        self.assertEqual([sorted(owned) for _, owned in dispatches], [["a.py", "b.py"], ["a.py", "b.py"]])
        self.assertEqual([owned.lens for _, owned in dispatches], [review_loop_plan.LENS_A, review_loop_plan.LENS_B])

    def test_a_one_file_change_sends_one_code_reviewer_with_no_lens(self):
        module = self.load_script_module()

        dispatches = module.first_round_plan({"a.py": [500, "M"]})

        code_reviewers = [owned for agent, owned in dispatches if agent == "code-reviewer"]
        self.assertEqual(code_reviewers, [["a.py"]])
        self.assertEqual(getattr(code_reviewers[0], "lens", ""), "")

    def test_a_lens_reviewer_prompt_ends_with_its_lens_line_and_a_plain_one_carries_none(self):
        module = self.load_script_module()
        loop = mock.Mock(repo=self.repo, prior_issues=[], round_two_fix_diff_path="", asks=[], brief="",
                         test_strategy="", iter_count=1, no_code_rulings=[], ruled_out=set())
        lensed = ("code-reviewer", review_loop_plan.LensOwned(["a.py", "b.py"], review_loop_plan.LENS_B))
        plain = ("code-reviewer", ["a.py"])

        _role, _agent, lensed_prompt = module.LoopRun.review_request(loop, lensed)
        _role, _agent, plain_prompt = module.LoopRun.review_request(loop, plain)

        self.assertTrue(lensed_prompt.endswith("\n" + review_loop_plan.LENS_B))
        self.assertNotIn(review_loop_plan.LENS_A, plain_prompt)
        self.assertNotIn(review_loop_plan.LENS_B, plain_prompt)

    def test_a_lens_split_with_no_test_reviewer_gives_every_test_file_a_reviewer(self):
        module = self.load_script_module()
        files = {"a.py": [5, "M"], "b.py": [5, "M"], "c.py": [5, "M"],
                 "tests/test_a.py": [100, "M"], "tests/test_b.py": [100, "M"], "tests/test_c.py": [100, "M"]}

        dispatches = module.first_round_plan(files)

        self.assertEqual([agent for agent, _ in dispatches], ["code-reviewer", "code-reviewer"])
        for _agent, owned in dispatches:
            self.assertEqual(sorted(owned), sorted(files))

    def test_the_finding_id_changes_with_the_gate(self):
        module = load_script_module()

        def finding_id(gate):
            return module.stable_finding_id("s1", "code", ["scope"], gate, "app.py:3#1")

        self.assertEqual(finding_id("code-reviewer"), finding_id("code-reviewer"))
        self.assertNotEqual(finding_id("code-reviewer"), finding_id("smell-reviewer"))

    def test_two_near_identical_asks_at_one_line_are_two_asks(self):
        two_asks = ("## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit apply to the first caller?\n"
                    "- `app.py:3` should the limit apply to the second caller?\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": two_asks}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(len(packet["ask"]), 2)
        asks = [row for row in self.finding_rows() if row["disposition"] == "ask"]
        self.assertEqual(len(asks), 2)

    def test_an_ask_that_only_points_back_to_another_ask_is_dropped(self):
        asks_with_a_pointer = ("## Fix\nNone\n\n## Ask\n- `app.py:3` should the window be pinned?\n"
                               "- `app.py:4` should the limit be cached?\n"
                               "- The open ask about pinning the window still stands.\n"
                               "- After ask 1 is answered, should the cache key change too?\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": asks_with_a_pointer}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([item["question"] for item in packet["ask"]][-1],
                         "After ask 1 is answered, should the cache key change too?")
        self.assertEqual(len(packet["ask"]), 3)
        asks = [row for row in self.finding_rows() if row["disposition"] == "ask"]
        self.assertEqual(len(asks), 3)
        self.assertEqual(packet["dropped_asks"], ["ask only points back to another ask, so it was dropped: "
                                                  "'The open ask about pinning the window still stands.'"])

    def test_a_pointer_ask_repeated_in_a_later_round_is_one_dropped_ask_warning(self):
        pointer_and_ask = ("## Ask\n- `app.py:3` should the window be pinned?\n"
                           "- The open ask about pinning the window still stands.\n\n## Nit\nNone\n")
        first_round = "## Fix\n- `app.py:2` the limit is wrong for `limit`\n\n" + pointer_and_ask
        second_round = "## Fix\nNone\n\n" + pointer_and_ask

        completed = self.run_script({
            "code-reviewer": [{"result": first_round}, {"result": second_round}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["dropped_asks"], ["ask only points back to another ask, so it was dropped: "
                                                  "'The open ask about pinning the window still stands.'"])

    def test_an_ask_the_session_rejected_comes_back_as_a_dropped_ask_not_a_stop(self):
        ask_report = "## Fix\nNone\n\n## Ask\n- `app.py:3` [bug] should the window be pinned?\n\n## Nit\nNone\n"
        first = self.run_script({"code-reviewer": [{"result": ask_report}]})
        self.assertEqual(first.returncode, 0, first.stderr)
        _, first_packet = self.stored_packet()
        self.assertEqual(len(first_packet["ask"]), 1)
        self.reset_fake_run()
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"],
                                          "CLAUDE_CODE_SESSION_ID": SESSION}):
            review_asks.record_rejected_asks([SESSION], os.path.realpath(self.repo), first_packet["ask"], [REJECTED])
        # The reviewer words the same ask again, on another line.
        again = "## Fix\nNone\n\n## Ask\n- `app.py:9` [bug] should the window be pinned?\n\n## Nit\nNone\n"

        second = self.run_script({"code-reviewer": [{"result": again}]})

        self.assertEqual(second.returncode, 0, second.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])
        self.assertEqual(len(packet["dropped_asks"]), 1, packet["dropped_asks"])
        self.assertTrue(packet["dropped_asks"][0].startswith(f"{review_loop_findings.REJECTED_ASK_REASON}, so it "
                                                             "was dropped"), packet["dropped_asks"])
        self.assertIn("should the window be pinned?", packet["dropped_asks"][0])

    def test_a_design_fix_the_session_rejected_is_dropped_when_raised_again(self):
        plan_text = "PLAN-IMPACT: the reword is narrower than the ticket. acceptance_criteria: none"
        rejected_ask = {"file_line": "app.py:3", "question": plan_text}
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"],
                                          "CLAUDE_CODE_SESSION_ID": SESSION}):
            review_asks.record_rejected_asks([SESSION], os.path.realpath(self.repo), [rejected_ask], [REJECTED])
        again = f"## Fix\n- `app.py:3` [design-decision] {plan_text}\n\n## Ask\nNone\n\n## Nit\nNone\n"

        second = self.run_script({"code-reviewer": [{"result": again}]})

        self.assertEqual(second.returncode, 0, second.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["plan_impacts"], [])
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        self.assertEqual(len(packet["dropped_asks"]), 1, packet["dropped_asks"])
        self.assertTrue(packet["dropped_asks"][0].startswith(f"{review_loop_findings.REJECTED_ASK_REASON}, so it "
                                                             "was dropped"), packet["dropped_asks"])

    def test_a_rejected_ask_with_a_change_part_is_dropped_when_raised_again_word_for_word(self):
        ask_text = ("`app.py:3` [bug] the retry window is never pinned — should the window be pinned to the config "
                    "value? — change: read RETRY_WINDOW from config and pass it to retry()")
        ask_report = f"## Fix\nNone\n\n## Ask\n- {ask_text}\n\n## Nit\nNone\n"
        first = self.run_script({"code-reviewer": [{"result": ask_report}]})
        self.assertEqual(first.returncode, 0, first.stderr)
        _, first_packet = self.stored_packet()
        self.assertEqual(len(first_packet["ask"]), 1)
        self.reset_fake_run()
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"],
                                          "CLAUDE_CODE_SESSION_ID": SESSION}):
            review_asks.record_rejected_asks([SESSION], os.path.realpath(self.repo), first_packet["ask"], [REJECTED])

        second = self.run_script({"code-reviewer": [{"result": ask_report}]})

        self.assertEqual(second.returncode, 0, second.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])
        self.assertEqual(len(packet["dropped_asks"]), 1, packet["dropped_asks"])

    def test_a_repeated_ask_logs_no_finding_row_and_is_not_counted(self):
        ask_question = "should the window be pinned?"
        two_of_a_kind = ("## Fix\nNone\n\n## Ask\n"
                         f"- `app.py:3` [bug] {ask_question}\n"
                         f"- `app.py:4` [bug] {ask_question}\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": two_of_a_kind}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        ask_rows = [row for row in self.finding_rows() if row["disposition"] == "ask"]
        self.assertEqual(len(ask_rows), 1, ask_rows)
        first_run = fake_ledger.recorded_rows(self.env, "review_run")[0]
        self.assertEqual(first_run["n_findings"], "1")

    def test_a_repeat_of_a_rejected_ask_logs_no_finding_row_and_is_not_counted(self):
        ask_report = "## Fix\nNone\n\n## Ask\n- `app.py:3` [bug] should the window be pinned?\n\n## Nit\nNone\n"
        first = self.run_script({"code-reviewer": [{"result": ask_report}]})
        self.assertEqual(first.returncode, 0, first.stderr)
        _, first_packet = self.stored_packet()
        self.reset_fake_run()
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"],
                                          "CLAUDE_CODE_SESSION_ID": SESSION}):
            review_asks.record_rejected_asks([SESSION], os.path.realpath(self.repo), first_packet["ask"], [REJECTED])
        again = "## Fix\nNone\n\n## Ask\n- `app.py:9` [bug] should the window be pinned?\n\n## Nit\nNone\n"
        first_finding_count = len(self.finding_rows())
        first_run_count = len(fake_ledger.recorded_rows(self.env, "review_run"))

        second = self.run_script({"code-reviewer": [{"result": again}]})

        self.assertEqual(second.returncode, 0, second.stderr)
        second_findings = self.finding_rows()[first_finding_count:]
        self.assertEqual([row for row in second_findings if row["disposition"] == "ask"], [])
        run = fake_ledger.recorded_rows(self.env, "review_run")[first_run_count]
        self.assertEqual(run["n_findings"], "0")

    def test_pass_notes_and_a_repeated_ask_leave_exactly_one_ask_and_show_as_dropped_asks(self):
        ask_question = "should the window be pinned?"
        notes_and_a_repeat = ("## Fix\nNone\n\n## Ask\n"
                              f"- `app.py:3` [bug] {ask_question}\n"
                              f"- `app.py:4` [bug] {ask_question}\n"
                              "- I checked the other claims against the code and each one holds.\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": notes_and_a_repeat}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([item["question"] for item in packet["ask"]], [f"`app.py:3` [bug] {ask_question}"])
        self.assertEqual(len(packet["dropped_asks"]), 2, packet["dropped_asks"])
        repeat_entry = next(entry for entry in packet["dropped_asks"] if "app.py:4" in entry)
        note_entry = next(entry for entry in packet["dropped_asks"] if "I checked the other claims" in entry)
        self.assertTrue(repeat_entry.startswith(f"{review_loop_findings.REPEATED_ASK_REASON}, so it was dropped"),
                        repeat_entry)
        self.assertTrue(note_entry.startswith(f"{review_loop_findings.NOTE_ASK_REASON}, so it was dropped"),
                        note_entry)

    def test_pass_notes_in_several_wordings_and_a_repeated_ask_leave_exactly_one_ask(self):
        ask_question = "should the window be pinned?"
        notes = ["(none new; the open ask is left as it was)",
                 "I checked every claim against the code, and each one holds.",
                 "Checks run (no defects found):",
                 "`python3 tests/parallel_tests.py x.py` gave 36 tests, 0 failed."]
        ask_lines = [f"`app.py:3` [bug] {ask_question}", *notes, f"`app.py:7` [bug] {ask_question}"]
        ask_section = "".join(f"- {line}\n" for line in ask_lines)
        report = f"## Fix\nNone\n\n## Ask\n{ask_section}\n## Nit\nNone\n"

        completed = self.run_script({"code-reviewer": [{"result": report}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([item["question"] for item in packet["ask"]], [f"`app.py:3` [bug] {ask_question}"])
        self.assertEqual(len(packet["dropped_asks"]), len(notes) + 1, packet["dropped_asks"])

    def test_a_report_that_opens_its_ask_section_with_none_new_and_notes_leaves_no_ask(self):
        report = (FIXTURES / "review_ask_pass_notes_report.md").read_text()

        completed = self.run_script({"code-reviewer": [{"result": report}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])
        self.assertEqual(packet["dropped_asks"], [])

    def test_two_fixes_at_one_line_are_two_rows_with_distinct_ids(self):
        two_at_one_line = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                           "- `app.py:2` the name `limit` shadows the module setting\n\n"
                           "## Ask\nNone\n\n## Nit\nNone\n\n"
                           "Overall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": two_at_one_line}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1 and 2.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        findings = self.finding_rows()
        self.assertEqual(len(findings), 2)
        self.assertEqual(len({row["finding_id"] for row in findings}), 2)
        first_run = fake_ledger.recorded_rows(self.env, "review_run")[0]
        self.assertEqual(first_run["n_findings"], "2")

    def test_two_fixes_identical_apart_from_their_line_are_two_rows_with_distinct_ids(self):
        same_title = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                      "- `app.py:4` the limit is wrong for `limit`\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                      "Overall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": same_title}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1 and 2.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        findings = self.finding_rows()
        self.assertEqual(len(findings), 2)
        self.assertEqual(len({row["finding_id"] for row in findings}), 2)

    def test_an_ask_with_the_title_of_an_earlier_fix_is_its_own_row_and_ask(self):
        same_title_ask = ("## Fix\nNone\n\n## Ask\n- `app.py:2` the limit is wrong for `limit`?\n\n## Nit\nNone\n")

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": same_title_ask}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(len(packet["ask"]), 1)
        findings = self.finding_rows()
        self.assertEqual(sorted(row["disposition"] for row in findings), ["ask", "fix"])
        self.assertEqual(len({row["finding_id"] for row in findings}), 2)

    def test_a_finding_that_drops_out_in_round_two_keeps_its_row_and_the_other_is_not_refiled_as_it(self):
        fix_and_nit = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n\n## Ask\nNone\n\n"
                       "## Nit\n- `app.py:2` the docs could name the unit\n\nOverall Assessment: NEEDS CHANGES\n")
        nit_only = ("## Fix\nNone\n\n## Ask\nNone\n\n## Nit\n- `app.py:2` the docs could name the unit\n\n"
                    "Overall Assessment: PASS\n")

        completed = self.run_script({
            "code-reviewer": [{"result": fix_and_nit}, {"result": nit_only}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        findings = self.finding_rows()
        self.assertEqual(sorted((row["disposition"], row["actioned"]) for row in findings),
                         [("fix", "fixed"), ("nit", "none")])
        self.assertEqual(len({row["finding_id"] for row in findings}), 2)

    def test_a_reworded_ask_in_round_two_keeps_one_row_and_one_ask_id(self):
        first_ask = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n\n"
                     "## Ask\n- `app.py:3` should the limit be configurable?\n\n## Nit\nNone\n")
        reworded_ask = ("## Fix\nNone\n\n"
                        "## Ask\n- `app.py:3` should the limit become configurable per caller?\n\n## Nit\nNone\n")

        completed = self.run_script({
            "code-reviewer": [{"result": first_ask}, {"result": reworded_ask}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(len(packet["ask"]), 1)
        self.assertRegex(packet["ask"][0]["finding_id"], FINDING_ID)
        asks = [row for row in self.finding_rows() if row["disposition"] == "ask"]
        self.assertEqual(len(asks), 1)

    def test_a_class_tag_after_the_file_line_wins_over_a_tag_before_it(self):
        smell_prefixed = ("## Fix\n- [smell] `app.py:2` [duplication] the limit is repeated\n\n## Ask\nNone\n\n"
                          "## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": smell_prefixed}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([row["class"] for row in self.finding_rows()], ["duplication"])
        metrics = fake_ledger.recorded_rows(self.env, "review_metrics")
        self.assertEqual(metrics[0]["smells"], "0")

    def test_two_distinct_findings_in_one_file_from_one_reviewer_are_two_rows(self):
        other_fix_review = ("## Fix\n- `app.py:5` the last limit skips the unit\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                            "Overall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": other_fix_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 1.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        findings = self.finding_rows()
        self.assertEqual([(row["iter"], row["line"]) for row in findings], [("1", "2"), ("2", "5")])
        self.assertEqual(len({row["finding_id"] for row in findings}), 2)

    def test_a_finding_whose_line_moved_is_one_row(self):
        moved_review = ("## Fix\n- `app.py:3` the limit is wrong for `limit`\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                        "Overall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": moved_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 1.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([row["iter"] for row in self.finding_rows()], ["1"])
        metrics = fake_ledger.recorded_rows(self.env, "review_metrics")
        self.assertEqual((metrics[0]["fix"], metrics[0]["fixed"]), ("1", "1"))

    def test_a_skip_in_round_one_and_a_fix_in_round_two_are_each_logged_with_their_outcome(self):
        two_fix_review = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                          "- `notes.py:1` the keys of `value` are out of order\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                          "Overall Assessment: NEEDS CHANGES\n")
        new_fix_review = ("## Fix\n- `app.py:4` the fourth limit repeats the third\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                          "Overall Assessment: NEEDS CHANGES\n")

        completed = self.run_script({
            "code-reviewer": [{"result": two_fix_review}, {"result": new_fix_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.\nSKIPPED 2: the order is deliberate", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 1.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        actioned = {(row["iter"], row["path_key"]): row["actioned"] for row in self.finding_rows()}
        self.assertEqual(actioned, {("1", "app.py"): "fixed", ("1", "notes.py"): "skipped_fp",
                                    ("2", "app.py"): "fixed"})

    def test_round_two_scope_ignores_files_a_format_hook_would_reflow(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED},
                       "edits_when_format_hook_on": {"notes.py": NOTES_REFLOWED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.fake_calls()
        self.assertEqual({call["hook_off"] for call in calls}, {"1"})
        later_prompts = [call["prompt"] for call in calls[2:]]
        self.assertEqual(len(later_prompts), 2)
        for prompt in later_prompts:
            self.assertNotIn("notes.py", prompt)
        _, packet = self.stored_packet()
        self.assertEqual(packet["files_touched"], ["app.py"])

    def test_structure_pass_skip_drops_the_first_round_smell_reviewer(self):
        scenario = {"code-reviewer": [{"result": CLEAN_REVIEW}] * 2, "smell-reviewer": [{"result": CLEAN_REVIEW}]}
        (self.repo / "fresh.py").write_text("created = True\n")

        self.run_script(scenario, header_extra="structure-pass: skip\n")
        skipped_keys = sorted(call["key"] for call in self.fake_calls())
        (self.fake_dir / "calls.jsonl").unlink()
        (self.fake_dir / "counters.json").unlink()
        self.run_script(scenario)
        full_keys = sorted(call["key"] for call in self.fake_calls())

        self.assertEqual(skipped_keys, ["code-reviewer", "code-reviewer"])
        self.assertEqual(full_keys, ["code-reviewer", "code-reviewer", "smell-reviewer"])

    def test_real_handoff_is_the_only_handoff_in_each_reviewer_prompt(self):
        self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        reviewer_prompts = [call["prompt"] for call in self.fake_calls() if call["key"] == "code-reviewer"]
        self.assertEqual(len(reviewer_prompts), 2)
        for prompt in reviewer_prompts:
            self.assertEqual(prompt.count("handoff:"), 1)
            self.assertEqual(prompt.count("Review scope (this round):"), 1)
            self.assertIn("Handoff:\nhandoff:\n  files:\n    - path: app.py", prompt)
            self.assertIn("phase: 2", prompt)
            scope_text = prompt.split("Review scope (this round):")[1].split("Handoff:")[0]
            scope_text = scope_text.replace("owned files:", "")
            for label in ("files:", "tests-run:", "flagged:", "plan_change:", "prior-issues:"):
                self.assertNotIn(label, scope_text)

    def test_ask_change_marker_splits_question_from_change(self):
        ask_review = ("## Fix\nNone\n\n## Ask\n- `app.py:3` the limit is fixed — should it be configurable? — "
                      "change: read the limit from settings\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": ask_review}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        ask = packet["ask"][0]
        self.assertEqual(ask["question"], "`app.py:3` the limit is fixed — should it be configurable?")
        self.assertEqual(ask["change"], "read the limit from settings")

    def test_a_class_closure_with_open_members_sends_one_more_coder_and_ends_converged(self):
        open_member = "`app.py:4` the same limit is wrong here too"
        closure = json.dumps({"receipt": "one member still open", "open": [open_member]})

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": closure}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["iter"]), ("converged", 4))
        self.assertEqual(packet["open_classes"], [])
        self.assertIn(open_member, [entry["finding"] for entry in packet["fixed"]])
        self.assertNotIn("still open", packet["class_closure"])
        self.assertIn("the class repair fixed these class members", packet["class_closure"])
        self.assertIn(open_member, packet["class_closure"])
        self.assertFalse(self.stored_packet()[0]["unreviewed_fix"])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 2)
        metrics = fake_ledger.recorded_rows(self.env, "review_metrics")
        self.assertEqual(metrics[0]["fixed"], "2")

    def test_the_class_closure_prompt_names_one_diff_file_per_path_and_holds_no_diff_text(self):
        (self.repo / "generated").mkdir()
        self.commit_files({"generated/snapshot.json": "{}\n"})
        # The snapshot is part of the change under review, so the fix pass may rewrite it.
        (self.repo / "generated/snapshot.json").write_text("{ }\n")
        snapshot = "".join(f'{{"row": {number}, "marker": "SNAPSHOT-LINE"}}\n' for number in range(20000))
        self.assertGreater(len(snapshot), 400_000)

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "generated/snapshot.json": snapshot}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        closure_prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "closure")
        self.assertLess(len(closure_prompt), 6000)
        self.assertNotIn("SNAPSHOT-LINE", closure_prompt)
        self.assertNotIn("limit = 20", closure_prompt)

        diff_files = sorted((self.state_dir / "loop-script" / AGENT_ID / "fix-diffs").rglob("*.diff"))
        self.assertEqual([path.name for path in diff_files], ["app.py.diff", "snapshot.json.diff"])
        app_diff_file = diff_files[0]
        self.assertIn("-limit = 2", app_diff_file.read_text())
        self.assertIn(f"- app.py (+2 -2): {app_diff_file}", closure_prompt)
        self.assertIn("- generated/snapshot.json (+20000 -1): regenerated, do not read", closure_prompt)
        self.assertNotIn(str(diff_files[1]), closure_prompt)

    def test_a_class_closure_reply_with_braces_in_its_prose_still_reads_the_closing_object(self):
        closure = f"Closed. Every `{{CUBE}}.flag` site re-read.\n\n```json\n{CLOSED}\n```"

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": closure}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertIn("one exit, all re-read", packet["class_closure"])

    def test_a_disposition_reply_with_braces_in_its_prose_still_reads_the_findings_object(self):
        finding = "`app.py:2` the limit is 5, should be 20"
        disposition = ('Kept the {fix} placeholder as written.\n\n'
                       + json.dumps({"fix": [finding], "ask": [], "nit": []}))

        completed = self.run_script({
            "code-reviewer": [{"result": "The limit looks wrong."}, {"result": CLEAN_REVIEW}],
            "disposition": [{"result": disposition}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertIn(finding, [entry["finding"] for entry in packet["fixed"]])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 1)

    def disposition_calls_with(self, replies):
        """Runs disposition_call against canned replies; returns (module, calls as (role, prompt), outcome)."""
        module = self.load_script_module()
        calls = []
        queued = list(replies)

        def claude_call(role, prompt, *args, **kwargs):
            calls.append((role, prompt))
            return queued.pop(0)

        with mock.patch.object(module, "claude_call", claude_call):
            try:
                outcome = module.disposition_call("reviewer text", self.repo, self.scratch)
            except review_loop_findings.ReplyShapeError as error:
                outcome = error
        return calls, outcome

    def test_a_bad_disposition_reply_then_a_good_one_retries_once_and_returns_the_findings(self):
        bad = "x" * 300
        good = json.dumps({"fix": ["`app.py:2` the limit is wrong"], "ask": [], "nit": []})

        calls, findings = self.disposition_calls_with([bad, good])

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(findings["fix"]), 1)
        retry_prompt = calls[1][1]
        self.assertTrue(retry_prompt.startswith(calls[0][1]))
        self.assertIn("A previous reply to this prompt could not be used: ", retry_prompt)
        self.assertIn("JSON object only", retry_prompt)
        note = retry_prompt[len(calls[0][1]):]
        self.assertIn("x" * 100, note)
        self.assertNotIn("x" * 200, note)

    def test_two_bad_disposition_replies_raise_the_reply_shape_error(self):
        calls, outcome = self.disposition_calls_with(["no object here", "still none"])

        self.assertEqual(len(calls), 2)
        self.assertIsInstance(outcome, review_loop_findings.ReplyShapeError)
        self.assertIn("still none", str(outcome))

    def test_the_disposition_retry_runs_under_its_own_role(self):
        calls, _ = self.disposition_calls_with(["no object", json.dumps({"fix": [], "ask": [], "nit": []})])

        self.assertEqual([role for role, _ in calls], ["disposition", "disposition-retry"])

    def test_a_round_goes_on_after_one_unparseable_disposition_reply(self):
        finding = "`app.py:2` the limit is 5, should be 20"
        good = json.dumps({"fix": [finding], "ask": [], "nit": []})

        completed = self.run_script({
            "code-reviewer": [{"result": "The limit looks wrong."}, {"result": CLEAN_REVIEW}],
            "disposition": [{"result": "not json"}, {"result": good}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual([call["key"] for call in self.fake_calls()].count("disposition"), 2)

    def coder_impact_packet(self, report):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": report, "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        return self.stored_packet()[1]

    def test_a_coder_report_of_plan_impact_is_recorded_and_the_loop_still_reviews_again(self):
        report = "Fixed 1 but it needs a new column the plan rules out.\nplan-impact: yes"

        packet = self.coder_impact_packet(report)

        self.assertEqual(packet["status"], "converged")
        self.assertEqual([call["key"] for call in self.fake_calls()].count("code-reviewer"), 2)
        self.assertEqual(len(packet["plan_impacts"]), 1)
        self.assertIn("needs a new column", packet["plan_impacts"][0]["text"])
        self.assertEqual(packet["plan_impacts"][0]["gate"], "coder")
        self.assertTrue(packet["plan_impacts"][0]["ac_change"])
        self.assertFalse(packet["plan_impacts"][0]["adopted"])

    def test_a_coder_plan_impact_report_with_no_edits_keeps_the_finding_open_and_applies_nothing(self):
        report = "Cannot fix 1: it needs a new column the plan rules out.\nplan-impact: yes"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": report}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["skipped_fp"], [])
        self.assertEqual([entry["finding"] for entry in packet["findings_remaining"]],
                         ["`app.py:2` the limit is wrong for `limit`"])
        self.assertIs(packet["plan_impacts"][0]["applied"], False)
        self.assertEqual([row["actioned"] for row in self.finding_rows() if row["iter"] == "1"], ["none"])

    def test_a_held_finding_the_next_round_re_reports_and_the_coder_fixes_leaves_the_open_list(self):
        report = "Cannot fix 1: it needs a new column the plan rules out.\nplan-impact: yes"
        rewordings = {
            "same wording": "`app.py:2` the limit is wrong for `limit`",
            "slightly different wording": "`app.py:2` the limit is wrong for `limit` here",
        }
        for number, (name, finding) in enumerate(rewordings.items()):
            with self.subTest(name):
                self.reset_fake_run()
                # Code, not a comment: a fix pass that adds only a comment line is judged by the comment rules.
                fixed_source = APP_FIXED + f"edit_{number} = 1\n"
                second_review = f"## Fix\n- {finding}\n\n## Ask\nNone\n\n## Nit\nNone\n"
                completed = self.run_script({
                    "code-reviewer": [{"result": FIX_REVIEW}, {"result": second_review}, {"result": CLEAN_REVIEW}],
                    "coder": [{"result": report}, {"result": "Fixed 1.", "edits": {"app.py": fixed_source}}],
                    "closure": [{"result": CLOSED}],
                })

                self.assertEqual(completed.returncode, 0, completed.stderr)
                _, packet = self.stored_packet()
                self.assertEqual(packet["findings_remaining"], [])
                self.assertEqual(len(packet["fixed"]), 1)

    def test_fixing_a_different_finding_in_the_same_file_keeps_the_held_finding_open(self):
        report = "Cannot fix 1: it needs a new column the plan rules out.\nplan-impact: yes"
        second_review = "## Fix\n- `app.py:5` the timeout is never read\n\n## Ask\nNone\n\n## Nit\nNone\n"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": second_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": report}, {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([entry["finding"] for entry in packet["findings_remaining"]],
                         ["`app.py:2` the limit is wrong for `limit`"])

    def test_a_finding_skipped_beside_an_impact_that_is_not_held_is_a_plain_skip_not_an_open_fix(self):
        reports = {
            "adopted": "Skipped 1: the limit is right.\nPLAN-IMPACT:\n  assumed: a column\n  found: none\n"
                       "  cause: plan\n  acceptance_criteria: none\nplan-impact: yes",
            "toolkit": "Skipped 1: the limit is right.\nPLAN-IMPACT:\n  assumed: the gate checks it\n"
                       "  found: its base is old\n  cause: toolkit\nplan-impact: yes",
        }
        for name, report in reports.items():
            with self.subTest(name):
                self.reset_fake_run()
                completed = self.run_script({
                    "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
                    "coder": [{"result": report}],
                    "closure": [{"result": CLOSED}],
                })

                self.assertEqual(completed.returncode, 0, completed.stderr)
                _, packet = self.stored_packet()
                self.assertEqual(packet["findings_remaining"], [])
                self.assertEqual(len(packet["skipped_fp"]), 1)
                self.assertEqual(handback.held_plan_impacts(packet), [])

    def test_a_coder_plan_impact_block_with_no_criterion_change_and_a_plan_cause_is_adopted_by_rule(self):
        report = ("Fixed 1.\nPLAN-IMPACT:\n  assumed: a column\n  found: none\n  cause: plan\n"
                  "  acceptance_criteria: none\nplan-impact: yes")

        packet = self.coder_impact_packet(report)

        self.assertEqual(packet["status"], "converged")
        self.assertEqual([(entry["ac_change"], entry["adopted"], entry["cause"]) for entry in packet["plan_impacts"]],
                         [(False, True, "plan")])
        self.assertTrue(packet["plan_impacts"][0]["text"].startswith("PLAN-IMPACT:"))

    def test_a_coder_plan_impact_of_a_toolkit_cause_is_recorded_with_its_cause_and_never_adopted(self):
        report = ("Fixed 1.\nPLAN-IMPACT:\n  assumed: the gate checks it\n  found: its base is old\n"
                  "  cause: toolkit\n  acceptance_criteria: none\nplan-impact: yes")

        packet = self.coder_impact_packet(report)

        self.assertEqual(packet["status"], "converged")
        self.assertEqual([(entry["cause"], entry["adopted"]) for entry in packet["plan_impacts"]],
                         [("toolkit", False)])

    def test_a_stray_cause_line_outside_the_plan_impact_block_is_not_the_impact_cause(self):
        report = ("Skipped 2: cause: toolkit is not what broke here.\nFixed 1.\n"
                  "PLAN-IMPACT:\n  assumed: a column\n  found: none\n  cause: plan\nplan-impact: yes")

        packet = self.coder_impact_packet(report)

        self.assertEqual([entry["cause"] for entry in packet["plan_impacts"]], ["plan"])


    def test_a_coder_plan_impact_with_no_cause_line_is_held_and_a_reviewer_ask_reads_as_plan(self):
        report = ("Fixed 1.\nPLAN-IMPACT:\n  assumed: a column\n  found: none\nplan-impact: yes")

        packet = self.coder_impact_packet(report)

        self.assertEqual(packet["status"], "converged")
        self.assertEqual([(entry["cause"], entry["adopted"]) for entry in packet["plan_impacts"]],
                         [(plan_format.NO_CAUSE_LINE, False)])
        self.assertEqual(packet["plan_impacts"], handback.held_plan_impacts(packet))

        ask_review = f"## Fix\nNone\n\n## Ask\n- {PLAN_CHANGE_STATUS}: the fix needs a new column\n\n## Nit\nNone\n"
        self.reset_fake_run()
        self.run_script({"code-reviewer": [{"result": ask_review}]})
        self.assertEqual([entry["cause"] for entry in self.stored_packet()[1]["plan_impacts"]], ["plan"])

    RESOLVED_FOOTER = ("    plan_impact: RESOLVED - Adopt plan change.\n    carried-findings:\n"
                       f"      - plan impact: `app.py:3` [plan-drift] {PLAN_CHANGE_STATUS}: the fix needs a new column "
                       "the plan rules out\n")

    def held_ask_review(self, location="`app.py:3`"):
        return ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n\n## Ask\n"
                f"- {location} [plan-drift] {PLAN_CHANGE_STATUS}: the fix needs a new column the plan rules out\n\n"
                "## Nit\nNone\n")

    def test_a_plan_impact_ask_never_stops_the_loop_and_the_round_s_fixes_still_run(self):
        completed = self.run_script({
            "code-reviewer": [{"result": self.held_ask_review()}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["iter"], 2)
        self.assertEqual([entry["finding"] for entry in packet["fixed"]], ["`app.py:2` the limit is wrong for `limit`"])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("code-reviewer"), 2)
        coder_prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertNotIn("needs a new column", coder_prompt)
        self.assertEqual(packet["ask"], [])
        self.assertEqual([(entry["ac_change"], entry["adopted"], entry["cause"]) for entry in packet["plan_impacts"]],
                         [(True, False, "plan")])
        self.assertIn("needs a new column", packet["plan_impacts"][0]["text"])

    def test_a_plan_impact_ask_reads_the_same_with_a_line_range_or_a_list_of_ranges(self):
        for location in ("`app.py:3`", "`app.py:3-5`", "`app.py:3\N{EN DASH}5`", "`app.py:3-5,8-9`"):
            with self.subTest(location):
                self.reset_fake_run()

                completed = self.run_script({
                    "code-reviewer": [{"result": self.held_ask_review(location)}, {"result": CLEAN_REVIEW}],
                    "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
                    "closure": [{"result": CLOSED}],
                })

                self.assertEqual(completed.returncode, 0, completed.stderr)
                _, packet = self.stored_packet()
                self.assertEqual(packet["status"], "converged")
                self.assertEqual([entry["ac_change"] for entry in packet["plan_impacts"]], [True])
                self.assertEqual(packet["ask"], [])
                self.assertEqual([call["key"] for call in self.fake_calls()].count("code-reviewer"), 2)

    def test_a_plan_impact_ask_that_changes_no_criterion_is_adopted_and_fixed_in_the_same_round(self):
        adopted_ask = ("## Fix\nNone\n\n## Ask\n- `app.py:2` [plan-drift] "
                       f"{PLAN_CHANGE_STATUS}: the limit is wrong for `limit`; acceptance_criteria: none\n\n"
                       "## Nit\nNone\n")

        completed = self.run_script({
            "code-reviewer": [{"result": adopted_ask}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual([(entry["ac_change"], entry["adopted"]) for entry in packet["plan_impacts"]],
                         [(False, True)])
        coder_prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("the limit is wrong", coder_prompt)
        self.assertEqual(packet["ask"], [])
        self.assertIn("the limit is wrong", " ".join(entry["finding"] for entry in packet["fixed"]))

    def test_a_resolved_handoff_makes_a_plan_marked_item_a_plain_fix(self):
        completed = self.run_script({
            "code-reviewer": [{"result": self.held_ask_review()}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 2.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, footer=self.RESOLVED_FOOTER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["plan_impacts"], [])
        self.assertEqual(packet["ask"], [])
        coder_prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("needs a new column", coder_prompt)

    def test_a_resolved_block_handoff_makes_a_plan_marked_item_a_plain_fix(self):
        disagreement = (f"`app.py:3` [plan-drift] {PLAN_CHANGE_STATUS}: the fix needs a new column the plan rules out")
        block = ("RESOLVED: the user ruled on this disagreement. Review the code against the ruling.\n"
                 "Decision: Adopt plan change\nThe ruling:\n  add the column\nPLAN-IMPACT:\n"
                 f"  {disagreement}")
        footer = "    plan_impact: |\n" + "".join(f"      {line}\n" for line in block.splitlines())

        completed = self.run_script({
            "code-reviewer": [{"result": self.held_ask_review()}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 2.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, footer=footer)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["plan_impacts"], [])
        coder_prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("needs a new column", coder_prompt)

    RULED_FINDING = ("app.py:2 [plan-drift] PLAN-IMPACT: the reworded AC2 is narrower than the ticket. "
                     "Question for the user: do you accept AC2? acceptance_criteria: AC2.")
    USER_RULED_HEADER = "user-ruled: 1\nuser-ruled-at: 2026-11-13 11:32:00Z\n"
    CODER_IMPACT_ON_AC2 = ("SKIPPED 1: needs the user's sign-off.\nPLAN-IMPACT:\n  assumed: AC2 as written\n"
                           "  found: the reword is narrower\n  cause: plan\n  acceptance_criteria: AC2\n"
                           "plan-impact: yes")
    REVIEWER_IMPACT_ON_AC2 = ("## Fix\nNone\n\n## Ask\n- `app.py:2` [plan-drift] PLAN-IMPACT: the reword of AC2 "
                              "is narrower than the ticket. acceptance_criteria: AC2\n\n## Nit\nNone\n")

    def run_ruled_fix(self, header_extra):
        return self.run_script({
            "coder": [{"result": self.CODER_IMPACT_ON_AC2, "edits": {"app.py": APP_FIXED}}, {"result": "Fixed 1."}],
            "code-reviewer": [{"result": self.REVIEWER_IMPACT_ON_AC2}, {"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header(self.RULED_FINDING) + header_extra)

    def test_a_user_ruled_finding_reaches_the_fix_coder_marked_with_the_ruling_time(self):
        completed = self.run_ruled_fix(self.USER_RULED_HEADER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        issues = self.fake_calls()[0]["prompt"].partition("## Issues")[2]
        self.assertIn("[accepted by the user, ruled 2026-11-13 11:32:00Z]", issues)

    def test_a_long_user_ruled_finding_keeps_its_marker_in_the_issue_the_coder_reads(self):
        long_finding = self.RULED_FINDING + " " + "The reword drops the second clause of the ticket. " * 8
        self.assertGreater(len(long_finding), 240)

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header(long_finding) + self.USER_RULED_HEADER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        issues = self.fake_calls()[0]["prompt"].partition("## Issues")[2]
        self.assertIn("[accepted by the user, ruled 2026-11-13 11:32:00Z]", issues)

    def test_a_finding_the_user_did_not_rule_on_is_not_marked(self):
        completed = self.run_ruled_fix("")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("accepted by the user", self.fake_calls()[0]["prompt"])

    def test_a_user_ruled_line_with_no_time_stops_the_run(self):
        completed = self.run_ruled_fix("user-ruled: 1\n")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("expected `user-ruled-at: <time>`", completed.stderr + completed.stdout)

    def test_only_the_ruled_finding_of_two_carries_the_marker(self):
        other = "app.py:5 [bug] the limit is off by one."
        header = self.findings_header(self.RULED_FINDING, other) + self.USER_RULED_HEADER

        completed = self.run_script({
            "coder": [{"result": "Fixed 2.", "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=header)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        issues = self.fake_calls()[0]["prompt"].partition("## Issues")[2]
        marked = [line for line in issues.splitlines() if "accepted by the user" in line]
        self.assertEqual(len(marked), 1, marked)
        self.assertIn("AC2", marked[0])

    def test_a_coder_plan_impact_on_the_criterion_of_an_accepted_finding_is_still_held(self):
        completed = self.run_script({
            "coder": [{"result": self.CODER_IMPACT_ON_AC2, "edits": {"app.py": APP_FIXED}}, {"result": "Fixed 1."}],
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header(self.RULED_FINDING) + self.USER_RULED_HEADER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([(entry["gate"], entry["adopted"], entry["settled"]) for entry in packet["plan_impacts"]],
                         [("coder", False, False)])
        self.assertEqual(len(handback.held_plan_impacts(packet)), 1)

    def test_a_coder_plan_impact_a_handoff_ruling_settles_is_adopted_settled_and_not_held(self):
        disagreement = (f"`app.py:3` [plan-drift] {PLAN_CHANGE_STATUS}: the fix needs a new column the plan rules "
                        "out. acceptance_criteria: AC2")
        block = ("RESOLVED: the user ruled on this disagreement. Review the code against the ruling.\n"
                 "Decision: Adopt plan change\nThe ruling:\n  add the column\nPLAN-IMPACT:\n"
                 f"  {disagreement}")
        footer = "    plan_impact: |\n" + "".join(f"      {line}\n" for line in block.splitlines())
        coder_impact = ("Fixed 1.\nPLAN-IMPACT:\n  assumed: no new column\n"
                        "  found: the fix needs a new column the plan rules out\n  cause: plan\n"
                        "  acceptance_criteria: AC2\nplan-impact: yes")

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": coder_impact, "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, footer=footer)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        coder_entries = [entry for entry in packet["plan_impacts"] if entry["gate"] == "coder"]
        self.assertEqual([(entry["adopted"], entry["settled"]) for entry in coder_entries], [(True, True)])
        self.assertEqual(handback.held_plan_impacts(packet), [])

    def test_a_reviewer_plan_impact_on_a_ruled_criterion_goes_to_the_coder_not_the_asks(self):
        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Fixed 1."}],
            "code-reviewer": [{"result": self.REVIEWER_IMPACT_ON_AC2}, {"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header(self.RULED_FINDING) + self.USER_RULED_HEADER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["plan_impacts"], [])
        self.assertEqual(packet["ask"], [])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 2)

    def test_an_unmarked_plan_drift_ask_on_a_ruled_criterion_is_not_asked_again(self):
        drift_ask = ("## Fix\nNone\n\n## Ask\n- `app.py:2` [plan-drift] does AC2 still hold for deletes? "
                     "acceptance_criteria: AC2\n\n## Nit\nNone\n")

        completed = self.run_script({
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "code-reviewer": [{"result": drift_ask}, {"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra=self.findings_header(self.RULED_FINDING) + self.USER_RULED_HEADER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])

    def test_a_plan_drift_ask_beside_a_plan_impact_on_one_criterion_logs_no_ask_row(self):
        both = ("## Fix\nNone\n\n## Ask\n"
                "- `app.py:2` [plan-drift] PLAN-IMPACT: the reword of AC2 is narrower than the ticket. "
                "acceptance_criteria: AC2\n"
                "- `app.py:5` [plan-drift] does AC2 still hold for deletes? acceptance_criteria: AC2\n\n"
                "## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": both}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        dropped_drift = [entry for entry in packet["dropped_asks"] if "still hold for deletes" in entry]
        self.assertEqual(len(dropped_drift), 1, packet["dropped_asks"])
        ask_rows = [row for row in self.finding_rows() if row["disposition"] == "ask"]
        self.assertEqual([row for row in ask_rows if "still hold for deletes" in str(row)], [], ask_rows)

    def test_the_same_plan_impacts_are_held_when_the_user_ruled_on_nothing(self):
        completed = self.run_ruled_fix("")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([entry["gate"] for entry in packet["plan_impacts"]], ["coder", "code-reviewer"])

    def test_a_user_ruled_line_that_names_no_finding_stops_the_run(self):
        completed = self.run_ruled_fix("user-ruled: 4\nuser-ruled-at: 2026-11-13 11:32:00Z\n")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("user-ruled", completed.stderr + completed.stdout)

    def test_a_user_ruled_word_that_is_no_finding_number_stops_the_run_naming_the_word(self):
        words = {"letters": "abc", "negative": "-1", "non-ascii digit": "٣", "zero": "0"}
        for label, word in words.items():
            with self.subTest(label):
                completed = self.run_ruled_fix(f"user-ruled: {word}\nuser-ruled-at: 2026-11-13 11:32:00Z\n")

                self.assertNotEqual(completed.returncode, 0, label)
                self.assertIn(f"holds {word!r}", completed.stderr + completed.stdout)

    def test_a_plan_impact_first_raised_after_the_ruling_is_held_and_never_sent_to_the_coder(self):
        new_impact = ("## Fix\nNone\n\n## Ask\n- `app.py:7` [plan-drift] "
                      f"{PLAN_CHANGE_STATUS}: the tenant table needs a shard key\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": new_impact}]}, footer=self.RESOLVED_FOOTER)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([(entry["ac_change"], entry["adopted"]) for entry in packet["plan_impacts"]],
                         [(True, False)])
        self.assertNotIn("coder", [call["key"] for call in self.fake_calls()])

    def test_a_plan_impact_ask_with_no_fix_in_the_round_converges_and_holds_the_impact(self):
        ask_only = f"## Fix\nNone\n\n## Ask\n- {PLAN_CHANGE_STATUS}: the fix needs a new column\n\n## Nit\nNone\n"

        completed = self.run_script({"code-reviewer": [{"result": ask_only}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual([call["key"] for call in self.fake_calls()], ["code-reviewer"])
        self.assertEqual(len(packet["plan_impacts"]), 1)
        self.assertEqual(packet["ask"], [])

    def test_a_plan_impact_ask_carries_beside_the_round_s_asks_and_design_items(self):
        plan_change = ("## Fix\n- `app.py:3` [design-decision] pick one owner for the limits\n\n## Ask\n"
                       f"- {PLAN_CHANGE_STATUS}: the fix needs a new column\n"
                       "- `app.py:1` should the limit be configurable? — change: read it from the config\n\n"
                       "## Nit\nNone\n")
        later = ("## Fix\n- `app.py:4` [design-decision] split the limits module\n\n## Ask\n"
                 "- `app.py:5` should the cap be per tenant? — change: key the cap by tenant\n\n## Nit\nNone\n")
        (self.repo / "fresh.py").write_text("created = True\n")

        completed = self.run_script({"code-reviewer": [{"result": plan_change}] * 2,
                                     "smell-reviewer": [{"result": later}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertIn("needs a new column", packet["plan_impacts"][0]["text"])
        questions = " | ".join(entry["question"] for entry in packet["ask"])
        for carried in ("pick one owner for the limits", "should the limit be configurable?",
                        "split the limits module", "should the cap be per tenant?"):
            self.assertIn(carried, questions)
        self.assertNotIn("needs a new column", questions)

    def test_a_design_decision_with_a_plan_impact_mark_is_held_and_does_not_stop_the_loop(self):
        design_plan_change = ("## Fix\n- `app.py:3` [design-decision] plan-impact: the owner moves to a new table\n\n"
                              "## Ask\nNone\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": design_plan_change}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertIn("the owner moves to a new table", packet["plan_impacts"][0]["text"])
        self.assertEqual(packet["ask"], [])

    def test_a_fix_fixed_in_a_round_that_also_held_a_plan_impact_is_counted_fixed(self):
        re_report = ("## Fix\nNone\n\n## Ask\n"
                     f"- {PLAN_CHANGE_STATUS}: the fix needs a new column\n\n## Nit\nNone\n")

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": re_report}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual([entry["finding"] for entry in packet["fixed"]], ["`app.py:2` the limit is wrong for `limit`"])
        self.assertEqual(packet["findings_remaining"], [])
        self.assertEqual(len(packet["plan_impacts"]), 1)

    def test_the_same_plan_impact_from_two_reviewers_is_one_impact(self):
        impact = f"## Fix\nNone\n\n## Ask\n- {PLAN_CHANGE_STATUS}: the fix needs a new column\n\n## Nit\nNone\n"
        (self.repo / "fresh.py").write_text("created = True\n")

        completed = self.run_script({"code-reviewer": [{"result": impact}] * 2,
                                     "smell-reviewer": [{"result": impact}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(len(packet["plan_impacts"]), 1)

    def test_a_merged_finding_keeps_each_part_with_its_own_line(self):
        first = finding_record.parse_finding("`app.py:2` the limit is wrong for `limit`")
        second = finding_record.parse_finding("`app.py:9` `limit` has no upper bound")
        third = finding_record.parse_finding("`app.py:14` `limit` is unchecked")
        other_file = finding_record.parse_finding("`other.py:1` `limit` is read twice")

        merged = review_loop_findings.merge_findings([first, second, other_file, third])

        self.assertEqual(len(merged), 2)
        self.assertEqual([(part.path, part.line) for part in merged[0].parts],
                         [("app.py", 2), ("app.py", 9), ("app.py", 14)])
        self.assertEqual([part.parts for part in merged[0].parts], [(), (), ()])
        self.assertEqual(merged[0].text, f"{first.text} Also reported: {second.text} Also reported: {third.text}")
        self.assertEqual(merged[1], other_file)

    def test_code_identifiers_skip_file_paths_and_file_line_pointers(self):
        cases = {
            "`src/app.py` and `limit`": {"limit"},
            "`app.py:3`": set(),
            "`config.json`": set(),
            "`README.md:~40` and `limit`": {"limit"},
            "`load(path.json)`": {"load(path.json)"},
            "`vc.tree_fingerprint`": {"vc.tree_fingerprint"},
            "`script_utils.first_location`": {"script_utils.first_location"},
        }

        for text, expected in cases.items():
            with self.subTest(text):
                self.assertEqual(finding_record.code_identifiers(text), frozenset(expected))

    def test_a_finding_on_a_scoped_package_path_keeps_its_at_sign(self):
        text = "`@scope/pkg/file.ts:12-14` the limit is wrong"

        finding = finding_record.parse_finding(text)

        self.assertEqual((finding.path, finding.line), ("@scope/pkg/file.ts", 12))
        self.assertEqual(finding.title, "the limit is wrong")
        self.assertEqual(handback.entry_locations({"finding": text}), [(finding.path, finding.line)])

    def test_the_same_ask_from_two_reviewers_is_one_ask(self):
        same_ask = "- `app.py:1` should the limit be configurable? — change: read it from the config\n"
        first = f"## Fix\nNone\n\n## Ask\n{same_ask}\n## Nit\nNone\n"
        plan_change_ask = f"- {PLAN_CHANGE_STATUS}: the fix needs a new column\n"
        later = f"## Fix\nNone\n\n## Ask\n{same_ask}{plan_change_ask}\n## Nit\nNone\n"
        (self.repo / "fresh.py").write_text("created = True\n")

        completed = self.run_script({"code-reviewer": [{"result": first}] * 2,
                                     "smell-reviewer": [{"result": later}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual([entry["question"] for entry in packet["ask"]],
                         ["`app.py:1` should the limit be configurable?"])
        shared_ask_rows = [row for row in self.finding_rows()
                           if row["disposition"] == "ask" and row.get("line") == "1"]
        self.assertEqual(len(shared_ask_rows), 1)

    def test_a_coder_report_of_plan_impact_keeps_the_fixes_it_applied_and_the_loop_goes_on(self):
        two_fixes = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                     "- `app.py:4` the fourth value has no test\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                     "Overall Assessment: NEEDS CHANGES\n")
        report = "SKIPPED 2: it needs a new column the plan rules out.\nplan-impact: yes"

        completed = self.run_script({
            "code-reviewer": [{"result": two_fixes}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": report, "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual([entry["finding"] for entry in packet["fixed"]], ["`app.py:2` the limit is wrong for `limit`"])
        self.assertEqual([row["actioned"] for row in self.finding_rows() if row["line"] == "4"], ["none"])
        self.assertEqual(len(packet["plan_impacts"]), 1)
        self.assertTrue(packet["plan_impacts"][0]["applied"])
        self.assertEqual([e["finding"] for e in packet["findings_remaining"]],
                         ["`app.py:4` the fourth value has no test"])
        self.assertEqual(packet["skipped_fp"], [])
        self.assertIn("app.py", packet["files_touched"])

    def test_a_crash_after_a_fix_round_keeps_the_fixed_finding_in_the_crash_packet(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
        })

        self.assertNotEqual(completed.returncode, 0)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual([entry["file_line"] for entry in packet["fixed"]], ["app.py:2"])

    def test_an_ask_with_an_empty_change_asks_its_question_as_the_change(self):
        ask_review = ("## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit be configurable? — change:\n\n"
                      "## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": ask_review}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        ask = packet["ask"][0]
        question = "`app.py:3` should the limit be configurable?"
        self.assertEqual((ask["question"], ask["change"]), (question, question))

    def test_prose_that_mentions_a_quality_check_does_not_name_the_check_command(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="Run a quality check before you push; `false` is not it.\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertTrue(packet["full_check"].startswith("not run (no check found"), packet["full_check"])

    def test_child_calls_do_not_inherit_the_terminal_pane_variables(self):
        for name in ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH", "TUIOS_SOCKET"):
            self.env[name] = "set"

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.fake_calls()
        self.assertTrue(calls)
        for call in calls:
            self.assertEqual(set(call["pane_env"].values()), {None})

    def test_each_child_session_is_named_as_a_child_of_the_session_that_ran_the_loop(self):
        sessions = self.scratch / "home" / ".claude" / "sessions"
        sessions.mkdir(parents=True)
        live_row = {"pid": os.getpid(), "sessionId": SESSION, "name": "app-abc-12-e6"}
        (sessions / "4242.json").write_text(json.dumps(live_row))
        (sessions / "4343.json").write_text(json.dumps({"pid": 4343, "sessionId": "other", "name": "app-abc-12-9f"}))

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call["name"] for call in self.fake_calls()],
                         ["child of app-abc-12-e6 (review1-code-reviewer)"])

    def test_a_child_session_whose_parent_is_not_registered_is_named_by_the_parent_session_id(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call["name"] for call in self.fake_calls()],
                         [f"child of session {SESSION} (review1-code-reviewer)"])

    def assert_every_headless_role_is_named_as_a_child_of(self, label):
        finding = "`app.py:2` the limit is 5, should be 20"
        scenario = {
            "code-reviewer": [{"result": "The limit looks wrong."}, {"result": CLEAN_REVIEW},
                              {"result": CLEAN_REVIEW}],
            "smell-reviewer": [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "test-reviewer": [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "disposition": [{"result": "not json"},
                            {"result": json.dumps({"fix": [finding], "ask": [], "nit": []})}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_FIXED + "limit = 7\n"}}],
            "closure": [{"result": '{"receipt": "one site left", "open": ["app.py:4 - same limit - fix it"]}'}],
        }
        roles = ["review1-code-reviewer", "disposition", "disposition-retry", "coder1",
                 "class-closure", "coder-class"]

        completed = self.run_script(scenario, quality_check="test -f app.py")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        launched = {call["name"] for call in self.fake_calls()}
        for role in roles:
            self.assertIn(f"child of {label} ({role})", launched)
        for name in launched:
            self.assertTrue(name.startswith(f"child of {label} ("), name)

    def test_every_headless_role_is_named_as_a_child_of_a_parent_that_has_a_display_name(self):
        sessions = self.scratch / "home" / ".claude" / "sessions"
        sessions.mkdir(parents=True)
        live_row = {"pid": os.getpid(), "sessionId": SESSION, "name": "app-abc-12-e6"}
        (sessions / "4242.json").write_text(json.dumps(live_row))

        self.assert_every_headless_role_is_named_as_a_child_of("app-abc-12-e6")

    def test_every_headless_role_is_named_as_a_child_of_a_parent_that_has_no_display_name(self):
        self.assert_every_headless_role_is_named_as_a_child_of(f"session {SESSION}")

    def test_the_gate_env_of_the_prompt_reaches_the_full_check_and_the_coder_brief(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, quality_check='test "$GATE_TEST_FLAG" = on', footer="gate-env: GATE_TEST_FLAG=on\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        coder_prompt = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("gate-env: GATE_TEST_FLAG=on", coder_prompt)

    def test_a_quoted_gate_env_value_with_a_space_reaches_the_full_check_whole(self):
        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
        }, quality_check='test "$A" = 1 && test "$B" = "x y"', footer="gate-env: A=1 B='x y'\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")

    def test_a_bulleted_quality_check_line_in_claude_md_needs_no_check_finder(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="- Quality check: `true`\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertNotIn("check-finder", [call["key"] for call in self.fake_calls()])

    def test_a_repo_whose_full_suite_runs_in_ci_converges_on_its_declared_check_with_no_tests(self):
        repos = [("Quality check: `true`\nFull suite: CI\n", "passed (check only; CI runs the full suite)"),
                 ("- Full suite: CI\n", "not run (CI)")]
        for claude_md, full_check_result in repos:
            with self.subTest(claude_md=claude_md):
                self.reset_fake_run()

                completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]}, claude_md=claude_md)

                self.assertEqual(completed.returncode, 0, completed.stderr)
                _, packet = self.stored_packet()
                self.assertEqual((packet["status"], packet["full_check"]), ("converged", full_check_result))
                self.assertEqual([call["key"] for call in self.fake_calls()], ["code-reviewer"])

    def test_a_check_only_pass_in_a_ci_repo_runs_the_scoped_tests(self):
        self.save_gate_commands(["grep -q 'limit = 99' app.py"])

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="Quality check: `true`\nFull suite: CI\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["full_check"], "passed (check only; CI runs the full suite)")
        scoped_tests = packet["scoped_tests"]
        self.assertTrue(scoped_tests.startswith("failed: grep -q 'limit = 99' app.py"), scoped_tests)

    def test_a_full_check_that_exits_zero_with_no_runner_summary_is_unverified_and_gets_no_repair(self):
        check = "echo 496 tests registered"

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]}, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check"], "unverified (exit 0, no test result shown)")
        self.assertEqual((packet["full_check_command"], packet["full_check_summary"]), (check, "not found"))
        self.assertNotIn("coder", [call["key"] for call in self.fake_calls()])

    def test_a_passed_full_check_puts_the_command_and_the_runner_summary_in_the_packet(self):
        check = "echo '4000 passed in 41.2s'"

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]}, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["full_check"], "passed")
        self.assertEqual((packet["full_check_command"], packet["full_check_summary"]), (check, "4000 passed in 41.2s"))

    def test_files_a_check_rewrote_or_created_are_reported_and_never_reach_files_touched(self):
        check = "echo generated v2 > notes.py; echo built > made.txt; echo '2 passed in 1s'"

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]}, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual((packet["check_changed"], packet["check_created"]), (["notes.py"], ["made.txt"]))
        self.assertEqual(packet["files_touched"], [])
        self.assertEqual((self.repo / "notes.py").read_text(), "generated v2\n")

    def test_a_file_the_check_rewrote_over_edits_it_held_before_is_reported_and_counts_as_touched(self):
        check = "echo 'edited again' >> notes.py; echo '2 passed in 1s'"
        (self.repo / "notes.py").write_text("edited by the coder\n")

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}] * 2}, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["check_rewrote_edited"], ["notes.py"])
        self.assertEqual((packet["check_changed"], packet["files_touched"]), ([], ["notes.py"]))

    def test_a_file_the_first_failing_check_created_is_still_in_the_packet_after_the_repair_and_recheck(self):
        check = f"{FAILS_ONLY_WITH_THE_DIFF}echo built > made.txt; echo 'FAIL: test_x'; exit 1"

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Repaired.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(self.call_keys().count("coder"), 1)
        self.assertEqual(packet["check_created"], ["made.txt"])

    def test_a_failing_check_that_rewrote_a_tracked_file_leaves_it_out_of_the_repairs_files_touched(self):
        check = f"{FAILS_ONLY_WITH_THE_DIFF}echo generated v2 > notes.py; echo 'FAIL: test_x'; exit 1"

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Repaired.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual(packet["files_touched"], ["app.py"])
        self.assertEqual(packet["check_changed"], ["notes.py"])

    def test_a_file_the_check_rewrote_counts_as_touched_when_the_repair_coder_edits_it_too(self):
        check = f"{FAILS_ONLY_WITH_THE_DIFF}echo generated v2 > notes.py; echo 'FAIL: test_x'; exit 1"

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Repaired.", "edits": {"notes.py": "repaired by the coder\n"}},
                      {"result": "Repaired."}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["files_touched"], ["notes.py"])
        self.assertEqual(packet["check_rewrote_edited"], ["notes.py"])
        self.assertNotIn("notes.py", packet["check_changed"])

    def test_a_file_the_check_changed_and_a_repair_coder_then_edited_is_reported_as_edited_not_changed(self):
        check = (f"{FAILS_ONLY_WITH_THE_DIFF}if [ -f marker ]; then echo '2 passed in 1s'; else echo x > marker; "
                 "echo generated v2 > notes.py; echo 'FAIL: test_x'; exit 1; fi")

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Repaired.", "edits": {"notes.py": "repaired by the coder\n"}},
                      {"result": "Repaired."}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertIn("notes.py", packet["files_touched"])
        self.assertNotIn("notes.py", packet["check_changed"])
        self.assertIn("notes.py", packet["check_rewrote_edited"])

    def test_a_recheck_that_rewrites_a_file_an_earlier_run_changed_leaves_it_changed_when_no_coder_edited_it(self):
        check = (f"{FAILS_ONLY_WITH_THE_DIFF}echo run >> counter.txt; cp counter.txt notes.py; "
                 "echo 'FAIL: test_x'; exit 1")

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "coder": [{"result": "Repaired.", "edits": {"app.py": APP_FIXED}}, {"result": "Repaired."}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(self.call_keys().count("coder"), 1)
        self.assertEqual((self.repo / "counter.txt").read_text().splitlines(), ["run", "run"])
        self.assertEqual(packet["check_changed"], ["notes.py"])
        self.assertNotIn("notes.py", packet["check_rewrote_edited"])

    def test_a_full_check_past_its_limit_is_not_run_and_no_failure(self):
        loop_script = self.load_script_module()

        with mock.patch.object(loop_script.full_check_gate, "CHECK_TIMEOUT_SECONDS", 1):
            result, _tail, _details = loop_script.full_check_gate.run_full_check(self.repo, self.scratch, "sleep 30")

        self.assertEqual(result, "not run (timeout)")
        self.assertFalse(loop_script.full_check.is_failure(result))
        self.assertEqual(review_loop_calls.LIVE_CHILDREN, set())

    def test_sigterm_kills_the_process_group_of_a_running_claude_call(self):
        self.env["FAKE_CLAUDE_HANG"] = "1"
        (self.fake_dir / "scenario.json").write_text(json.dumps({"code-reviewer": [{"result": CLEAN_REVIEW}]}))
        prompt = self.scratch / "prompt.txt"
        prompt.write_text(self.prompt_file_text())
        script = subprocess.Popen(self.script_command(prompt), env=self.env, start_new_session=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(script.wait)
        grandchild_file = self.fake_dir / "grandchild.pid"
        deadline = time.time() + 20
        while not grandchild_file.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(grandchild_file.exists(), "the stand-in claude never started its grandchild")
        grandchild = int(grandchild_file.read_text())
        self.addCleanup(self.kill_quietly, grandchild)

        os.killpg(script.pid, signal.SIGTERM)
        script.wait(timeout=20)

        deadline = time.time() + 20
        while self.is_running(grandchild) and time.time() < deadline:
            time.sleep(0.05)
        self.assertFalse(self.is_running(grandchild), "the grandchild of the claude call survived the stop")

    @staticmethod
    def is_running(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        try:
            stat_text = pathlib.Path(f"/proc/{pid}/stat").read_text()
        except (FileNotFoundError, ProcessLookupError):
            return False
        return stat_text.rpartition(")")[2].split()[0] != "Z"

    def test_is_running_reports_a_pid_that_vanishes_after_the_signal_check_as_dead(self):
        gone = subprocess.Popen(["true"])
        gone.wait()

        with mock.patch.object(os, "kill", return_value=None):
            self.assertFalse(self.is_running(gone.pid))

    @staticmethod
    def kill_quietly(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    def test_a_second_round_fix_gets_one_final_read_and_no_coder_after_it(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        keys = [call["key"] for call in self.fake_calls()]
        self.assertEqual((keys.count("code-reviewer"), keys.count("coder")), (3, 2))
        self.assertFalse(row["no_reviewer"])
        self.assertFalse(row["unreviewed_fix"])
        final_prompt = [call for call in self.fake_calls() if call["key"] == "code-reviewer"][2]["prompt"]
        self.assertIn("final-fix.diff", final_prompt)
        self.assertIn("app.py", final_prompt)

    def test_a_class_repair_after_the_last_read_gets_one_final_read_of_its_diff(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": json.dumps(OPEN_MEMBER)}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(self.call_keys().count("code-reviewer"), 3)
        self.assertFalse(row["unreviewed_fix"])
        final_prompt = [call for call in self.fake_calls() if call["key"] == "code-reviewer"][2]["prompt"]
        self.assertIn("late-repair.diff", final_prompt)

    def test_a_capped_run_lists_its_closure_prose_and_late_repair_read_in_walk_order(self):
        self.save_gate_commands([self.stale_prose_command(1)])
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": LATE_FIX},
                              {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT + "# class repaired\n"}},
                      {"result": "Fixed the claim.", "edits": {"app.py": APP_AFTER_EDIT + "# corrected claim\n"}}],
            "closure": [{"result": json.dumps(OPEN_MEMBER)}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "cap-reached")
        self.assertEqual(packet["fix_rounds"], 2)
        self.assertEqual(packet["post_cap_passes"], ["final read", "class closure", "prose repair", "scoped re-review"])
        summary = review_loop_post_cap.cap_summary_line(packet)
        expected = ("cap reached after 2 fix round(s); post-cap passes: final read, class closure, prose repair, "
                    "scoped re-review")
        self.assertEqual(summary, expected)
        printed = self.review_fix_packet_output()
        self.assertIn("cap reached after 2 fix round(s); post-cap passes: final read, class closure", printed)
        cap_line = next(line for line in printed.splitlines() if line.startswith("cap reached"))
        self.assertNotRegex(cap_line, r"\b([3-9]|\d{2,})\b")
        self.assertGreater(packet["iter"], 2)
        self.assertNotRegex(printed, rf"(?<![\w.:]){packet['iter']}\b")
        self.assertGreater(packet["review_round"], 2)
        self.assertNotRegex(printed, rf"(?<![\w.:]){packet['review_round']}\b")

    def review_fix_packet_output(self):
        """What `review_fix.py packet` prints for the packet the run stored."""
        row, _packet = self.stored_packet()
        review_fix_script = toolkit_paths.REVIEW_DIR / "review_fix.py"
        printed = subprocess.run([sys.executable, "-I", str(review_fix_script), "packet", "--skill", "review"],
                                 input=row["message"], cwd=self.repo, capture_output=True, text=True,
                                 env={**self.env, "CLAUDE_CODE_SESSION_ID": SESSION})
        return printed.stdout + printed.stderr

    def test_a_capped_run_with_a_stale_prose_repair_lists_it_among_its_post_cap_passes(self):
        self.save_gate_commands([self.stale_prose_command(1)])
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": LATE_FIX},
                              {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}},
                      {"result": "Fixed the claim.", "edits": {"app.py": APP_AFTER_EDIT + "# corrected claim\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "cap-reached")
        self.assertEqual(packet["fix_rounds"], 2)
        self.assertEqual(packet["post_cap_passes"], ["final read", "prose repair", "scoped re-review"])

    def test_a_run_that_converges_in_round_one_and_then_closes_a_class_reports_one_fix_round_and_no_cap_line(self):
        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": json.dumps(OPEN_MEMBER)}],
        }, header_extra=self.findings_header("app.py:2 the limit is wrong for `limit`"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["fix_rounds"], 1)
        self.assertEqual(packet["post_cap_passes"], ["class closure", "scoped re-review"])
        self.assertNotIn("cap reached after", self.review_fix_packet_output())

    def test_a_relaunch_header_with_a_word_for_fix_rounds_stops_naming_the_line(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    header_extra="iter: 1\nfix_rounds: many\n")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("expected a whole number", completed.stderr)
        self.assertIn("fix_rounds", completed.stderr)

    def test_a_run_that_converges_in_its_first_round_reports_one_fix_round_and_no_pass(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["fix_rounds"], packet["post_cap_passes"]), ("converged", 1, []))

    def test_a_converged_run_counts_its_two_walk_rounds_and_lists_its_closure_passes_apart(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": json.dumps(OPEN_MEMBER)}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        # The closure and the late-repair read are not fix rounds: only the fix round and the clean round count.
        self.assertEqual(packet["fix_rounds"], 2)
        self.assertEqual(packet["post_cap_passes"], ["class closure", "scoped re-review"])

    # Header 2 and header 5 both end at 2: the run adds its own round and the outcome clamp holds the count at the
    # budget. Dropping the outcome clamp makes both fail; the seed clamp in the loop's main has no case of its own.
    def test_a_relaunch_header_at_the_budget_stays_at_the_budget(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    header_extra="iter: 1\nfix_rounds: 2\npost_cap_passes: final read\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["fix_rounds"], 2)
        self.assertEqual(packet["post_cap_passes"], ["final read"])

    def test_a_relaunch_header_of_one_fix_round_adds_the_runs_own_round_and_reports_two(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    header_extra="iter: 1\nfix_rounds: 1\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["fix_rounds"], 2)

    def test_a_relaunch_header_above_the_round_budget_is_reported_at_the_outcome_budget(self):
        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    header_extra="iter: 1\nfix_rounds: 5\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["fix_rounds"], 2)

    def test_a_class_repair_outside_the_review_scope_stays_unreviewed_and_the_packet_names_the_pass(self):
        open_member = {"receipt": "one member still open", "open": ["`notes.py:1` the same limit is wrong here too"]}
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"notes.py": "value = {'a': 1, 'b': 4}\n"}}],
            "closure": [{"result": json.dumps(open_member)}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual(self.call_keys().count("code-reviewer"), 2)
        self.assertTrue(row["unreviewed_fix"])
        self.assertIn("no reviewer read the coder-class pass", packet["scoped_tests"])

    def test_a_final_read_finding_on_a_held_file_is_dropped_and_the_last_fix_counts_as_read(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_review = FIX_REVIEW.replace("app.py:2", "notes.py:1")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": held_review}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["findings_remaining"], [])
        self.assertEqual(self.call_keys().count("code-reviewer"), 3)
        self.assertFalse(row["unreviewed_fix"])

    def test_a_last_fix_that_touches_only_a_held_file_gets_no_final_read(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"notes.py": "value = {'a': 1}\n"}}],
            "closure": [{"result": CLOSED}],
        }, header_extra=SCOPED_WITH_NOTES_HELD)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, _packet = self.stored_packet()
        self.assertEqual(self.call_keys().count("code-reviewer"), 2)
        self.assertTrue(row["unreviewed_fix"])

    def test_a_final_read_ask_reaches_the_packet_and_its_run_row_is_filed(self):
        late_ask = ("## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit be configurable?\n\n## Nit\nNone\n\n"
                    "Overall Assessment: APPROVED\n")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": late_ask}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["app.py:3"])

    def test_a_final_read_that_files_a_fix_lists_it_as_remaining_and_sends_no_coder(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": LATE_FIX}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        keys = [call["key"] for call in self.fake_calls()]
        self.assertEqual((keys.count("code-reviewer"), keys.count("coder")), (3, 2))
        self.assertEqual([item["file_line"] for item in packet["findings_remaining"]], ["app.py:5"])
        self.assertEqual(packet["status"], "cap-reached")
        self.assertFalse(row["unreviewed_fix"])
        self.assertTrue(packet["full_check"].startswith("unverified (exit 0"), packet["full_check"])
        self.assertNotEqual(packet["scoped_tests"], "")
        final_prompt = [call for call in self.fake_calls() if call["key"] == "code-reviewer"][2]["prompt"]
        self.assertIn("final-fix.diff", final_prompt)
        self.assertIn("app.py", final_prompt)

    def test_a_red_scoped_test_after_a_final_read_fix_stays_a_critical_blocker(self):
        self.save_gate_commands(["grep -q 'limit = 99' app.py"])
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}, {"result": LATE_FIX}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("grep -q 'limit = 99' app.py", packet["blockers"][0])

    def call_keys(self):
        return [call["key"] for call in self.fake_calls()]

    def test_a_fix_to_a_test_file_the_code_reviewer_owned_gets_a_second_review(self):
        fix_in_test = ("## Fix\n- `tests/test_app.py:1` the assertion is wrong for `limit`\n\n## Ask\nNone\n\n"
                       "## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")
        (self.repo / "tests").mkdir()
        self.commit_files({"tests/test_app.py": "assert 1 == 1\n"})
        (self.repo / "tests/test_app.py").write_text("assert 1 == 2\n")

        completed = self.run_script({
            "code-reviewer": [{"result": fix_in_test}] * 2 + [{"result": CLEAN_REVIEW}] * 2,
            "coder": [{"result": "Fixed 1.", "edits": {"tests/test_app.py": "assert 2 == 2\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.call_keys().count("code-reviewer"), 4)

    def test_a_correctness_fix_to_a_markdown_file_gets_a_second_review(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1 in the agent file.", "edits": {"CHANGES.md": "the limit is 20\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.call_keys().count("code-reviewer"), 2)

    def test_a_docs_class_fix_that_changes_only_markdown_ends_the_rounds_with_no_second_review(self):
        docs_review = FIX_REVIEW.replace("`app.py:2` the", "`app.py:2` [docs] the")
        completed = self.run_script({
            "code-reviewer": [{"result": docs_review}],
            "coder": [{"result": "Fixed 1 in the docs.", "edits": {"CHANGES.md": "the limit is 20\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(self.call_keys().count("code-reviewer"), 1)
        self.assertEqual(packet["files_touched"], ["CHANGES.md"])
        self.assertTrue(row["unreviewed_fix"])

    def test_a_docs_class_fix_that_edits_a_code_file_gets_a_second_review(self):
        docs_review = FIX_REVIEW.replace("`app.py:2` the", "`app.py:2` [docs] the")
        completed = self.run_script({
            "code-reviewer": [{"result": docs_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1 in the code.", "edits": {"app.py": "limit = 20\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.call_keys().count("code-reviewer"), 2)

    def test_a_docs_fix_together_with_a_correctness_fix_gets_a_second_review(self):
        mixed_review = FIX_REVIEW.replace(
            "- `app.py:2` the limit is wrong for `limit`\n",
            "- `app.py:2` [docs] the limit is wrong for `limit`\n- `app.py:3` [correctness] the offset is wrong\n")
        completed = self.run_script({
            "code-reviewer": [{"result": mixed_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1 and 2.", "edits": {"CHANGES.md": "the limit is 20\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.call_keys().count("code-reviewer"), 2)

    def test_a_fix_that_changes_only_a_test_file_leaves_no_source_reviewer_for_round_two(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Fixed 1 with a test.", "edits": {"app.test.py": "assert limit == 20\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(self.call_keys().count("code-reviewer"), 1)
        self.assertNotIn("test-reviewer", self.call_keys())

    def test_a_new_source_file_with_a_test_sends_the_test_reviewer_and_reads_its_tagged_bullets(self):
        (self.repo / "util.py").write_text("limit = 20\n")
        (self.repo / "util.test.py").write_text("assert limit == 20\n")
        tagged = ("- ask: `util.test.py:1` should this test pin the limit from the config?\n"
                  "- nit: `util.test.py:1` name the test for the limit\n")

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}] * 2,
            "test-reviewer": [{"result": tagged}],
            "smell-reviewer": [{"result": CLEAN_REVIEW}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertIn("test-reviewer", self.call_keys())
        self.assertEqual([entry["gate"] for entry in packet["ask"]], ["test-reviewer"])
        self.assertEqual(packet["ask"][0]["file_line"], "util.test.py:1")
        self.assertEqual([entry["file_line"] for entry in packet["nit"]], ["util.test.py:1"])

    def test_only_the_test_reviewer_gets_the_plans_test_strategy_section(self):
        self.commit_files({"plan.md": "# Plan\n\n## Phase 2: Limits\n\nSet the limit.\n\n"
                                      "## Testing Strategy\n\nEach check constraint has a direct-insert test.\n\n"
                                      "## Rollout\n\nShip it.\n"})
        (self.repo / "util.py").write_text("limit = 20\n")
        (self.repo / "util.test.py").write_text("assert limit == 20\n")

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}] * 2,
            "test-reviewer": [{"result": CLEAN_REVIEW}],
            "smell-reviewer": [{"result": CLEAN_REVIEW}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        prompts = {call["key"]: call["prompt"] for call in self.fake_calls()}
        strategy = "## Testing Strategy\n\nEach check constraint has a direct-insert test."
        self.assertIn(strategy, prompts["test-reviewer"])
        self.assertNotIn("Rollout", prompts["test-reviewer"])
        self.assertNotIn("direct-insert", prompts["code-reviewer"])
        self.assertNotIn("direct-insert", prompts["smell-reviewer"])

    def test_a_plan_without_a_test_strategy_adds_no_strategy_line_to_the_test_reviewer(self):
        self.commit_files({"plan.md": "# Plan\n\n## Phase 2: Limits\n\nSet the limit.\n\n## Rollout\n\nShip it.\n"})
        (self.repo / "util.py").write_text("limit = 20\n")
        (self.repo / "util.test.py").write_text("assert limit == 20\n")

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}] * 2,
            "test-reviewer": [{"result": CLEAN_REVIEW}],
            "smell-reviewer": [{"result": CLEAN_REVIEW}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        prompts = {call["key"]: call["prompt"] for call in self.fake_calls()}
        self.assertNotIn("test strategy binds", prompts["test-reviewer"])

    def test_a_test_reviewer_reply_of_bold_head_items_goes_to_the_disposition_call(self):
        (self.repo / "util.py").write_text("limit = 20\n")
        (self.repo / "util.test.py").write_text("assert limit == 20\n")
        bold_heads = ("**The limit has no test.**\n"
                      "`util.py:1`. Add a test for it.\n\n"
                      "**The existing test sets one field.**\n"
                      "`util.test.py:1` only checks one value.\n"
                      "- Fix: check the second value too.\n")
        asked = "`util.py:1` should the limit have a test? change: add a test for it"
        disposition = json.dumps({"fix": [], "ask": [asked], "nit": []})

        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}] * 2,
            "test-reviewer": [{"result": bold_heads}],
            "smell-reviewer": [{"result": CLEAN_REVIEW}],
            "disposition": [{"result": disposition}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertIn("disposition", self.call_keys())
        self.assertEqual([entry["file_line"] for entry in packet["ask"]], ["util.py:1"])

    def test_a_full_check_failing_in_a_spec_file_stops_with_no_repair_coder(self):
        failing_spec = f"{FAILS_ONLY_WITH_THE_DIFF}echo 'FAIL src/orders.spec.ts'; exit 1"

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]}, quality_check=failing_spec)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("orders.spec.ts", packet["blockers"][0])
        self.assertNotIn("coder", self.call_keys())

    def test_a_full_check_that_fails_after_the_class_repair_is_a_critical_blocker(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"broken.flag": "x\n"}}],
            "closure": [{"result": '{"receipt": "one site left", "open": ["app.py:4 - same limit - fix it"]}'}],
        }, quality_check="test ! -f broken.flag")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("failing after the class repair", packet["blockers"][0])
        self.assertEqual(self.call_keys().count("coder"), 2)

    def test_a_coder_skip_line_moves_the_finding_to_skipped_and_out_of_fixed(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "SKIPPED 1: the limit is meant to be 5", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["fixed"], [])
        self.assertEqual(len(packet["skipped_fp"]), 1)
        self.assertEqual(packet["skipped_fp"][0]["file_line"], "app.py:2")
        self.assertIn("meant to be 5", packet["skipped_fp"][0]["reason"])
        self.assertEqual(self.call_keys().count("code-reviewer"), 2)

    def test_a_nit_gets_its_file_line_in_the_packet_and_unlocated_when_it_names_none(self):
        nit_review = ("## Fix\nNone\n\n## Ask\nNone\n\n## Nit\n- `app.py:3` rename `limit`\n- tidy the module\n\n"
                      "Overall Assessment: PASS\n")

        completed = self.run_script({"code-reviewer": [{"result": nit_review}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual([entry["file_line"] for entry in packet["nit"]], ["app.py:3", "unlocated"])

    def test_no_usage_row_is_written_when_telemetry_is_off(self):
        self.env["CLAUDE_TOOLKIT_TELEMETRY"] = "0"

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse((self.scratch / "agent-usage.jsonl").exists())

    @unittest.skipIf(os.geteuid() == 0, "root reads a mode 000 file")
    def test_crash_writes_a_critical_blocker_packet_and_the_rows(self):
        locked = self.repo / "locked.txt"
        locked.write_text("secret\n")
        locked.chmod(0o000)
        self.addCleanup(locked.chmod, 0o644)

        completed = self.run_script({})

        self.assertNotEqual(completed.returncode, 0)
        row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("calls.jsonl", packet["blockers"][0])
        self.assertIn("PermissionError", packet["blockers"][0])
        self.assertEqual(row["status"], "critical-blocker")
        self.assertEqual([stored["kind"] for stored in self.store_rows()], ["handback", "stop"])
        self.assertEqual(len(self.usage_rows()), 1)


DECISIONS_PATH = "docs/plans/x/03-decisions.md"
DECISIONS_TEXT = ("# Decisions\n\n- 2026-11-11: Keep plan as written. Ruled by the session, not the user at "
                  "2026-11-11 03:17.\n\n  The ruling: kept as written.\n")
SIGNOFF_FINDING_REVIEW = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                          f"- `{DECISIONS_PATH}:3` [plan-drift] the ruling here is wrong; it should be reversed\n\n"
                          "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")


class SignoffLinesLoopTest(ReviewLoopHarness, unittest.TestCase):
    """A coder never edits a sign-off line of a decision log; the loop asks the caller instead."""

    def setUp(self):
        super().setUp()
        (self.repo / "docs/plans/x").mkdir(parents=True)
        self.commit_files({DECISIONS_PATH: DECISIONS_TEXT})

    def run_loop(self, review, coder):
        scenario = {
            "code-reviewer": [{"result": review}, *[{"result": CLEAN_REVIEW}] * 3],
            "coder": [coder],
            "closure": [{"result": CLOSED}],
        }
        completed = self.run_script(scenario)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        return packet

    def test_a_finding_on_a_ruled_by_line_goes_to_ask_and_not_to_the_coder(self):
        coder = {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}

        packet = self.run_loop(SIGNOFF_FINDING_REVIEW, coder)

        issues = self.coder_issues()
        self.assertIn("app.py:2", issues)
        self.assertNotIn(DECISIONS_PATH, issues)
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], [f"{DECISIONS_PATH}:3"])

    def test_lost_lines_counts_repeated_identical_sign_off_lines(self):
        before = [(3, "Ruled by the session."), (5, "Ruled by the session.")]

        lost = review_loop_signoffs.lost_lines(before, "# D\n\nRuled by the session.\n")

        self.assertEqual(lost, [(5, "Ruled by the session.")])

    def coder_issues(self):
        """The numbered issue list of the coder prompt; fails when the prompt has no such list."""
        sent = next(call["prompt"] for call in self.fake_calls() if call["key"] == "coder")
        self.assertIn("## Issues", sent)
        self.assertIn("Files in scope:", sent)
        issues = sent.partition("## Issues")[2].partition("Files in scope:")[0]
        self.assertTrue(issues.strip())
        return issues

    def review_with(self, decision_finding):
        return ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                f"- `{DECISIONS_PATH}:1` [plan-drift] {decision_finding}\n\n"
                "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")

    def test_a_finding_that_objects_to_a_ruling_on_another_line_goes_to_ask_named_by_its_own_line(self):
        coder = {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}

        packet = self.run_loop(self.review_with("the ruling is wrong"), coder)

        self.assertNotIn(DECISIONS_PATH, self.coder_issues())
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], [f"{DECISIONS_PATH}:1"])

    def test_a_decision_log_finding_with_no_sign_off_line_and_no_ruling_words_reaches_the_coder(self):
        coder = {"result": "Fixed 1 and 2.", "edits": {"app.py": APP_FIXED, DECISIONS_PATH: DECISIONS_TEXT + "\n"}}

        packet = self.run_loop(self.review_with("the heading should say Decisions Log"), coder)

        self.assertIn(DECISIONS_PATH, self.coder_issues())
        self.assertEqual(packet["ask"], [])

    def test_a_coder_that_rewrites_a_ruled_by_line_gets_the_file_put_back_byte_for_byte(self):
        rewritten = DECISIONS_TEXT.replace("Ruled by the session", "Ruled by the user")
        coder = {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, DECISIONS_PATH: rewritten}}

        self.run_loop(FIX_REVIEW, coder)

        self.assertEqual((self.repo / DECISIONS_PATH).read_text(), DECISIONS_TEXT)

    def test_a_plan_folder_file_the_sign_off_snapshot_does_not_hold_is_put_back_by_the_scope_guard(self):
        evidence_path = "docs/plans/x/evidence.json"
        nested_path = "packages/a/docs/plans/p/03-decisions.md"
        (self.repo / "packages/a/docs/plans/p").mkdir(parents=True)
        self.commit_files({evidence_path: "{}\n", nested_path: DECISIONS_TEXT})
        coder = {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, evidence_path: '{"a": 1}\n',
                                                 nested_path: "# Decisions\n"}}

        self.run_loop(FIX_REVIEW, coder)

        self.assertEqual((self.repo / evidence_path).read_text(), "{}\n")
        self.assertEqual((self.repo / nested_path).read_text(), DECISIONS_TEXT)

    def test_a_decision_log_the_sign_off_snapshot_holds_is_left_to_the_sign_off_guard(self):
        """The scope guard puts back nothing here: the sign-off guard keeps the pass's other edits to the file."""
        edited = DECISIONS_TEXT + "\nA note the coder added.\n"
        coder = {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, DECISIONS_PATH: edited}}

        self.run_loop(FIX_REVIEW, coder)

        self.assertEqual((self.repo / DECISIONS_PATH).read_text(), edited)

    def test_a_coder_that_deletes_a_sign_off_in_a_plan_deviations_section_gets_the_file_put_back(self):
        plan_path = "docs/plans/x/plan.md"
        plan_text = "# Plan\n\n## Plan Deviations\n\n- Phase 1 moved. Ruled by the session, 2026-11-11.\n"
        self.commit_files({plan_path: plan_text})
        coder = {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, plan_path: "# Plan\n"}}

        packet = self.run_loop(FIX_REVIEW, coder)

        self.assertEqual((self.repo / plan_path).read_text(), plan_text)
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], [f"{plan_path}:5"])

    def test_a_real_fix_in_a_file_whose_sign_off_line_was_put_back_stays_fixed_and_touched(self):
        plan_path = "docs/plans/x/plan.md"
        self.commit_files({plan_path: self.PLAN_WITH_DEVIATIONS})
        fixed_plan = ("# Plan\n\n## Phase 1: x\n\n- the wording is clear\n\n## Plan Deviations\n\n"
                      "- the ruling wording is unclear\n")
        coder = {"result": "Fixed 1 and 2.", "edits": {"app.py": APP_FIXED, plan_path: fixed_plan}}

        packet = self.run_loop(self.plan_review(5), coder)

        restored = (self.repo / plan_path).read_text()
        self.assertIn("Ruled by the session, 2026-11-11.", restored)
        self.assertIn("- the wording is clear", restored)
        self.assertIn(plan_path, packet["files_touched"])
        self.assertNotIn("the ruling wording is unclear", json.dumps(packet["findings_remaining"]))
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], [f"{plan_path}:9"])

    def test_a_put_back_file_leaves_its_findings_open_and_names_each_lost_entry(self):
        two_rulings = DECISIONS_TEXT + "\n- Ruled by the user, 2026-11-12.\n"
        self.commit_files({DECISIONS_PATH: two_rulings})
        review = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                  f"- `{DECISIONS_PATH}:1` [docs] the heading is bare\n\n"
                  "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")
        coder = {"result": "Fixed 1 and 2.", "edits": {"app.py": APP_FIXED, DECISIONS_PATH: "# Decisions\n"}}

        packet = self.run_loop(review, coder)

        self.assertEqual((self.repo / DECISIONS_PATH).read_text(), two_rulings)
        self.assertEqual(sorted(ask["file_line"] for ask in packet["ask"]),
                         [f"{DECISIONS_PATH}:3", f"{DECISIONS_PATH}:5", f"{DECISIONS_PATH}:7"])
        self.assertEqual([item["file_line"] for item in packet["fixed"]], ["app.py:2"])
        self.assertIn(DECISIONS_PATH, json.dumps(packet["findings_remaining"]))
        self.assertEqual(json.dumps(packet["findings_remaining"]).count("the heading is bare"), 1)

    PLAN_WITH_DEVIATIONS = ("# Plan\n\n## Phase 1: x\n\n- the ruling wording is unclear\n\n"
                            "## Plan Deviations\n\n- Phase 1 moved. Ruled by the session, 2026-11-11.\n"
                            "- the ruling wording is unclear\n")

    def plan_review(self, line):
        return ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                f"- `docs/plans/x/plan.md:{line}` [docs] the ruling wording is unclear\n\n"
                "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")

    def test_an_objection_on_a_phase_line_of_plan_md_reaches_the_coder(self):
        self.commit_files({"docs/plans/x/plan.md": self.PLAN_WITH_DEVIATIONS})
        coder = {"result": "Fixed 1 and 2.", "edits": {"app.py": APP_FIXED}}

        packet = self.run_loop(self.plan_review(5), coder)

        self.assertIn("docs/plans/x/plan.md", self.coder_issues())
        self.assertEqual(packet["ask"], [])

    def test_an_objection_on_a_deviations_line_of_plan_md_goes_to_ask(self):
        self.commit_files({"docs/plans/x/plan.md": self.PLAN_WITH_DEVIATIONS})
        coder = {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}

        packet = self.run_loop(self.plan_review(10), coder)

        self.assertNotIn("docs/plans/x/plan.md", self.coder_issues())
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["docs/plans/x/plan.md:10"])

    def test_signoff_scope_of_plan_md_without_a_deviations_heading_is_empty(self):
        text = "# Plan\n\nthe ruling is here\n"

        self.assertFalse(review_loop_signoffs.in_signoff_scope("docs/plans/x/plan.md", text, 3))
        self.assertFalse(review_loop_signoffs.in_signoff_scope("docs/plans/x/plan.md", text, 0))

    def test_signoff_scope_of_an_evidence_file_without_a_heading_is_every_line(self):
        text = "# Notes\n\nRuled by the user.\n"

        self.assertTrue(review_loop_signoffs.in_signoff_scope("docs/plans/x/notes.md", text, 1))
        self.assertTrue(review_loop_signoffs.in_signoff_scope("docs/plans/x/notes.md", text, 0))

    def test_a_coder_that_deletes_a_ruled_by_line_gets_the_file_put_back_and_an_ask_is_filed(self):
        coder = {"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, DECISIONS_PATH: "# Decisions\n"}}

        packet = self.run_loop(FIX_REVIEW, coder)

        self.assertEqual((self.repo / DECISIONS_PATH).read_text(), DECISIONS_TEXT)
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], [f"{DECISIONS_PATH}:3", f"{DECISIONS_PATH}:5"])
        self.assertIn("a coder pass changed or removed this recorded ruling", packet["ask"][0]["question"])


APP_COMMENT = "# the limits are tuned by hand\n"


class CommentRemovalLoopTest(ReviewLoopHarness, unittest.TestCase):
    """A fix pass never removes a code comment that no finding names."""

    def setUp(self):
        super().setUp()
        (self.repo / "app.py").write_text(APP_BEFORE + APP_COMMENT)

    def run_loop(self, review, edited=APP_FIXED, exit_code=0):
        coder = {"result": "Fixed 1.", "edits": {"app.py": edited}, "exit": exit_code}
        scenario = {
            "code-reviewer": [{"result": review}, *[{"result": CLEAN_REVIEW}] * 3],
            "coder": [coder],
            "closure": [{"result": CLOSED}],
        }
        completed = self.run_script(scenario)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        return packet

    def test_a_pass_that_deletes_an_unnamed_comment_gets_the_line_back_and_an_ask(self):
        packet = self.run_loop(FIX_REVIEW)

        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED + APP_COMMENT)
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["app.py:6"])
        self.assertIn("removed this code comment", packet["ask"][0]["question"])

    def test_a_pass_that_deletes_a_comment_a_finding_names_keeps_it_deleted_with_no_ask(self):
        review = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n"
                  "- `app.py:6` [docs] the comment is stale\n\n"
                  "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")

        packet = self.run_loop(review)

        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED)
        self.assertEqual(packet["ask"], [])

    def test_a_named_comment_is_exempt_but_a_second_unnamed_one_is_put_back_with_one_ask(self):
        (self.repo / "app.py").write_text(APP_BEFORE + APP_COMMENT + "limit = 6\n# second note\n")
        review = ("## Fix\n- `app.py:6` [docs] the comment is stale\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                  "Overall Assessment: NEEDS CHANGES\n")

        packet = self.run_loop(review, edited=APP_BEFORE + "limit = 6\n")

        self.assertEqual((self.repo / "app.py").read_text(), APP_BEFORE + "limit = 6\n# second note\n")
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["app.py:8"])

    def test_a_pass_that_adds_lines_above_a_comment_keeps_it_and_files_no_ask(self):
        packet = self.run_loop(FIX_REVIEW, edited=APP_FIXED + "limit = 6\n" + APP_COMMENT)

        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED + "limit = 6\n" + APP_COMMENT)
        self.assertEqual(packet["ask"], [])

    def test_a_coder_that_fails_after_deleting_an_unnamed_comment_gets_the_line_back_and_one_ask(self):
        packet = self.run_loop(FIX_REVIEW, exit_code=1)

        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED + APP_COMMENT)
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["app.py:6"])

    def test_a_finding_with_no_line_does_not_exempt_the_comments_of_its_file(self):
        review = ("## Fix\n- `app.py` the limits are wrong\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
                  "Overall Assessment: NEEDS CHANGES\n")

        packet = self.run_loop(review)

        self.assertEqual((self.repo / "app.py").read_text(), APP_FIXED + APP_COMMENT)
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["app.py:6"])

    def test_the_filed_ask_carries_the_deletion_as_its_change(self):
        packet = self.run_loop(FIX_REVIEW)

        ask = packet["ask"][0]
        self.assertIn(review_loop_comment_removal.delete_change_text("app.py", APP_COMMENT.strip()), str(ask))
        self.assertNotIn("the loop put it back", ask["change"])


class FakeCommentRun(review_loop_comment_removal.CommentRemovalRuns):
    """A LoopRun stand-in with what `undo_comment_pass` reads: a repo and the asks it files."""

    def __init__(self, repo):
        self.repo = str(repo)
        self.asks = []
        self.rejected_questions = []
        self.dropped_asks = []

    drop_asks = review_loop_ruled.RuledFindings.drop_asks

    def add_ask(self, gate, finding):
        self.asks.append(finding)


class CommentRemovalUnitTest(unittest.TestCase):
    """`undo_comment_pass` and its helpers on plain files, with no loop around them."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.repo = pathlib.Path(self.dir.name)
        self.run_ = FakeCommentRun(self.repo)

    def pass_over(self, name, before, after, finding_lines=(), findings=None):
        """Write `before`, snapshot, write `after` (None deletes the file), run the put-back; returns the put-back."""
        target = self.repo / name
        target.write_bytes(before.encode())
        snapshot = review_loop_comment_removal.snapshot_comments(self.repo, [name])
        if after is None:
            target.unlink()
        else:
            target.write_bytes(after.encode())
        if findings is None:
            findings = [finding_record.parse_finding(f"{name}:{line} [bug] problem") for line in finding_lines]
        return self.run_.undo_comment_pass(snapshot, findings)

    def test_removed_entries_count_repeats(self):
        before = [(1, "# same"), (2, "# same"), (3, "# other")]
        after = [(1, "# same"), (2, "# other")]

        self.assertEqual(protected_lines.entries_missing(before, after), [(2, "# same")])

    def test_two_identical_comments_with_one_removed_put_back_one_and_file_one_ask(self):
        put_back = self.pass_over("a.py", "x = 1\n# same\ny = 2\n# same\n", "x = 1\n# same\ny = 2\n")

        self.assertEqual(len(put_back), 1)
        self.assertEqual(len(self.run_.asks), 1)
        self.assertEqual((self.repo / "a.py").read_text().count("# same"), 2)

    def test_a_deleted_comment_whose_text_repeats_later_is_put_back_at_its_own_place_with_one_ask(self):
        before = "a = 1\n# sep\nb = 2\nc = 3\n# sep\nd = 4\n"

        put_back = self.pass_over("a.py", before, "a = 1\nb = 2\nc = 3\n# sep\nd = 4\n")

        self.assertEqual(len(put_back), 1)
        self.assertEqual((self.repo / "a.py").read_text(), before)
        self.assertEqual(len(self.run_.asks), 1)
        self.assertEqual(self.run_.asks[0].line, 2)

    def test_a_file_with_no_comment_style_or_deleted_by_the_pass_is_left_alone(self):
        cases = {
            "a json file": ("a.json", '{"a": 1}\n', '{"a": 2}\n'),
            "a deleted file": ("a.py", "x = 1\n# note\n", None),
        }
        for name, (path, before, after) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.pass_over(path, before, after), [])
        self.assertEqual(self.run_.asks, [])

    def test_a_comment_reworded_in_place_is_left_and_files_no_ask(self):
        after = "x = 1\n# the limit is set by config\ny = 2\n"

        put_back = self.pass_over("a.py", "x = 1\n# the limit is tuned by hand\ny = 2\n", after)

        self.assertEqual(put_back, [])
        self.assertEqual((self.repo / "a.py").read_text(), after)
        self.assertEqual(self.run_.asks, [])

    def test_a_comment_block_shortened_by_a_rewrite_is_put_back_with_one_ask(self):
        before = "x = 1\n# first line\n# second line\ny = 2\n"

        self.pass_over("a.py", before, "x = 1\n# first line, merged\ny = 2\n")

        self.assertEqual((self.repo / "a.py").read_text(),
                         "x = 1\n# first line\n# second line\ny = 2\n")
        self.assertEqual(len(self.run_.asks), 1)
        change = review_loop_comment_removal.delete_block_change_text("a.py", ["# first line", "# second line"])
        self.assertIn(f"Change: {change}", self.run_.asks[0].text)

    def test_a_deleted_comment_block_is_put_back_whole_with_one_ask_quoting_every_line(self):
        before = "x = 1\n# one\n# two\n# three\ny = 2\n"

        put_back = self.pass_over("a.py", before, "x = 1\ny = 2\n")

        self.assertEqual(len(put_back), 1)
        self.assertEqual((self.repo / "a.py").read_text(), before)
        self.assertEqual(len(self.run_.asks), 1)
        ask_text = self.run_.asks[0].text
        for line in ("# one", "# two", "# three"):
            self.assertIn(line, ask_text)
        self.assertEqual(self.run_.asks[0].path, "a.py")

    def test_two_comment_blocks_apart_file_one_ask_each(self):
        before = "# a1\n# a2\nx = 1\n# b1\n# b2\ny = 2\n"

        self.pass_over("a.py", before, "x = 1\ny = 2\n")

        self.assertEqual(len(self.run_.asks), 2)
        first, second = (ask.text for ask in self.run_.asks)
        self.assertIn("# a1", first)
        self.assertIn("# a2", first)
        self.assertNotIn("# b1", first)
        self.assertIn("# b1", second)
        self.assertIn("# b2", second)

    def test_a_comment_reworded_into_more_comment_lines_is_left_and_files_no_ask(self):
        after = "x = 1\n# the limit is set\n# by config\ny = 2\n"

        put_back = self.pass_over("a.py", "x = 1\n# the limit is tuned by hand\ny = 2\n", after)

        self.assertEqual(put_back, [])
        self.assertEqual(self.run_.asks, [])

    def test_a_comment_swapped_for_an_unrelated_comment_in_one_stretch_counts_as_a_rewording(self):
        after = "a = 0\nx = 2\n# TODO\ny = 2\n"

        put_back = self.pass_over("a.py", "a = 0\n# retry three times before giving up\nx = 1\ny = 2\n", after)

        self.assertEqual(put_back, [])
        self.assertEqual((self.repo / "a.py").read_text(), after)
        self.assertEqual(self.run_.asks, [])

    def test_a_comment_rewritten_into_code_is_put_back_with_one_ask(self):
        before = "x = 1\n# the limit is tuned by hand\ny = 2\n"

        self.pass_over("a.py", before, "x = 1\nlimit = 5\ny = 2\n")

        self.assertIn("# the limit is tuned by hand", (self.repo / "a.py").read_text())
        self.assertEqual(len(self.run_.asks), 1)

    def test_an_accepted_block_ask_also_covers_a_block_that_grew_by_a_neighbour(self):
        change = review_loop_comment_removal.delete_block_change_text("a.py", ["# one", "# two"])
        accepted = finding_record.parse_finding(f"a.py:9 [comment] Proposed change: {change}")

        put_back = self.pass_over("a.py", "x = 1\n# one\n# two\n# three\ny = 2\n", "x = 1\ny = 2\n",
                                  findings=[accepted])

        self.assertEqual(len(put_back), 1)
        self.assertEqual((self.repo / "a.py").read_text(), "x = 1\n# three\ny = 2\n")

    def test_an_accepted_block_ask_suppresses_the_put_back_of_every_line_in_it(self):
        change = review_loop_comment_removal.delete_block_change_text("a.py", ["# one", "# two"])
        accepted = finding_record.parse_finding(f"a.py:9 [comment] Proposed change: {change}")

        put_back = self.pass_over("a.py", "x = 1\n# one\n# two\ny = 2\n", "x = 1\ny = 2\n", findings=[accepted])

        self.assertEqual(put_back, [])
        self.assertEqual((self.repo / "a.py").read_text(), "x = 1\ny = 2\n")
        self.assertEqual(self.run_.asks, [])

    def reject_as_stored(self, ask):
        """Records `ask` as rejected through the hand-back store and reads it back, as the loop does at its start."""
        item = {"question": review_loop_findings.ask_parts(ask.text).question, "file_line": f"{ask.path}:{ask.line}"}
        repo = os.path.realpath(self.repo)
        store_dir = tempfile.TemporaryDirectory()
        self.addCleanup(store_dir.cleanup)
        environment = {"HANDBACK_STORE_DIR": store_dir.name, "CLAUDE_CODE_SESSION_ID": SESSION}
        with mock.patch.dict(os.environ, environment):
            rows_repo = handback_store.ruled_rows_repo(repo)
            review_asks.record_rejected_asks([SESSION], rows_repo, [item], [REJECTED])
            rejected_questions = review_loop_ruled.rejected_ask_questions(SESSION, repo)
        self.assertEqual(len(rejected_questions), 1)
        self.run_.rejected_questions = rejected_questions
        self.run_.asks = []

    def test_a_rejection_stored_through_the_store_is_read_back_as_its_question(self):
        self.pass_over("a.py", "x = 1\n# note\ny = 2\n", "x = 1\ny = 2\n")
        ask = self.run_.asks[0]
        item = {"question": review_loop_findings.ask_parts(ask.text).question, "file_line": "a.py:2"}
        repo = os.path.realpath(self.repo)
        with tempfile.TemporaryDirectory() as store_dir:
            environment = {"HANDBACK_STORE_DIR": store_dir, "CLAUDE_CODE_SESSION_ID": SESSION}
            stored = self.rejected_questions_after_two_rejections(item, repo, environment)

        self.assertEqual(stored, [review_asks.ask_question(ask)])

    def rejected_questions_after_two_rejections(self, item, repo, environment):
        """Stores `item` as rejected and a row with no question field, then reads the questions back."""
        with mock.patch.dict(os.environ, environment):
            rows_repo = handback_store.ruled_rows_repo(repo)
            review_asks.record_rejected_asks([SESSION], rows_repo, [item], [REJECTED])
            handback_store.record_rejected_ask(SESSION, "a.py:3 no question field", rows_repo, "")

            return review_loop_ruled.rejected_ask_questions(SESSION, repo)

    def test_a_rejected_ask_keeps_the_put_back_and_is_not_filed_again_when_its_line_moved(self):
        self.pass_over("a.py", "x = 1\n# note\ny = 2\n", "x = 1\ny = 2\n")
        self.reject_as_stored(self.run_.asks[0])
        before = "w = 0\nv = 0\nx = 1\n# note\ny = 2\n"

        put_back = self.pass_over("a.py", before, "w = 0\nv = 0\nx = 1\ny = 2\n")

        self.assertEqual(len(put_back), 1)
        self.assertEqual((self.repo / "a.py").read_text(), before)
        self.assertEqual(self.run_.asks, [])
        self.assertEqual(len(self.run_.dropped_asks), 1)

    def test_a_rejected_ask_in_a_folder_with_a_space_is_not_filed_again_when_its_line_moved(self):
        (self.repo / "my dir").mkdir()
        self.pass_over("my dir/a.py", "x = 1\n# note\ny = 2\n", "x = 1\ny = 2\n")
        self.reject_as_stored(self.run_.asks[0])
        before = "w = 0\nv = 0\nx = 1\n# note\ny = 2\n"

        self.pass_over("my dir/a.py", before, "w = 0\nv = 0\nx = 1\ny = 2\n")

        self.assertEqual((self.repo / "my dir/a.py").read_text(), before)
        self.assertEqual(self.run_.asks, [])

    def test_a_rejected_multi_line_block_ask_keeps_the_put_back_and_is_not_filed_again(self):
        block = "# retry the fetch\n# three times\n"
        self.pass_over("a.py", f"x = 1\n{block}y = 2\n", "x = 1\ny = 2\n")
        self.reject_as_stored(self.run_.asks[0])
        before = f"w = 0\nv = 0\nx = 1\n{block}y = 2\n"

        put_back = self.pass_over("a.py", before, "w = 0\nv = 0\nx = 1\ny = 2\n")

        self.assertEqual(len(put_back), 1)
        self.assertEqual((self.repo / "a.py").read_text(), before)
        self.assertEqual(self.run_.asks, [])
        self.assertEqual(len(self.run_.dropped_asks), 1)

    def test_a_block_removed_again_after_its_line_moved_files_no_second_ask(self):
        self.pass_over("a.py", "x = 1\n# note\ny = 2\n", "x = 1\ny = 2\n")
        before = "w = 0\nv = 0\nx = 1\n# note\ny = 2\n"

        self.pass_over("a.py", before, "w = 0\nv = 0\nx = 1\ny = 2\n")

        self.assertEqual((self.repo / "a.py").read_text(), before)
        self.assertEqual(len(self.run_.asks), 1)

    def test_a_rejected_ask_for_the_same_comment_in_another_file_does_not_drop_its_ask(self):
        self.pass_over("a.py", "x = 1\n# TODO\ny = 2\n", "x = 1\ny = 2\n")
        self.reject_as_stored(self.run_.asks[0])

        self.pass_over("b.py", "x = 1\n# TODO\ny = 2\n", "x = 1\ny = 2\n")

        self.assertEqual(len(self.run_.asks), 1)
        self.assertEqual(self.run_.dropped_asks, [])

    def test_an_accepted_block_ask_covers_a_run_in_the_middle_and_at_the_tail_of_a_block(self):
        run_change = review_loop_comment_removal.delete_block_change_text("a.py", ["# one", "# two"])
        accepted = finding_record.parse_finding(f"a.py:9 [comment] Proposed change: {run_change}")
        cases = {
            "middle": ("x = 1\n# top\n# one\n# two\n# end\ny = 2\n", "x = 1\n# top\n# end\ny = 2\n"),
            "head": ("x = 1\n# one\n# two\n# end\ny = 2\n", "x = 1\n# end\ny = 2\n"),
            "tail": ("x = 1\n# top\n# one\n# two\ny = 2\n", "x = 1\n# top\ny = 2\n"),
        }
        for name, (before, expected) in cases.items():
            with self.subTest(name):
                self.pass_over("a.py", before, "x = 1\ny = 2\n", findings=[accepted])
                self.assertEqual((self.repo / "a.py").read_text(), expected, name)

    def test_two_accepted_runs_inside_one_block_are_both_cut_out(self):
        first = review_loop_comment_removal.delete_block_change_text("a.py", ["# one", "# two"])
        second = review_loop_comment_removal.delete_block_change_text("a.py", ["# six", "# seven"])
        accepted_one_line = f"{first} {second}"
        block = [(2, "# one"), (3, "# two"), (4, "# mid"), (5, "# six"), (6, "# seven"), (7, "# end")]

        kept = review_loop_comment_removal.without_accepted_runs("a.py", block, accepted_one_line)

        self.assertEqual(kept, [(4, "# mid"), (7, "# end")])

    def test_a_rejected_ask_for_one_comment_does_not_drop_the_ask_for_another_in_the_file(self):
        self.pass_over("a.py", "x = 1\n# retry the fetch three times before giving up\ny = 2\n", "x = 1\ny = 2\n")
        self.reject_as_stored(self.run_.asks[0])
        before = "x = 1\n# cache keyed by user id\ny = 2\n"

        self.pass_over("a.py", before, "x = 1\ny = 2\n")

        self.assertEqual(len(self.run_.asks), 1)
        self.assertEqual(self.run_.dropped_asks, [])

    def test_a_rejected_ask_does_not_drop_the_ask_for_a_block_that_differs_in_case_and_punctuation(self):
        self.pass_over("a.py", "x = 1\n# Retry the fetch.\ny = 2\n", "x = 1\ny = 2\n")
        self.reject_as_stored(self.run_.asks[0])

        self.pass_over("a.py", "x = 1\n# retry the fetch\ny = 2\n", "x = 1\ny = 2\n")

        self.assertEqual(len(self.run_.asks), 1)
        self.assertEqual(self.run_.dropped_asks, [])

    def test_two_removed_blocks_that_differ_only_in_a_location_each_file_an_ask(self):
        before = "x = 1\n# see a.py:10\ny = 2\n# see b.py:20\nz = 3\n"

        self.pass_over("a.py", before, "x = 1\ny = 2\nz = 3\n")

        self.assertEqual(len(self.run_.asks), 2)

    def test_an_ask_covers_only_the_entries_the_put_back_restored(self):
        unnamed = [(2, "# a")]
        current_entries = [(1, "# a")]

        restored = review_loop_comment_removal.restored_entries(unnamed, current_entries, "# a\nx = 1\n", "a.py")

        self.assertEqual(restored, [])

    def test_an_ask_covers_the_subset_of_entries_the_put_back_restored(self):
        unnamed = [(2, "# a"), (3, "# b")]
        current_entries = [(1, "# a")]

        restored = review_loop_comment_removal.restored_entries(unnamed, current_entries, "# a\n# b\nx = 1\n", "a.py")

        self.assertEqual(restored, [(3, "# b")])

    def test_trailing_comments_docstrings_and_strings_are_not_protected(self):
        cases = {
            "trailing comment": ("x = 1  # old\n", "x = 2  # new\n"),
            "docstring": ('def f():\n    """Wrong claim.\n    More.\n    """\n    return 1\n',
                          'def f():\n    """Returns one."""\n    return 1\n'),
            "multi-line string": ('PROMPT = """a\nThen stop.\n"""\n', 'PROMPT = """a\nThen stop now.\n"""\n'),
            "markdown heading in a string": ('PLAN = """\n# Plan\n\n## Phase 1\n"""\n',
                                             'PLAN = """\n# Plan\n\n## Phase 2\n"""\n'),
        }
        # No finding names a line: a put-back or an ask appears if any of these lines counts as a comment.
        for name, (before, after) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.pass_over("a.py", before, after), [])
                self.assertEqual((self.repo / "a.py").read_text(), after)

    def test_deleting_a_named_dead_function_with_an_inner_comment_is_kept(self):
        before = "x = 1\n\ndef unused():\n    # Doubles x.\n    return 2\n"

        put_back = self.pass_over("a.py", before, "x = 1\n", finding_lines=[3])

        self.assertEqual(put_back, [])
        self.assertEqual((self.repo / "a.py").read_text(), "x = 1\n")

    def test_rewrapping_a_two_line_comment_named_at_its_first_line_is_kept(self):
        before = "x = 1\n# one long\n# comment here\ny = 2\n"
        after = "x = 1\n# one long comment here\ny = 2\n"

        put_back = self.pass_over("a.py", before, after, finding_lines=[2])

        self.assertEqual(put_back, [])
        self.assertEqual((self.repo / "a.py").read_text(), after)

    def test_a_stale_comment_updated_with_the_code_line_a_finding_names_is_kept(self):
        before = "# returns one\nreturn 1\n"
        after = "# returns two\nreturn 2\n"

        self.assertEqual(self.pass_over("a.py", before, after, finding_lines=[2]), [])

    def test_an_unnamed_deleted_comment_comes_back_alone_and_other_edits_stay(self):
        before = "x = 1\n# note\ny = 2\nz = 3\n"

        self.pass_over("a.py", before, "x = 1\ny = 2\nz = 4\n")

        self.assertEqual((self.repo / "a.py").read_text(), "x = 1\n# note\ny = 2\nz = 4\n")

    def test_crlf_line_endings_survive_a_put_back(self):
        before = "x = 1\r\n# note\r\ny = 2\r\nz = 3\r\n"

        self.pass_over("a.py", before, "x = 1\r\ny = 2\r\nz = 4\r\n")

        self.assertEqual((self.repo / "a.py").read_bytes(), b"x = 1\r\n# note\r\ny = 2\r\nz = 4\r\n")

    def test_non_utf8_bytes_survive_a_put_back(self):
        before = b"s = '\xe9'\n# note\ny = 2\n"
        target = self.repo / "a.py"
        target.write_bytes(before)
        snapshot = review_loop_comment_removal.snapshot_comments(self.repo, ["a.py"])
        target.write_bytes(b"s = '\xe9'\ny = 3\n")

        self.run_.undo_comment_pass(snapshot, [])

        self.assertEqual(target.read_bytes(), b"s = '\xe9'\n# note\ny = 3\n")

    def test_a_finding_that_quotes_a_comment_whose_line_moved_keeps_it_removed_with_no_ask(self):
        before = "a = 1\n" * 13 + "#  moved   note\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding("a.py:10 [bug] the comment `# moved note` is stale")]

        put_back = self.pass_over("a.py", before, after, findings=findings)

        self.assertEqual(put_back, [])
        self.assertEqual(self.run_.asks, [])
        self.assertNotIn("moved", (self.repo / "a.py").read_text())

    def test_a_quote_split_across_a_line_break_in_the_finding_names_the_comment(self):
        before = "a = 1\n" * 13 + "# moved note\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding("a.py:10 [bug] the comment \"# moved\n   note\" is stale")]

        put_back = self.pass_over("a.py", before, after, findings=findings)

        self.assertEqual(put_back, [])
        self.assertEqual(self.run_.asks, [])

    def test_a_double_quoted_span_names_the_comment(self):
        before = "a = 1\n" * 13 + "# moved note\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding('a.py:10 [bug] the comment "# moved note" is stale')]

        put_back = self.pass_over("a.py", before, after, findings=findings)

        self.assertEqual(put_back, [])
        self.assertEqual(self.run_.asks, [])

    def test_a_quote_without_marker_names_a_comment_whose_text_starts_with_a_star(self):
        before = "a = 1\n" * 13 + "# *important*\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding("a.py:10 [bug] the comment `*important*` is stale")]

        put_back = self.pass_over("a.py", before, after, findings=findings)

        self.assertEqual(put_back, [])
        self.assertEqual(self.run_.asks, [])

    def test_a_quote_of_a_bare_marker_does_not_name_a_removed_empty_comment(self):
        before = "a = 1\n" * 13 + "#\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding("a.py:10 [bug] the line `#` is stale")]

        self.pass_over("a.py", before, after, findings=findings)

        self.assertIn("#\n", (self.repo / "a.py").read_text())
        self.assertEqual(len(self.run_.asks), 1)

    def test_a_merged_findings_second_part_names_the_comment_in_its_own_file(self):
        before = "a = 1\n" * 13 + "# moved note\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        first = finding_record.parse_finding("other.py:3 [bug] unrelated")
        second = finding_record.parse_finding("a.py:10 [bug] the comment `# moved note` is stale")
        merged = finding_record.combine([first, second])

        put_back = self.pass_over("a.py", before, after, findings=[merged])

        self.assertEqual(put_back, [])
        self.assertEqual(self.run_.asks, [])

    def test_a_finding_that_names_the_file_but_quotes_nothing_of_the_comment_still_puts_it_back_and_asks(self):
        before = "a = 1\n" * 13 + "# moved note\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding("a.py:10 [bug] something unrelated")]

        self.pass_over("a.py", before, after, findings=findings)

        self.assertIn("# moved note", (self.repo / "a.py").read_text())
        self.assertEqual(len(self.run_.asks), 1)

    def test_apostrophes_in_a_finding_do_not_make_a_quote_that_names_the_comment(self):
        before = "a = 1\n" * 13 + "# loop\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        text = "a.py:10 [bug] it doesn't check the loop bound, and the caller's guard is gone"
        findings = [finding_record.parse_finding(text)]

        self.pass_over("a.py", before, after, findings=findings)

        self.assertIn("# loop", (self.repo / "a.py").read_text())
        self.assertEqual(len(self.run_.asks), 1)

    def test_a_quote_in_a_finding_of_another_file_does_not_name_the_comment(self):
        before = "a = 1\n" * 13 + "# moved note\nb = 2\n"
        after = "a = 1\n" * 13 + "b = 2\n"
        findings = [finding_record.parse_finding("other.py:10 [bug] the comment `# moved note` is stale")]

        self.pass_over("a.py", before, after, findings=findings)

        self.assertIn("# moved note", (self.repo / "a.py").read_text())
        self.assertEqual(len(self.run_.asks), 1)

    def test_a_word_inside_a_longer_word_of_a_finding_does_not_name_the_comment(self):
        before = "a = 1\n" * 13 + "# end\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding("a.py:10 [bug] the `endpoint` returns None")]

        self.pass_over("a.py", before, after, findings=findings)

        self.assertIn("# end", (self.repo / "a.py").read_text())
        self.assertEqual(len(self.run_.asks), 1)

    def test_a_quote_of_a_longer_comment_does_not_name_a_shorter_removed_comment(self):
        before = "a = 1\n" * 13 + "# TODO\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding("a.py:10 [bug] the comment `# TODO: drop after v2` is stale")]

        self.pass_over("a.py", before, after, findings=findings)

        self.assertIn("# TODO", (self.repo / "a.py").read_text())
        self.assertEqual(len(self.run_.asks), 1)

    def test_an_unquoted_word_of_a_finding_does_not_name_the_comment(self):
        before = "a = 1\n" * 13 + "# loop\nb = 2\n" + "c = 3\n" * 10
        after = "a = 1\n" * 13 + "b = 2\n" + "c = 3\n" * 10
        findings = [finding_record.parse_finding("a.py:10 [bug] fix the off-by-one in the loop")]

        self.pass_over("a.py", before, after, findings=findings)

        self.assertIn("# loop", (self.repo / "a.py").read_text())
        self.assertEqual(len(self.run_.asks), 1)

    def test_a_finding_that_quotes_a_block_comment_line_whose_line_moved_keeps_it_removed(self):
        before = "a = 1;\n" * 13 + "/* moved note */\nb = 2;\n" + "c = 3;\n" * 10
        after = "a = 1;\n" * 13 + "b = 2;\n" + "c = 3;\n" * 10
        findings = [finding_record.parse_finding("a.ts:10 [bug] the comment `moved note` is stale")]

        put_back = self.pass_over("a.ts", before, after, findings=findings)

        self.assertEqual(put_back, [])
        self.assertEqual(self.run_.asks, [])

    def test_a_skipped_held_file_keeps_its_removed_comment_and_files_no_ask(self):
        target = self.repo / "held.py"
        target.write_text("# note\nx = 1\n")
        snapshot = review_loop_comment_removal.snapshot_comments(self.repo, ["held.py"])
        target.write_text("x = 1\n")

        put_back = self.run_.undo_comment_pass(snapshot, [], skip={"held.py"})

        self.assertEqual(put_back, [])
        self.assertEqual(target.read_text(), "x = 1\n")
        self.assertEqual(self.run_.asks, [])

    def test_an_uncommented_line_of_code_is_kept_beside_the_restored_comment(self):
        before = "# z = compute(a, b)\n"

        self.pass_over("a.py", before, "z = compute(a, b)\n", finding_lines=[])

        self.assertEqual((self.repo / "a.py").read_text(), "# z = compute(a, b)\nz = compute(a, b)\n")

    def test_an_accepted_ask_for_a_comment_with_repeated_spaces_or_a_change_mark_is_honored(self):
        for comment in ("#   aligned    note", "# On change: re-read"):
            with self.subTest(comment):
                change = review_loop_comment_removal.delete_change_text("a.py", comment)
                accepted = finding_record.parse_finding(
                    f"a.py:9 [comment] Proposed change: {' '.join(change.split())}")

                put_back = self.pass_over("a.py", f"x = 1\n{comment}\ny = 2\n", "x = 1\ny = 2\n",
                                          findings=[accepted])

                self.assertEqual(put_back, [])

    def test_an_accepted_ask_deletes_the_comment_even_when_its_line_moved(self):
        before = "x = 1\n# note\ny = 2\n"
        change = review_loop_comment_removal.delete_change_text("a.py", "# note")
        accepted = finding_record.parse_finding(f"a.py:9 [comment] Proposed change: {change}")

        put_back = self.pass_over("a.py", before, "x = 1\ny = 2\n", findings=[accepted])

        self.assertEqual(put_back, [])
        self.assertEqual((self.repo / "a.py").read_text(), "x = 1\ny = 2\n")


if __name__ == "__main__":
    unittest.main()
