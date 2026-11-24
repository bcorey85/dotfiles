#!/usr/bin/env python3
"""Pre-commit step: checks the STAGED toolkit against agent-evals, so a commit cannot drift from it.

  toolkit_drift.py     run from the repo top (the pre-commit hook does); exit 0 when clean or skipped, 1 on drift

Runs only when the staged set touches claude/.claude/agents/, claude/.claude/skills/ or a CLAUDE.md under
claude/.claude/. Two checks:
  1. every live rule-meter scenario whose rule source (or rule_file) is a staged path still finds its rule_text in the
     staged copy of that file;
  2. when a skill path is staged, agent-evals' bin/test_skill_names.py passes against the staged index.

rule_meter reads the toolkit from the home folder, so the staged claude/.claude is exported from the index into a
temporary folder and each live scenario is pointed at it. $AGENT_EVALS_DIR (default ~/agent-evals) names the checkout.

Fails closed on drift and on a rule_meter that cannot be loaded; skips with a note on stderr (exit 0) when
agent-evals or one of the two scripts it needs is absent, because a machine without agent-evals cannot be checked."""
import copy
import importlib
import os
import pathlib
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "claude" / ".claude" / "scripts" / "lib"))
import index_export  # noqa: E402

TOOLKIT_DIR = "claude/.claude"
TRIGGER_PATTERN = re.compile(r"^claude/\.claude/(agents/|skills/|(.*/)?CLAUDE\.md$)")
SKILL_PATTERN = re.compile(r"^claude/\.claude/skills/")
DEFAULT_RULE_SOURCE = "CLAUDE.md"


def run_git(*args):
    """Runs git in the current folder; a git failure stops the step with git's own message."""
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"toolkit_drift: git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def staged_paths():
    """Staged paths, deletions included."""
    return run_git("diff", "--cached", "--name-only").splitlines()


def live_toolkit_roots():
    """The folders that mean 'the live toolkit': ~/.claude and the main checkout's claude/.claude, which ~/.claude
    links to. Resolved, so a link and its target compare equal."""
    home = pathlib.Path.home()
    return {(home / ".claude").resolve(), (home / "dotfiles" / TOOLKIT_DIR).resolve()}


def reads_live_toolkit(scenario, live_roots):
    root = scenario.get("toolkit_root")
    if not root:
        return True
    return pathlib.Path(root).expanduser().resolve() in live_roots


def staged_files_of(scenario):
    """The staged-path spellings of the toolkit files the scenario's rule is read from."""
    if scenario.get("rule_file"):
        return {f"{TOOLKIT_DIR}/{scenario['rule_file']}"}
    return {f"{TOOLKIT_DIR}/{scenario.get('rule_source') or DEFAULT_RULE_SOURCE}"}


def scenarios_to_check(scenarios, staged, export_root):
    """Live, unretired scenarios whose source file is staged, copied to read the exported toolkit."""
    live_roots = live_toolkit_roots()
    picked = {}
    for rule, scenario in scenarios.items():
        if scenario.get("retired"):
            continue
        if not reads_live_toolkit(scenario, live_roots):
            continue
        if not staged_files_of(scenario) & staged:
            continue
        staged_scenario = copy.deepcopy(scenario)
        staged_scenario["toolkit_root"] = str(export_root)
        if not staged_scenario.get("rule_source"):
            staged_scenario["rule_source"] = DEFAULT_RULE_SOURCE
        picked[rule] = staged_scenario
    return picked


def rule_text_problems(rule_meter, scenarios):
    """One message per failing scenario: check_rule_texts exits on its first failure, so it runs once per scenario."""
    problems = []
    for rule, scenario in scenarios.items():
        try:
            rule_meter.check_rule_texts({rule: scenario})
        except SystemExit as stopped:
            source = " / ".join(sorted(staged_files_of(scenario)))
            problems.append(f"scenario {rule} ({source}): {stopped.code}")
    return problems


def import_rule_meter(bin_dir):
    sys.path.insert(0, str(bin_dir))
    return importlib.import_module("rule_meter")


def check_rule_texts_of_staged(bin_dir, staged):
    rule_meter = import_rule_meter(bin_dir)
    scenarios = rule_meter.load_scenarios()
    with tempfile.TemporaryDirectory() as destination:
        export_root = index_export.export_index_folder(pathlib.Path.cwd(), TOOLKIT_DIR, destination)
        picked = scenarios_to_check(scenarios, staged, export_root)
        return rule_text_problems(rule_meter, picked)


def skill_list_problem(skill_test):
    """The skill test's own failure output, or an empty string when it passes against the staged index."""
    git_dir = pathlib.Path(run_git("rev-parse", "--absolute-git-dir").strip())
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_DIR": str(git_dir),
        "GIT_INDEX_FILE": str(index_export.index_file_path(git_dir)),
    }
    result = subprocess.run([sys.executable, str(skill_test)], capture_output=True, text=True, env=env)
    if result.returncode == 0:
        return ""
    return (result.stdout + result.stderr).strip()


def main():
    staged = staged_paths()
    if not any(TRIGGER_PATTERN.match(path) for path in staged):
        return 0

    evals_dir = pathlib.Path(os.environ.get("AGENT_EVALS_DIR") or pathlib.Path.home() / "agent-evals")
    rule_meter_file = evals_dir / "bin" / "rule_meter.py"
    skill_test = evals_dir / "bin" / "test_skill_names.py"
    if not rule_meter_file.is_file() or not skill_test.is_file():
        print(f"toolkit_drift: {evals_dir} lacks bin/rule_meter.py or bin/test_skill_names.py; "
              "rule texts and the skill list were not checked", file=sys.stderr)
        return 0

    failures = check_rule_texts_of_staged(evals_dir / "bin", set(staged))
    if any(SKILL_PATTERN.match(path) for path in staged):
        skill_problem = skill_list_problem(skill_test)
        if skill_problem:
            failures.append(f"skill list (bin/test_skill_names.py):\n{skill_problem}")

    if not failures:
        return 0
    print("toolkit_drift: the staged toolkit drifted from agent-evals:", file=sys.stderr)
    for failure in failures:
        print(f"  {failure}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
