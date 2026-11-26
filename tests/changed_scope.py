#!/usr/bin/env python3
"""Tells tests/run.sh how much of the unit suite a change needs.

  changed_scope.py scope   print `markdown-only` when every change is a .md file under claude/.claude/skills/ or
                           claude/.claude/agents/, else `full`
  changed_scope.py kept    print the test files that still run on a markdown-only change, one per line

The changes are the work tree against the merge base with origin/master: committed branch changes, staged and
unstaged edits, and untracked files. The suite is required before a branch is handed over, so a committed change
counts as much as an uncommitted one. Anything this script cannot read (no git, no origin/master, no change at all)
answers `full`: a guess never skips a test."""
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPT_MARKDOWN = re.compile(r"^claude/\.claude/(skills|agents)/.+\.md$")

# The test files that load a skills/ or agents/ markdown file of the real tree; each still runs on a markdown-only
# change, so a prompt edit that breaks one fails. Found by recording every Python open() of such a file during a full
# run (test_rule_anchors is added by hand: rule-anchors.sh reads the files in awk). A new test that reads a prompt file
# of the real tree goes in this list.
PROMPT_READING_TESTS = (
    "test_adr_flow.py",
    "test_code_skill_text.py",
    "test_docs_kind.py",
    "test_fork_write_scope.py",
    "test_guidance_rules.py",
    "test_lane_brief.py",
    "test_log_escape.py",
    "test_log_review_finding.py",
    "test_phase_asks.py",
    "test_refactor_flow.py",
    "test_review_loop_coder.py",
    "test_review_loop_named_tests.py",
    "test_review_loop_nearest.py",
    "test_review_loop_repeats.py",
    "test_review_loop_round_two_fixes.py",
    "test_review_loop_ruled.py",
    "test_review_loop_script.py",
    "test_rule_anchors.py",
    "test_spec_agent_tools.py",
    "test_telemetry_switch.py",
    "test_toolkit_prose_facts.py",
)

# What a test file shows when it reads a prompt file of the real tree: a path helper for one, a prompt folder it
# walks, or the name of a module that loads prompts (the review loop, log-escape, docs-kind, rule-anchors).
PROMPT_READER_SIGNAL = re.compile(
    r'CLAUDE_DIR\s*/\s*"(skills|agents)[/"]|CODE_SKILL_FILE|CODE_FORK_AGENT_FILE|REAL_CLAUDE\w*\s*/\s*"(skills|agents)"'
    r'|TREE_CLAUDE_DIR\s*/\s*"(skills|agents)"|PROMPT_DIRS|review_loop_script|log_escape|docs_kind|rule[-_]anchors'
)
# Test files that show the signal but read no skill or agent markdown, with why; test_prompt_reader_list checks both
# lists against the signal. A file that stops matching leaves PROMPT_READING_TESTS or this list.
SIGNAL_BUT_NO_PROMPT_READ = {
    "test_change_size_bar.py": "names a signal module but reads no prompt",
    "test_clone_pairs.py": "runs a skill's Python script",
    "test_fix_induced.py": "names a signal module but reads no prompt",
    "test_ledger_write.py": "runs a skill's script",
    "test_log_escape_check.py": "runs a review skill's script",
    "test_log_review_metrics.py": "runs a review skill's script",
    "test_parallel_tests.py": "names a signal module but reads no prompt",
    "test_phase_asks_chain.py": "names a signal module but reads no prompt",
    "test_review_loop_scope_guard.py": "names a signal module but reads no prompt",
    "test_review_scope.py": "runs a review skill's script",
    "test_shape_clones.py": "runs a skill's Python script",
    "test_shell_statements.py": "links a skill folder to test script trust, reads no markdown",
    "test_stage_run.py": "runs a skill's script",
    "test_sweep_markers.py": "runs a skill's Python script",
    "test_toml_file.py": "lists skill Python scripts",
    "test_toolkit_self_location.py": "scans the skill folders but skips .md files",
    "test_verify_branch_script.py": "runs a review skill's script",
}


def git_lines(*args):
    """The NUL-separated output of a git command run in the repo, or None when git fails."""
    try:
        finished = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=False)
    except OSError:
        return None
    if finished.returncode != 0:
        return None
    return [line for line in finished.stdout.split("\0") if line]


def changed_paths():
    """The changed paths against the merge base with origin/master, or None when they cannot be read."""
    base_lines = git_lines("merge-base", "HEAD", "origin/master")
    if not base_lines:
        return None
    tracked = git_lines("diff", "--name-only", "--no-renames", "-z", base_lines[0].strip())
    untracked = git_lines("ls-files", "--others", "--exclude-standard", "-z")
    if tracked is None or untracked is None:
        return None
    return tracked + untracked


def is_markdown_only(paths):
    if not paths:
        return False
    return all(PROMPT_MARKDOWN.match(path) for path in paths)


def scope():
    if is_markdown_only(changed_paths()):
        return "markdown-only"
    return "full"


def main(argv):
    if argv == ["scope"]:
        print(scope())
        return 0
    if argv == ["kept"]:
        print("\n".join(PROMPT_READING_TESTS))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
