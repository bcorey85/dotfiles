"""Checks for stale-citation-gate.py, the PostToolUse hook that warns on stale document citations and planning
vocabulary in shipped source. It never blocks."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or pathlib.Path.home() / ".claude" / "scripts")
SCRIPT = SCRIPTS_DIR / "stale-citation-gate.py"


class StaleCitationGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = pathlib.Path(self.tmp.name).resolve()
        self.home = base / "home"
        self.home.mkdir()
        self.repo = base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)

    def write(self, relative, content, root=None):
        path = (root or self.repo) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return str(path)

    def run_hook(self, stdin):
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": self.tmp.name}
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                              env=environment)

    def edit(self, path):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": path}}
        finished = self.run_hook(json.dumps(payload))
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")
        return finished.stderr

    def test_invalid_input_and_missing_file_pass(self):
        for stdin in ("not json", "", json.dumps({"tool_input": {}}),
                      json.dumps({"tool_input": {"file_path": str(self.repo / "nope.md")}})):
            finished = self.run_hook(stdin)
            self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def test_file_outside_git_tree_passes(self):
        outside = pathlib.Path(self.tmp.name) / "plain"
        path = self.write("a.md", "see docs/gone.md\n", root=outside)
        self.assertEqual(self.edit(path), "")

    def test_skipped_paths_pass(self):
        for relative in (".claude/a.md", "node_modules/a.md", ".venv/a.md", "dist/a.md", "build/a.md", "a.min.js",
                         "poetry.lock"):
            with self.subTest(relative=relative):
                path = self.write(relative, "docs/gone.md\n# phase 2\n")
                self.assertEqual(self.edit(path), "")

    def test_resolving_citation_passes(self):
        self.write("docs/real.md", "x\n")
        path = self.write("notes.md", "see docs/real.md for more\n")
        self.assertEqual(self.edit(path), "")

    def test_missing_path_in_existing_directory_is_reported(self):
        self.write("docs/real.md", "x\n")
        path = self.write("notes.md", "see docs/gone.md and docs/real.md.\n")
        self.assertEqual(self.edit(path),
                         "stale-citation-gate: notes.md cites paths that do not resolve — a rename, renumber or "
                         "deletion elsewhere falsified them:\n  docs/gone.md — no such path\n")

    def test_missing_directory_is_not_repo_relative(self):
        path = self.write("notes.md", "see other-repo/src/thing.py\n")
        self.assertEqual(self.edit(path), "")

    def test_line_beyond_end_of_file_is_reported(self):
        self.write("docs/real.md", "a\nb\nc\n")
        path = self.write("notes.md", "docs/real.md:3 fine, docs/real.md:4 not, (docs/real.md:99)\n")
        self.assertEqual(self.edit(path),
                         "stale-citation-gate: notes.md cites paths that do not resolve — a rename, renumber or "
                         "deletion elsewhere falsified them:\n  docs/real.md:4 — file has 3 lines\n"
                         "  docs/real.md:99 — file has 3 lines\n")

    def test_citation_resolves_against_document_directory(self):
        self.write("docs/guide/real.md", "x\n")
        path = self.write("docs/index.md", "see guide/real.md and guide/missing.md\n")
        self.assertEqual(self.edit(path),
                         "stale-citation-gate: docs/index.md cites paths that do not resolve — a rename, renumber "
                         "or deletion elsewhere falsified them:\n  guide/missing.md — no such path\n")

    def test_template_and_glob_citations_are_skipped(self):
        self.write("docs/real.md", "x\n")
        path = self.write("notes.md", "docs/<name>.md docs/*.md docs/{a,b}.md docs/N.md docs/step-N.md\n")
        self.assertEqual(self.edit(path), "")

    def test_plan_documents_may_name_files_they_will_create(self):
        self.write("docs/real.md", "a\n")
        for relative in ("docs/plans/x.md", "feature/spec.md", "feature-plan.md", "notes/PREREG-1.md",
                         "plans-final/x.md".replace("plans-final", "docs/plans-final")):
            with self.subTest(relative=relative):
                path = self.write(relative, "creates docs/new.md\n")
                self.assertEqual(self.edit(path), "")
        path = self.write("docs/plans/y.md", "docs/real.md:5 and docs/new.md\n")
        self.assertIn("docs/real.md:5 — file has 1 lines", self.edit(path))

    def test_longest_extension_wins(self):
        self.write("data/rows.jsonl", "x\n")
        path = self.write("notes.md", "data/rows.jsonl data/other.jsonl data/rows.tsv\n")
        stderr = self.edit(path)
        self.assertIn("  data/other.jsonl — no such path\n", stderr)
        self.assertIn("  data/rows.tsv — no such path\n", stderr)
        self.assertNotIn("data/rows.jsonl", stderr)

    def test_citations_are_sorted_and_deduplicated(self):
        self.write("docs/real.md", "x\n")
        path = self.write("notes.md", "docs/b.md docs/a.md docs/b.md\n")
        stderr = self.edit(path)
        self.assertTrue(stderr.endswith("  docs/a.md — no such path\n  docs/b.md — no such path\n"), stderr)

    def test_other_document_extensions_are_checked(self):
        self.write("docs/real.md", "x\n")
        for name in ("a.markdown", "a.rst", "a.txt"):
            with self.subTest(name=name):
                path = self.write(name, "docs/gone.md\n")
                self.assertIn("docs/gone.md — no such path", self.edit(path))

    def test_planning_vocabulary_in_source_comment_is_reported(self):
        content = "x = 1\n# phase 2 work\ny = 2  # per D3\n# AC4 holds\n# an earlier version said no\n"
        path = self.write("src/a.py", content)
        self.assertEqual(self.edit(path),
                         "stale-citation-gate: planning vocabulary in shipped source src/a.py — keep the fact, cut "
                         "the reference (see skills/_shared/code-vocabulary.md):\n  2:# phase 2 work\n"
                         "  4:# AC4 holds\n  5:# an earlier version said no\n")

    def test_planning_vocabulary_outside_comment_lines_is_ignored(self):
        path = self.write("src/a.py", "x = 'phase 2'  # note\nname = 'AC4'\n")
        self.assertEqual(self.edit(path), "")

    def test_hard_markers_are_reported_on_any_line(self):
        path = self.write("src/a.ts", "const a = 'docs/plans/x';\n// PLAN-IMPACT\nconst b = ACCEPTANCE-CONTRACT;\n")
        stderr = self.edit(path)
        self.assertTrue(stderr.endswith(":\n  1:const a = 'docs/plans/x';\n  2:// PLAN-IMPACT\n"
                                        "  3:const b = ACCEPTANCE-CONTRACT;\n"), stderr)

    def test_line_matching_both_checks_is_reported_once(self):
        path = self.write("src/a.py", "# phase 2 docs/plans/x\n")
        stderr = self.edit(path)
        self.assertEqual(stderr.count("# phase 2 docs/plans/x"), 1)

    def test_unlisted_extension_passes(self):
        path = self.write("src/a.toml", "# phase 2\n")
        self.assertEqual(self.edit(path), "")

    def test_clean_source_passes(self):
        path = self.write("src/a.py", "# a plain comment\nx = 1\n")
        self.assertEqual(self.edit(path), "")


if __name__ == "__main__":
    unittest.main()
