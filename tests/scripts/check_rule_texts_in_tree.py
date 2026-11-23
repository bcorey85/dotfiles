"""Check that each live scenario's rule_text is verbatim in its agent or skill file under <toolkit root>.

Usage: check_rule_texts_in_tree.py <scenarios.json> <toolkit root>. Exit 0 when every checked scenario matches,
1 naming each that does not, 2 on input it cannot parse. Skipped: retired scenarios, a rule_source outside agents/ or
skills/, and a toolkit_root that is a frozen copy outside the root's git repository (the meter checks those itself).
"""
import json
import subprocess
import sys
from pathlib import Path

CHECKED_PREFIXES = ("agents/", "skills/")


def fail_input(message):
    print(f"check_rule_texts_in_tree: {message}", file=sys.stderr)
    sys.exit(2)


def git_common_dir(folder):
    """The repository the folder belongs to, or None outside any repository."""
    run = subprocess.run(["git", "-C", str(folder), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


class BadScenarioError(Exception):
    """A scenario that names a rule_source but carries no rule_text to look for."""


def mismatch(name, scenario, root, repository):
    """Return why the scenario's rule_text is not in its file, or None when it is or the scenario is skipped.

    Raises BadScenarioError for a checked scenario whose rule_text is not a non-empty string."""
    source = scenario.get("rule_source")
    if scenario.get("retired") or not isinstance(source, str) or not source.startswith(CHECKED_PREFIXES):
        return None
    toolkit_root = scenario.get("toolkit_root")
    if toolkit_root and git_common_dir(Path(toolkit_root).expanduser()) != repository:
        return None
    rule_text = scenario.get("rule_text")
    if not isinstance(rule_text, str) or not rule_text:
        raise BadScenarioError(f"scenario {name}: rule_source {source} but rule_text is not a non-empty string")
    if not (root / source).is_file():
        return f"{source} is missing from {root}"
    return None if rule_text in (root / source).read_text(encoding="utf-8") else f"rule_text not verbatim in {source}"


def main(argv):
    if len(argv) != 3:
        fail_input("usage: check_rule_texts_in_tree.py <scenarios.json> <toolkit root>")
    try:
        scenarios = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail_input(f"cannot read {argv[1]}: {error}")
    if not isinstance(scenarios, dict) or not all(isinstance(s, dict) for s in scenarios.values()):
        fail_input(f"{argv[1]} must be a JSON object of scenario objects")
    root, repository = Path(argv[2]), git_common_dir(Path(argv[2]))
    if repository is None:
        fail_input(f"{root} is not inside a git repository")
    failed = False
    bad_scenarios = []
    for name, scenario in scenarios.items():
        try:
            why = mismatch(name, scenario, root, repository)
        except BadScenarioError as error:
            bad_scenarios.append(str(error))
            continue
        if why:
            print(f"FAIL {name}: {why}")
            failed = True
    if bad_scenarios:
        fail_input("; ".join(bad_scenarios))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
