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
import handback

SCRIPT = pathlib.Path(os.environ.get("REVIEW_LOOP_SCRIPT") or toolkit_paths.REVIEW_DIR / "review_loop_script.py")
SESSION = "session-1"
RUN_ID = "run-1"
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
prompt = args[args.index("-p") + 1]
agent = args[args.index("--agent") + 1] if "--agent" in args else None
key = agent or ("closure" if "class-shaped" in prompt
                else "check-finder" if "full quality check" in prompt else "disposition")
fake_dir = os.environ["FAKE_CLAUDE_DIR"]

with open(os.path.join(fake_dir, "calls.jsonl"), "a") as handle:
    pane_names = ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH", "TUIOS_SOCKET")
    pane_env = {name: os.environ.get(name) for name in pane_names}
    record = {"key": key, "hook_off": os.environ.get("CLAUDE_FORMAT_HOOK_OFF"), "prompt": prompt,
              "pane_env": pane_env}
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

edits = dict(reply.get("edits", {}))
if os.environ.get("CLAUDE_FORMAT_HOOK_OFF") != "1":
    edits.update(reply.get("edits_when_format_hook_on", {}))
for path, text in edits.items():
    with open(path, "w") as handle:
        handle.write(text)

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
FIX_REVIEW = ("## Fix\n- `app.py:2` the limit is wrong for `limit`\n\n## Ask\nNone\n\n## Nit\nNone\n\n"
              "Overall Assessment: NEEDS CHANGES\n")
CLOSED = '{"receipt": "one exit, all re-read", "open": []}'


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


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
        self.state_dir = self.scratch / "state"

    def commit_files(self, files):
        for name, text in files.items():
            (self.repo / name).write_text(text)
        git(self.repo, "add", *files)
        git(self.repo, "commit", "-q", "-m", "files")

    def prompt_file_text(self, header_extra="", footer=""):
        return ("mode: review-first\ncaller: code\nlane: code\nplan: plan.md\nphase: 2\n"
                f"{header_extra}\nhandoff:\n  files:\n    - path: app.py\n{footer}")

    def script_command(self, prompt, session=SESSION):
        return [sys.executable, str(SCRIPT), str(self.repo), "--state-dir", str(self.state_dir), "--session", session,
                "--run-id", RUN_ID, "--agent-id", AGENT_ID, "--prompt-file", str(prompt)]

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

    def store_rows(self):
        path = self.scratch / "handback" / f"{SESSION}.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def run_events(self):
        code_step = git(self.repo, "rev-parse", "--path-format=absolute", "--git-path", "code-step")
        path = pathlib.Path(code_step) / "runs" / RUN_ID / "events.jsonl"
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

        handback_events = [event for event in self.run_events() if event["event"] == "handback"]
        self.assertEqual(len(handback_events), 1)
        self.assertEqual((handback_events[0]["agent_id"], handback_events[0]["agent_type"]), (AGENT_ID, "review-loop"))
        self.assertEqual(handback_events[0]["message"], row["message"])

        kinds = [stored["kind"] for stored in self.store_rows()]
        self.assertEqual(kinds, ["handback", "stop"])
        stop = self.store_rows()[1]
        self.assertEqual((stop["agent_id"], stop["open_dispatches"], stop["ask_rows"]), (AGENT_ID, 0, []))
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": self.env["HANDBACK_STORE_DIR"]}):
            latest_stop = handback.latest(SESSION)["stop"]
        self.assertEqual(latest_stop["open_dispatches"], 0)

        runs = fake_ledger.recorded_rows(self.env, "review_run")
        self.assertEqual([run["scope"] for run in runs], ["phase", "phase"])

        usage = self.usage_rows()
        self.assertEqual(len(usage), 1)
        self.assertEqual((usage[0]["agent"], usage[0]["model"], usage[0]["driver"]),
                         ("review-loop", "script", "script"))
        self.assertEqual((usage[0]["calls"], usage[0]["tokens"]), (4, 80))

    def test_untracked_binary_file_does_not_stop_a_clean_review(self):
        (self.repo / "logo.png").write_bytes(b"\x89PNG\xff\xfe\x00")

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}],
                                     "smell-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")

    def launch_with_dirty_gate(self):
        # What /code leaves behind when it launches the loop: the dispatch row and a dirty commit gate. Nothing else
        # runs after the script, as when the /code run ended before the loop handed back.
        store = self.scratch / "handback"
        store.mkdir()
        (store / f"{SESSION}.jsonl").write_text(json.dumps({"kind": "dispatch", "session_id": SESSION}) + "\n")
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

    def test_check_finder_names_the_full_check_when_claude_md_has_no_line(self):
        completed = self.run_script({"check-finder": [{"result": 'Found it in the Makefile. {"command": "true"}'}],
                                     "code-reviewer": [{"result": CLEAN_REVIEW}],
                                     "smell-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="Run make ci before you push.\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(self.fake_calls()[0]["key"], "check-finder")

    def test_a_repo_with_no_check_found_is_reviewed_and_its_packet_says_no_full_check_ran(self):
        no_check = '{"command": null, "reason": "no CI config or task runner"}'

        completed = self.run_script({"check-finder": [{"result": no_check}],
                                     "code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="No check named here.\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(packet["full_check"], "not run (no check found; the coder's scoped tests stand)")
        self.assertIn("code-reviewer", [call["key"] for call in self.fake_calls()])

    def test_plan_change_ask_maps_to_plan_impact(self):
        ask_review = (f"## Fix\nNone\n\n## Ask\n- {PLAN_CHANGE_STATUS}: the fix needs a new column the plan "
                      "rules out\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": ask_review}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], PLAN_CHANGE_STATUS)
        self.assertIn("needs a new column", packet["plan_impact"])
        self.assertEqual([call["key"] for call in self.fake_calls()], ["code-reviewer"])

    def test_a_tagged_plan_change_ask_maps_to_plan_impact(self):
        ask_review = (f"## Fix\nNone\n\n## Ask\n- `src/a.py:12` [plan-drift] — {PLAN_CHANGE_STATUS}: the fix needs "
                      "a new column the plan rules out\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": ask_review}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], PLAN_CHANGE_STATUS)
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

    def test_a_plan_change_ask_that_opens_with_its_file_line_stops_the_loop(self):
        located_ask = (f"## Fix\nNone\n\n## Ask\n- `app.py:3` [plan-drift] {PLAN_CHANGE_STATUS}: the fix needs a new "
                       "column the plan rules out\n\n## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": located_ask}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], PLAN_CHANGE_STATUS)

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
        scenario = {"code-reviewer": [{"result": CLEAN_REVIEW}], "smell-reviewer": [{"result": CLEAN_REVIEW}]}
        (self.repo / "fresh.py").write_text("created = True\n")

        self.run_script(scenario, header_extra="structure-pass: skip\n")
        skipped_keys = sorted(call["key"] for call in self.fake_calls())
        (self.fake_dir / "calls.jsonl").unlink()
        (self.fake_dir / "counters.json").unlink()
        self.run_script(scenario)
        full_keys = sorted(call["key"] for call in self.fake_calls())

        self.assertEqual(skipped_keys, ["code-reviewer"])
        self.assertEqual(full_keys, ["code-reviewer", "smell-reviewer"])

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
            "coder": [{"result": "Fixed 1.", "edits": {"app.py": APP_FIXED}}, {"result": "Closed the class."}],
            "closure": [{"result": closure}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual((packet["status"], packet["iter"]), ("converged", 3))
        self.assertIn(open_member, [entry["finding"] for entry in packet["fixed"]])
        self.assertTrue(self.stored_packet()[0]["unreviewed_fix"])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("coder"), 2)
        metrics = fake_ledger.recorded_rows(self.env, "review_metrics")
        self.assertEqual(metrics[0]["fixed"], "2")

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

    def test_a_coder_report_of_plan_impact_stops_with_the_report_and_no_second_review(self):
        report = "Cannot fix 1: it needs a new column the plan rules out.\nplan-impact: yes"

        completed = self.run_script({
            "code-reviewer": [{"result": FIX_REVIEW}],
            "coder": [{"result": report}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], PLAN_CHANGE_STATUS)
        self.assertIn("needs a new column", packet["plan_impact"])
        self.assertEqual([call["key"] for call in self.fake_calls()].count("code-reviewer"), 1)
        self.assertEqual([row["actioned"] for row in self.finding_rows()], ["none"])

    def test_an_ask_with_an_empty_change_is_a_critical_blocker_that_keeps_the_ask_rows(self):
        ask_review = ("## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit be configurable? — change:\n\n"
                      "## Nit\nNone\n")

        completed = self.run_script({"code-reviewer": [{"result": ask_review}]})

        self.assertNotEqual(completed.returncode, 0)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "critical-blocker")
        self.assertIn("ask entry has no change", packet["blockers"][0])
        stop = self.store_rows()[-1]
        self.assertEqual([(row["file"], row["line"]) for row in stop["ask_rows"]], [("app.py", 3)])

    def test_prose_that_mentions_a_quality_check_does_not_name_the_check_command(self):
        completed = self.run_script({"check-finder": [{"result": '{"command": "true"}'}],
                                     "code-reviewer": [{"result": CLEAN_REVIEW}]},
                                    claude_md="Run a quality check before you push; `false` is not it.\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        _, packet = self.stored_packet()
        self.assertEqual(packet["status"], "converged")
        self.assertEqual(self.fake_calls()[0]["key"], "check-finder")

    def test_child_calls_do_not_inherit_the_terminal_pane_variables(self):
        for name in ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH", "TUIOS_SOCKET"):
            self.env[name] = "set"

        completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.fake_calls()
        self.assertTrue(calls)
        for call in calls:
            self.assertEqual(set(call["pane_env"].values()), {None})

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

    def test_a_repo_whose_full_suite_runs_in_ci_converges_without_running_its_check(self):
        for claude_md in ("Quality check: `false`\nFull suite: CI\n", "- Full suite: CI\n"):
            with self.subTest(claude_md=claude_md):
                (self.fake_dir / "calls.jsonl").unlink(missing_ok=True)
                (self.fake_dir / "counters.json").unlink(missing_ok=True)
                (self.scratch / "handback").mkdir(exist_ok=True)
                for stored in (self.scratch / "handback").iterdir():
                    stored.unlink()

                completed = self.run_script({"code-reviewer": [{"result": CLEAN_REVIEW}]}, claude_md=claude_md)

                self.assertEqual(completed.returncode, 0, completed.stderr)
                _, packet = self.stored_packet()
                self.assertEqual((packet["status"], packet["full_check"]), ("converged", "not run (CI)"))
                self.assertEqual([call["key"] for call in self.fake_calls()], ["code-reviewer"])

    def test_a_full_check_past_its_limit_is_not_run_and_no_failure(self):
        spec = importlib.util.spec_from_file_location("review_loop_script_under_test", SCRIPT)
        loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loop_script)

        with mock.patch.object(loop_script, "CHECK_TIMEOUT_SECONDS", 1):
            result, _tail = loop_script.run_full_check(self.repo, self.scratch, "sleep 30")

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
        stat = pathlib.Path(f"/proc/{pid}/stat")
        return not (stat.exists() and stat.read_text().rpartition(")")[2].split()[0] == "Z")

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
        self.assertEqual(packet["findings_remaining"], [])
        self.assertFalse(row["no_reviewer"])
        self.assertTrue(row["unreviewed_fix"])

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
