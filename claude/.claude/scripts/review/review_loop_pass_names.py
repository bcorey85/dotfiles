"""review_loop_pass_names.py: the names of the fix coder passes. Imports nothing, so any loop module can read it.
Owner of the pass names and of `is_finding_pass`. Import them; never spell a pass name elsewhere."""
FIRST_FIX_PASS = "coder0"
CLASS_FIX_PASS = "coder-class"
GATE_FIX_PASS = "coder-gate"
LINT_FIX_PASS = "coder-lint"
PROSE_FIX_PASS = "coder-prose"
ROUND_FIX_PREFIX = "coder"
MISSED_FIX_PREFIX = "coder-missed"
RESTORE_PASS_SUFFIX = "-restore"


def round_fix_pass(iter_count):
    """The name of the fix pass on the findings of review round `iter_count`."""
    return f"{ROUND_FIX_PREFIX}{iter_count}"


def missed_fix_pass(iter_count):
    """The name of the pass on the fixes of review round `iter_count` that no earlier pass of the round was briefed
    on."""
    return f"{MISSED_FIX_PREFIX}{iter_count}"


def restore_pass(call_name):
    """The name of the pass that restores the plan-named tests that the pass `call_name` removed."""
    return f"{call_name}{RESTORE_PASS_SUFFIX}"


def is_finding_pass(call_name):
    """True when the coder pass `call_name` is given reviewer or caller findings: the first, round, missed-fix and
    class passes. The gate, lint, prose and restore passes get prompts built from a check's output."""
    if call_name in (FIRST_FIX_PASS, CLASS_FIX_PASS):
        return True
    if call_name.startswith(MISSED_FIX_PREFIX) and call_name.removeprefix(MISSED_FIX_PREFIX).isdigit():
        return True
    round_number = call_name.removeprefix(ROUND_FIX_PREFIX)
    return call_name.startswith(ROUND_FIX_PREFIX) and round_number.isdigit()
