"""Checks for log-escape: it writes one review_escape row through `ledger write`.

A stand-in `ledger` (fake_ledger) records what the script sends. Every case runs in a temp git repo with HOME
set to a temp dir, so nothing reaches a real log.

Script location: LOG_ESCAPE_SCRIPT, defaulting to ~/.claude/scripts/telemetry/log-escape.
"""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

import fake_ledger
import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("LOG_ESCAPE_SCRIPT") or toolkit_paths.TELEMETRY_DIR / "log-escape")

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

PLANTED_BRANCH = "planted-branch-zq"
VALID_ARGS = ["gate_missed=review", "stage_found=pr-human", "severity=high", "class=bug", "guard=none",
              "miss_reason=overlooked"]
PROMPT_DIRS = ("skills", "agents", "commands")
TEMPLATE_PAIR = re.compile(r'(\w+)=("[^"]*"|<[^>]*>|[^\s`)]+)')
# A placeholder with no options of its own (`<...>`, `<comment gist>`) takes this value for its key.
PLACEHOLDER_VALUES = {"stage_found": "cc", "gate_missed": "review", "class": "bug", "severity": "low",
                      "lane": "code", "guard": "none", "miss_reason": "overlooked", "line": "1"}
MISS_REASONS = ("out-of-scope", "needs-other-file", "needs-runtime", "plan-gap", "seen-dismissed", "rule-absent",
                "overlooked", "unknown")


class LogEscapeTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.ledger_env = fake_ledger.install(self.temp_root)
        self.repo = self.temp_root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", PLANTED_BRANCH)
        (self.repo / "kept.txt").write_text("one\n")
        self.git("add", "kept.txt")
        self.git("commit", "-q", "-m", "base")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True,
                              capture_output=True, text=True).stdout.strip()

    def environment(self, **extra):
        caller_env = {key: value for key, value in os.environ.items()
                     if key not in ("CLAUDE_TOOLKIT_TELEMETRY", "CLAUDE_CODE_SESSION_ID")}
        return {**caller_env, **GIT_ENV, **self.ledger_env, "HOME": str(self.home),
                "CLAUDE_TOOLKIT_TELEMETRY": "1", **extra}

    def run_escape(self, *args, env=None):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.repo, env=env or self.environment(),
                              capture_output=True, text=True)

    def escape_rows(self):
        return fake_ledger.recorded_rows(self.ledger_env, "review_escape")

    def test_writes_review_escape_with_string_values(self):
        done = self.run_escape(*VALID_ARGS, "line=7", "lane=code")
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        rows = self.escape_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gate_missed"], "review")
        self.assertEqual(rows[0]["line"], "7")
        for field in ("date", "schema_version", "repo", "session"):
            self.assertNotIn(field, rows[0])

    def test_drops_desc_and_scan_flagged(self):
        done = self.run_escape(*VALID_ARGS, "desc=planted description zq", "scan_flagged=1")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.escape_rows()[0]
        self.assertNotIn("desc", row)
        self.assertNotIn("scan_flagged", row)

    def test_renames_file_and_branch_to_keyed_fields(self):
        done = self.run_escape(*VALID_ARGS, "file=src/planted_widget_zq.rs", "branch=caller-branch")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.escape_rows()[0]
        self.assertEqual(row["path_key"], "src/planted_widget_zq.rs")
        self.assertEqual(row["branch_key"], "caller-branch")
        self.assertNotIn("file", row)
        self.assertNotIn("branch", row)

    def test_seeds_head_and_branch_from_git(self):
        done = self.run_escape(*VALID_ARGS)
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.escape_rows()[0]
        self.assertEqual(row["head"], self.git("rev-parse", "HEAD"))
        self.assertEqual(row["branch_key"], PLANTED_BRANCH)

    def test_caller_branch_wins(self):
        done = self.run_escape(*VALID_ARGS, "branch=caller-branch")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["branch_key"], "caller-branch")

    def test_an_empty_line_is_refused_and_writes_no_row(self):
        done = self.run_escape(*VALID_ARGS, "line=")
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: line= is not a whole number.", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_a_line_with_a_trailing_newline_is_refused_and_writes_no_row(self):
        done = self.run_escape(*VALID_ARGS, "line=12\n")
        self.assertEqual(done.returncode, 1)
        self.assertIn("line=12\\n is not a whole number.", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_space_in_a_non_free_value_is_refused(self):
        done = self.run_escape(*VALID_ARGS, "lane=two words")
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: lane= contains a space: 'two words'", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_pairs_in_one_unsplit_argument_are_folded_one_by_one(self):
        # zsh does not split an unquoted variable: C="gate_missed=review severity=high"; log-escape $C
        # sends one argument.
        done = self.run_escape("gate_missed=review stage_found=pr-human  severity=high", "class=bug", "guard=none",
                               "miss_reason=unknown")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.escape_rows()[0]
        self.assertEqual((row["gate_missed"], row["stage_found"], row["severity"]), ("review", "pr-human", "high"))

    def test_a_spaced_value_with_a_bare_word_after_a_pair_is_refused(self):
        done = self.run_escape(*VALID_ARGS, "lane=code line=7 extra")
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: lane= contains a space", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_file_with_a_swallowed_pair_is_refused(self):
        swallowing = ("a.py lane=code", "a.py\tlane=code", "a.py\nb.py", "a.py\rb.py")
        for path in swallowing:
            with self.subTest(path=path):
                done = self.run_escape(*VALID_ARGS, f"file={path}")
                self.assertEqual(done.returncode, 1)
                self.assertIn("refusing to log: file= holds a line break or whitespace then a name=", done.stderr)
                self.assertIn("Quote each key=value separately", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        done = self.run_escape(*VALID_ARGS, "file=src/my dir/a b.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["path_key"], "src/my dir/a b.py")

    def test_desc_with_spaces_is_accepted_and_dropped(self):
        done = self.run_escape(*VALID_ARGS, "desc=free text, with spaces")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("desc", self.escape_rows()[0])

    def test_missing_guard_is_refused_with_the_ratchet_pointer(self):
        args = [argument for argument in VALID_ARGS if argument != "guard=none"]
        done = self.run_escape(*args)
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: guard= is required.", done.stderr)
        self.assertIn("escape-ratchet.md", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_each_miss_reason_reaches_the_ledger_as_plain_text(self):
        for label in MISS_REASONS:
            with self.subTest(label=label):
                args = [argument for argument in VALID_ARGS if not argument.startswith("miss_reason=")]
                done = self.run_escape(*args, f"miss_reason={label}")
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(self.escape_rows()[-1]["miss_reason"], label)

    def test_a_missing_miss_reason_is_refused_with_the_ratchet_pointer(self):
        args = [argument for argument in VALID_ARGS if not argument.startswith("miss_reason=")]
        done = self.run_escape(*args)
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: miss_reason=", done.stderr)
        self.assertIn("escape-ratchet.md", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_an_eng_spec_escape_needs_no_miss_reason_and_sends_none(self):
        args = [argument for argument in VALID_ARGS
                if not argument.startswith(("miss_reason=", "gate_missed=", "stage_found="))]
        env = self.environment(FAKE_LEDGER_UNKNOWN_FIELDS="miss_reason")
        done = self.run_escape(*args, "gate_missed=eng-spec", "stage_found=plan-review", env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("does not store miss_reason", done.stderr)
        (row,) = self.escape_rows()
        self.assertNotIn("miss_reason", row)
        self.assertEqual(row["gate_missed"], "eng-spec")

    def test_an_eng_spec_escape_with_an_empty_miss_reason_sends_none(self):
        args = [argument for argument in VALID_ARGS
                if not argument.startswith(("miss_reason=", "gate_missed="))]
        done = self.run_escape(*args, "gate_missed=eng-spec", "miss_reason=")
        self.assertEqual(done.returncode, 0, done.stderr)
        (row,) = self.escape_rows()
        self.assertNotIn("miss_reason", row)

    def test_an_eng_spec_escape_still_validates_a_given_miss_reason(self):
        args = [argument for argument in VALID_ARGS
                if not argument.startswith(("miss_reason=", "gate_missed="))]
        refused = self.run_escape(*args, "gate_missed=eng-spec", "miss_reason=vibes")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("refusing to log: miss_reason=", refused.stderr)
        self.assertEqual(self.escape_rows(), [])
        accepted = self.run_escape(*args, "gate_missed=eng-spec", "miss_reason=plan-gap")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(self.escape_rows()[-1]["miss_reason"], "plan-gap")

    def test_only_the_eng_spec_gate_may_omit_miss_reason(self):
        for gate in ("plan", "eng-spec-x"):
            with self.subTest(gate=gate):
                args = [argument for argument in VALID_ARGS
                        if not argument.startswith(("miss_reason=", "gate_missed=", "stage_found="))]
                done = self.run_escape(*args, f"gate_missed={gate}", "stage_found=plan-review")
                self.assertEqual(done.returncode, 1)
                self.assertIn("refusing to log: miss_reason=", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_a_miss_reason_outside_the_list_is_refused(self):
        for label in ("vibes", "plan", "plan-gap,unknown", ""):
            with self.subTest(label=label):
                args = [argument for argument in VALID_ARGS if not argument.startswith("miss_reason=")]
                done = self.run_escape(*args, f"miss_reason={label}")
                self.assertEqual(done.returncode, 1)
                self.assertIn("refusing to log: miss_reason=", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_unknown_class_reaches_the_ledger(self):
        args = [argument.replace("class=bug", "class=nonsense") for argument in VALID_ARGS]
        done = self.run_escape(*args)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["class"], "nonsense")

    def test_unknown_guard_reaches_the_ledger_as_given(self):
        args = [argument.replace("guard=none", "guard=vibes") for argument in VALID_ARGS]
        done = self.run_escape(*args)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["guard"], "vibes")

    def test_check_writes_nothing(self):
        done = self.run_escape("--check", *VALID_ARGS)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertEqual(self.escape_rows(), [])

    def test_telemetry_off_writes_nothing(self):
        done = self.run_escape(*VALID_ARGS, env=self.environment(CLAUDE_TOOLKIT_TELEMETRY="0"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "not logged: toolkit telemetry is off\n")
        self.assertEqual(self.escape_rows(), [])

    def local_rows(self):
        log_text = (self.home / ".claude" / "review-escapes.jsonl").read_text()
        return [json.loads(line) for line in log_text.splitlines()]

    def test_a_ledger_failure_keeps_the_row_locally_with_one_note_and_exit_0(self):
        for code in (2, 1, 75):
            with self.subTest(code=code):
                done = self.run_escape(*VALID_ARGS, env=self.environment(FAKE_LEDGER_WRITE_EXIT=str(code)))
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(len(done.stderr.splitlines()), 1, done.stderr)
                self.assertIn(f"ledger write exit {code}", done.stderr)
                self.assertEqual(self.local_rows()[-1]["miss_reason"], "overlooked")
        self.assertEqual(len(self.local_rows()), 3)
        self.assertEqual(self.escape_rows(), [])

    def test_the_local_row_names_the_file_and_branch_as_the_no_ledger_path_does(self):
        env = self.environment(FAKE_LEDGER_WRITE_EXIT="1")
        done = self.run_escape(*VALID_ARGS, "file=src/planted_widget_zq.rs", env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        (row,) = self.local_rows()
        self.assertEqual(row["file"], "src/planted_widget_zq.rs")
        self.assertEqual(row["branch"], PLANTED_BRANCH)

    def test_each_required_field_is_refused_before_the_ledger(self):
        for field in ("gate_missed", "stage_found", "class"):
            with self.subTest(field=field):
                args = [argument for argument in VALID_ARGS if not argument.startswith(f"{field}=")]
                done = self.run_escape(*args)
                self.assertEqual(done.returncode, 1)
                self.assertIn(f"refusing to log: {field}= is required.", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        self.assertFalse((self.home / ".claude" / "review-escapes.jsonl").exists())

    def test_a_ledger_build_without_miss_reason_gets_the_row_without_it_and_the_caller_goes_on(self):
        done = self.run_escape(*VALID_ARGS, env=self.environment(FAKE_LEDGER_UNKNOWN_FIELDS="miss_reason"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("does not store miss_reason", done.stderr)
        self.assertNotIn("field_unknown", done.stderr)
        (row,) = self.escape_rows()
        self.assertNotIn("miss_reason", row)
        self.assertEqual(row["gate_missed"], "review")

    def test_a_refusal_of_another_field_keeps_the_row_locally_with_its_miss_reason(self):
        done = self.run_escape(*VALID_ARGS, env=self.environment(FAKE_LEDGER_UNKNOWN_FIELDS="guard"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("field_unknown guard", done.stderr)
        self.assertNotIn("does not store", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        (row,) = self.local_rows()
        self.assertEqual(row["miss_reason"], "overlooked")

    def test_a_refusal_after_the_miss_reason_retry_keeps_the_row_locally(self):
        env = self.environment(FAKE_LEDGER_UNKNOWN_FIELDS="miss_reason,guard")
        done = self.run_escape(*VALID_ARGS, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows(), [])
        self.assertEqual(len(self.local_rows()), 1)

    def test_with_no_ledger_the_row_lands_in_the_local_file_with_its_miss_reason(self):
        no_ledger_path = fake_ledger.path_without_ledger(self.ledger_env["PATH"])
        env = self.environment(PATH=no_ledger_path, CARGO_HOME=str(self.home / ".cargo"))
        done = self.run_escape(*VALID_ARGS, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("no ledger found; row appended to", done.stderr)
        (row,) = self.local_rows()
        self.assertEqual(row["miss_reason"], "overlooked")

    def test_help_prints_usage_and_writes_nothing(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                done = self.run_escape(flag)
                self.assertEqual((done.returncode, done.stderr), (0, ""))
                self.assertIn("usage: log-escape [--check] key=value", done.stdout)
                self.assertEqual(fake_ledger.recorded_rows(self.ledger_env), [])

    def test_every_prompt_template_passes_check(self):
        templates = prompt_templates()
        self.assertTrue(templates)
        for source, line in templates:
            with self.subTest(source=source, line=line):
                done = self.run_escape("--check", *template_args(line))
                self.assertEqual(done.returncode, 0, done.stderr)


def prompt_templates():
    """Each (file, line) in the prompt files that shows a log-escape call with its fields."""
    templates = []
    for prompt_dir in PROMPT_DIRS:
        for prompt_file in sorted((toolkit_paths.CLAUDE_DIR / prompt_dir).rglob("*.md")):
            for line in prompt_file.read_text().splitlines():
                if "log-escape" in line and "stage_found=" in line:
                    templates.append((prompt_file.name, line))
    return templates


def template_args(line):
    """The template's key=value pairs, each placeholder filled with its first option or a known valid value."""
    args = []
    for key, raw_value in TEMPLATE_PAIR.findall(line):
        value = raw_value.strip('"')
        if value.startswith("<") and value.endswith(">"):
            first_option = value[1:-1].split("|")[0]
            has_options = "|" in value and first_option != "..."
            value = first_option if has_options else PLACEHOLDER_VALUES.get(key, "x")
        args.append(f"{key}={value}")
    return args


if __name__ == "__main__":
    unittest.main()
