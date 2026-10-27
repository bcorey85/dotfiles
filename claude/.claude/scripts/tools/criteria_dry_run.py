"""Dry-run every Automated Verification command of a plan against the tree as it is now, and judge each result.

Usage: criteria_dry_run.py <spec.md> [--repo DIR] [--skip N ...] [--timeout SECONDS]

Prints one `CHECK <phase>.<n> <verdict> rc=<code> <command>` line per command, in plan order, plus a `  FLAG` line
under it for each problem the exit code cannot show:
- a filtered test run that exits 0 while reporting no passed test is RED (the test is not written yet);
- a `pgrep -f` pattern that matches the shell running the check always finds that shell;
- a count criterion whose stated number differs from the number the plan's own code blocks give.
Exit 0 when every command is RED and unflagged; exit 1 otherwise (GREEN, BROKEN or any flag need an answer before the
plan is final). `--skip N` leaves out check N (every phase's checks are numbered in one sequence) for a command that
writes."""
import argparse
import pathlib
import re
import shlex
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS_DIR / "lib"), str(SCRIPTS_DIR / "code")]
import code_step_boundary
import plan_format
import script_utils
from test_run_output import matches_no_test

DEFAULT_TIMEOUT_SECONDS = 600
FENCE_LINE = re.compile(r"^\s*(?:`{3,}|~{3,})")
PGREP_WORD = re.compile(r"\bpgrep\b([^|;&]*)")
BRACKET_CLASS = re.compile(r"\[[^\]]+\]")
SEARCH_PROGRAMS = {"rg", "grep", "egrep"}
SEARCH_VALUE_FLAGS = {"-e", "-g", "--glob", "--iglob", "-t", "--type", "-T", "--type-not", "-m", "--max-count", "-A",
                      "-B", "-C", "-f", "--file", "-j", "--threads", "-E", "--encoding", "--max-depth", "-d"}
COMMAND_BREAKS = {"|", "||", "&&", ";", "&"}
STATED_IN_COMMAND = re.compile(r"(?:-eq|==?)\s*[\"']?(\d+)\b")
STATED_IN_ITEM = re.compile(r"\b(?:is|are|=|==|equals?|returns?|prints?|outputs?|shows?|gives?|reports?|expects?|"
                            r"expected)\s+(?:exactly\s+)?(\d+)\b", re.IGNORECASE)


def self_matching_pgrep(command):
    """The pgrep pattern words when the command runs `pgrep -f` with a pattern that has no `[x]` character class, else
    None. The shell that runs the check has the pattern in its own command line, so it always matches itself."""
    match = PGREP_WORD.search(command)
    if not match:
        return None
    words = match.group(1).split()
    flags = [word for word in words if word.startswith("-")]
    full_match = any(flag == "--full" or (not flag.startswith("--") and "f" in flag) for flag in flags)
    patterns = [word for word in words if not word.startswith("-")]
    if not full_match or not patterns or BRACKET_CLASS.search(" ".join(patterns)):
        return None
    return " ".join(patterns)


def search_count_pattern(command):
    """(pattern, ignore_case, fixed) of the first rg or grep in the command when it counts matching lines (`-c`,
    `--count`, or a pipe into `wc -l`), else None. None too for a form the plan's code cannot be matched against."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        return None
    program_index = next((index for index, word in enumerate(words) if word in SEARCH_PROGRAMS), None)
    if program_index is None:
        return None

    segment = []
    for word in words[program_index + 1:]:
        if word in COMMAND_BREAKS:
            break
        segment.append(word)
    counts = any(word == "--count" or re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", word) for word in segment)
    counts = counts or any(words[index] == "wc" and "-l" in words[index + 1:index + 2] for index in range(len(words)))
    if not counts:
        return None

    ignore_case = fixed = False
    pattern = None
    index = 0
    while index < len(segment):
        word = segment[index]
        if word in ("-e", "--regexp") and index + 1 < len(segment):
            pattern = segment[index + 1]
            index += 2
            continue
        if word in SEARCH_VALUE_FLAGS:
            index += 2
            continue
        if word.startswith("-") and len(word) > 1:
            letters = word[1:] if not word.startswith("--") else ""
            ignore_case = ignore_case or "i" in letters or word == "--ignore-case"
            fixed = fixed or "F" in letters or word == "--fixed-strings"
            if any(unsupported in letters for unsupported in "UvwxPo") or word in ("--multiline", "--invert-match"):
                return None
        elif pattern is None:
            pattern = word
        index += 1
    return (pattern, ignore_case, fixed) if pattern else None


def stated_count(command, item_text):
    """The number the criterion says the count must be: `-eq 3` or `= 3` in the command, else a number after a word
    such as `prints` or `returns` in the item's text. None when it states none."""
    for text, rule in ((command, STATED_IN_COMMAND), (item_text.replace(command, ""), STATED_IN_ITEM)):
        match = rule.search(text)
        if match:
            return int(match.group(1))
    return None


def count_in_code(code_lines, pattern, ignore_case, fixed):
    """How many of the plan's code lines match the pattern, or None when the pattern is not a regex Python reads."""
    needle = re.escape(pattern) if fixed else pattern
    try:
        rule = re.compile(needle, re.IGNORECASE if ignore_case else 0)
    except re.error:
        return None
    return sum(1 for line in code_lines if rule.search(line))


def count_mismatch(command, item_text, code_lines):
    """(stated, from_code) when a count criterion states a number and the plan's code blocks hold a different, non-zero
    number of matching lines; else None. A code count of 0 says only that the counted file is not in the plan."""
    search = search_count_pattern(command)
    stated = stated_count(command, item_text)
    if search is None or stated is None:
        return None
    from_code = count_in_code(code_lines, *search)
    if not from_code or from_code == stated:
        return None
    return stated, from_code


def phase_code_lines(lines, section):
    """The lines inside fenced code blocks of one phase section, fence lines left out."""
    section_lines = lines[section["start"]:section["end"]]
    fenced = script_utils.fenced_line_indexes(section_lines)
    return [line for index, line in enumerate(section_lines)
            if index in fenced and not FENCE_LINE.match(line)]


def is_ban(line, command):
    """True when the item writes its command as a negated search (`! rg ...`): exit 1, no match, holds it."""
    spans = script_utils.backticked_spans(line)
    return any(code_step_boundary.without_negation(span) == command and span != command for span in spans)


def criteria_in_plan(lines, repo_dir):
    """(label, line, command, code_lines) for each Automated Verification item that gets a command, in plan order;
    label is `<phase>.<n>` with n counting from 1 across the whole plan. Items with no command to run come back with
    command None. A closing phase's items are left out: its skill checks them from the session's evidence and runs no
    command, as the plan check reads them."""
    spans, _ = plan_format.phase_spans(lines)
    criteria = []
    for phase_id, section in spans:
        if plan_format.closing_skill(section["title"]):
            continue

        section_lines = lines[section["start"]:section["end"]]
        code_lines = phase_code_lines(lines, section)
        for _, line in plan_format.automated_verification_rows(section_lines):
            if plan_format.runs_no_command(line):
                continue
            command = code_step_boundary.verification_command(line, repo_dir)
            criteria.append((f"{phase_id}.{len(criteria) + 1}", line, command, code_lines))
    return criteria


def verdict_for(command, banned, code, output):
    """GREEN, RED or BROKEN for one run, and the flag text for a zero-test match."""
    if code in (script_utils.COMMAND_NOT_FOUND_EXIT_CODE, script_utils.TIMEOUT_EXIT_CODE):
        return "BROKEN", None
    if matches_no_test(command, code, output):
        return "RED", "matches no test: the run exits 0 but reports no passed test, so it reads RED until a test exists"
    if banned:
        return ("GREEN" if code == 1 else "RED" if code == 0 else "BROKEN"), None
    return ("GREEN" if code == 0 else "RED"), None


def dry_run(plan_path, repo_dir, skipped, timeout):
    """Run the plan's criteria and print the report. Returns the exit code."""
    lines = plan_path.read_text().splitlines()
    needs_answer = False
    for label, line, command, code_lines in criteria_in_plan(lines, repo_dir):
        item_text = plan_format.automated_item_text(line)
        if command is None:
            print(f"CHECK {label} UNPARSED {item_text[:120]}")
            needs_answer = True
            continue
        if int(label.split(".")[1]) in skipped:
            print(f"CHECK {label} SKIPPED {command}")
            continue

        code, output = script_utils.run_command(command, repo_dir, timeout=timeout)
        verdict, flag = verdict_for(command, is_ban(line, command), code, output)
        print(f"CHECK {label} {verdict} rc={code} {command}")
        flags = [flag] if flag else []

        pgrep_pattern = self_matching_pgrep(command)
        if pgrep_pattern:
            flags.append(f"pgrep -f matches the shell running the check: pattern {pgrep_pattern!r} is in that shell's "
                         "own command line. Bracket one letter ('[x]yz') or match by name with `pgrep -x`")
        mismatch = count_mismatch(command, item_text, code_lines)
        if mismatch:
            flags.append(f"count criterion says {mismatch[0]} but the plan's own code blocks give {mismatch[1]}")
        if verdict == "BROKEN":
            flags.append(f"cannot run: {output[-200:]}")
        for flag_text in flags:
            print(f"  FLAG {flag_text}")
        needs_answer = needs_answer or verdict != "RED" or bool(flags)
    return 1 if needs_answer else 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("plan", type=pathlib.Path)
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument("--skip", type=int, action="append", default=[])
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    return dry_run(args.plan, args.repo, set(args.skip), args.timeout)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
