#!/usr/bin/env python3
"""plan_check.py: the write-time check of a plan file.

  plan_check.py check [--final] <plan>   print each way the plan does not hold; exit 1 when any, else 0. --final also
                                         fails a spec whose criteria file was never written.
"""
import os
import pathlib
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("code", "lib", "review")]
import expected_red
import full_check
import plan_format
import script_utils
from plan_verification import verification_format_failure

USAGE = "usage: plan_check.py check [--final] <plan>"


def expected_red_failure(plan_lines, plan_name, repo_dir):
    # The message for Expected red lines that do not hold against the repo's Quality check, or None when all hold.
    quality_check = full_check.configured_check_command(repo_dir)
    rows = expected_red.failure_rows(plan_lines, quality_check, plan_name)
    if not rows:
        return None
    return "The plan's Expected red lines do not hold. Fix each line:\n" + "\n".join(rows)


def print_failure(failure):
    # Print one failure message, if any, and give it back so the caller can count it.
    if failure:
        print(failure)
    return failure


def check_plan(plan_lines, plan, plan_path, final):
    # Print each way the plan does not hold; True when any is a failure (warnings print but do not fail).
    for row in plan_format.plan_failure_rows(plan, plan_path):
        print(row)
    manual_failure = print_failure(plan_format.manual_format_failure(plan_lines, plan_path))
    # From a repo subdirectory the checks resolve against the repo root; outside a repo against the current directory.
    repo_dir = script_utils.repo_root(os.getcwd()) or pathlib.Path.cwd()
    verification_failure = print_failure(verification_format_failure(plan_lines, plan_path, repo_dir, plan["entries"]))
    red_failure = print_failure(expected_red_failure(plan_lines, plan_path, repo_dir))
    for row in plan_format.plain_verification_item_warnings(plan_lines, plan_path):
        print(row)
    ac_failures = plan_format.spec_ac_failures(pathlib.Path(plan_path))
    for row in ac_failures:
        print(row)
    criteria_failure = None
    if final:
        criteria_failure = print_failure(plan_format.missing_criteria_failure(pathlib.Path(plan_path)))
    return bool(plan["failures"] or manual_failure or verification_failure or red_failure or ac_failures
                or criteria_failure)


def main(args):
    if "--help" in args or "-h" in args:
        return print(USAGE)

    final = args[1:2] == ["--final"] and args[0:1] == ["check"]
    path_args = args[2:] if final else args[1:]
    if not path_args or args[0] != "check":
        sys.exit(USAGE)
    plan_path = path_args[0]

    plan_lines = pathlib.Path(plan_path).read_text().splitlines()
    plan = plan_format.parse_plan_with_closing_phases(plan_lines)

    sys.exit(1 if check_plan(plan_lines, plan, plan_path, final) else 0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(USAGE)
    main(sys.argv[1:])
