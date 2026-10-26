import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

from toolkit_paths import TOOLS_DIR

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


class SkipTest(unittest.TestCase):
    def test_skip_leaves_a_numbered_check_unrun(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = pathlib.Path(temp) / "plan.md"
            plan.write_text(PLAN.split("## Phase 2")[0])
            finished = subprocess.run([sys.executable, str(SCRIPT), str(plan), "--repo", temp, "--skip", "1"],
                                      capture_output=True, text=True)
        self.assertIn("SKIPPED", finished.stdout)
        self.assertEqual(finished.returncode, 0)


if __name__ == "__main__":
    unittest.main()
