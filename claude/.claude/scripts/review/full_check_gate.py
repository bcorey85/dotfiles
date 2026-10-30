"""The review loop's full-check gate: the check run, its base run on HEAD, the autofix formatters and the repair and
recheck steps. LoopRun inherits FullCheckSteps; the loop script's SIGTERM handler calls remove_live_base_trees."""

import functools
import os
import pathlib
import re
import shutil
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parent / folder) for folder in (".", "review", "code", "lib")]
import code_step_core
import expected_red
import format_files
import full_check
import script_utils
from finding_record import parse_finding
from worktree_snapshot import CHANGE_KINDS

CHECK_TIMEOUT_SECONDS = 900
# Process-group leaders of the claude calls and checks now running: each starts its own session, so the group kill
# that stops the loop script does not reach them.
LIVE_CHILDREN = set()
# (repo root, worktree) of the base run's detached worktree while it exists: the stop signal removes it, because the
# exit skips the base run's own cleanup.
LIVE_BASE_TREES = set()


def run_full_check(repo, out, check_command, gate_env=(), runner=None, log_name=code_step_core.FULL_CHECK_LOG):
    """(the full_check result, the log's last lines with the failing tests above them, the run's details: runner
    summaries and the files the check changed or created). A SIGTERM kills the check's process group with the claude
    calls. `runner` (full_check.run by default) is any function with run's check arguments, such as
    full_check.base_run, whose result this returns as it is."""
    runner = runner or full_check.run
    assignments = script_utils.environment_from_assignments(gate_env)
    check_pids = []

    def check_started(pid):
        check_pids.append(pid)
        LIVE_CHILDREN.add(pid)

    try:
        return runner(repo, check_command, out / log_name, CHECK_TIMEOUT_SECONDS,
                      env={**os.environ, **assignments}, on_start=check_started)
    finally:
        LIVE_CHILDREN.difference_update(check_pids)


def remove_live_base_trees():
    """Remove the worktree of every base run still running, with its temp folder."""
    for root, tree in list(LIVE_BASE_TREES):
        full_check.remove_worktree(root, tree)
        shutil.rmtree(tree.parent, ignore_errors=True)


class FullCheckSteps:
    """The full-check state and steps of a LoopRun. The host sets repo, out, gate_env, files_touched, untested_fix and
    expected_red, and provides stop(status, remaining), repair(call_name, findings) and mark_repaired(findings,
    changed)."""

    def init_full_check_state(self):
        self.full_check = ""
        self.full_check_command = ""
        self.expected_red = []  # the phase's Expected red entries that the check leaves out
        self.base_checked = False
        self.base_run = None
        self.check_details = {"summaries": [], **{kind: [] for kind in CHANGE_KINDS}}

    def full_check_pass(self, check_command):
        """The full check, with one coder repair when it fails outside a spec file. A check that did not run, in CI
        or past its time limit, and one that exited 0 with no runner summary or ran no test, is no failure and gets no
        repair; one the environment could not run stops as `setup-fault`."""
        tail = self.run_check(check_command)
        if full_check.is_setup_fault_result(self.full_check):
            self.stop_on_setup_fault(check_command, tail)
            return

        if not full_check.is_failure(self.full_check):
            return

        gate_findings = [f"full check failed (`{check_command}`), failing lines:\n{tail}"]
        if re.search(r"\.spec\.", tail):
            self.stop("critical-blocker", gate_findings)
            return

        gate_records = [parse_finding(text) for text in gate_findings]
        _report, _diffs, gate_changed = self.repair("coder-gate", gate_records)
        self.mark_repaired(gate_records, gate_changed)
        self.recheck_full_check(check_command, "full check still failing after one repair")

    def run_check(self, check_command):
        """Run the full check, keep its result, command and details for the packet. Returns the log's tail.
        The changed, rewrote_edited and created paths add up across runs; the summaries are the latest run's. The
        check leaves the files it rewrote or created in place, and a repair measures its changes as the text
        difference around its own call, so a changed or created file reaches files_touched only when the repair coder
        edits it itself. A rewrote_edited file holds coder work and always counts as touched. A check that the
        Expected red entries leave out whole does not run, and sets untested_fix so the changed files' tests run, and
        so does a check-only pass in a repo whose full suite runs in CI."""
        self.full_check_command = check_command or ""
        if check_command is None and self.expected_red:
            self.full_check = expected_red.not_run_result(self.expected_red)
            self.untested_fix = True
            return ""

        self.full_check, tail, details = run_full_check(self.repo, self.out, check_command, self.gate_env)
        if self.full_check == full_check.PASSED:
            self.untested_fix = False
        elif self.full_check == full_check.CHECK_ONLY_PASSED:
            self.untested_fix = True
        check_wrote = set(self.check_details["changed"]) | set(self.check_details["created"])
        details["rewrote_edited"] = [path for path in details["rewrote_edited"]
                                     if path not in check_wrote or path in self.files_touched]
        for key in CHANGE_KINDS:
            details[key] = sorted(set(self.check_details[key]) | set(details[key]))
        details["rewrote_edited"] = sorted(set(details["rewrote_edited"])
                                           | ((set(details["changed"]) | set(details["created"])) & self.files_touched))
        for key in ("changed", "created"):
            details[key] = [path for path in details[key] if path not in details["rewrote_edited"]]
        self.check_details = details
        if full_check.is_failure(self.full_check) and self.fails_without_the_diff(check_command):
            self.full_check = full_check.PRE_EXISTING
        return tail

    def fails_without_the_diff(self, check_command):
        """True when the check's latest log fails as the base run does on HEAD without the working-tree changes: the
        same result, failing lines that are not empty and all in the base run's, every failing-block detail line in the
        base run's, and no other line new to the log holding an error marker. When every failing line is a
        `FAILED: <steps>` summary, no line may be new to the log. The base run happens once per loop; later checks
        reuse its failing lines."""
        if not self.base_checked:
            self.base_checked = True
            gate_assignments = script_utils.environment_from_assignments(self.gate_env)
            base_runner = functools.partial(full_check.base_run, live_trees=LIVE_BASE_TREES,
                                            gate_env=gate_assignments)
            self.base_run = run_full_check(self.repo, self.out, check_command, self.gate_env,
                                           runner=base_runner, log_name=code_step_core.FULL_CHECK_BASE_LOG)
        return full_check.is_pre_existing(self.out / code_step_core.FULL_CHECK_LOG, self.full_check, self.base_run)

    def autofix_touched_files(self):
        """Run the autofix formatters on the files the loop touched, a web tool only where the repo configures it.
        True when one changed a file; the changed files count as touched."""
        changed = format_files.run_formatters(self.repo, sorted(self.files_touched), include_python=True,
                                              configured_only=True, check_command=self.full_check_command)
        self.files_touched.update(changed)
        return bool(changed)

    def recheck_full_check(self, check_command, failure_heading):
        """The full check after a coder repair. A failure the formatters can fix is fixed and checked once more. Then a
        setup fault stops as `setup-fault`, any other failure as `critical-blocker`."""
        tail = self.run_check(check_command)
        if full_check.is_failure(self.full_check) and self.autofix_touched_files():
            tail = self.run_check(check_command)
        if full_check.is_setup_fault_result(self.full_check):
            self.stop_on_setup_fault(check_command, tail)
        elif full_check.is_failure(self.full_check):
            self.stop("critical-blocker", [f"{failure_heading}:\n{tail}"])

    def stop_on_setup_fault(self, check_command, tail):
        """The full check could not run here, which no coder repair changes: stop for the user."""
        self.stop("setup-fault", [f"the full check could not run in this environment (`{check_command}`), full "
                                  f"log {self.out / code_step_core.FULL_CHECK_LOG}, last lines:\n{tail}"])
