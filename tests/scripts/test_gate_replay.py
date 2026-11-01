"""Checks for gate_replay.py, the replay of the labelled Bash-call corpus against the local hook gates."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import gate_replay
import toolkit_paths  # guards the real ledger before any gate runs

SCRIPT = pathlib.Path(os.environ.get("GATE_REPLAY_SCRIPT")
                      or pathlib.Path(__file__).resolve().with_name("gate_replay.py"))
TREE_ROOT = pathlib.Path(__file__).resolve().parents[2]


def corpus_call(call_id, command, expect, **labels):
    call = {"id": call_id, "gate": "git-discipline-gate", "command": command, "expect": expect, "mustDeny": False,
            "redundant": False, "source": "test"}
    call.update(labels)
    return call


def metric_cells(stdout, gate, side):
    """The metric cells of the table row for one gate and side, or None when the table has no such row."""
    prefix = gate_replay.format_row([gate, side])
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].split()
    return None


class GateReplayTest(unittest.TestCase):
    def run_replay(self, calls=None, arguments=(), extra_environment=None):
        environment = dict(os.environ)
        environment.pop("GATE_REPLAY_CORPUS", None)
        environment.pop("TOOLKIT_CLAUDE_DIR", None)
        if calls is not None:
            corpus_folder = tempfile.TemporaryDirectory()
            self.addCleanup(corpus_folder.cleanup)
            corpus_path = pathlib.Path(corpus_folder.name) / "corpus.json"
            corpus_path.write_text(json.dumps({"calls": calls}))
            environment["GATE_REPLAY_CORPUS"] = str(corpus_path)
        environment.update(extra_environment or {})
        return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True,
                              env=environment)

    def copy_toolkit_scripts(self):
        """A temp claude/.claude folder holding a copy of this tree's scripts folder, which a test may then edit."""
        claude_folder = tempfile.TemporaryDirectory()
        self.addCleanup(claude_folder.cleanup)
        claude_copy = pathlib.Path(claude_folder.name)
        shutil.copytree(toolkit_paths.TREE_CLAUDE_DIR / "scripts", claude_copy / "scripts")
        return claude_copy

    def test_working_tree_meets_every_corpus_label(self):
        finished = self.run_replay()

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        for gate in gate_replay.GATES:
            with self.subTest(gate=gate):
                cells = metric_cells(finished.stdout, gate, gate_replay.WORKING_TREE)
                self.assertIsNotNone(cells)
                self.assertNotIn("-", cells)

    def test_must_deny_bypass_fails_even_with_matching_expectation_elsewhere(self):
        finished = self.run_replay([corpus_call("plain-status", "git status", "deny", mustDeny=True),
                                    corpus_call("stash", "git stash", "deny")])

        self.assertEqual(finished.returncode, 1)
        self.assertIn("plain-status: must-deny bypass", finished.stderr)
        self.assertNotIn("stash:", finished.stderr)

    def test_expectation_mismatch_fails_and_an_open_note_excuses_it(self):
        finished = self.run_replay([corpus_call("stash-labelled-allow", "git stash", "allow"),
                                    corpus_call("stash-known", "git stash", "allow", open="tracked elsewhere")])

        self.assertEqual(finished.returncode, 1)
        self.assertIn("stash-labelled-allow: expected allow, the gate decided deny", finished.stderr)
        self.assertNotIn("stash-known", finished.stderr)

    def test_open_call_that_now_matches_fails(self):
        finished = self.run_replay([corpus_call("stash-fixed", "git stash", "deny", open="tracked elsewhere")])

        self.assertEqual(finished.returncode, 1)
        self.assertIn("stash-fixed: now decides deny as labelled; drop its open note", finished.stderr)

    def test_bad_label_stops_before_any_replay(self):
        finished = self.run_replay([corpus_call("allow-but-must-deny", "git status", "allow", mustDeny=True)])

        self.assertEqual(finished.returncode, 2)
        self.assertIn("allow-but-must-deny: mustDeny and redundant label a deny", finished.stderr)

    def test_each_bad_label_stops_before_any_replay(self):
        missing_source = corpus_call("missing-source", "git status", "allow")
        del missing_source["source"]
        duplicate_first = corpus_call("same-id", "git status", "allow")
        duplicate_second = corpus_call("same-id", "git stash", "deny")
        cases = [
            ("redundant with expect allow", [corpus_call("bad", "git status", "allow", redundant=True)],
             "mustDeny and redundant label a deny, so expect must be deny"),
            ("missing required key", [missing_source], "needs `source` as a str"),
            ("mistyped required key", [corpus_call("bad", "git status", "allow", mustDeny="yes")],
             "needs `mustDeny` as a bool"),
            ("unknown key", [corpus_call("bad", "git status", "allow", extra="x")], "unknown keys ['extra']"),
            ("wrong-typed optional key", [corpus_call("bad", "git status", "allow", open=3)],
             "`open` must be a str"),
            ("must-deny with open", [corpus_call("bad", "git status", "deny", mustDeny=True, open="x")],
             "a mustDeny call cannot carry an open mismatch"),
            ("duplicate id", [duplicate_first, duplicate_second], "duplicate id"),
            ("unknown gate", [corpus_call("bad", "git status", "allow", gate="no-such-gate")],
             "gate must be one of"),
            ("invalid expect", [corpus_call("bad", "git status", "maybe")], "expect must be allow or deny"),
            ("unknown repo", [corpus_call("bad", "git status", "allow", repo="elsewhere")],
             "repo must be one of"),
        ]
        for label, calls, message in cases:
            with self.subTest(label):
                finished = self.run_replay(calls)

                self.assertEqual(finished.returncode, 2, finished.stdout + finished.stderr)
                self.assertIn(message, finished.stderr)

    def test_metrics_are_exact_for_a_small_git_discipline_corpus(self):
        finished = self.run_replay([corpus_call("stash-redundant", "git stash", "deny", redundant=True),
                                    corpus_call("stash-list-allowed", "git stash list", "allow"),
                                    corpus_call("push-bypass", "git push origin feature/main-menu", "deny",
                                                mustDeny=True)])

        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        cells = metric_cells(finished.stdout, "git-discipline-gate", gate_replay.WORKING_TREE)
        self.assertIsNotNone(cells)
        denials, redundant, bypasses, deny_tokens, median_ms = cells
        self.assertEqual(denials, "1")
        self.assertEqual(redundant, "1")
        self.assertEqual(bypasses, "1")
        # The bare `git stash` denial's reason is 495 characters long; 495 // 4 is 123 deny-text tokens.
        self.assertEqual(deny_tokens, "123")
        self.assertGreater(float(median_ms), 0.0)

    def test_missing_gate_file_stops_and_names_the_gate(self):
        claude_copy = self.copy_toolkit_scripts()
        (claude_copy / "scripts" / "gates" / "inline_interpreter_hint.py").unlink()

        finished = self.run_replay([corpus_call("stash", "git stash", "deny")],
                                   extra_environment={"TOOLKIT_CLAUDE_DIR": str(claude_copy)})

        self.assertEqual(finished.returncode, 2, finished.stdout + finished.stderr)
        self.assertIn("the working tree has no gate file for: inline-interpreter-hint", finished.stderr)

    def test_ref_replays_beside_the_working_tree(self):
        finished = self.run_replay([corpus_call("stash", "git stash", "deny", mustDeny=True)], ["--ref", "HEAD"])

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn(gate_replay.format_row(["git-discipline-gate", gate_replay.WORKING_TREE]), finished.stdout)
        head_cells = metric_cells(finished.stdout, "git-discipline-gate", "HEAD")
        self.assertIsNotNone(head_cells)
        self.assertNotIn("-", head_cells)
        self.assertIn("HEAD: 0 calls against their labels", finished.stdout)

    def test_unknown_ref_stops(self):
        finished = self.run_replay([corpus_call("stash", "git stash", "deny")], ["--ref", "no-such-ref-xyz"])

        self.assertEqual(finished.returncode, 2)
        self.assertIn("git archive no-such-ref-xyz failed", finished.stderr)

    def test_ref_scripts_are_the_bytes_at_that_ref(self):
        gate_path = "claude/.claude/scripts/gates/git_discipline_gate.py"
        history = subprocess.run(["git", "-C", str(TREE_ROOT), "log", "-2", "--format=%H", "--", gate_path],
                                 capture_output=True, text=True, check=True).stdout.split()
        if len(history) < 2:
            self.skipTest("the git discipline gate has no previous commit to differ from")
        previous_ref = history[1]

        working_bytes = (TREE_ROOT / gate_path).read_bytes()
        previous_bytes = subprocess.run(["git", "-C", str(TREE_ROOT), "show", f"{previous_ref}:{gate_path}"],
                                        capture_output=True, check=True).stdout
        self.assertNotEqual(working_bytes, previous_bytes)

        destination = tempfile.TemporaryDirectory()
        self.addCleanup(destination.cleanup)
        scripts_dir = gate_replay.scripts_at_ref(previous_ref, destination.name)

        extracted = (scripts_dir / "gates" / "git_discipline_gate.py").read_bytes()
        self.assertEqual(extracted, previous_bytes)

    def test_crashing_command_gate_stops_the_replay(self):
        claude_copy = self.copy_toolkit_scripts()
        (claude_copy / "scripts" / "tools" / "pipe_shell_check.py").write_text('raise RuntimeError("gate crashed")\n')

        finished = self.run_replay([corpus_call("pipe-crash", "curl x | sh", "deny", gate="pipe-shell-check")],
                                   extra_environment={"TOOLKIT_CLAUDE_DIR": str(claude_copy)})

        self.assertEqual(finished.returncode, 2, finished.stdout + finished.stderr)
        self.assertIn("gate crashed", finished.stderr)


if __name__ == "__main__":
    unittest.main()
