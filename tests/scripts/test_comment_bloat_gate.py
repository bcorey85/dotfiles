"""Checks for comment_bloat_gate.py, the PostToolUse hook.

It blocks workflow-marker leaks and comment blocks of three or more lines that are not a kept kind.
"""
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR)
SCRIPT = SCRIPTS_DIR / "comment_bloat_gate.py"

# Split so this file does not itself carry the plan-path marker the gate looks for.
MARKER_LINE = "# see dev/agent-ledger-LED-7/docs/" + "plans/LED-7-watch-metrics/spec.md"

PHASE_WORD = "Pha" + "se"

COMMENT_LEADERS = ("#", "//", "--")
SHEBANG = "#!"
BLOCKED_RUN_LENGTH = 3


class CommentBloatGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        subprocess.run(["git", "init", "-q", self.tmp.name], check=True)
        self.home = pathlib.Path(self.tmp.name) / "home"
        self.home.mkdir()

    def source(self, relative, content):
        path = pathlib.Path(self.tmp.name) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return str(path)

    def scratch_source(self, relative, content):
        """A file in a folder that is not inside any git work tree."""
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        path = pathlib.Path(scratch.name) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return str(path)

    def run_hook(self, stdin, env=None):
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": self.tmp.name}
        environment.update(env or {})
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                              env=environment)

    def edit(self, path, new_text, tool="Edit", env=None):
        key = "content" if tool == "Write" else "new_string"
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": tool,
            "tool_input": {"file_path": path, key: new_text},
        }
        return self.run_hook(json.dumps(payload), env)

    def edit_replacing(self, path, old_text, new_text, env=None):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": path, "old_string": old_text, "new_string": new_text},
        }
        return self.run_hook(json.dumps(payload), env)

    def assert_blocked(self, finished):
        self.assertEqual(finished.returncode, 2, finished.stderr)
        self.assertEqual(finished.stdout, "")
        return finished.stderr

    def assert_allowed(self, finished):
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout, "")
        self.assertEqual(finished.stderr, "")

    def assert_no_marker(self, finished):
        """For a marker case: a plain comment sample is blocked by the kept-kind rule, a code sample passes, and a
        marker never blocks either."""
        self.assertNotIn("marker", finished.stderr)
        self.assertNotIn("private-workflow", finished.stderr)
        if finished.returncode == 0:
            self.assertEqual(finished.stderr, "")
            return
        self.assertEqual(finished.returncode, 2, finished.stderr)
        self.assertIn("not a kept kind", finished.stderr)

    def assert_fails_open(self, finished):
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")
        self.assertTrue(finished.stderr.startswith("comment-bloat-gate: skipped after JSONDecodeError"),
                        finished.stderr)

    def test_invalid_json_and_missing_fields_pass(self):
        self.assert_fails_open(self.run_hook("not json"))
        self.assert_fails_open(self.run_hook(""))
        self.assert_allowed(self.run_hook(json.dumps({"tool_input": {}})))
        self.assert_allowed(self.run_hook(json.dumps({"tool_input": {"file_path": "/nonexistent/a.py"}})))

    def test_scratch_file_outside_any_repo_passes(self):
        path = self.scratch_source("probe/check.py", MARKER_LINE + "\n")
        self.assert_allowed(self.edit(path, MARKER_LINE, tool="Write"))

    def test_same_text_in_a_repo_file_is_still_flagged(self):
        path = self.source("repo/probe/check.py", MARKER_LINE + "\n")
        stderr = self.assert_blocked(self.edit(path, MARKER_LINE, tool="Write"))
        self.assertIn("  1:" + MARKER_LINE + "  <- marker ", stderr)

    def test_a_file_git_ignores_passes_but_a_tracked_file_matching_an_ignore_pattern_is_still_flagged(self):
        self.source(".gitignore", "probe/\n")
        ignored = self.source("probe/check.py", MARKER_LINE + "\n")
        self.assert_allowed(self.edit(ignored, MARKER_LINE, tool="Write"))
        tracked = self.source("probe/tracked.py", MARKER_LINE + "\n")
        subprocess.run(["git", "-C", self.tmp.name, "add", "-f", "probe/tracked.py"], check=True)
        self.assert_blocked(self.edit(tracked, MARKER_LINE, tool="Write"))

    def test_symlink_from_outside_a_repo_into_a_repo_file_is_checked(self):
        target = self.source("repo/probe/check.py", MARKER_LINE + "\n")
        link = pathlib.Path(self.scratch_source("keep.txt", "x\n")).parent / "link.py"
        link.symlink_to(target)
        self.assert_blocked(self.edit(str(link), MARKER_LINE, tool="Write"))

    def test_without_git_a_repo_file_is_checked_and_a_scratch_file_passes(self):
        without_git = {"PATH": self.tmp.name}
        repo_path = self.source("repo/a.py", MARKER_LINE + "\n")
        self.assert_blocked(self.edit(repo_path, MARKER_LINE, env=without_git))
        scratch_path = self.scratch_source("b.py", MARKER_LINE + "\n")
        self.assert_allowed(self.edit(scratch_path, MARKER_LINE, env=without_git))

    def test_non_code_extension_passes(self):
        path = self.source("notes.md", "# phase 2 per the plan\n")
        self.assert_allowed(self.edit(path, "# phase 2 per the plan"))

    def test_agent_surface_is_exempt(self):
        path = self.source("repo/.claude/agents/a.py", "# phase 2 notes\n")
        self.assert_allowed(self.edit(path, "# phase 2 notes"))

    def test_worktree_checkout_is_ordinary_code(self):
        path = self.source("repo/.claude/worktrees/feature/src/a.py", "# phase 2 notes\n")
        stderr = self.assert_blocked(self.edit(path, "# phase 2 notes"))
        self.assertIn("a.py", stderr)

    def test_worktree_agent_surface_is_still_exempt(self):
        path = self.source("repo/.claude/worktrees/feature/.claude/agents/a.py", "# phase 2 notes\n")
        self.assert_allowed(self.edit(path, "# phase 2 notes"))

    def test_empty_new_text_passes(self):
        path = self.source("a.py", "# phase 2\n")
        self.assert_allowed(self.edit(path, ""))
        payload = {"tool_input": {"file_path": path}}
        self.assert_allowed(self.run_hook(json.dumps(payload)))

    def test_markers_in_added_lines_block(self):
        samples = [
            "# phase 3 cleanup",
            "x = 1  # see docs/plans/auth.md",
            "# fixed in PR #123",
            "# issue #9",
            "# per the architect",
            "# written by the coder",
            "# the decision ledger says",
            "# acceptance criteria",
            "# acceptance contract",
            "# plan impact: none",
            "# plan-impact",
            "# user ruling",
            "# end-of-branch",
            "# (D4) chosen",
            "# D12: rule",
            "# PD3 applies",
            "# AC4 covered",
            "x = 1 # AC4",
            "AC9 = 1",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                path = self.source("a.py", "x = 1\n" + sample + "\ny = 2\n")
                stderr = self.assert_blocked(self.edit(path, sample))
                self.assertTrue(stderr.startswith(
                    "comment-bloat-gate: private-workflow marker in an added line (a.py). Zero exceptions"), stderr)
                self.assertIn("  2:" + sample + "  <- marker ", stderr)

    def test_the_deny_names_the_bare_marker_text(self):
        cases = [
            ("# AC4 covered", "AC4"),
            ("# AC12a covered", "AC12a"),
            ("x = 1 # AC4", "AC4"),
            ("AC1 holds here", "AC1"),
            ("x = 1  # (AC2) done", "AC2"),
            ("# phase 2 docs/plans/x", "docs/plans/"),
        ]
        for sample, expected in cases:
            with self.subTest(sample=sample):
                path = self.source("a.py", "x = 1\n" + sample + "\n")
                stderr = self.assert_blocked(self.edit(path, sample))
                self.assertTrue(stderr.endswith(f'  2:{sample}  <- marker "{expected}"\n'), stderr)

    def test_domain_words_in_an_agent_evals_file_pass_but_other_markers_block(self):
        domain_samples = [
            '"""Count the plan impacts each work plan names."""',
            "class PlanImpactsTest(unittest.TestCase):",
            "# acceptance criteria per ticket",
        ]
        for checkout in ("agent-evals", "agent-evals-intake"):
            for sample in domain_samples:
                with self.subTest(checkout=checkout, sample=sample):
                    path = self.source(f"{checkout}/bin/work_plan_impacts.py", "x = 1\n" + sample + "\n")
                    self.assert_no_marker(self.edit(path, sample))

        path = self.source("agent-evals/bin/work_plan_impacts.py", "x = 1\n# phase 3 cleanup\n")
        self.assert_blocked(self.edit(path, "# phase 3 cleanup"))

    def test_domain_words_on_a_shell_code_line_pass_but_a_shell_comment_blocks(self):
        step = 'run plan-impacts "$repo"'
        path = self.source("bin/work-intake.sh", "set -e\n" + step + "\n")
        self.assert_allowed(self.edit(path, step))

        comment = "# plan impact: none"
        path = self.source("bin/work-intake.sh", "set -e\n" + comment + "\n")
        self.assert_blocked(self.edit(path, comment))

    def test_rows_are_listed_in_line_order_with_two_space_indent(self):
        content = "# phase 2\nx = 1\n# docs/plans/y\n"
        path = self.source("a.py", content)
        stderr = self.assert_blocked(self.edit(path, content, tool="Write"))
        self.assertTrue(stderr.endswith('  1:# phase 2  <- marker "phase 2"\n'
                                        '  3:# docs/plans/y  <- marker "docs/plans/"\n'), stderr)

    def test_things_that_are_not_markers_pass(self):
        samples = ["# decode utf-8 phase 2 bytes", "# sha-256 phase 1", "x = f(**AC1_args)", "# ACID rules", "# #AC4",
                   "# 3D: model", "# quad2 phase", "# pull request notes", "# plan of attack"]
        for sample in samples:
            with self.subTest(sample=sample):
                path = self.source("a.py", "x = 1\n" + sample + "\n")
                self.assert_no_marker(self.edit(path, sample))

    def test_marker_text_inside_a_string_literal_passes_but_a_comment_after_it_blocks(self):
        fixture = f'plan = "## {PHASE_WORD} 1: Build\\n## {PHASE_WORD} 2: Refactor"'
        path = self.source("test_plan.py", "x = 1\n" + fixture + "\n")
        self.assert_allowed(self.edit(path, fixture))
        commented = fixture + "  # " + PHASE_WORD + " 3"
        path = self.source("test_plan.py", "x = 1\n" + commented + "\n")
        self.assert_blocked(self.edit(path, commented))

    def test_a_plan_path_or_provenance_in_a_shipped_string_blocks_but_a_phase_fixture_string_passes(self):
        plan_path = "docs/" + "plans/auth.md"
        samples = (("a.py", f'raise ValueError("token expired, see {plan_path}")'),
                   ("a.ts", f'throw new Error("token expired, see {plan_path}");'),
                   ("a.py", 'log.info("retry ' + 'per the spec")'),
                   ("a.go", 'return errors.New("written by the ' + 'agent")'))
        for name, sample in samples:
            with self.subTest(sample=sample):
                path = self.source(name, "x = 1\n" + sample + "\n")
                self.assert_blocked(self.edit(path, sample))
        fixture = f'plan = "## {PHASE_WORD} 1: Build"'
        path = self.source("test_plan.py", "x = 1\n" + fixture + "\n")
        self.assert_allowed(self.edit(path, fixture))

    def test_a_plan_path_in_a_test_file_string_passes_but_one_in_its_comment_blocks(self):
        plan_path = "docs/" + "plans/auth.md"
        fixture = f'PLAN_PATH = "{plan_path}"'
        for name in ("tests/fixtures.py", "test_plan.py", "plan.test.ts"):
            with self.subTest(name=name):
                path = self.source(name, "x = 1\n" + fixture + "\n")
                self.assert_allowed(self.edit(path, fixture))
        commented = f"x = 2  # see {plan_path}"
        path = self.source("tests/fixtures.py", "x = 1\n" + commented + "\n")
        self.assert_blocked(self.edit(path, commented))

    def test_plan_fixture_in_a_triple_quoted_string_passes(self):
        content = f'PLAN = """\n## {PHASE_WORD} 1: Build\n## {PHASE_WORD} 2: Refactor\n"""\n'
        path = self.source("test_plan.py", content)
        self.assert_allowed(self.edit(path, content, tool="Write"))

    def test_marker_on_the_opening_line_of_a_multi_line_data_string_passes(self):
        samples = (("test_plan.py", f'PLAN = """## {PHASE_WORD} 1: Build\n## {PHASE_WORD} 2: Refactor\n"""\n'),
                   ("plan.test.ts", f"const plan = `## {PHASE_WORD} 1: Build\n## {PHASE_WORD} 2: Refactor\n`;\n"),
                   ("test_plan.py",
                    f'PLAN = textwrap.dedent(\n    """## {PHASE_WORD} 1: Build\n'
                    f'    ## {PHASE_WORD} 2: Refactor\n    """)\n'),
                   ("a.py", f'x = render("{PHASE_WORD} 2 note", """\ndata\n""")\n'),
                   ("a.ts", f'const x = render("{PHASE_WORD} 2 note", `\ndata\n`);\n'))
        for name, content in samples:
            with self.subTest(name=name):
                path = self.source(name, content)
                self.assert_allowed(self.edit(path, content, tool="Write"))

    def test_marker_before_the_opening_quote_of_a_multi_line_data_string_blocks(self):
        ac_word = "A" + "C7"
        samples = (("a.py", f'x = f({ac_word}, """\ndata\n""")\n'),
                   ("a.py", f'def f():\n    """{PHASE_WORD} 6 renderer.\n    body\n    """\n'),
                   ("a.ts", f'it("{PHASE_WORD} 2 leftover", () => run(`\ndata\n`));\n'),
                   ("a.ts", f'it(`{PHASE_WORD} 2 leftover`, () => run(`\ndata\n`));\n'))
        for name, content in samples:
            with self.subTest(content=content):
                path = self.source(name, content)
                self.assert_blocked(self.edit(path, content, tool="Write"))

    def test_plan_fixture_in_a_multi_line_template_literal_passes(self):
        content = f'const plan = `\n## {PHASE_WORD} 1: Build\n## {PHASE_WORD} 2: Refactor\n`;\n'
        path = self.source("plan.test.ts", content)
        self.assert_allowed(self.edit(path, content, tool="Write"))

    def test_marker_in_a_test_name_blocks(self):
        ac_word = "A" + "C3"
        samples = (f'it("{ac_word} rejects an empty name", () => {{', f'describe("{PHASE_WORD} 6 render", () => {{',
                   f'it.each([1, 2])("{ac_word} rejects %s", (n) => {{', f'test.each`a`("{ac_word} x", () => {{')
        for sample in samples:
            with self.subTest(sample=sample):
                path = self.source("a.test.ts", "const x = 1;\n" + sample + "\n")
                self.assert_blocked(self.edit(path, sample))

    def test_marker_in_a_go_run_a_subtest_or_a_param_id_blocks(self):
        ac_word = "A" + "C3"
        samples = (("a_test.go", f't.Run("{ac_word} rejects an empty name", func(t *testing.T) {{'),
                   ("test_a.py", f'    with self.subTest("{PHASE_WORD} 6 render"):'),
                   ("test_a.py", f'    pytest.param(1, id="{ac_word} rejects empty"),'),
                   ("test_a.py", f'    pytest.mark.parametrize("n", [1, 2], ids=["{ac_word} empty", "b"])'),
                   ("test_a.py", f'    with self.subTest(msg="{PHASE_WORD} 6 render"):'),
                   ("a.test.ts",
                    f'it("renders", () => {{ it("{ac_word} x", () => {{}}); it("{ac_word} y", () => {{}}); }});'))
        for name, sample in samples:
            with self.subTest(sample=sample):
                path = self.source(name, "x = 1\n" + sample + "\n")
                self.assert_blocked(self.edit(path, sample))

    def test_a_marker_in_a_string_that_is_not_a_test_name_passes(self):
        samples = (("a.ts", f'const ok = pattern.test("{PHASE_WORD} 2");'),
                   ("a.ts", f'it("renders", () => f("## {PHASE_WORD} 3"));'),
                   ("a.py", f'half = len(rows) // 2; plan = "## {PHASE_WORD} 1"'),
                   ("a.ts", f'this.#plan = parse("## {PHASE_WORD} 1")'))
        for name, sample in samples:
            with self.subTest(sample=sample):
                path = self.source(name, "x = 1\n" + sample + "\n")
                self.assert_allowed(self.edit(path, sample))

    def test_marker_on_a_docstring_continuation_line_with_contractions_blocks(self):
        for sample in (f"    It's the {PHASE_WORD} 6 renderer, isn't it.", f'    Returns the "{PHASE_WORD} 3" rows.'):
            for prefix in ("", "r"):
                with self.subTest(sample=sample, prefix=prefix):
                    content = f'def f():\n    {prefix}"""Render.\n' + sample + '\n    """\n'
                    path = self.source("a.py", content)
                    self.assert_blocked(self.edit(path, content, tool="Write"))

    def test_formatter_wrapped_plan_fixtures_pass(self):
        samples = (f'plan = textwrap.dedent(\n    """\n    ## {PHASE_WORD} 1: Build\n    """\n)\n',
                   f'PLANS = [\n    """\n## {PHASE_WORD} 1\n""",\n]\n')
        for sample in samples:
            with self.subTest(sample=sample):
                path = self.source("a.py", sample)
                self.assert_allowed(self.edit(path, sample, tool="Write"))

    def test_marker_on_a_block_comment_line_without_a_star_blocks(self):
        sample = f"    It's the {PHASE_WORD} 6 renderer, isn't it."
        content = "const x = 1;\n/*\n" + sample + "\n*/\n"
        path = self.source("a.ts", content)
        self.assert_blocked(self.edit(path, content, tool="Write"))

    def test_marker_in_a_trailing_comment_with_quotes_blocks(self):
        for sample in ("x = 1  # it's Phase 3 now, isn't it", 'foo("a")  # see "Phase 3"'):
            with self.subTest(sample=sample):
                path = self.source("a.py", "x = 1\n" + sample + "\n")
                self.assert_blocked(self.edit(path, sample))

    def test_uppercase_markers_are_case_sensitive(self):
        path = self.source("a.py", "x = 1\n# ac4 done\n# d4: x\n# pd3\n")
        self.assert_no_marker(self.edit(path, "# ac4 done\n# d4: x\n# pd3"))

    def test_marker_already_in_file_but_not_in_edit_passes(self):
        path = self.source("a.py", "# phase 2\nx = 1\n")
        self.assert_allowed(self.edit(path, "x = 1"))

    def test_added_line_must_match_whole_line(self):
        path = self.source("a.py", "# phase 2 notes\n")
        self.assert_allowed(self.edit(path, "# phase 2"))
        self.assert_blocked(self.edit(path, "keep\n# phase 2 notes\nmore"))

    def test_marker_line_starting_with_dash_or_dash_e_is_checked_as_text(self):
        # The bash original passed the line to `grep -qxF` without `--`, so a leading dash was read as an option
        # and the leak was missed. The port treats it as text.
        path = self.source("q.sql", "select 1;\n-- see docs/plans/x\n")
        stderr = self.assert_blocked(self.edit(path, "select 1;\n-- see docs/plans/x"))
        self.assertIn("  2:-- see docs/plans/x  <- marker ", stderr)
        path = self.source("q.sql", "-e phase 2\n")
        self.assert_blocked(self.edit(path, "-e phase 2"))

    def test_code_extensions_covered(self):
        for extension in ("ts", "go", "rs", "sh", "yaml", "json", "sql"):
            with self.subTest(extension=extension):
                path = self.source("a." + extension, "# phase 2\n")
                self.assert_blocked(self.edit(path, "# phase 2"))

    def test_json_path_values_are_data_not_comments(self):
        content = ('{\n  "branch": "x",\n  "files": [\n    {\n      "file": '
                   '"docs/plans/LED-5-yield-view/dotfiles-writer-switch.patch",\n      "path": '
                   '"docs/plans/LED-5-yield-view/dotfiles-writer-switch.patch"\n    }\n  ]\n}\n')
        path = self.source("refactor-flow-6ff1271d5972.json", content)
        self.assert_allowed(self.edit(path, content, tool="Write"))

    def test_skip_variable_does_not_disable_gate(self):
        path = self.source("a.py", "# phase 2\n")
        self.assert_blocked(self.edit(path, "# phase 2", env={"CLAUDE_SKIP_HOOKS": "1"}))

    def written(self, name, content):
        """Write the file, then report the same text as a Write: every line of it is added."""
        path = self.source(name, content)
        return self.edit(path, content, tool="Write")

    def written_block(self, name, content):
        """Like `written`, with each whole comment line of `content` repeated to a run of three, the shortest run the
        gate blocks."""
        lines = []
        for line in content.split("\n"):
            is_comment = line.lstrip().startswith(COMMENT_LEADERS) and not line.startswith(SHEBANG)
            lines.extend([line] * BLOCKED_RUN_LENGTH if is_comment else [line])
        return self.written(name, "\n".join(lines))

    def test_a_plain_explaining_comment_block_is_blocked_and_the_deny_names_the_line(self):
        content = "x = 1\n# x counts the retries\n_y = 2\n"
        stderr = self.assert_blocked(self.written_block("a.py", content))
        self.assertIn("2: # x counts the retries", stderr)
        self.assertIn("Delete each one, or turn it into a name", stderr)

    def test_a_non_kept_comment_block_of_one_or_two_lines_passes_and_of_three_blocks(self):
        for length in (1, 2):
            with self.subTest(length=length):
                self.assert_allowed(self.written("a.py", "x = 1\n" + "# note\n" * length + "_y = 2\n"))
        stderr = self.assert_blocked(self.written("b.py", "x = 1\n" + "# note\n" * 3 + "_y = 2\n"))
        self.assertIn("architecture docs", stderr)
        self.assertIn("coder-core", stderr)
        self.assertIn("2: # note\n  3: # note\n  4: # note\n", stderr)

    def test_comment_lines_split_by_code_or_a_blank_line_do_not_add_up(self):
        self.assert_allowed(self.written("a.py", "x = 1\n# one\n# two\ny = 2\n# three\n# four\nz = 3\n"))
        self.assert_allowed(self.written("b.py", "x = 1\n# one\n# two\n\n# three\n# four\nz = 3\n"))

    def test_a_blank_line_inside_a_private_docstring_does_not_split_the_run(self):
        docstring = '"""Summary.\nMore detail.\n\nEven more.\nThird para.\n\nAnd more.\nLast one.\n"""'
        content = "def _f():\n    " + docstring.replace("\n", "\n    ") + "\n    return 1\n"
        self.assert_blocked(self.written("a.py", content))

    def test_a_url_line_inside_a_new_comment_block_does_not_split_the_run(self):
        content = "x = 1\n# one\n# two\n# see https://example.com\n# three\n# four\nprint(x)\n"
        self.assert_blocked(self.written("a.py", content))

    def test_a_suppression_line_inside_a_new_comment_block_does_not_split_the_run(self):
        content = "x = 1\n# one\n# two\n# noqa: E501\n# three\n# four\nprint(x)\n"
        self.assert_blocked(self.written("a.py", content))

    def test_a_tool_directive_line_inside_a_new_comment_block_does_not_split_the_run(self):
        content = "x = 1\n# one\n# two\n# mypy: ignore-errors\n# three\n# four\nprint(x)\n"
        self.assert_blocked(self.written("a.py", content))

    def test_old_comment_lines_next_to_two_added_lines_do_not_count_toward_the_limit(self):
        path = self.source("a.py", "x = 1\n# a\n# b\n# c\n# d\nprint(x)\n")
        self.assert_allowed(self.edit_replacing(path, "# b", "# b\n# c\n# d"))

    def test_only_the_added_comment_line_is_charged(self):
        new_note = "# new note\n# new note\n# new note"
        path = self.source("a.py", "# old note\nx = 1\n" + new_note + "\n")
        self.assert_allowed(self.edit(path, "x = 1"))
        self.assert_allowed(self.edit_replacing(path, new_note, new_note))
        stderr = self.assert_blocked(self.edit_replacing(path, "x = 1", "x = 1\n" + new_note))
        self.assertIn("3: # new note", stderr)
        self.assertNotIn("1: # old note", stderr)

    def test_a_write_charges_only_lines_the_committed_file_lacks(self):
        path = self.source("a.py", "x = 1\n# stays\n")
        subprocess.run(["git", "-C", self.tmp.name, "add", "a.py"], check=True)
        subprocess.run(["git", "-C", self.tmp.name, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "-m", "base"], check=True)
        content = "x = 1\n# stays\ny = 2\n# fresh\n# fresh\n# fresh\n"
        pathlib.Path(path).write_text(content)
        stderr = self.assert_blocked(self.edit(path, content, tool="Write"))
        self.assertIn("4: # fresh", stderr)
        self.assertNotIn("# stays", stderr)

    def test_license_header_kinds_pass(self):
        headers = {
            "a.py": "#!/usr/bin/env python3\n# SPDX-License-Identifier: MIT\nx = 1\n",
            "b.ts": "// Copyright 2026 Example Corp\nexport const x = 1;\n",
            "c.go": "/*\n * Licensed under the Apache License, Version 2.0.\n * Unless required.\n */\npackage a\n",
            "d.sh": "#!/bin/sh\n# This file is released under the MIT License.\n# Do what you want.\nx=1\n",
        }
        for name, content in headers.items():
            with self.subTest(name=name):
                self.assert_allowed(self.written(name, content))

    def test_a_license_word_outside_the_leading_block_does_not_keep_the_comment(self):
        self.assert_blocked(self.written_block("a.py", "x = 1\n# License is checked here\n"))

    def test_lint_and_format_suppressions_pass(self):
        suppressions = {
            "a.ts": [
                "// eslint-disable-next-line no-console", "// prettier-ignore", "// @ts-ignore",
                "// @ts-expect-error legacy", "// @ts-nocheck", "//nolint:errcheck",
                "// biome-ignore lint/style: ok", "// NOLINT(runtime/int)", "/* istanbul ignore next */",
                "// c8 ignore next",
            ],
            "a.py": ["# noqa: E501", "# type: ignore", "# pylint: disable=unused-import", "# fmt: off", "# fmt: on"],
            "a.rb": ["# rubocop:disable Style/Foo"],
            "a.sh": ["# shellcheck disable=SC2086"],
            "a.yaml": ["# yamllint disable-line rule:line-length"],
        }
        for name, samples in suppressions.items():
            for suppression in samples:
                with self.subTest(name=name, suppression=suppression):
                    self.assert_allowed(self.written(name, "x = 1\n" + suppression + "\ny = 2\n"))
        for name in suppressions:
            with self.subTest(name=name, plain=True):
                leader = "//" if name.endswith(".ts") else "#"
                self.assert_blocked(self.written_block(name, f"x = 1\n{leader} plain\n_y = 2\n"))

    def test_tool_directives_pass(self):
        directives = {
            "a.go": ["//go:generate stringer -type=X", "// +build linux", "//go:build linux"],
            "a.ts": ["/// <reference types=\"node\" />", "// @ts-check", "/** @type {import('x').Y} */",
                     "/** @typedef {number} N */"],
            "a.c": ["// clang-format off", "// clang-format on"],
            "a.swift": ["// swiftlint:disable force_cast", "// swiftlint:enable force_cast"],
            "a.py": ["# mypy: ignore-errors", "# pyright: basic", "# pragma: no cover",
                     "# -*- coding: utf-8 -*-"],
        }
        for name, samples in directives.items():
            for directive in samples:
                with self.subTest(name=name, directive=directive):
                    self.assert_allowed(self.written(name, "x = 1\n" + directive + "\ny = 2\n"))

    def test_a_jsdoc_that_is_not_a_type_tag_is_charged_from_three_lines(self):
        self.assert_allowed(self.written("a.ts", "const a = 1;\n/** explains a */\nconst b = 2;\n"))
        jsdoc = "const a = 1;\n/**\n * explains a\n * and more\n * and more\n */\nconst b = 2;\n"
        self.assert_blocked(self.written("b.ts", jsdoc))

    def test_sql_and_lua_star_semicolon_and_length_lines_are_code(self):
        self.assert_allowed(self.written("q.sql", "SELECT\n    *\nFROM users\n;\n"))
        self.assert_allowed(self.written("q.lua", "local n = f\n  #t\n"))

    def test_a_dash_comment_in_sql_or_lua_is_charged(self):
        self.assert_blocked(self.written_block("q.sql", "SELECT 1\n-- note\n"))
        self.assert_blocked(self.written_block("q.lua", "local x = 1\n-- note\n"))

    def test_a_heredoc_body_line_in_a_shell_file_is_data(self):
        self.assert_allowed(self.written("s.sh", "cat > conf <<CONF\n# setting for foo\nfoo=1\nCONF\n"))
        self.assert_blocked(self.written_block("s.sh", "cat > conf <<CONF\nfoo=1\nCONF\n# note after it\n"))

    def test_a_go_package_doc_is_kept(self):
        self.assert_allowed(self.written("a.go", "// Package a does a thing.\npackage a\n"))
        self.assert_blocked(self.written_block("b.go", "package b\n\n// helper note\nvar x = 1\n"))

    def test_a_leading_rust_module_doc_run_is_kept(self):
        self.assert_allowed(self.written("a.rs", "//! Crate docs.\n//! More docs.\n\nfn f() {}\n"))
        self.assert_blocked(self.written_block("b.rs", "fn f() {}\n\n//! not leading\n"))
        self.assert_blocked(self.written_block("c.rs", "// plain\n//! docs\nfn f() {}\n"))

    def test_a_write_charges_only_lines_missing_from_the_file_before_the_write(self):
        content = "x = 1\n# user note\n# new note\n# new note\n# new note\n"
        path = self.source("a.py", content)
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": path, "content": content},
            "tool_response": {"originalFile": "x = 1\n# user note\n"},
        }
        stderr = self.assert_blocked(self.run_hook(json.dumps(payload)))
        self.assertIn("3: # new note", stderr)
        self.assertNotIn("# user note", stderr)

    def test_an_old_line_inside_a_new_comment_block_does_not_split_the_run(self):
        content = "x = 1\n# alpha\n# beta\n#\n# gamma\n# delta\n"
        path = self.source("a.py", content)
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": path, "content": content},
            "tool_response": {"originalFile": "x = 1\n#\n"},
        }
        stderr = self.assert_blocked(self.run_hook(json.dumps(payload)))
        self.assertIn("2: # alpha", stderr)
        self.assertIn("6: # delta", stderr)
        self.assertNotIn("4: #\n", stderr)

    def test_a_comment_that_only_names_a_linter_is_not_a_suppression(self):
        self.assert_blocked(self.written_block("a.rs", "fn f() {\n    // clippy complains here\n}\n"))
        self.assert_blocked(self.written_block("b.kt", "fun f() {\n    // @Suppress is used here\n}\n"))

    def test_an_edit_charges_only_comment_lines_inside_the_new_text(self):
        old_file = "function helper() {\n  /*\n   *\n   */\n  return 1;\n}\n"
        path = self.source("a.js", old_file + "export function f() {}\n")
        new_text = "/**\n *\n * Reads.\n */\nexport function f() {}"
        pathlib.Path(path).write_text(old_file + new_text + "\n")
        self.assert_allowed(self.edit_replacing(path, "export function f() {}", new_text))

    def test_an_edit_charges_a_bare_hash_line_when_an_older_one_has_the_same_text(self):
        old_file = "def a():\n    #\n    x = 1\n\n\n"
        new_text = "def b():\n    #\n    #\n    #\n    y = 2"
        path = self.source("a.py", old_file + "def b():\n    y = 2\n")
        pathlib.Path(path).write_text(old_file + new_text + "\n")
        stderr = self.assert_blocked(self.edit_replacing(path, "def b():\n    y = 2", new_text))
        self.assertIn("7: #", stderr)

    def test_an_edit_whose_text_also_sits_earlier_in_the_file_charges_the_added_line(self):
        block = "    # reset state\n    # reset state\n    # reset state\n    x = 1"
        path = self.source("a.py", "def _a():\n" + block + "\n\n\ndef _b():\n    y = 2\n")
        pathlib.Path(path).write_text("def _a():\n" + block + "\n\n\ndef _b():\n" + block + "\n")
        stderr = self.assert_blocked(self.edit_replacing(path, "    y = 2", block))
        self.assertIn("9: # reset state", stderr)

    def test_a_replace_all_edit_charges_every_occurrence(self):
        path = self.source("a.py", "def _a():\n    x = 1\n\n\ndef _b():\n    x = 1\n")
        note = "    # note\n    # note\n    # note\n"
        pathlib.Path(path).write_text("def _a():\n" + note + "    x = 1\n\n\ndef _b():\n" + note + "    x = 1\n")
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {
            "file_path": path, "old_string": "    x = 1", "new_string": note + "    x = 1", "replace_all": True}}
        stderr = self.assert_blocked(self.run_hook(json.dumps(payload)))
        self.assertIn("2: # note", stderr)
        self.assertIn("9: # note", stderr)

    def test_an_edit_whose_new_text_is_not_in_the_file_falls_back_to_the_text_match(self):
        path = self.source("a.py", "x = 1\n# plain comment\n# plain comment\n# plain comment\n")
        new_text = "x = 1\n# plain comment\n# plain comment\n# plain comment\nmissing"
        stderr = self.assert_blocked(self.edit_replacing(path, "x = 1", new_text))
        self.assertIn("2: # plain comment", stderr)

    def test_an_old_comment_with_the_same_text_as_a_new_one_is_not_charged(self):
        state = "    # reset state\n"
        path = self.source("a.py", "def _a():\n" + state + "    x = 1\n\n\ndef _b():\n    y = 2\n")
        pathlib.Path(path).write_text(
            "def _a():\n" + state + "    x = 1\n\n\ndef _b():\n" + state * 3 + "    y = 2\n")
        stderr = self.assert_blocked(
            self.edit_replacing(path, "def _b():\n    y = 2", "def _b():\n" + state * 3 + "    y = 2")
        )
        self.assertIn("7: # reset state", stderr)
        self.assertNotIn("2: # reset state", stderr)

    def test_an_edit_that_moves_a_committed_comment_is_not_charged(self):
        path = self.source("a.py", "x = 1\n# stays\ny = 2\n")
        subprocess.run(["git", "-C", self.tmp.name, "add", "a.py"], check=True)
        subprocess.run(["git", "-C", self.tmp.name, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "-m", "base"], check=True)
        pathlib.Path(path).write_text("x = 1\ny = 2\n# stays\n")
        self.assert_allowed(self.edit_replacing(path, "y = 2", "y = 2\n# stays"))

    def test_a_hash_comment_under_a_public_docstring_is_charged(self):
        content = 'def f():\n    """Doc."""\n    # inner note\n    return 1\n'
        stderr = self.assert_blocked(self.written_block("a.py", content))
        self.assertIn("3: # inner note", stderr)
        self.assertNotIn("Doc.", stderr)

    def test_a_multi_line_public_docstring_keeps_only_its_quoted_lines(self):
        content = 'def f():\n    """Doc\n    more."""\n    # note\n    return 1\n'
        stderr = self.assert_blocked(self.written_block("m.py", content))
        self.assertIn("4: # note", stderr)
        self.assertNotIn("more.", stderr)

    def test_a_public_python_constant_keeps_its_comment_and_a_private_one_does_not(self):
        self.assert_allowed(self.written("c1.py", "# Max retries.\nMAX_RETRIES = 3\n"))
        self.assert_allowed(self.written("c2.py", "# Max retries.\nMAX_RETRIES: int = 3\n"))
        self.assert_blocked(self.written_block("c3.py", "# Max retries.\n_MAX_RETRIES = 3\n"))
        self.assert_blocked(self.written_block("c4.py", "# note\nCONSTANT == 3\n"))
        self.assert_blocked(self.written_block("c5.py", "# note\nX == y\n"))
        self.assert_blocked(self.written_block("c6.py", "def f():\n    # note\n    LIMIT = 3\n    return LIMIT\n"))

    def test_members_of_an_exported_ts_class_or_interface_keep_their_comments(self):
        exported_class = "export class C {\n  // Send one request.\n  send(): void {}\n}\n"
        self.assert_allowed(self.written("a.ts", exported_class))
        exported_interface = "export interface O {\n  // Timeout in ms.\n  timeout: number;\n}\n"
        self.assert_allowed(self.written("b.ts", exported_interface))
        private_member = "export class C {\n  // Secret.\n  private x = 1;\n}\n"
        self.assert_blocked(self.written_block("c.ts", private_member))
        hash_member = "export class C {\n  // Secret.\n  #x = 1;\n}\n"
        self.assert_blocked(self.written_block("d.ts", hash_member))
        protected_member = "export class C {\n  // Secret.\n  protected y = 1;\n}\n"
        self.assert_blocked(self.written_block("f.ts", protected_member))
        modified_private = "export class C {\n  // Secret.\n  static private z = 1;\n}\n"
        self.assert_blocked(self.written_block("i.ts", modified_private))
        unexported = "class C {\n  // Send.\n  send(): void {}\n}\n"
        self.assert_blocked(self.written_block("e.ts", unexported))

    def test_commonjs_exports_keep_their_comments(self):
        self.assert_allowed(self.written("a.cjs", "/** Adds two. */\nmodule.exports.add = () => 1;\n"))
        self.assert_allowed(self.written("b.js", "// Subtracts.\nexports.sub = () => 1;\n"))

    def test_a_kotlin_local_at_indent_four_in_a_function_does_not_keep_a_comment(self):
        content = "fun main() {\n    // compute the total\n    val total = 1\n}\n"
        self.assert_blocked(self.written_block("l.kt", content))

    def test_a_kotlin_member_of_a_public_class_keeps_its_comment(self):
        self.assert_allowed(self.written("k.kt", "class A {\n    // Reads.\n    fun load() {}\n}\n"))

    def test_a_kotlin_member_of_a_class_with_a_multi_line_constructor_keeps_its_comment(self):
        content = "data class Foo(\n    val a: Int,\n) {\n    // Doc of bar.\n    fun bar() {}\n}\n"
        self.assert_allowed(self.written("d.kt", content))

    def test_a_kotlin_annotated_function_keeps_its_comment(self):
        self.assert_allowed(self.written("n.kt", "// Reads.\n@JvmStatic fun f() {}\n"))

    def test_a_kotlin_member_of_a_private_or_internal_owner_or_a_protected_member_does_not_keep_a_comment(self):
        cases = {
            "p.kt": "private class A {\n    // Reads.\n    fun load() {}\n}\n",
            "i.kt": "internal object O {\n    // Reads.\n    fun load() {}\n}\n",
            "q.kt": "class A {\n    // Reads.\n    protected fun load() {}\n}\n",
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                self.assert_blocked(self.written_block(name, content))

    def test_a_ts_member_of_a_multi_line_class_header_keeps_its_comment(self):
        content = "export class A<\n  T,\n> {\n  // Doc of run.\n  run() {}\n}\n"
        self.assert_allowed(self.written("g.ts", content))

    def test_a_member_of_an_exported_declare_class_keeps_its_comment(self):
        content = "export declare class A {\n  // Doc of run.\n  run(): void;\n}\n"
        self.assert_allowed(self.written("h.ts", content))

    def test_a_kotlin_declaration_indented_past_member_level_does_not_keep_a_comment(self):
        self.assert_blocked(self.written_block("a.kt", "private fun f() {\n    // narrate\n        val x = 1\n}\n"))

    def test_a_go_struct_field_keeps_its_doc_comment(self):
        content = "package a\n\ntype T struct {\n\t// Name is the name.\n\tName string\n}\n"
        self.assert_allowed(self.written("a.go", content))

    def test_members_of_grouped_or_enum_like_public_declarations_keep_their_comments(self):
        samples = {
            "a.go": "package a\n\nconst (\n\t// Max is the limit.\n\tMax = 3\n)\n",
            "b.go": "package a\n\nvar (\n\t// Name is the name.\n\tName = \"x\"\n)\n",
            "a.ts": "export enum E {\n  // First one.\n  A,\n}\n",
            "b.ts": "export type T = {\n  // Name of it.\n  name: string;\n}\n",
            "c.ts": "export namespace N {\n  // Helper.\n  export const x = 1;\n}\n",
            "a.rs": "pub enum E {\n    // First one.\n    A,\n}\n",
            "b.rs": "pub trait T {\n    // Runs it.\n    fn run(&self);\n}\n",
            "a.py": "class C:\n    # Upper bound.\n    LIMIT = 3\n",
        }
        for name, content in samples.items():
            with self.subTest(name=name):
                self.assert_allowed(self.written(name, content))

    def test_an_unexported_line_in_an_exported_ts_namespace_does_not_keep_a_comment(self):
        content = "export namespace N {\n  // Helper.\n  const y = 1;\n}\n"
        self.assert_blocked(self.written_block("n.ts", content))

    def test_a_python_class_constant_after_a_comment_or_a_multi_line_string_reads_its_class(self):
        path = self.source("a.py", "class C:\n    x = 1\n# aside\n    # Upper bound.\n    LIMIT = 3\n")
        self.assert_allowed(self.edit_replacing(path, "    LIMIT = 3", "    # Upper bound.\n    LIMIT = 3"))
        string_owner = 'class C:\n    t = """\nend\n"""\n    # Upper bound.\n    LIMIT = 3\n'
        self.assert_allowed(self.written("b.py", string_owner))
        private_owner = 'class _C:\n    t = """\nend\n"""\n    # Upper bound.\n    LIMIT = 3\n'
        self.assert_blocked(self.written_block("c.py", private_owner))

    def test_a_python_attribute_of_a_private_class_does_not_keep_a_comment(self):
        self.assert_blocked(self.written_block("d.py", "class _C:\n    # Upper bound.\n    LIMIT = 3\n"))

    def test_a_go_capitalised_line_in_a_function_body_does_not_keep_a_comment(self):
        bodies = {
            "call": "func f() {\n\t// call the helper now\n\tDoThing()\n}\n",
            "assignment": "func f() {\n\t// set result\n\tResult := 1\n}\n",
            "loop": "func run() {\n\t// loop over the items and process each\n\tProcess(items)\n}\n",
        }
        for name, body in bodies.items():
            with self.subTest(name=name):
                self.assert_blocked(self.written_block("a.go", "package a\n\n" + body))

    def test_a_rust_pub_crate_item_does_not_keep_a_comment(self):
        self.assert_blocked(self.written_block("a.rs", "// internal\npub(crate) fn f() {}\n"))

    def test_the_marker_check_still_runs_on_a_code_file_under_docs(self):
        path = self.source("docs/a.py", "x = 1\n" + MARKER_LINE + "\n")
        stderr = self.assert_blocked(self.edit(path, "x = 1\n" + MARKER_LINE, tool="Write"))
        self.assertIn("private-workflow marker", stderr)

    def test_a_write_in_a_repo_with_no_commit_charges_a_plain_comment(self):
        content = "x = 1\n# plain comment\n# plain comment\n# plain comment\n"
        path = self.source("fresh.py", content)
        stderr = self.assert_blocked(self.edit(path, content, tool="Write"))
        self.assertIn("2: # plain comment", stderr)

    def test_a_line_with_a_url_passes(self):
        self.assert_allowed(self.written("a.py", "x = 1\n# see https://example.com/spec for the format\n"))
        self.assert_allowed(self.written("a.go", "x := 1\n// http://example.com/rfc\n"))

    def test_doc_comments_on_public_symbols_pass(self):
        public = {
            "a.py": 'import os\n\n\ndef load(path):\n    """Read the file."""\n    return os.path.exists(path)\n',
            "b.py": '"""The module does one thing."""\nimport os\n',
            "c.py": 'class Loader:\n    """Reads files."""\n\n    def read(self):\n        """Read it."""\n',
            "d.py": "x = 1\n\n# Read the file.\ndef load():\n    pass\n",
            "e.ts": "const a = 1;\n/**\n * Reads the file.\n */\nexport function load() {}\n",
            "f.go": "package a\n\n// Load reads the file.\nfunc Load() {}\n",
            "g.rs": "// Reads the file.\npub fn load() {}\n",
            "h.java": "class A {\n    /** Reads the file. */\n    public void load() {}\n}\n",
            "i.kt": "// Reads the file.\nfun load() {}\n",
            "j.swift": "// Reads the file.\npublic func load() {}\n",
            "k.php": "<?php\n// Reads the file.\npublic function load() {}\n",
            "l.rb": "x = 1\n# Reads the file.\ndef load\nend\n",
            "m.h": "int a;\n// Reads the file.\nint load(void);\n",
            "n.py": "x = 1\n\n# Reads the file.\n@cache\ndef load():\n    pass\n",
        }
        for name, content in public.items():
            with self.subTest(name=name):
                self.assert_allowed(self.written(name, content))

    def test_doc_comments_on_private_symbols_block(self):
        private = {
            "a.py": "x = 1\n\n# Reads the file.\ndef _load():\n    pass\n",
            "b.py": 'def run():\n    x = 1\n    def _inner():\n        """Inner.\n        more\n        again."""\n',
            "c.ts": "// Reads the file.\nfunction load() {}\n",
            "d.go": "package a\n\n// reads the file.\nfunc load() {}\n",
            "e.rs": "// Reads the file.\nfn load() {}\n",
            "f.java": "class A {\n    // Reads the file.\n    private void load() {}\n}\n",
            "g.kt": "// Reads the file.\nprivate fun load() {}\n",
            "h.swift": "// Reads the file.\nfunc load() {}\n",
            "i.php": "<?php\n// Reads the file.\nprivate function load() {}\n",
            "j.rb": "x = 1\n# Reads the file.\nx = 2\n",
            "k.h": "int a;\n// Reads the file.\nstatic int load(void);\n",
            "l.c": "int a;\n// Reads the file.\nint load(void) { return 1; }\n",
            "m.py": "x = 1\n# Reads the file.\n\ndef load():\n    pass\n",
        }
        for name, content in private.items():
            with self.subTest(name=name):
                self.assert_blocked(self.written_block(name, content))

    def test_languages_without_a_public_marker_never_keep_a_doc_comment(self):
        docs = {
            "a.sh": "x=1\n# Reads the file.\nload() { :; }\n",
            "b.lua": "x = 1\n-- Reads the file.\nfunction load() end\n",
            "c.sql": "select 1;\n-- Reads the file.\ncreate view v as select 1;\n",
            "d.yml": "a: 1\n# Reads the file.\nb: 2\n",
            "e.qml": "Item {\n    // Reads the file.\n    function load() {}\n}\n",
        }
        for name, content in docs.items():
            with self.subTest(name=name):
                self.assert_blocked(self.written_block(name, content))

    def test_a_comment_in_a_file_under_a_docs_folder_passes(self):
        self.assert_allowed(self.written("docs/guide/example.py", "x = 1\n# explains the thing\n"))
        self.assert_allowed(self.written("docs/example.ts", "// explains the thing\nconst a = 1;\n"))
        self.assert_blocked(self.written_block("src/docsy/example.py", "x = 1\n# explains the thing\n"))

    def test_comment_detection_per_language_family(self):
        comments = {
            "a.sh": "x=1\n# explains\n",
            "a.yaml": "a: 1\n# explains\n",
            "a.rb": "x = 1\n# explains\n",
            "a.js": "const a = 1;\n// explains\n",
            "a.go": "x := 1\n// explains\n",
            "a.c": "int x;\n// explains\n",
            "a.lua": "x = 1\n-- explains\n",
            "a.sql": "select 1;\n-- explains\n",
            "a.qml": "Item {\n    // explains\n}\n",
            "b.qml": "Item {\n    /* explains\n       the item\n       again */\n}\n",
            "b.ts": "const a = 1;\n/*\n   explains without a star\n   and more\n   and more\n*/\n",
            "a.py": 'x = 1\n"""\nexplains in a stray string\nand more\nand more\n"""\n',
        }
        for name, content in comments.items():
            with self.subTest(name=name):
                self.assert_blocked(self.written_block(name, content))

    def test_code_that_is_not_a_comment_passes(self):
        code = {
            "a.py": 'x = 1  # trailing\nprint(2 *\n      3)\nsql = """\nselect 1\n"""\nargs = f(*args, **kw)\n',
            "a.ts": "const a = 1; // trailing\nconst b = f(x\n  * 2);\nconst s = `\n// in a template\n`;\n",
            "a.json": '{\n  "a": "# not a comment",\n  "b": 1\n}\n',
        }
        for name, content in code.items():
            with self.subTest(name=name):
                self.assert_allowed(self.written(name, content))

    def test_bare_delimiters_are_not_charged(self):
        self.assert_allowed(self.written("a.ts", "const a = 1;\n/**\n */\nexport const b = 2;\n"))
        self.assert_allowed(self.written("a.py", 'x = 1\n"""\n"""\n'))

    def test_a_lone_shebang_is_not_charged_but_a_plain_comment_after_it_is(self):
        self.assert_allowed(self.written("a.py", "#!/usr/bin/env python3\nx = 1\n"))
        self.assert_allowed(self.written("b.sh", "#!/bin/sh\nx=1\n"))
        stderr = self.assert_blocked(self.written_block("c.py", "#!/usr/bin/env python3\n# explains\n_x = 1\n"))
        self.assertIn("2: # explains", stderr)
        self.assertNotIn("1: #!", stderr)

    def test_public_symbol_rows_pass(self):
        public = {
            "a.go": "package a\n\n// A is a type.\ntype A struct{}\n",
            "b.go": "package a\n\n// B is a var.\nvar B = 1\n",
            "c.go": "package a\n\n// C is a const.\nconst C = 1\n",
            "d.go": "package a\n\n// Load reads.\nfunc (r *T) Load() {}\n",
            "f.java": "// Reads.\n@Named(\"x\")\npublic void load() {}\n",
            "g.swift": "// Reads.\nopen class A {}\n",
            "h.kt": "// Reads.\nclass A\n",
            "i.php": "<?php\n// Reads.\nabstract class A {}\n",
            "j.rb": "# Reads.\nmodule M\nend\n",
            "k.rb": "x = 1\n# Reads.\ndef self.load\nend\n",
            "l.hpp": "int a;\n// Reads.\nint load();\n",
            "m.js": "const a = 1;\n// Reads.\nexport const b = 2;\n",
            "n.tsx": "const a = 1;\n// Reads.\nexport default function A() {}\n",
            "o.py": "class Loader:\n    # Builds it.\n    def __init__(self):\n        pass\n",
            "p.py": 'class Loader:\n    def __call__(self):\n        """Call it."""\n',
            "q.py": 'class Loader(\n    Base,\n):\n    """Reads."""\n',
            "r.py": "class Loader:\n    x = 1\n\n    # Reads.\n    def read(self):\n        pass\n",
            "s.mjs": "const a = 1;\n// Reads.\nexport { a };\n",
            "t.py": 'class Loader(\n    Base,\n):\n    def read(self):\n        """Read it."""\n',
            "u.py": 'class Loader:\n    x = """\nraw\n"""\n\n    def read(self):\n        """Read it."""\n',
            "v.py": 'class Pub:\n    x = """\ntext\n"""\n    # Reads.\n    def m(self):\n        pass\n',
            "w.java": "// Reads.\n@Override public void load() {}\n",
        }
        for name, content in public.items():
            with self.subTest(name=name):
                self.assert_allowed(self.written(name, content))

    def test_comments_above_body_lines_and_nested_or_hidden_python_symbols_block(self):
        private = {
            "a.java": 'class A {\n    // explain\n    String s = "public";\n}\n',
            "b.swift": "func f() {\n    // read before close\n    let h = open(path)\n}\n",
            "c.h": "static inline int f(void) {\n    // explain\n    return 1;\n}\n",
            "d.py": "def _run():\n    # helper\n    def helper():\n        pass\n",
            "e.py": "class _Hidden:\n    # Reads.\n    def read(self):\n        pass\n",
            "f.py": 'def run():\n    def inner():\n        """Inner.\n        more\n        again."""\n',
            "g.py": 'class _Hidden:\n    def read(self):\n        """Read it.\n        more\n        again."""\n',
            "h.py": "class Loader:\n    def run(self):\n        # Helper.\n        def inner():\n            pass\n",
            "j.py": 'def pub():\n    if x:\n        """not a docstring\n        more\n        again"""\n',
            "i.py": (
                "class Loader:\n    def _helper(self):\n        pass\n\n"
                "    # Reads.\n    def _read(self):\n        pass\n"
            ),
        }
        for name, content in private.items():
            with self.subTest(name=name):
                self.assert_blocked(self.written_block(name, content))

    def test_a_docstring_whose_header_is_out_of_reach_or_not_a_def_blocks(self):
        doc = '    """Doc.\n    more\n    again."""\n'
        far_header = "def load(\n" + "    a,\n" * 14 + "):\n" + doc
        self.assert_blocked(self.written("a.py", far_header))
        self.assert_blocked(self.written("b.py", "x = 1\nif x:\n" + doc))

    def test_a_re_indented_comment_is_not_new(self):
        path = self.source("a.py", "if y:\n    # note\n    x = 1\n")
        self.assert_allowed(self.edit_replacing(path, "# note\nx = 1", "    # note\n    x = 1"))

    def test_an_ancestor_folder_named_docs_does_not_exempt_the_repo(self):
        repo = pathlib.Path(self.tmp.name) / "docs" / "myrepo"
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        source = repo / "src" / "a.py"
        source.parent.mkdir()
        content = "x = 1\n# explains\n# explains\n# explains\n"
        source.write_text(content)
        self.assert_blocked(self.edit(str(source), content, tool="Write"))
        under_docs = repo / "docs" / "b.py"
        under_docs.parent.mkdir()
        under_docs.write_text(content)
        self.assert_allowed(self.edit(str(under_docs), content, tool="Write"))

    def test_a_write_through_a_symlink_reads_the_committed_target(self):
        path = self.source("real.py", "x = 1\n# stays\n")
        subprocess.run(["git", "-C", self.tmp.name, "add", "real.py"], check=True)
        subprocess.run(["git", "-C", self.tmp.name, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "-m", "base"], check=True)
        link = pathlib.Path(self.tmp.name) / "link.py"
        link.symlink_to(path)
        self.assert_allowed(self.edit(str(link), "x = 1\n# stays\n", tool="Write"))

    def test_a_write_outside_a_work_tree_is_silent(self):
        path = self.scratch_source("out.py", "x = 1\n# plain\n")
        self.assert_allowed(self.edit(path, "x = 1\n# plain\n", tool="Write"))

    def test_a_write_over_a_staged_new_file_is_checked(self):
        content = "x = 1\n# plain comment\n# plain comment\n# plain comment\n"
        path = self.source("n.py", content)
        subprocess.run(["git", "-C", self.tmp.name, "add", "n.py"], check=True)
        stderr = self.assert_blocked(self.edit(path, content, tool="Write"))
        self.assertIn("2: # plain comment", stderr)

    def test_a_write_skips_the_comment_check_when_git_cannot_say_what_the_file_held(self):
        path = self.source("a.py", "x = 1\n# stays\n")
        subprocess.run(["git", "-C", self.tmp.name, "add", "a.py"], check=True)
        finished = self.edit(path, "x = 1\n# stays\n", tool="Write", env={"PATH": self.tmp.name})
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("comment check skipped for a.py", finished.stderr)

    def test_an_edit_skips_the_comment_check_when_git_cannot_say_what_the_file_held(self):
        path = self.source("a.py", "x = 1\n# stays\n")
        subprocess.run(["git", "-C", self.tmp.name, "add", "a.py"], check=True)
        finished = self.edit_replacing(path, "x = 1", "x = 1\n# stays", env={"PATH": self.tmp.name})
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("comment check skipped for a.py", finished.stderr)

    def test_a_write_with_no_comment_line_runs_no_git_and_stays_silent(self):
        path = self.source("a.py", "x = 1\n")
        finished = self.edit(path, "x = 1\n", tool="Write", env={"PATH": self.tmp.name})
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stderr, "")

    def test_an_edit_whose_only_comment_is_in_old_string_runs_no_git_and_stays_silent(self):
        path = self.source("a.py", "x = 1\n# stays\ny = 2\n")
        finished = self.edit_replacing(path, "x = 1\n# stays", "x = 1\n# stays\ny = 2",
                                       env={"PATH": self.tmp.name})
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stderr, "")

    def test_a_crash_is_reported_on_stderr_with_the_gate_name_and_the_edit_goes_on(self):
        spec = importlib.util.spec_from_file_location("comment_bloat_gate_under_test", SCRIPT)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        captured = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with mock.patch.object(gate, "check", side_effect=ValueError("boom")), \
                mock.patch.object(sys, "stderr", captured):
            code = gate.main()
        captured.flush()
        self.assertEqual(code, 0)
        self.assertEqual(captured.buffer.getvalue().decode(), "comment-bloat-gate: skipped after ValueError: boom\n")


if __name__ == "__main__":
    unittest.main()
