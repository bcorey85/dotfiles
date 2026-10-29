"""Checks for comment_bloat_gate.py, the PostToolUse hook that blocks workflow-marker leaks and comment bloat."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR)
SCRIPT = SCRIPTS_DIR / "comment_bloat_gate.py"

# Split so this file does not itself carry the plan-path marker the gate looks for.
MARKER_LINE = "# see dev/agent-ledger-LED-7/docs/" + "plans/LED-7-watch-metrics/spec.md"

PHASE_WORD = "Pha" + "se"

FILLER = "\n".join(f"value_{index} = {index}" for index in range(40)) + "\n"


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

    def edit_replacing(self, path, old_text, new_text):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": path, "old_string": old_text, "new_string": new_text},
        }
        return self.run_hook(json.dumps(payload))

    def assert_blocked(self, finished):
        self.assertEqual(finished.returncode, 2, finished.stderr)
        self.assertEqual(finished.stdout, "")
        return finished.stderr

    def assert_allowed(self, finished):
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout, "")
        self.assertEqual(finished.stderr, "")

    def test_invalid_json_and_missing_fields_pass(self):
        self.assert_allowed(self.run_hook("not json"))
        self.assert_allowed(self.run_hook(""))
        self.assert_allowed(self.run_hook(json.dumps({"tool_input": {}})))
        self.assert_allowed(self.run_hook(json.dumps({"tool_input": {"file_path": "/nonexistent/a.py"}})))

    def test_scratch_file_outside_any_repo_passes(self):
        path = self.scratch_source("probe/check.py", MARKER_LINE + "\n")
        self.assert_allowed(self.edit(path, MARKER_LINE, tool="Write"))

    def test_same_text_in_a_repo_file_is_still_flagged(self):
        path = self.source("repo/probe/check.py", MARKER_LINE + "\n")
        stderr = self.assert_blocked(self.edit(path, MARKER_LINE, tool="Write"))
        self.assertIn("  1:" + MARKER_LINE + "\n", stderr)

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
                self.assertIn("  2:" + sample + "\n", stderr)

    def test_rows_are_listed_in_line_order_with_two_space_indent(self):
        content = "# phase 2\nx = 1\n# docs/plans/y\n"
        path = self.source("a.py", content)
        stderr = self.assert_blocked(self.edit(path, content, tool="Write"))
        self.assertTrue(stderr.endswith("  1:# phase 2\n  3:# docs/plans/y\n"), stderr)

    def test_things_that_are_not_markers_pass(self):
        samples = ["# decode utf-8 phase 2 bytes", "# sha-256 phase 1", "x = f(**AC1_args)", "# ACID rules", "# #AC4",
                   "# 3D: model", "# quad2 phase", "# pull request notes", "# plan of attack"]
        for sample in samples:
            with self.subTest(sample=sample):
                path = self.source("a.py", "x = 1\n" + sample + "\n")
                self.assert_allowed(self.edit(path, sample))

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
        self.assert_allowed(self.edit(path, "# ac4 done\n# d4: x\n# pd3"))

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
        self.assertIn("  2:-- see docs/plans/x\n", stderr)
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

    def test_density_over_cap_blocks(self):
        comments = "\n".join(f"# note {index}" for index in range(15)) + "\n"
        path = self.source("a.py", FILLER + comments)
        stderr = self.assert_blocked(self.edit(path, comments))
        self.assertEqual(stderr, "comment-bloat-gate: a.py is 27% comments (15/55 non-blank lines), cap ~20%. "
                                 "Delete the comments this edit added, or rename/split so they are unnecessary; "
                                 "a comment the task requires stays, named in the hand-back. Never add code to "
                                 "lower the ratio.\n")

    def test_rewording_an_existing_comment_in_an_over_cap_file_passes(self):
        comments = "\n".join(f"# note {index}" for index in range(15)) + "\n"
        path = self.source("a.py", FILLER + comments)
        self.assert_allowed(self.edit_replacing(path, "# note 3", "# a clearer note 3"))

    def test_an_edit_that_adds_a_comment_line_in_an_over_cap_file_blocks(self):
        comments = "\n".join(f"# note {index}" for index in range(15)) + "\n"
        path = self.source("a.py", FILLER + comments)
        self.assert_blocked(self.edit_replacing(path, "# note 3", "# note 3\n# one more line"))

    def test_density_at_threshold_passes(self):
        comments = "\n".join(f"# note {index}" for index in range(10)) + "\n"
        path = self.source("a.py", FILLER + comments)
        self.assert_allowed(self.edit(path, comments))

    def test_density_needs_thirty_non_blank_lines(self):
        content = "\n".join(f"# note {index}" for index in range(20)) + "\n"
        path = self.source("a.py", content)
        self.assert_allowed(self.edit(path, content))

    def test_density_ignores_edit_without_comments(self):
        comments = "\n".join(f"# note {index}" for index in range(15)) + "\n"
        path = self.source("a.py", FILLER + comments)
        self.assert_allowed(self.edit(path, "value_1 = 1"))

    def test_bare_delimiters_are_not_charged(self):
        docstrings = '"""\n' * 20
        path = self.source("a.py", FILLER + docstrings)
        self.assert_allowed(self.edit(path, '"""'))
        path = self.source("b.ts", FILLER + "/**\n*/\n" * 10)
        self.assert_allowed(self.edit(path, "/**\n */"))

    def test_jsdoc_continuation_counts_but_star_args_do_not(self):
        stars = "\n".join(f" * line {index}" for index in range(15)) + "\n"
        path = self.source("a.ts", FILLER + stars)
        self.assert_blocked(self.edit(path, stars))
        code = "\n".join(f"*args{index}" for index in range(15)) + "\n"
        path = self.source("b.ts", FILLER + code)
        self.assert_allowed(self.edit(path, code))

    def test_comment_leaders_all_count(self):
        leaders = ["//", "#", "--", ";", "<!--", "/*"]
        for leader in leaders:
            with self.subTest(leader=leader):
                comments = "\n".join(f"{leader} note {index}" for index in range(15)) + "\n"
                path = self.source("a.py", FILLER + comments)
                self.assert_blocked(self.edit(path, comments))


if __name__ == "__main__":
    unittest.main()
