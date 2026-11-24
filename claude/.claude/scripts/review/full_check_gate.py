"""The review loop's full-check gate: the check run, its base run on HEAD, the autofix formatters and the repair and
recheck steps. LoopRun inherits FullCheckSteps; the loop script's SIGTERM handler calls remove_live_base_trees."""

import functools
import os
import pathlib
import shutil
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parent / folder) for folder in (".", "review", "code", "lib")]
import accepted_failures
import format_files
import full_check
import full_check_receipt
import handback
import script_utils
import source_paths
from finding_record import parse_finding
from review_loop_pass_names import GATE_FIX_PASS, LINT_FIX_PASS
from worktree_snapshot import CHANGE_KINDS

CHECK_TIMEOUT_SECONDS = 900
# The files in the loop's state folder that hold the whole output of the full check and of its base run.
FULL_CHECK_LOG = "full-check.log"
FULL_CHECK_BASE_LOG = "full-check-base.log"
# The stems of the per-command logs a red scoped test run is compared on: its head output and its base run.
SCOPED_HEAD_LOG_STEM = "scoped-head"
SCOPED_BASE_LOG_STEM = "scoped-base"
# Process-group leaders of the claude calls and checks now running: each starts its own session, so the group kill
# that stops the loop script does not reach them.
LIVE_CHILDREN = set()
# (repo root, worktree) of the base run's detached worktree while it exists: the stop signal removes it, because the
# exit skips the base run's own cleanup.
LIVE_BASE_TREES = set()


def run_full_check(repo, out, check_command, gate_env=(), runner=None, log_name=FULL_CHECK_LOG, left_out=(),
                   source=None, base=None):
    """(the full_check result, the log's last lines with the failing tests above them, the run's details: runner
    summaries and the files the check changed or created). A SIGTERM kills the check's process group with the claude
    calls. `runner` (full_check.run by default) is any function with run's check arguments, such as
    full_check.base_run, whose result this returns as it is. `left_out` (the Expected red entries the command leaves
    out), `source` (where an overriding command came from) and `base` (the revision the diff that narrows the
    discovered check is taken against) go to the runner only when they hold some."""
    runner = runner or full_check.run
    assignments = script_utils.environment_from_assignments(gate_env)
    check_pids = []
    options = {"left_out": left_out} if left_out else {}
    if source:
        options["source"] = source
    if base:
        options["base"] = base

    def check_started(pid):
        check_pids.append(pid)
        LIVE_CHILDREN.add(pid)

    try:
        return runner(repo, check_command, out / log_name, CHECK_TIMEOUT_SECONDS,
                      env={**os.environ, **assignments}, on_start=check_started, **options)
    finally:
        LIVE_CHILDREN.difference_update(check_pids)


def remove_live_base_trees():
    """Remove the worktree of every base run still running, with its temp folder."""
    for root, tree in list(LIVE_BASE_TREES):
        full_check.remove_worktree(root, tree)
        shutil.rmtree(tree.parent, ignore_errors=True)


def lint_finding_texts(problems):
    """One finding text per (command text, output) lint problem."""
    return [f"lint failed (`{command}`), output:\n{output}" for command, output in problems]


class FullCheckSteps:
    """The full-check state and steps of a LoopRun. The host sets repo, out, gate_env, files_touched, untested_fix,
    expected_red, and provides review_scope(), stop(status, remaining), repair(call_name, findings),
    mark_repaired(findings, changed, reverted, records_skip=True) and format_reviewed_files(check_command)."""

    def init_full_check_state(self):
        self.full_check = ""
        self.full_check_command = ""
        self.expected_red = []  # the phase's Expected red entries that the check leaves out
        self.plan_on_disk = None  # the plan path and phase id phase_check reads the Expected red lines from
        self.phase = None
        # a `--test` command stands in for a default check that hit a setup fault or an environment gap, or was itself
        # an overridden run
        self.check_overridden = False
        self.base_runs = {}  # {full check command: its base run}, one base run per command per loop
        self.scoped_base_runs = {}  # {scoped test command: its base run}, one base run per command per loop
        self.check_details = {"summaries": [], **{kind: [] for kind in CHANGE_KINDS}}

    def full_check_pass(self, check_command):
        """The lint pass runs first, and a lint stop skips the check. Then the full check, with one coder repair when
        it fails outside a spec file. A check that did not run, in CI or past its time limit, and one that exited 0 with
        no runner summary or ran no test, is no failure and gets no repair. A missing tool or a missing declared
        module is a non-failing environment gap; any other check the environment could not run stops as
        `setup-fault`."""
        if not self.lint_pass(check_command):
            return

        tail = self.run_check(check_command)
        if full_check.is_setup_fault_result(self.full_check):
            self.stop_on_setup_fault(tail)
            return

        if not full_check.is_failure(self.full_check):
            return

        gate_findings = [f"full check failed (`{self.full_check_command}`), failing lines:\n{tail}"]
        if source_paths.names_spec_file(tail):
            self.stop("critical-blocker", gate_findings)
            return

        gate_records = [parse_finding(text) for text in gate_findings]
        _report, _diffs, gate_changed, gate_reverted = self.repair(GATE_FIX_PASS, gate_records)
        self.mark_repaired(gate_records, gate_changed, gate_reverted)
        self.recheck_full_check(check_command, "full check still failing after one repair")

    def reviewed_and_touched_files(self):
        """The sorted union of the review scope and the files a repair touched."""
        return sorted(set(self.review_scope()) | self.files_touched)

    def lint_pass(self, check_command):
        """Lint the reviewed and touched files with the repo's configured linters. A violation gets one coder repair
        and the formatters, then a second lint; one still failing stops as `critical-blocker`. True when the files
        are clean, or no linter applies."""
        problems = format_files.lint_problems(self.repo, self.reviewed_and_touched_files())
        if not problems:
            return True

        self.repair_lint_problems(problems)
        self.format_reviewed_files(check_command)
        problems = format_files.lint_problems(self.repo, self.reviewed_and_touched_files())
        if not problems:
            return True

        output = "\n".join(f"`{command}`:\n{text}" for command, text in problems)
        self.stop("critical-blocker", ["lint still failing after one repair:\n" + output])
        return False

    def repair_lint_problems(self, problems, records_skip=True):
        """One lint repair pass over `problems`, the (command text, output) pairs of format_files.lint_problems. With
        `records_skip`, a repair that changes nothing records its findings as skipped."""
        lint_records = [parse_finding(text) for text in lint_finding_texts(problems)]
        _report, _diffs, lint_changed, lint_reverted = self.repair(LINT_FIX_PASS, lint_records)
        self.mark_repaired(lint_records, lint_changed, lint_reverted, records_skip=records_skip)

    def lint_fixed_files(self, changed):
        """Lints the files `changed` by a fix pass, so a violation gets its repair before the next review round reads
        the file. A violation the repair leaves is for the lint pass of a converged run; a stopped run lints nothing
        more. A mid-loop repair that changes nothing records no skip: the exit lint pass lints the file again."""
        problems = format_files.lint_problems(self.repo, sorted(changed))
        if problems:
            self.repair_lint_problems(problems, records_skip=False)

    def run_check(self, check_command):
        """Run the full check, keep its result, command and details for the packet. Returns the log's tail.
        The changed, rewrote_edited and created paths add up across runs; the summaries are the latest run's. The
        check leaves the files it rewrote or created in place, and a repair measures its changes as the text
        difference around its own call, so a changed or created file reaches files_touched only when the repair coder
        edits it itself. A rewrote_edited file holds coder work and always counts as touched. A check that the
        Expected red entries leave out whole does not run, and sets untested_fix so the changed files' tests run, and
        so does a check-only pass in a repo whose full suite runs in CI. Every run, the left-out one too, writes the
        full-check receipt."""
        base = self.review_base or full_check.DEFAULT_DIFF_BASE
        check_command = self.check_command_for_diff(check_command, base)
        self.full_check_command = check_command or ""
        source = full_check_receipt.SOURCE_OVERRIDDEN if self.check_overridden else None
        self.full_check, tail, details = run_full_check(self.repo, self.out, check_command, self.gate_env,
                                                        left_out=self.expected_red, source=source, base=base)
        if check_command is None and self.expected_red:
            self.untested_fix = True
        elif self.full_check == full_check.PASSED:
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

    def check_command_for_diff(self, check_command, base):
        """The check to run now: the repo's check resolved again against the current diff from `base`, with the phase's
        Expected red entries applied again, so a fix pass that touched a file of another part runs that part. The
        entries it leaves out replace `expected_red`. An overridden check runs as it is."""
        if self.check_overridden:
            return check_command

        found_command = full_check.configured_check_command(self.repo, base)
        command, self.expected_red = full_check.phase_check(self.repo, found_command, self.plan_on_disk, self.phase,
                                                            base)
        return command

    def fails_without_the_diff(self, check_command):
        """True when the check's latest log fails as the base run does on HEAD without the working-tree changes: the
        same result, failing lines that are not empty and all in the base run's, every failing-block detail line in the
        base run's, and no other line new to the log holding an error marker. When every failing line is a
        `FAILED: <steps>` summary, no line may be new to the log. The base run happens once per check command per
        loop; later checks of the same command reuse its failing lines."""
        if check_command not in self.base_runs:
            gate_assignments = script_utils.environment_from_assignments(self.gate_env)
            base_runner = functools.partial(full_check.base_run, live_trees=LIVE_BASE_TREES,
                                            gate_assignments=gate_assignments)
            base_log = FULL_CHECK_BASE_LOG
            if self.base_runs:
                stem = FULL_CHECK_BASE_LOG.removesuffix(".log")
                base_log = f"{stem}-{len(self.base_runs)}.log"
            self.base_runs[check_command] = run_full_check(self.repo, self.out, check_command, self.gate_env,
                                                           runner=base_runner, log_name=base_log)
        return full_check.is_pre_existing(self.out / FULL_CHECK_LOG, self.full_check, self.base_runs[check_command])

    def scoped_failures_pre_existing(self, real_failures):
        """True when every red scoped test command, each a (command, outcome, output) from
        coder_gate.scoped_run (ScopedRun.real_failures), fails as its base run does on HEAD without
        the working-tree changes, by full_check.is_pre_existing, which also takes the recorded acceptances. A new
        failing test, a new error line or a base run that passes makes it False. Each command's base run happens
        once per loop."""
        if not real_failures:
            return False

        gate_assignments = script_utils.environment_from_assignments(self.gate_env)
        base_runner = functools.partial(full_check.base_run, live_trees=LIVE_BASE_TREES,
                                        gate_assignments=gate_assignments)
        accepted = accepted_failures.accepted_lines(self.repo)
        for index, (command, outcome, output) in enumerate(real_failures):
            if command not in self.scoped_base_runs:
                base_log = f"{SCOPED_BASE_LOG_STEM}-{len(self.scoped_base_runs)}.log"
                self.scoped_base_runs[command] = run_full_check(self.repo, self.out, command, self.gate_env,
                                                                runner=base_runner, log_name=base_log)
            head_log = self.out / f"{SCOPED_HEAD_LOG_STEM}-{index}.log"
            head_log.write_text(output)
            head_result = f"failed ({outcome})"
            base = self.scoped_base_runs[command]
            if not full_check.is_pre_existing(head_log, head_result, base, accepted):
                return False
        return True

    def accept_failure_hint(self, real_failures):
        """The accept commands for the failing lines of the red scoped commands, with a lead line; empty when no
        failing line is named."""
        failing = []
        for _command, _outcome, output in real_failures:
            failing += accepted_failures.failing_lines_of(output)
        if not failing:
            return ""

        commands = accepted_failures.accept_command_text(self.repo, list(dict.fromkeys(failing)))
        return "If a failing line above also fails without this diff, record that it is accepted:\n" + commands

    def autofix_touched_files(self):
        """Run the autofix formatters on the files the loop touched, a web tool only where the repo configures it.
        True when one changed a file; the changed files count as touched."""
        changed = format_files.run_formatters(self.repo, sorted(self.files_touched), include_python=True,
                                              configured_only=True, check_command=self.full_check_command)
        self.files_touched.update(changed)
        return bool(changed)

    def recheck_full_check(self, check_command, failure_heading):
        """The lint pass runs first, so every repair that ends here is linted, and a lint stop skips the check. Then
        the full check after a coder repair. A failure the formatters can fix is fixed and checked once more. Then a
        setup fault stops as `setup-fault`, any other failure as `critical-blocker`."""
        if not self.lint_pass(check_command):
            return

        tail = self.run_check(check_command)
        if full_check.is_failure(self.full_check) and self.autofix_touched_files():
            tail = self.run_check(check_command)
        if full_check.is_setup_fault_result(self.full_check):
            self.stop_on_setup_fault(tail)
        elif full_check.is_failure(self.full_check):
            self.stop("critical-blocker", [f"{failure_heading}:\n{tail}"])

    def stop_on_setup_fault(self, tail):
        """The full check could not run here, which no coder repair changes: stop for the user. An overridden check's
        own fault stops too; the default check never runs on an overridden launch. The message names the command that
        ran, which `run_check` stores."""
        self.stop(handback.SETUP_FAULT_STATUS,
                  [f"the full check could not run in this environment (`{self.full_check_command}`), full "
                   f"log {self.out / FULL_CHECK_LOG}, last lines:\n{tail}"])
