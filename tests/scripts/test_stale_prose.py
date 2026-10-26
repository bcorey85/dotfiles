"""Checks for stale_prose.py, which lists the prose lines that name a symbol the working tree's diff changed, renamed
or removed. STALE_PROSE_SCRIPT overrides the script path; it defaults to the installed one."""
import contextlib
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

SCRIPT = pathlib.Path(os.environ.get("STALE_PROSE_SCRIPT") or toolkit_paths.CODE_DIR / "stale_prose.py")
module_spec = importlib.util.spec_from_file_location("stale_prose", SCRIPT)
stale_prose = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(stale_prose)

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}
TS_BEFORE = "export function fetchWidget(id: string) {\n  return id;\n}\n"
TS_AFTER = "export function loadWidget(id: string) {\n  return id;\n}\n"


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError(f"git {args} failed: {done.stderr}")
    return done.stdout.strip()


class StaleProseTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")

    def write(self, relative, content):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit_files(self, files):
        for relative, content in files.items():
            self.write(relative, content)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")

    def run_script(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd or self.repo, env=GIT_ENV,
                              capture_output=True, text=True)

    def rename_scenario(self):
        self.commit_files({
            "src/widget.ts": TS_BEFORE,
            "docs/guide.md": "Call fetchWidget to get one.\nUnrelated line.\n",
            "src/other.ts": "// fetchWidget is the only way in\nconst x = 1;\n",
            "config/app.yaml": "name: app\ndescription: wraps fetchWidget calls\nother: fetchWidget\n",
            "config/app.json": '{\n  "description": "wraps fetchWidget"\n}\n',
            "src/second.ts": "export const SECOND_LIMIT = 1;\n",
            "docs/second.md": "SECOND_LIMIT caps the second thing at 1.\n",
        })
        self.write("src/widget.ts", TS_AFTER)

    def test_rename_finds_old_name_in_markdown_comment_and_yaml_description(self):
        self.rename_scenario()

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("fetchWidget (removed):", done.stdout)
        self.assertIn("docs/guide.md:1: Call fetchWidget to get one.", done.stdout)
        self.assertIn("src/other.ts:1: // fetchWidget is the only way in", done.stdout)
        self.assertIn("config/app.yaml:2: description: wraps fetchWidget calls", done.stdout)
        self.assertIn('config/app.json:2:', done.stdout)
        self.assertNotIn("config/app.yaml:3", done.stdout)
        self.assertNotIn("Unrelated line", done.stdout)
        self.assertNotIn("loadWidget", done.stdout)

    def test_removed_function_is_found(self):
        self.commit_files({"src/a.ts": "function dropMe() {\n  return 1;\n}\nconst keep = 2;\n",
                           "README.md": "Use dropMe here.\n"})
        self.write("src/a.ts", "const keep = 2;\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode)
        self.assertIn("dropMe (removed):", done.stdout)
        self.assertIn("README.md:1: Use dropMe here.", done.stdout)

    def test_changed_constant_value_is_found(self):
        self.commit_files({"src/limits.ts": "export const MAX_RETRIES = 3;\n",
                           "docs/limits.md": "MAX_RETRIES is 3.\n"})
        self.write("src/limits.ts", "export const MAX_RETRIES = 5;\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode)
        self.assertIn("MAX_RETRIES (changed):", done.stdout)
        self.assertIn("docs/limits.md:1: MAX_RETRIES is 3.", done.stdout)

    def value_only_scenario(self, before, after):
        self.commit_files({
            "src/limits.ts": before,
            "docs/limits.md": ("DEFAULT_GRACE_HOURS is measured from the due time.\n"
                               "The page length is the INVENTORY_PAGE_SIZE constant, 50 tools a page.\n"),
        })
        self.write("src/limits.ts", after)

    def test_value_only_change_drops_prose_lines_without_the_old_literal(self):
        self.value_only_scenario("export const DEFAULT_GRACE_HOURS = 24;\nexport const INVENTORY_PAGE_SIZE = 50;\n",
                                 "export const DEFAULT_GRACE_HOURS = 4;\nexport const INVENTORY_PAGE_SIZE = 25;\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertNotIn("is measured from the due time", done.stdout)
        self.assertIn("docs/limits.md:2: The page length is the INVENTORY_PAGE_SIZE constant, 50 tools a page.",
                      done.stdout)

    def test_value_only_change_with_no_prose_line_holding_the_old_literal_exits_zero(self):
        self.value_only_scenario("export const DEFAULT_GRACE_HOURS = 24;\n", "export const DEFAULT_GRACE_HOURS = 4;\n")

        done = self.run_script()

        self.assertEqual(0, done.returncode, done.stdout)

    def test_a_signature_change_keeps_every_hit(self):
        self.commit_files({"src/limits.ts": "export function graceWindow(hours: number) {\n  return hours;\n}\n",
                           "docs/limits.md": "graceWindow is measured from the due time.\n"})
        self.write("src/limits.ts", "export function graceWindow(hours: number, days: number) {\n  return hours;\n}\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("docs/limits.md:1: graceWindow is measured from the due time.", done.stdout)

    def test_files_named_only_by_their_extension_are_unknown_types_not_a_crash(self):
        self.commit_files({"src/widget.ts": TS_BEFORE, ".md": "Call fetchWidget to get one.\n",
                           "docs/.py": "# fetchWidget is the only way in\n"})
        self.write("src/widget.ts", TS_AFTER)

        done = self.run_script()

        self.assertEqual(0, done.returncode, done.stderr)

    def test_body_change_is_found_through_the_hunk_header(self):
        body = "export function computeTotals(items) {\n  let sum = 0;\n  for (const item of items) sum += item;\n" \
               "  return sum;\n}\n"
        self.commit_files({"src/totals.ts": body, "docs/totals.md": "computeTotals adds everything up.\n"})
        self.write("src/totals.ts", body.replace("sum += item", "sum += item * 2"))

        done = self.run_script()

        self.assertEqual(1, done.returncode)
        self.assertIn("computeTotals (body changed):", done.stdout)
        self.assertIn("docs/totals.md:1:", done.stdout)

    def test_python_def_finds_docstring_and_hash_comment_lines_only(self):
        self.commit_files({
            "pkg/mod.py": "def parse_config(path):\n    return path\n",
            "pkg/user.py": ('def use():\n    """Reads the file through parse_config.\n\n    More text.\n    """\n'
                            "    # parse_config reads the file\n    value = parse_config('x')\n    return value\n"),
        })
        self.write("pkg/mod.py", "def read_config(path):\n    return path\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode)
        self.assertIn("pkg/user.py:2:", done.stdout)
        self.assertIn("pkg/user.py:6:", done.stdout)
        self.assertNotIn("pkg/user.py:7:", done.stdout)

    def test_plan_files_under_docs_plans_are_not_searched(self):
        self.commit_files({
            "src/widget.ts": TS_BEFORE,
            "docs/plans/BILL-212-invoicing/spec.md": "Phase 1 renames fetchWidget.\nfetchWidget stays pure.\n",
            "docs/guide.md": "Call fetchWidget to get one.\n",
        })
        self.write("src/widget.ts", TS_AFTER)

        done = self.run_script()

        self.assertEqual(1, done.returncode)
        self.assertIn("docs/guide.md:1:", done.stdout)
        self.assertNotIn("docs/plans", done.stdout)

    def test_assignment_text_inside_a_python_string_declares_no_symbol(self):
        module = '"""Notes.\n\nHEREDOC = the marker\n"""\n\n\ndef run():\n    return 1\n'
        self.commit_files({"pkg/mod.py": module, "docs/guide.md": "The HEREDOC marker is documented here.\n"})
        self.write("pkg/mod.py", module.replace("HEREDOC = the marker", "HEREDOC = the new marker"))

        done = self.run_script()

        self.assertEqual(0, done.returncode)
        self.assertNotIn("HEREDOC", done.stdout.replace("no prose line", ""))

    def test_assignment_outside_a_string_still_declares_a_symbol(self):
        self.commit_files({"pkg/mod.py": "HEREDOC = 1\n", "docs/guide.md": "The HEREDOC marker is 1 here.\n"})
        self.write("pkg/mod.py", "HEREDOC = 2\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode)
        self.assertIn("HEREDOC (changed):", done.stdout)

    def test_lines_the_diff_added_are_skipped(self):
        self.commit_files({"src/widget.ts": TS_BEFORE, "docs/guide.md": "Intro.\n"})
        self.write("src/widget.ts", TS_AFTER)
        self.write("docs/guide.md", "Intro.\nWe renamed fetchWidget to loadWidget.\n")

        done = self.run_script()

        self.assertEqual(0, done.returncode, done.stdout)
        self.assertIn("nothing new", done.stdout)

    def test_a_declaration_line_inside_a_docstring_is_not_a_hit(self):
        self.commit_files({
            "pkg/mod.py": "def parse_config(path):\n    return path\n",
            "pkg/user.py": '"""Example:\n\ndef parse_config(path):\n\nparse_config reads it.\n"""\n',
        })
        self.write("pkg/mod.py", "def read_config(path):\n    return path\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stdout)
        self.assertIn("pkg/user.py:5:", done.stdout)
        self.assertNotIn("pkg/user.py:3:", done.stdout)

    def test_a_removed_symbol_named_nowhere_exits_zero(self):
        self.commit_files({"src/a.ts": "function dropMe() {\n  return 1;\n}\nconst keep = 2;\n",
                           "README.md": "Nothing here.\n"})
        self.write("src/a.ts", "const keep = 2;\n")

        done = self.run_script()

        self.assertEqual(0, done.returncode, done.stdout + done.stderr)

    def test_the_removed_side_is_read_from_the_base_file_not_the_working_tree(self):
        self.commit_files({"pkg/m.py": "import os\n\ndef drop_this():\n    return 1\n",
                           "docs/g.md": "Call drop_this.\n"})
        self.write("pkg/m.py", 'import os\n"""\nnotes\n"""\n')

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stdout + done.stderr)
        self.assertIn("drop_this (removed):", done.stdout)

    def test_the_added_side_is_read_from_the_working_tree_not_the_base_file(self):
        self.commit_files({"pkg/m.py": '"""\nnotes\n"""\nY_VALUE = 2\ndef keep_name(a):\n    return 1\n',
                           "docs/g.md": "Call keep_name.\n"})
        self.write("pkg/m.py", "X_VALUE = 1\ndef keep_name(a, b):\n    return 1\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stdout + done.stderr)
        self.assertIn("keep_name (changed):", done.stdout)

    def test_plain_lowercase_name_matches_only_in_backticks_or_call_form(self):
        self.commit_files({
            "src/a.ts": "function total(items) {\n  return items.length;\n}\n",
            "docs/a.md": "The total is shown.\nSee `total` for it.\nCall total(items) here.\nTotal again.\n",
        })
        self.write("src/a.ts", "function sum(items) {\n  return items.length;\n}\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode)
        self.assertNotIn("docs/a.md:1:", done.stdout)
        self.assertIn("docs/a.md:2:", done.stdout)
        self.assertIn("docs/a.md:3:", done.stdout)
        self.assertNotIn("docs/a.md:4:", done.stdout)

    def test_short_names_are_ignored(self):
        self.commit_files({"src/a.ts": "const abc = 1;\n", "docs/a.md": "`abc` is one.\nAbc as well.\n"})
        self.write("src/a.ts", "const abc = 2;\n")

        done = self.run_script()

        self.assertEqual(0, done.returncode, done.stdout)

    def test_second_run_with_the_same_hits_passes_and_a_new_hit_fails_again(self):
        self.rename_scenario()
        first = self.run_script()
        second = self.run_script()
        self.write("src/second.ts", "export const SECOND_LIMIT = 2;\n")
        third = self.run_script()
        fourth = self.run_script()

        self.assertEqual([1, 0, 1, 0], [first.returncode, second.returncode, third.returncode, fourth.returncode])
        self.assertIn("nothing new", second.stdout)
        self.assertIn("[new] docs/second.md:1:", third.stdout)
        self.assertIn("docs/guide.md:1:", third.stdout)
        self.assertNotIn("[new] docs/guide.md", third.stdout)

    def test_state_lives_in_the_git_dir_and_is_keyed_by_path_and_text(self):
        self.rename_scenario()
        self.run_script()

        state = json.loads((self.repo / ".git" / "stale-prose-shown.json").read_text())

        self.assertIn("docs/guide.md\tCall fetchWidget to get one.", state["shown"])

    def test_state_is_per_base_commit_and_a_new_commit_shows_the_hits_again(self):
        self.rename_scenario()
        first = self.run_script()
        second = self.run_script()
        self.write("docs/unrelated.md", "Nothing here.\n")
        git(self.repo, "add", "docs/unrelated.md")
        git(self.repo, "commit", "-qm", "unrelated")
        third = self.run_script()

        self.assertEqual([1, 0, 1], [first.returncode, second.returncode, third.returncode])
        self.assertIn("[new] docs/guide.md:1:", third.stdout)

    def test_a_saved_state_whose_shown_is_not_a_list_exits_two(self):
        self.rename_scenario()
        (self.repo / ".git" / "stale-prose-shown.json").write_text('{"base": "x", "shown": "abc"}')

        done = self.run_script()

        self.assertEqual(2, done.returncode)
        self.assertIn("stale-prose-shown.json", done.stderr)

    def test_a_symbol_with_a_new_hit_is_listed_before_symbols_with_only_old_hits(self):
        self.commit_files({
            "src/widget.ts": TS_BEFORE,
            "src/second.ts": "export const SECOND_LIMIT = 1;\n",
            "docs/s.md": "SECOND_LIMIT caps it at 1.\n" + "".join(f"Line {index} about fetchWidget.\n"
                                                            for index in range(2, 71)),
        })
        self.write("src/widget.ts", TS_AFTER)

        runs = [self.run_script(), self.run_script()]
        self.write("src/second.ts", "export const SECOND_LIMIT = 2;\n")
        runs += [self.run_script(), self.run_script()]

        self.assertEqual([1, 1, 1, 0], [done.returncode for done in runs])
        self.assertIn("[new] docs/s.md:1:", runs[2].stdout)

    def test_a_form_feed_line_does_not_shift_the_comment_line_numbers(self):
        self.commit_files({"src/widget.ts": TS_BEFORE,
                           "src/other.ts": "\x0c\nconst x = 1;\n// fetchWidget is the only way in\n"})
        self.write("src/widget.ts", TS_AFTER)

        done = self.run_script()

        self.assertIn("src/other.ts:3:", done.stdout)

    def test_a_symbol_removed_in_one_file_and_edited_in_another_is_removed(self):
        self.commit_files({"a.py": "def handle_order(x):\n    y = 1\n    return y\n",
                           "b.py": "def handle_order(x):\n    return x\n",
                           "docs/o.md": "Call handle_order.\n"})
        self.write("a.py", "def handle_order(x):\n    y = 2\n    return y\n")
        self.write("b.py", "OTHER_VALUE = 1\n")

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("handle_order (removed):", done.stdout)

    def test_a_symbol_moved_between_files_is_changed_not_removed(self):
        self.commit_files({"a.py": "def move_me(x):\n    return x\n", "b.py": "VALUE_ONE = 1\n",
                           "docs/o.md": "Call move_me.\n"})
        self.write("a.py", "VALUE_TWO = 2\n")
        self.write("b.py", "VALUE_ONE = 1\ndef move_me(x):\n    return x\n")

        done = self.run_script()

        self.assertIn("move_me (changed):", done.stdout)

    def test_a_diff_that_does_not_parse_exits_two(self):
        self.rename_scenario()

        stderr = io.StringIO()
        with (contextlib.chdir(self.repo), mock.patch.object(sys, "argv", ["stale_prose.py"]),
              mock.patch.object(stale_prose.source_text, "parse_unified_diff", side_effect=ValueError("bad diff")),
              contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as stopped):
            stale_prose.main()

        self.assertEqual(2, stopped.exception.code)
        self.assertIn("stale-prose: bad diff", stderr.getvalue())

    def test_clean_diff_exits_zero(self):
        self.commit_files({"src/widget.ts": TS_BEFORE, "docs/guide.md": "Call fetchWidget.\n"})

        done = self.run_script()

        self.assertEqual(0, done.returncode)
        self.assertIn("nothing new", done.stdout)

    def test_a_staged_new_code_file_does_not_hide_a_rename_hit(self):
        self.rename_scenario()
        self.write("src/new.ts", TS_BEFORE.replace("fetchWidget", "brandNew"))
        git(self.repo, "add", "src/new.ts")

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("docs/guide.md:1:", done.stdout)

    def test_a_deleted_code_file_removes_its_symbols(self):
        self.commit_files({"src/gone.ts": "export function goneThing() {\n  return 1;\n}\n",
                           "docs/gone.md": "Call goneThing.\n"})
        (self.repo / "src" / "gone.ts").unlink()

        done = self.run_script()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("goneThing (removed):", done.stdout)

    def test_base_option_reads_the_diff_from_that_revision(self):
        self.commit_files({"src/widget.ts": TS_BEFORE, "docs/guide.md": "Call fetchWidget.\n"})
        self.write("src/widget.ts", TS_AFTER)
        git(self.repo, "commit", "-qam", "rename")

        at_head = self.run_script()
        at_parent = self.run_script("--base", "HEAD~1")

        self.assertEqual(0, at_head.returncode)
        self.assertEqual(1, at_parent.returncode)
        self.assertIn("docs/guide.md:1:", at_parent.stdout)

    def test_output_is_capped_at_sixty_lines_and_counts_the_rest(self):
        self.commit_files({"src/a.ts": "const widgetValue = 100;\n",
                           "docs/long.md": "".join(f"Line {index} about widgetValue 100.\n" for index in range(70))})
        self.write("src/a.ts", "const widgetValue = 200;\n")

        done = self.run_script()

        body = done.stdout.splitlines()[1:-1]
        self.assertEqual(1, done.returncode)
        self.assertEqual(60, len(body))
        self.assertEqual("11 more hit(s) not shown.", done.stdout.splitlines()[-1])

    def test_a_cut_list_shows_the_rest_on_the_next_run(self):
        self.commit_files({"src/a.ts": "const widgetValue = 100;\n",
                           "docs/long.md": "".join(f"Line {index} about widgetValue 100.\n" for index in range(70))})
        self.write("src/a.ts", "const widgetValue = 200;\n")

        first = self.run_script()
        second = self.run_script()
        third = self.run_script()

        self.assertEqual([1, 1, 0], [first.returncode, second.returncode, third.returncode])
        self.assertIn("[new] docs/long.md:70:", second.stdout)

    def test_outside_a_repo_exits_two_with_a_message(self):
        outside = self.root / "plain"
        outside.mkdir()

        done = self.run_script(cwd=outside)

        self.assertEqual(2, done.returncode)
        self.assertIn("stale-prose:", done.stderr)

    def test_bad_base_exits_two(self):
        self.commit_files({"README.md": "x\n"})

        done = self.run_script("--base", "no-such-rev")

        self.assertEqual(2, done.returncode)
        self.assertIn("stale-prose: --base 'no-such-rev' is not a commit", done.stderr)

    def test_names_past_one_grep_batch_are_all_searched(self):
        self.commit_files({"README.md": "Call alphaThing.\nCall betaThing.\nCall gammaThing.\n"})

        with mock.patch.object(stale_prose, "NAMES_PER_GREP", 2):
            found = stale_prose.grep_lines(self.repo, ["alphaThing", "betaThing", "gammaThing"])

        self.assertEqual({("README.md", 1), ("README.md", 2), ("README.md", 3)}, set(found))

    def test_unreadable_state_exits_two(self):
        self.rename_scenario()
        (self.repo / ".git" / "stale-prose-shown.json").write_text("{not json")

        done = self.run_script()

        self.assertEqual(2, done.returncode)
        self.assertIn("stale-prose-shown.json", done.stderr)


class DeclaredNamesTest(unittest.TestCase):
    def test_each_suffix_family_reads_its_declaration_and_keywords_declare_nothing(self):
        cases = [
            (".ts", "export async function fetchWidget(id: string) {", ["fetchWidget"]),
            (".tsx", "const loadWidget = async (id) => {", ["loadWidget"]),
            (".js", "export class WidgetStore {", ["WidgetStore"]),
            (".ts", "while (x) {", []),
            (".ts", "switch (x) {", []),
            (".py", "async def fetch_widget(x):", ["fetch_widget"]),
            (".go", "func (s *Server) HandleOrder(x int) {", ["HandleOrder"]),
            (".rs", "pub async fn fetch_widget() {", ["fetch_widget"]),
            (".java", "public static Widget fetchWidget(int id) {", ["fetchWidget"]),
            (".kt", "suspend fun fetchWidget(id: Int) {", ["fetchWidget"]),
            (".rb", "def self.fetch_widget(id)", ["fetch_widget"]),
            (".py", "class WidgetStore:", ["WidgetStore"]),
            (".ts", "export type WidgetId = string;", ["WidgetId"]),
            (".ts", "  async fetchWidget(id: string): Promise<W> {", ["fetchWidget"]),
            (".ts", "  handleClick = (event) => {", ["handleClick"]),
            (".ts", "export const enum WidgetKind {", ["WidgetKind"]),
            (".js", "function* widgetIds() {", ["widgetIds"]),
            (".java", "private static final int MAX_WIDGETS = 3;", ["MAX_WIDGETS"]),
            (".kt", "fun String.toWidget(): Widget {", ["toWidget"]),
            (".rb", "module WidgetHelpers", ["WidgetHelpers"]),
            (".rb", "MAX_WIDGETS = 3", ["MAX_WIDGETS"]),
        ]
        for suffix, line, expected in cases:
            self.assertEqual(expected, stale_prose.declared_names(line, suffix), f"{suffix}: {line}")


class DescriptionLineTest(unittest.TestCase):
    def test_description_summary_and_title_keys_match_in_every_written_form(self):
        for line in ("summary: x", "title: x", "  - description: x", "Description: x", '"title": "x"'):
            self.assertIsNotNone(stale_prose.DESCRIPTION_LINE.match(line), line)

    def test_a_key_nested_after_another_key_does_not_match(self):
        self.assertIsNone(stale_prose.DESCRIPTION_LINE.match("other: description: x"))


if __name__ == "__main__":
    unittest.main()
