#!/usr/bin/env python3
"""concentration.py <base-sha>: the concentration gate of the refactor closing phase.

Prints the added source lines of the branch's largest module and of the whole branch (`git diff <base-sha>...HEAD`),
then either the module to run `/refactor simplify` on and why, or that the gate does not trigger. A module is a
directory; tests, lockfiles, generated files (migration snapshots and journals included) and anything under a docs
folder do not count. Only committed work counts: uncommitted and untracked changes are left out, so commit the finished
phase before running the gate.

A second line splits the same committed diff's added lines into docs, tests and code:
`Diff split: docs <n> (<p>%), tests <n> (<p>%), code <n> (<p>%) of <total> added lines.` A test file is tests, any other
Markdown file or file under a docs folder is docs, every other file is code; lockfiles, generated files and binary files
count nowhere. When the split's total is at least 300 added lines and the docs or the tests part is over 40%,
the line ends with `OVERSIZED: <part> <p>% (limit 40%): ...` for each such part, docs first;
otherwise with `No part over 40%.`
"""
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
from numstat import added_lines_by_group
from script_utils import git_output, rounded_percent
from source_paths import is_counted_source, is_doc_path, is_test_path, is_uncounted_path

MODULE_TRIGGER_LINES = 100
BRANCH_TRIGGER_LINES = 300
SPLIT_SHARE_LIMIT = 40
SPLIT_PARTS = ("docs", "tests", "code")
OVERSIZED_PARTS = ("docs", "tests")
USAGE = "usage: concentration.py <base-sha>"


def module_of(path):
    # A module is the directory a file sits in; a file at the repo root is the module ".".
    return str(pathlib.PurePosixPath(path).parent)


def is_gate_counted(path):
    # Source the gate counts: no test, lockfile or generated file, and nothing under a docs folder (plans, ADRs).
    folders = pathlib.PurePosixPath(path).parts[:-1]
    return is_counted_source(path) and "docs" not in folders


def concentration_gate(repo_dir, base):
    """{"module", "largest", "branch", "trigger", "split"} for the diff `base...HEAD`, or None when git cannot read it.
    `trigger` is "concentrated", "distributed" or None. `split` is the added-line counts
    {"docs": n, "tests": n, "code": n}."""
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
    split = added_lines_by_group(numstat_text, part_of, is_uncounted_path)
    return {"module": module, "largest": largest, "branch": branch, "trigger": trigger,
            "split": {part: split.get(part, 0) for part in SPLIT_PARTS}}


def part_of(path):
    # Tests come first, so a test file under a docs folder counts as tests.
    if is_test_path(path):
        return "tests"
    if is_doc_path(path):
        return "docs"
    return "code"


def split_line(split):
    """The `Diff split:` line for {"docs": n, "tests": n, "code": n}."""
    total = sum(split.values())
    shares = {part: rounded_percent(split[part], total) for part in SPLIT_PARTS}
    counts = ", ".join(f"{part} {split[part]} ({shares[part]}%)" for part in SPLIT_PARTS)
    line = f"Diff split: {counts} of {total} added lines."

    if total < BRANCH_TRIGGER_LINES:
        return f"{line} No part over {SPLIT_SHARE_LIMIT}%."

    oversized = [part for part in OVERSIZED_PARTS if shares[part] > SPLIT_SHARE_LIMIT]
    if not oversized:
        return f"{line} No part over {SPLIT_SHARE_LIMIT}%."

    verdicts = [
        f"OVERSIZED: {part} {shares[part]}% (limit {SPLIT_SHARE_LIMIT}%): check each new {part} file against a plan "
        "step, criterion or finding, and cut the rest."
        for part in oversized
    ]
    return f"{line} {' '.join(verdicts)}"


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
    print(split_line(gate["split"]))


if __name__ == "__main__":
    main(sys.argv[1:])
