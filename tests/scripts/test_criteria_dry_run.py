import contextlib
import io
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from toolkit_paths import TOOLS_DIR

sys.path.insert(0, str(TOOLS_DIR))
import criteria_dry_run

SCRIPT = pathlib.Path(os.environ.get("CRITERIA_DRY_RUN_SCRIPT") or TOOLS_DIR / "criteria_dry_run.py")

PLAN = """# Plan

## Phase 1: First

#### Automated Verification:

- [ ] `test -e first-phase-file` exits 0

## Phase 2: Second

#### Automated Verification:

- [ ] `test -e second-phase-file` exits 0
- [ ] `vitest run -t not_written_yet` passes
- [ ] `vitest run -t written` passes
- [ ] `pgrep -f 'zz-no-such-daemon'` prints nothing
- [ ] `pgrep -f '[z]z-no-such-daemon'` prints nothing
- [ ] `rg -c 'handler' src.ts` prints 2

Code the phase writes:

```ts
const handler = a;
const handler = b;
const handler = c;
```
"""


def fake_vitest(bin_dir):
    """A vitest that exits 0 for every filter and reports a passed test only for `-t written`."""
    program = bin_dir / "vitest"
    program.write_text('#!/bin/sh\nif [ "$3" = written ]; then echo "Tests  1 passed (1)"; '
                       'else echo "No test files found"; fi\nexit 0\n')
    program.chmod(program.stat().st_mode | stat.S_IEXEC)


class CriteriaDryRunTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = pathlib.Path(temp.name)
        fake_vitest(self.repo)
        (self.repo / "plan.md").write_text(PLAN)
        env = dict(os.environ, PATH=f"{self.repo}{os.pathsep}{os.environ['PATH']}")
        self.run_result = subprocess.run([sys.executable, str(SCRIPT), str(self.repo / "plan.md"), "--repo",
                                          str(self.repo)], capture_output=True, text=True, env=env)
        self.report = self.run_result.stdout

    def check_lines(self):
        return [line for line in self.report.splitlines() if line.startswith("CHECK")]

    def test_runs_the_commands_of_every_phase_not_only_the_first(self):
        commands = [line for line in self.check_lines() if "second-phase-file" in line]
        self.assertEqual(len(commands), 1, self.report)
        self.assertGreaterEqual(len(self.check_lines()), 7, self.report)

    def test_a_filtered_run_that_matches_no_test_is_red(self):
        line = next(line for line in self.check_lines() if "not_written_yet" in line)
        self.assertIn(" RED ", line)
        self.assertIn("matches no test", self.report)

    def test_a_filtered_run_that_reports_a_passed_test_is_green(self):
        line = next(line for line in self.check_lines() if "-t written" in line)
        self.assertIn(" GREEN ", line)

    def test_flags_a_pgrep_pattern_that_matches_the_shell_running_the_check(self):
        flagged = [line for line in self.report.splitlines() if "pgrep -f matches the shell" in line]
        self.assertEqual(len(flagged), 1, self.report)
        self.assertIn("zz-no-such-daemon", flagged[0])

    def test_flags_a_count_that_differs_from_the_count_in_the_plans_code(self):
        self.assertIn("count criterion says 2 but the plan's own code blocks give 3", self.report)

    def test_exits_1_when_a_check_needs_an_answer(self):
        self.assertEqual(self.run_result.returncode, 1)


SEARCH_PLAN = """# Plan

## Phase 1: Search

#### Automated Verification:

- [ ] `grep foo src.txt` finds no match
- [ ] `grep foo src.txt | wc -l` prints 0
- [ ] `grep foo src.txt` finds the handler, present in the file
"""


class SearchItemVerdictTest(unittest.TestCase):
    """The dry run judges a search item as /code's verification does."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = pathlib.Path(temp.name)
        (repo / "src.txt").write_text("foo\n")
        (repo / "plan.md").write_text(SEARCH_PLAN)
        finished = subprocess.run([sys.executable, str(SCRIPT), str(repo / "plan.md"), "--repo", str(repo)],
                                  capture_output=True, text=True)
        self.checks = [line for line in finished.stdout.splitlines() if line.startswith("CHECK")]

    def test_a_plain_search_with_ban_wording_that_hits_is_red(self):
        self.assertIn(" RED ", self.checks[0])

    def test_a_pipe_search_that_prints_a_count_is_red_though_the_pipe_exits_0(self):
        self.assertIn(" RED ", self.checks[1])

    def test_a_plain_search_with_presence_wording_that_hits_is_green(self):
        self.assertIn(" GREEN ", self.checks[2])


ENV_PLAN = """# Plan

## Phase 1: Shim

#### Automated Verification:

- [ ] `uv-shim-check run` passes
"""


# What mise 2026.11.3 prints from the uv shim when the pinned uv is not installed.
MISE_NOT_INSTALLED_LINES = (
    "mise ERROR Tool not installed for shim: uv",
    "Missing tool version: aqua:astral-sh/uv@0.1.0",
    "Install all missing tools with: mise install",
)


class EnvironmentFailureTest(unittest.TestCase):
    def test_a_tool_that_cannot_start_reads_env_with_a_flag_and_needs_an_answer(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = pathlib.Path(temp)
            program = repo / "uv-shim-check"
            echoes = "".join(f"echo '{line}'\n" for line in MISE_NOT_INSTALLED_LINES)
            program.write_text(f"#!/bin/sh\n{echoes}exit 1\n")
            program.chmod(program.stat().st_mode | stat.S_IEXEC)
            (repo / "plan.md").write_text(ENV_PLAN)
            env = dict(os.environ, PATH=f"{repo}{os.pathsep}{os.environ['PATH']}")
            finished = subprocess.run([sys.executable, str(SCRIPT), str(repo / "plan.md"), "--repo", temp],
                                      capture_output=True, text=True, env=env)
        self.assertIn("CHECK 1.1 ENV rc=1", finished.stdout)
        self.assertIn("FLAG environment failure: mise ERROR Tool not installed for shim: uv", finished.stdout)
        self.assertNotIn(" RED ", finished.stdout)
        self.assertEqual(finished.returncode, 1)


class CappedRunTest(unittest.TestCase):
    """dry_run starts each criterion's command inside the shared capped slice when the machine can run one."""

    def started_command(self, cap_available):
        with tempfile.TemporaryDirectory() as temp:
            repo = pathlib.Path(temp)
            plan = repo / "plan.md"
            plan.write_text("# Plan\n\n## Phase 1: Tool\n\n#### Automated Verification:\n\n"
                            "- [ ] `echo hi` exits 0\n")
            with mock.patch.object(criteria_dry_run.memory_cap_scope, "cap_available", return_value=cap_available), \
                    mock.patch.object(criteria_dry_run.script_utils, "run_command",
                                      return_value=(0, "")) as run_command, \
                    contextlib.redirect_stdout(io.StringIO()):
                criteria_dry_run.dry_run(plan, repo, set(), 5)
        return run_command.call_args.args[0]

    def test_a_capped_machine_runs_the_command_as_the_capped_argv(self):
        argv = self.started_command(True)

        self.assertIn("--slice=tests.slice", argv)
        self.assertEqual("-c", argv[-2])
        self.assertIn("echo hi", argv[-1])

    def test_a_machine_without_a_scope_runs_the_plain_shell_command(self):
        self.assertEqual("echo hi", self.started_command(False))


class DryRunMissingToolTest(unittest.TestCase):
    def test_a_command_that_exits_127_on_a_missing_tool_reads_env_with_the_fix_not_broken(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = pathlib.Path(temp)
            probe = repo / "probe.sh"
            probe.write_text("#!/bin/sh\necho 'bash: no-such-tool-for-the-dry-run: command not found' >&2\nexit 127\n")
            probe.chmod(0o755)
            (repo / "plan.md").write_text("# Plan\n\n## Phase 1: Tool\n\n#### Automated Verification:\n\n"
                                          "- [ ] `./probe.sh` exits 0\n")
            finished = subprocess.run([sys.executable, str(SCRIPT), str(repo / "plan.md"), "--repo", temp],
                                      capture_output=True, text=True)

        self.assertIn("CHECK 1.1 ENV rc=127", finished.stdout)
        self.assertIn("fix: install no-such-tool-for-the-dry-run or add the pyenv shims to PATH", finished.stdout)
        self.assertNotIn("BROKEN", finished.stdout)
        self.assertEqual(finished.returncode, 1)


class PinnedInterpreterTest(unittest.TestCase):
    def test_a_linked_worktree_runs_a_tool_only_the_shims_hold_when_the_main_checkout_pins_a_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            main_checkout = root / "main"
            linked = root / "linked"
            subprocess.run(["git", "init", "-q", str(main_checkout)], check=True)
            subprocess.run(["git", "-C", str(main_checkout), "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                            "-q", "--allow-empty", "-m", "base"], check=True)
            subprocess.run(["git", "-C", str(main_checkout), "worktree", "add", "-q", str(linked)], check=True)
            (main_checkout / ".python-version").write_text("3.12.4\n")
            shim = root / "pyenv" / "shims" / "pinned-dry-run-tool"
            shim.parent.mkdir(parents=True)
            shim.write_text('#!/bin/sh\n[ "$PYENV_VERSION" = 3.12.4 ] && echo pinned && exit 0\nexit 1\n')
            shim.chmod(0o755)
            probe = linked / "probe.sh"
            probe.write_text("#!/bin/sh\npinned-dry-run-tool\n")
            probe.chmod(0o755)
            (linked / "plan.md").write_text("# Plan\n\n## Phase 1: Pin\n\n#### Automated Verification:\n\n"
                                            "- [ ] `./probe.sh` exits 0\n")
            env = dict(os.environ, PYENV_ROOT=str(root / "pyenv"))
            finished = subprocess.run([sys.executable, str(SCRIPT), str(linked / "plan.md"), "--repo", str(linked)],
                                      capture_output=True, text=True, env=env)

        self.assertIn("CHECK 1.1 GREEN rc=0 ./probe.sh", finished.stdout)


class StatedCountTest(unittest.TestCase):
    def test_a_number_inside_another_backticked_span_is_not_the_stated_count(self):
        item = "`grep -c foo a` counts the lines, unlike `echo returns 9`"
        self.assertIsNone(criteria_dry_run.stated_count("grep -c foo a", item))

    def test_a_number_after_a_stating_word_outside_the_spans_is_the_stated_count(self):
        self.assertEqual(criteria_dry_run.stated_count("grep -c foo a", "`grep -c foo a` prints 3"), 3)


class SkipTest(unittest.TestCase):
    def test_skip_leaves_a_numbered_check_unrun(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = pathlib.Path(temp) / "plan.md"
            plan.write_text(PLAN.split("## Phase 2")[0])
            finished = subprocess.run([sys.executable, str(SCRIPT), str(plan), "--repo", temp, "--skip", "1"],
                                      capture_output=True, text=True)
        self.assertIn("SKIPPED", finished.stdout)
        self.assertEqual(finished.returncode, 0)


class ClosingPhaseTest(unittest.TestCase):
    def test_a_closing_phase_item_is_listed_as_closing_and_not_run(self):
        closing_plan = ("# Plan\n\n## Phase 1: Build\n\n#### Automated Verification:\n\n"
                        "- [ ] `test -e not-built-yet` exits 0\n\n## Phase 2: Refactor pass\n\n"
                        "#### Automated Verification:\n\n"
                        '- [ ] `CHANGED="$(git diff --name-only)" && test -n "$CHANGED"` exits 0\n'
                        "- [ ] N/A: nothing to run for this pass\n")

        with tempfile.TemporaryDirectory() as temp:
            plan = pathlib.Path(temp) / "plan.md"
            plan.write_text(closing_plan)
            finished = subprocess.run([sys.executable, str(SCRIPT), str(plan), "--repo", temp],
                                      capture_output=True, text=True)

        output_lines = finished.stdout.splitlines()
        command_lines = [line for line in output_lines if line.startswith("CHECK 2.2 ")]
        self.assertEqual(len(command_lines), 1, finished.stdout)
        self.assertTrue(command_lines[0].startswith("CHECK 2.2 CLOSING /refactor +deep "), command_lines[0])
        self.assertIn("git diff --name-only", command_lines[0])
        self.assertNotIn("rc=", command_lines[0])
        prose_lines = [line for line in output_lines if line.startswith("CHECK 2.3 ")]
        self.assertEqual(len(prose_lines), 1, finished.stdout)
        self.assertTrue(prose_lines[0].startswith("CHECK 2.3 CLOSING /refactor +deep "), prose_lines[0])
        self.assertIn("N/A", prose_lines[0])
        self.assertNotIn("rc=", prose_lines[0])
        self.assertNotIn("UNPARSED", finished.stdout)
        self.assertEqual(finished.returncode, 0, finished.stdout)


if __name__ == "__main__":
    unittest.main()
