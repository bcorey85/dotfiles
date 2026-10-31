#!/usr/bin/env python3
"""concentration.py <base-sha>: the concentration gate of the refactor closing phase.

Prints the added source lines of the branch's largest module and of the whole branch (`git diff <base-sha>...HEAD`),
then either the module to run `/refactor simplify` on and why, or that the gate does not trigger. A module is a
directory; tests, lockfiles, generated files and anything under a docs folder do not count.
"""
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
from numstat import added_lines_by_group
from script_utils import git_output
from source_paths import is_counted_source

MODULE_TRIGGER_LINES = 100
BRANCH_TRIGGER_LINES = 300
USAGE = "usage: concentration.py <base-sha>"


def module_of(path):
    # A module is the directory a file sits in; a file at the repo root is the module ".".
    return str(pathlib.PurePosixPath(path).parent)


def is_gate_counted(path):
    # Source the gate counts: no test, lockfile or generated file, and nothing under a docs folder (plans, ADRs).
    folders = pathlib.PurePosixPath(path).parts[:-1]
    return is_counted_source(path) and "docs" not in folders


def concentration_gate(repo_dir, base):
    """{"module", "largest", "branch", "trigger"} for the diff `base...HEAD`, or None when git cannot read it.
    `trigger` is "concentrated", "distributed" or None."""
    numstat_text = git_output(repo_dir, "diff", "--numstat", "-z", "--no-renames", f"{base}...HEAD")
    if numstat_text is None:
        return None

    by_module = added_lines_by_group(numstat_text, module_of, lambda path: not is_gate_counted(path))
    module, largest = max(by_module.items(), key=lambda pair: pair[1], default=("-", 0))
    branch = sum(by_module.values())
    trigger = None
    if largest >= MODULE_TRIGGER_LINES:
        trigger = "concentrated"
    elif branch >= BRANCH_TRIGGER_LINES:
        trigger = "distributed"
    return {"module": module, "largest": largest, "branch": branch, "trigger": trigger}


def gate_line(gate):
    counts = (f"largest module {gate['module']} {gate['largest']} added lines (trigger {MODULE_TRIGGER_LINES}), "
              f"branch {gate['branch']} added lines (trigger {BRANCH_TRIGGER_LINES})")
    if gate["trigger"] is None:
        return f"Concentration gate: {counts}. Not triggered: no simplify run needed."
    return (f"Concentration gate: {counts}. TRIGGERED ({gate['trigger']}): run `/refactor simplify {gate['module']}` "
            "on that one module.")


def main(argv):
    if len(argv) != 1:
        sys.exit(USAGE)

    gate = concentration_gate(pathlib.Path.cwd(), argv[0])
    if gate is None:
        sys.exit(f"concentration: git could not diff {argv[0]}...HEAD, so the counts cannot be computed. Give a base "
                 "commit that exists in this repo.")

    print(gate_line(gate))


if __name__ == "__main__":
    main(sys.argv[1:])
