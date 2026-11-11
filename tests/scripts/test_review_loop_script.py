"""Checks for review_loop_script.py, the scripted review loop.

A stand-in `claude` on PATH answers each call with a canned reply chosen by the agent of the call. Set
REVIEW_LOOP_SCRIPT to run against another copy, such as a staged one."""
import collections
import importlib.util
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import fake_ledger
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import finding_record
import handback
import handback_store
import plan_format
import review_loop_closure
import review_loop_findings
import review_loop_held
import review_loop_packet
import review_loop_plan

SCRIPT = pathlib.Path(os.environ.get("REVIEW_LOOP_SCRIPT") or toolkit_paths.REVIEW_DIR / "review_loop_script.py")
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
                else "check-finder" if "full quality check" in prompt else "disposition")
fake_dir = os.environ["FAKE_CLAUDE_DIR"]

with open(os.path.join(fake_dir, "calls.jsonl"), "a") as handle:
    pane_names = ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH", "TUIOS_SOCKET")
    pane_env = {name: os.environ.get(name) for name in pane_names}
    record = {"key": key, "hook_off": os.environ.get("CLAUDE_FORMAT_HOOK_OFF"), "prompt": prompt,
              "pane_env": pane_env, "name": args[args.index("--name") + 1] if "--name" in args else None}
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

replies = json.load(open(os.path.join(fake_dir, "scenario.json"))).get(key, [])
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
HELD_FILE_REASON = review_loop_held.HELD_FILE_REASON
FIX_REVIEW = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
              "Overall Assessment: NEEDS CHANGES\n")
# A check starts with this to fail only with the diff: the base run on HEAD has no diff and passes.
FAILS_ONLY_WITH_THE_DIFF = "git diff --quiet HEAD -- app.py && exit 0; "
CLOSED = '{"receipt": "one exit, all re-read", "open": []}'
FIX_THEN_CLEAN = {
    "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
    "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
    "closure": [{"result": CLOSED}],
}


# A stand-in for the stale-prose script, written under its real name: it prints a hit line and exits with the code
# the test gives it (1 is a hit, 2 a fault of the script).
STALE_PROSE_STAND_IN = "import sys\nprint('STALE app.py:1 names a changed symbol')\nsys.exit(int(sys.argv[1]))\n"
READABILITY_STAND_IN = "import sys\nprint('app.py:1 handle — LONG (50 lines, limit 40)')\nsys.exit(int(sys.argv[1]))\n"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class LastJsonObjectTest(unittest.TestCase):
    def test_the_last_object_that_holds_a_wanted_key_is_returned_past_prose_braces(self):
        cases = [
            ("prose braces before the object", 'see {CUBE} then {"command": "make test"}', ("command",),
             {"command": "make test"}),
            ("the last of two objects", '{"open": 1} and {"open": 2}', ("open",), {"open": 2}),
            ("an object without a wanted key", '{"other": 1}', ("command",), None),
            ("no object", "plain text", ("command",), None),
        ]
        for message, reply, keys, expected in cases:
            with self.subTest(message):
                self.assertEqual(expected, review_loop_findings.last_json_object(reply, keys))


class SkipHeldItemsTest(unittest.TestCase):
    def test_a_held_item_is_recorded_once_however_many_times_it_is_met(self):
        held_item = finding_record.parse_finding("`notes.py:1` the keys are out of order")
        real_item = finding_record.parse_finding("`app.py:2` the limit is wrong for `limit`")
        skipped_fp = []

        repo = pathlib.Path("/work/repo")
        first_kept, first_held, first_recorded = review_loop_held.skip_held_items([held_item, real_item], {"notes.py"},
                                                                                  {"app.py"}, skipped_fp, repo)
        second_kept, second_held, second_recorded = review_loop_held.skip_held_items([held_item], {"notes.py"},
                                                                                     {"app.py"}, skipped_fp, repo)

        self.assertEqual((first_kept, first_held, first_recorded), ([real_item], [held_item], 1))
        self.assertEqual((second_kept, second_held, second_recorded), ([], [held_item], 0))
        self.assertEqual(skipped_fp, [{"item": held_item, "reason": HELD_FILE_REASON}])


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
        with self.assertRaises(ValueError):
            self.closure('{"receipt": "a "b" c", "open": ["app.py:4 - unclosed]}')

    def test_the_prompt_tells_the_model_to_escape_quotes_in_the_receipt(self):
        prompts = []

        def claude_call(_label, prompt, *_args, **_kwargs):
            prompts.append(prompt)
            return '{"receipt": "none", "open": []}'

        review_loop_closure.closure_check(pathlib.Path("/repo"), pathlib.Path("/out"), ["app.py:3 - limit"],
                                          claude_call)

        self.assertIn('escape every double quote inside the receipt as \\"', prompts[0])


class ReviewLoopScriptTest(unittest.TestCase):
    def setUp(self):
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

    def test_converged_two_round_run_writes_packet_and_rows(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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

    def test_a_round_two_docs_fix_outside_the_fix_diff_is_deferred_not_sent_to_the_coder(self):
        outside_docs = "`notes.py:1` [docs] the value has no comment"
        second_review = f"## Fix\n- {outside_docs}\n\n## Ask\nNone\n\n## Nit\nNone\n"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": second_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Fixed 1."}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], handback.DEFERRED)
        self.assertEqual([entry["finding"] for entry in packet["findings_remaining"]], [outside_docs])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 1)
        notes_rows = [row for row in self.finding_rows() if row["path_key"] == "notes.py"]
        self.assertEqual([row["actioned"] for row in notes_rows], ["none"])

    def test_a_round_two_bug_fix_outside_the_fix_diff_still_goes_to_the_coder(self):
        outside_bug = "`notes.py:1` [bug] the value drops key c"
        outside_docs = "`notes.py:1` [docs] the value has no comment"
        second_review = f"## Fix\n- {outside_bug}\n- {outside_docs}\n\n## Ask\nNone\n\n## Nit\nNone\n"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": second_review}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 1.", "edits": {"notes.py": "value = {'a': 1, 'b': 2, 'c': 3}\n"}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        coders = [call for call in self.fake_calls() if call["key"] == "coder"]
        self.assertEqual(len(coders), 2)
        self.assertIn("the value drops key c", coders[1]["prompt"])
        self.assertNotIn("the value has no comment", coders[1]["prompt"])
        _, packet = self.stored_packet()
        self.assertIn(outside_bug, [entry["finding"] for entry in packet["fixed"]])
        self.assertEqual([entry["finding"] for entry in packet["findings_remaining"]], [outside_docs])

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
        }, header_extra="files: app.py\n")

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
        self.assertEqual([entry["file_line"] for entry in packet["skipped_fp"]], ["notes.py:1"])
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
        self.assertEqual([entry["file_line"] for entry in packet["skipped_fp"]], ["notes.py:1"])

    def test_a_held_file_that_changes_during_the_coder_call_is_left_and_named_in_the_hand_back(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        later = "value = {'a': 1, 'b': 4}  # the other session's edit made during the coder call\n"
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "outside_edits": {"notes.py": later}}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n")

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
        }, header_extra="files: app.py\n")

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual((self.repo / "notes.py").read_text(), later)
        _row, packet = self.stored_packet()
        self.assertIn("boom", packet["tool_fault"])
        self.assertIn("held files changed while coder1 ran", packet["tool_fault"])
        self.assertIn("notes.py", packet["tool_fault"])

    def test_a_finding_that_names_a_held_file_by_absolute_path_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_review = (f"## Fix\n- `{self.repo / 'notes.py'}:1` the keys are out of order\n\n## Ask\nNone\n\n"
                       "## Nit\nNone\n")
        completed = self.run_script({
            "code-reviewer": [{"result": held_review}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], [HELD_FILE_REASON])

    def test_a_finding_on_a_held_file_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_review = "## Fix\n- `notes.py:1` the keys are out of order\n\n## Ask\nNone\n\n## Nit\nNone\n"
        completed = self.run_script({
            "code-reviewer": [{"result": held_review}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], [HELD_FILE_REASON])

    def test_a_held_finding_beside_a_real_one_is_skipped_and_only_the_real_one_is_fixed(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        mixed = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n- `notes.py:1` the keys are out of order\n\n"
                 "## Ask\nNone\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")
        completed = self.run_script({
            "code-reviewer": [{"result": mixed}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], [HELD_FILE_REASON])
        self.assertEqual(packet["skipped_fp"][0]["file_line"], "notes.py:1")
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
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], [HELD_FILE_REASON])

    def test_a_plan_ask_on_a_held_file_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        held_ask = ("## Fix\nNone\n\n## Ask\n- `notes.py:1` [plan-drift] "
                    f"{PLAN_CHANGE_STATUS}: the owner moves to a new table; acceptance_criteria: none\n\n"
                    "## Nit\nNone\n")
        completed = self.run_script({
            "code-reviewer": [{"result": held_ask}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], [HELD_FILE_REASON])
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
        }, header_extra="files: app.py\n")

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
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], [HELD_FILE_REASON])

    def test_a_given_finding_on_a_held_file_is_skipped_and_no_coder_runs(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        completed = self.run_script({
            "code-reviewer": [{"result": CLEAN_REVIEW}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n" + self.findings_header("notes.py:1 the keys are out of order"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder"], [])
        _row, packet = self.stored_packet()
        self.assertEqual([entry["reason"] for entry in packet["skipped_fp"]], [HELD_FILE_REASON])

    def test_a_class_member_open_in_a_held_file_is_only_skipped_and_no_class_coder_runs(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        open_member = "`notes.py:1` the same limit is wrong here too"
        closure = json.dumps({"receipt": "one member still open", "open": [open_member]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": closure}],
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([call for call in self.fake_calls() if call["key"] == "coder-class"], [])
        _row, packet = self.stored_packet()
        self.assertEqual(packet["open_classes"], [])
        self.assertEqual([(entry["file_line"], entry["reason"]) for entry in packet["skipped_fp"]],
                         [("notes.py:1", HELD_FILE_REASON)])
        self.assertIn("held by another session", packet["class_closure"])
        self.assertIn("notes.py:1", packet["class_closure"])
        self.assertNotIn("one member still open", packet["class_closure"])

    def assert_packet_carries_the_member_left_alone(self, closure, class_coder, branch_text=None):
        left_alone = "`log.py:2` prints the limit, not a bound"
        closure_reply = json.dumps({**closure, "left_alone": [left_alone]})
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, *class_coder],
            "closure": [{"result": closure_reply}],
        }, header_extra="files: app.py\n")

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": closure_reply}],
        }, header_extra="files: app.py\n")

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": closure_reply}],
        }, header_extra="files: app.py\n")

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": closure}],
        }, header_extra="files: app.py\n")

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Nothing to change."}],
            "closure": [{"result": closure}],
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["open_classes"], [sent_member])
        _open_part, _sep, held_part = packet["class_closure"].partition("; skipped, held by another session: ")
        self.assertIn(held_member, held_part)
        self.assertTrue(
            packet["class_closure"].startswith("class members still open, the class repair changed nothing"))

    def test_a_nit_on_a_held_file_never_reaches_the_fix_coder(self):
        (self.repo / "notes.py").write_text("value = {'a': 1, 'b': 3}  # another session's edit\n")
        nit_review = FIX_REVIEW.replace("## Nit\nNone", "## Nit\n- `notes.py:1` rename the value")
        completed = self.run_script({
            "code-reviewer": [{"result": nit_review}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n")

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
        }, header_extra="files: app.py\n")

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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

    def test_a_held_untracked_file_the_coder_deletes_is_never_put_back(self):
        held_file = self.repo / "held_scratch.txt"
        held_file.write_text("select 1;\n")
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}, "deletes": [str(held_file)]}],
            "closure": [{"result": CLOSED}],
        }, header_extra="files: app.py\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(held_file.exists())
        _row, packet = self.stored_packet()
        self.assertIn("held_scratch.txt", packet["tool_fault"])
        self.assertNotIn("restored", packet["tool_fault"])

    def test_a_fix_that_moves_the_added_lines_into_a_new_file_converges(self):
        added = self.start_with_a_twelve_line_change()
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
        self.assertIn("Scoped tests after the last fix: passed", handback.render(packet, "review"))

    def test_a_scoped_test_left_red_by_the_last_fix_stops_the_loop(self):
        completed = self.run_with_scoped_tests(["grep -q 'limit = 99' app.py"], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        log_path = self.state_dir / "loop-script" / AGENT_ID / "scoped-tests.log"
        self.assertEqual(packet["scoped_tests"], f"failed: grep -q 'limit = 99' app.py; full output: {log_path}")
        self.assertIn("grep -q 'limit = 99' app.py", packet["blockers"][0])

    def stale_prose_command(self, exit_code):
        script = self.scratch / "stale_prose.py"
        script.write_text(STALE_PROSE_STAND_IN)
        return f"python3 {script} {exit_code}"

    def readability_command(self, exit_code):
        script = self.scratch / "readability_check.py"
        script.write_text(READABILITY_STAND_IN)
        return f"python3 {script} {exit_code}"

    def test_a_readability_hit_goes_to_the_coder_before_a_stale_prose_hit(self):
        readability_reply = {"result": "Split it.", "edits": {"app.py": APP_FIXED + "# split\n"}}
        prose_reply = {"result": "Every claim still holds."}
        scenario = {**FIX_THEN_CLEAN, "coder": [*FIX_THEN_CLEAN["coder"], readability_reply, prose_reply]}
        self.save_gate_commands(["grep -q 'limit = 20' app.py", self.stale_prose_command(1),
                                 self.readability_command(1)])

        completed = self.run_script(scenario)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))
        self.assertTrue(row["unreviewed_fix"])
        calls = json.dumps(self.fake_calls())
        self.assertLess(calls.index("LONG (50 lines"), calls.index("STALE app.py:1"))

    def test_a_readability_check_that_fails_itself_stops_the_loop(self):
        completed = self.run_with_scoped_tests([self.readability_command(2)], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("readability check failing", packet["blockers"][0])

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
        self.assertIn("scoped tests failing after the last fix", packet["blockers"][0])
        self.assertIn("corrected claim", packet["blockers"][0])

    def test_a_stale_prose_hit_the_coder_fixes_converges_and_ends_on_an_unreviewed_fix(self):
        reply = {"result": "Fixed the claim.", "edits": {"app.py": APP_FIXED + "# corrected claim\n"}}

        completed = self.run_with_a_stale_prose_hit(reply)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["blockers"]), ("converged", []))
        self.assertEqual(2, len(packet["fixed"]))
        self.assertEqual(3, packet["iter"])
        self.assertEqual(2, packet["review_round"])
        self.assertTrue(row["unreviewed_fix"])
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
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)
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

    def test_a_stale_prose_hit_report_over_the_tail_limit_reaches_the_coder_whole(self):
        script = self.scratch / "stale_prose.py"
        script.write_text("import sys\nprint('HEADER-OF-THE-REPORT')\nprint('x' * 13000)\nprint('LAST-HIT-LINE')\n"
                          "sys.exit(1)\n")
        self.save_gate_commands([f"python3 {script}"])
        scenario = {**FIX_THEN_CLEAN, "coder": [*FIX_THEN_CLEAN["coder"], {"result": "Every claim still holds."}]}

        completed = self.run_script(scenario)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = json.dumps(self.fake_calls())
        self.assertIn("HEADER-OF-THE-REPORT", calls)
        self.assertIn("LAST-HIT-LINE", calls)

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

    def test_a_fix_with_no_scoped_test_commands_says_none_ran(self):
        completed = self.run_with_scoped_tests([], FIX_THEN_CLEAN)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["scoped_tests"], "not run (no scoped test commands)")

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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

    def launch_with_dirty_gate(self):
        # What /code leaves behind when it launches the loop: the dispatch row and a dirty commit gate. Nothing else
        # runs after the script, as when the /code run ended before the loop handed back.
        store = self.scratch / "handback"
        store.mkdir()
        (store / f"{SESSION}.jsonl").write_text(json.dumps({"kind": "dispatch", "session_id": SESSION,
                                                                 "repo": str(self.repo)}) + "\n")
        gate_dir = self.scratch / "home" / ".claude" / "state" / "review-gate"
        gate_dir.mkdir(parents=True)
        (gate_dir / SESSION).write_text("dirty\n")

    def commit_gate_reply(self):
        hook_input = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": SESSION,
                      "cwd": str(self.repo), "tool_input": {"command": "git commit -m phase"}}
        env = {"PATH": os.environ["PATH"], "HOME": str(self.scratch / "home"), "TMPDIR": str(self.scratch)}
        gate = toolkit_paths.REVIEW_DIR / "review_commit_gate.py"
        finished = subprocess.run([sys.executable, str(gate)], input=json.dumps(hook_input), capture_output=True,
                                  text=True, env=env, cwd=str(self.repo))
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout

    def test_converged_loop_lets_the_commit_through_when_its_code_run_ended_first(self):
        self.launch_with_dirty_gate()

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.commit_gate_reply(), "")

    def test_failed_loop_leaves_the_commit_gate_closed(self):
        self.launch_with_dirty_gate()

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
        })

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("no converged /review", self.commit_gate_reply())

    def test_the_packet_the_script_hands_back_is_one_json_object(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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

        self.assertNotEqual(completed.returncode, 0)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertEqual(packet["files_touched"], ["app.py"])
        self.assertIn(limit_hit, packet["blockers"][0])
        self.assertIn("changed app.py before it died", packet["blockers"][0])

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertTrue(packet["full_check"].startswith("pre-existing failure"), packet["full_check"])
        self.assertIn("did not verify this diff", packet["full_check"])

    def run_scoped_tests_with_autofix(self, scoped_results):
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": {"app.py"}})
        with mock.patch.object(loop_script.coder_gate, "run_scoped_tests_with_failures",
                               side_effect=scoped_results) as scoped, \
                mock.patch.object(loop, "autofix_touched_files", return_value=True) as autofix:
            passed = loop.run_test_commands(["npm run lint"])
        return loop, passed, scoped.call_count, autofix.call_count

    def run_scoped_tests_red(self, failing_output):
        """run_test_commands with one red scoped command, `cat failing.txt; exit 1`, whose head output is
        `failing_output`; the commit holds failing.txt with one old failing test, so the base run is real."""
        self.commit_files({"failing.txt": "FAIL: test_old (shop.tests.OldTest)\n"})
        command = "cat failing.txt; exit 1"
        red = (f"failed: {command}", [f"`{command}` (exit 1):\n{failing_output}"],
               [(command, "exit 1", failing_output)])
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)
        loop = loop_script.LoopRun(self.repo, self.scratch, "", (), {"fixed": [], "files_touched": {"app.py"}})
        with mock.patch.object(loop_script.coder_gate, "run_scoped_tests_with_failures", return_value=red), \
                mock.patch.object(loop, "autofix_touched_files", return_value=False):
            passed = loop.run_test_commands([command])
        return loop, passed

    def test_a_scoped_failure_that_fails_the_same_way_on_head_without_the_diff_does_not_stop_the_loop(self):
        loop, passed = self.run_scoped_tests_red("FAIL: test_old (shop.tests.OldTest)\n")

        self.assertTrue(passed)
        self.assertNotEqual(loop.status, "critical-blocker")
        self.assertTrue(loop.scoped_tests.startswith("pre-existing failure"), loop.scoped_tests)

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

    def test_the_loop_base_run_gets_the_module_live_base_trees_and_the_gate_environment_assignments(self):
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)
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
        self.assertEqual(base_run.call_args.kwargs["gate_env"], {"APP_DIR": "/x"})

    def test_sigterm_during_the_base_run_removes_the_base_worktree(self):
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)
        temp = self.scratch / "base-temp"
        temp.mkdir()
        tree = temp / "base"
        git(self.repo, "worktree", "add", "--detach", str(tree), "HEAD")
        loop_script.full_check_gate.LIVE_BASE_TREES.add((self.repo, tree))
        self.addCleanup(loop_script.full_check_gate.LIVE_BASE_TREES.discard, (self.repo, tree))

        with mock.patch.object(loop_script.os, "_exit") as exit_now:
            loop_script.stop_on_sigterm(signal.SIGTERM, None)

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED, "notes.md": "# notes\nmore\n"}},
                      {"result": "Repaired."}],
            "closure": [{"result": CLOSED}],
        }, quality_check=check)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        tool_calls = (self.fake_dir / "tools.log").read_text().splitlines()
        self.assertIn("ruff check --fix app.py", tool_calls)
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)

        prompt = loop_script.coder_prompt(str(self.repo), ["`app.py:2` wrong limit"], ["a small item"], ["app.py"])

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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

    def finding_rows(self):
        return fake_ledger.recorded_rows(self.env, "review_finding")

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": first}, {"result": reworded}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}],
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

    def load_script_module(self):
        loader = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)
        return module

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
                         test_strategy="", iter_count=1)
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
        loader = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": other_fix_review}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": moved_review}],
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
            "code-reviewer": [{"result": two_fix_review}, {"result": new_fix_review}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Closed the class.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": closure}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["iter"]), ("converged", 3))
        self.assertEqual(packet["open_classes"], [])
        self.assertIn(open_member, [entry["finding"] for entry in packet["fixed"]])
        self.assertNotIn("still open", packet["class_closure"])
        self.assertIn("the class repair fixed these class members", packet["class_closure"])
        self.assertIn(open_member, packet["class_closure"])
        self.assertTrue(self.stored_packet()[0]["unreviewed_fix"])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 2)
        metrics = fake_ledger.recorded_rows(self.env, "review_metrics")
        self.assertEqual(metrics[0]["fixed"], "2")

    def test_the_class_closure_prompt_names_one_diff_file_per_path_and_holds_no_diff_text(self):
        (self.repo / "generated").mkdir()
        self.commit_files({"generated/snapshot.json": "{}\n"})
        snapshot = "".join(f'{{"row": {number}, "marker": "SNAPSHOT-LINE"}}\n' for number in range(20000))
        self.assertGreater(len(snapshot), 400_000)

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            except ValueError as error:
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
        self.assertIn("A previous reply to this prompt could not be parsed: ", retry_prompt)
        self.assertIn("JSON object only", retry_prompt)
        note = retry_prompt[len(calls[0][1]):]
        self.assertIn("x" * 100, note)
        self.assertNotIn("x" * 200, note)

    def test_two_bad_disposition_replies_raise_the_value_error(self):
        calls, outcome = self.disposition_calls_with(["no object here", "still none"])

        self.assertEqual(len(calls), 2)
        self.assertIsInstance(outcome, ValueError)
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
                fixed_source = APP_FIXED + f"# edit {number}\n"
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
                    "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "`load(path.json)`": {"load(path.json)"},
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
        (sessions / "4242.json").write_text(json.dumps({"pid": 4242, "sessionId": SESSION, "name": "app-abc-12-e6"}))
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
            "code-reviewer": [{"result": "The limit looks wrong."}, {"result": CLEAN_REVIEW}],
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
        (sessions / "4242.json").write_text(json.dumps({"pid": 4242, "sessionId": SESSION, "name": "app-abc-12-e6"}))

        self.assert_every_headless_role_is_named_as_a_child_of("app-abc-12-e6")

    def test_every_headless_role_is_named_as_a_child_of_a_parent_that_has_no_display_name(self):
        self.assert_every_headless_role_is_named_as_a_child_of(f"session {SESSION}")

    def test_the_gate_env_of_the_prompt_reaches_the_full_check_and_the_coder_brief(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": CLEAN_REVIEW}],
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
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)

        with mock.patch.object(loop_script.full_check_gate, "CHECK_TIMEOUT_SECONDS", 1):
            result, _tail, _details = loop_script.full_check_gate.run_full_check(self.repo, self.scratch, "sleep 30")

        self.assertEqual(result, "not run (timeout)")
        self.assertFalse(loop_script.full_check.is_failure(result))
        self.assertEqual(loop_script.LIVE_CHILDREN, set())

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

    def test_second_round_fix_converges_without_a_third_review(self):
        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": FIX_REVIEW}],
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}},
                      {"result": "Fixed 2.", "edits": {"app.py": APP_AFTER_EDIT}}],
            "closure": [{"result": CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        keys = [call["key"] for call in self.fake_calls()]
        self.assertEqual((keys.count("code-reviewer"), keys.count("coder")), (2, 2))
        self.assertFalse(row["no_reviewer"])
        self.assertTrue(row["unreviewed_fix"])

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
        disposition = json.dumps({"fix": [], "ask": ["`util.py:1` add a test for the limit"], "nit": []})

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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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
            "code-reviewer": [{"result": FIX_REVIEW}, {"result": CLEAN_REVIEW}],
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


if __name__ == "__main__":
    unittest.main()
