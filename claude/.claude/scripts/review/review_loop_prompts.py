"""review_loop_prompts.py: the prompts the scripted review loop sends its reviewers and its coders."""
import json

import handback
import path_summary
import plan_format
import script_utils
from coder_report import ALREADY_APPLIED_MARKER, SKIPPED_MARKER

ISSUE_CHARS = 240
MAX_LISTED_ISSUES = 50
MAX_LISTED_PATHS = 40

FENCE = (
    'Fix only the issues listed below. Do not refactor surrounding code. Do not "improve" things you '
    "notice along the way. Do not rename, restructure, or add abstractions that aren't required by the "
    'fix itself. A focused 5-line fix is the right output, not a 50-line cleanup PR.\n'
    '\n'
    'After fixing each issue, check all callers and consumers of the changed code. If a fix changes a '
    'method signature, return type, or behavioral contract, update every caller in the same pass. Do not '
    'leave callers out of sync.\n'
    '\n'
    'If a listed issue turns out to be a false positive on inspection, skip it and report why. Do not '
    '"fix" issues that aren\'t actually broken just because the reviewer flagged them.'
)

SCOPED_TESTS = (
    "Run only the tests for the files you changed. Do not run lint suites, the full test suite or other repo-wide "
    "checks: the loop runs the full check after your pass."
)

SMALL_ITEMS = (
    "Small items follow the issues. They are the reviewer's optional notes, not findings. Apply a small "
    'item only when it names wrong behavior, or a false statement in a doc or a comment, and one '
    'correction is clear. Skip every other small item, and report each skip as `SKIPPED small <n>: <reason>`, '
    'where n is the small item\'s number. A small '
    'item never widens the change: no rename, no restructure, no new abstraction.'
)

OUT_OF_SCOPE_RULE = (
    "A change to an existing file that is outside the review's files and that no issue names may be put back "
    "after your pass."
)

NAMED_TESTS_RULE = "Tests the plan runs by name; never delete or rename them: "

LATER_PHASE_RULE = (
    "Never edit these files: the plan gives them to a later phase. When an issue needs one of them, leave it "
    "unapplied and report it as a PLAN-IMPACT: "
)

HELD_FILES_RULE = (
    "Never edit these files: another session holds uncommitted edits in them. When an issue needs one of them, skip "
    "it and say so: "
)

RULED_OUT_CODER_RULE = "The user ruled these files out of scope. Never edit, create or delete them: "

RULED_OUT_REVIEWER_RULE = "Out of scope by the user's ruling; file no finding on them: "

GUIDANCE_RULE = "Guidance from the main session. Follow it within the issues and the plan; it changes neither: "

CLASS_TAG_RULE = ("Tag each Fix, Ask and Nit item with its class in brackets, right after its file:line, or first when "
                  "it names none. One of: " + " ".join(f"[{name}]" for name in handback.CLASSES) + ".")


NO_CODE_REVIEW_RULE = ("These findings were ruled no code change. File a [plan-drift] finding for any code the fix "
                       "diff adds for one of them:")

NO_CODE_CODER_RULE = ("Issues ruled no code change: {numbers}. For each, edit no source or test file; make only the "
                      "doc or note edit the ruling names. When a ruling cannot be met without code, leave it "
                      f"unapplied and write `{SKIPPED_MARKER} <n>: <reason>` for it.")


def user_ruled_issue(text, ruled_at):
    """An issue the user accepted, marked with the time of the ruling. The marker comes first so the cut of a long
    issue never removes it."""
    return f"[accepted by the user, ruled {ruled_at}] {text}"


def review_scope_lines(repo, owned, prior_issues, open_asks):
    lines = [f"Repo root: {repo}", "Review scope (this round):", "  owned files:"]
    for path in owned:
        lines.append(f"    - {path}")
    if prior_issues:
        lines.append("  prior issues:")
    for item in prior_issues:
        lines.append(f"    - issue: {json.dumps(item['issue'])}")
        lines.append(f"      status: {item['status']}")
        lines.append(f"      file: {item['file']}")
        if item.get("reason"):
            lines.append(f"      reason: {json.dumps(item['reason'])}")
    if open_asks:
        lines.append("  open asks (do not re-raise):")
    for ask in open_asks:
        lines.append(f"    - {json.dumps(ask)}")
    return lines


def reviewer_prompt(repo, agent, owned, prior_issues, fix_diff_path="", open_asks=(), brief="", test_strategy="",
                    no_code_rulings=(), ruled_out=()):
    # The fix diff goes in a file the reviewer reads: inlined, a large diff runs the call past its prompt limit.
    lines = review_scope_lines(repo, owned, prior_issues, open_asks)
    lines.append("Your scope is the owned files listed under Review scope (this round).")
    if ruled_out:
        lines.append(RULED_OUT_REVIEWER_RULE + ", ".join(sorted(ruled_out)))
    lines.append(CLASS_TAG_RULE)
    if fix_diff_path:
        lines.append("Round-one fix diff (what the coder changed since the first review; read it, and review only "
                     "the owned files under Review scope (this round)): " + fix_diff_path)
    if agent == "test-reviewer":
        lines.append("Source under test: the diff's non-test files.")
        if test_strategy:
            lines.append("The plan's test strategy binds every phase. File a fix for each changed source the diff "
                         "leaves without the tests it asks for:\n" + test_strategy)
    if agent == "smell-reviewer":
        lines.append("Bound: the round-one fix diff." if fix_diff_path else "Bound: the diff under first review.")
    if no_code_rulings:
        lines.append(NO_CODE_REVIEW_RULE)
        lines += [f"  - {script_utils.one_line(text, ISSUE_CHARS)}" for text in no_code_rulings]
    if brief:
        lines.append(brief)
    return "\n".join(lines)


def listed_texts(texts, full_file, noun):
    """The lines that list `texts` in the coder prompt: the first MAX_LISTED_ISSUES, numbered, each cut to
    ISSUE_CHARS on one line. When anything was cut, the numbered full texts go to `full_file`, and the lines name
    it."""
    listed = texts[:MAX_LISTED_ISSUES]
    collapsed = [script_utils.one_line(text, None) for text in listed]
    shown = [text[:ISSUE_CHARS] for text in collapsed]
    lines = [f"{index}. {text}" for index, text in enumerate(shown, 1)]
    overflow = len(texts) > MAX_LISTED_ISSUES
    too_long = any(len(text) > ISSUE_CHARS for text in collapsed)
    if not (overflow or too_long):
        return lines

    full_file.parent.mkdir(parents=True, exist_ok=True)
    full_texts = [f"{index}. {text}" for index, text in enumerate(texts, 1)]
    script_utils.write_text_atomically(full_file, "\n\n".join(full_texts) + "\n")
    if overflow:
        lines.append(f"{noun.capitalize()}s {MAX_LISTED_ISSUES + 1} to {len(texts)} are only in {full_file}.")
    lines.append(f"Full text of every {noun}, in the same numbers: {full_file}. Read it before you fix.")
    return lines


def path_list(paths, list_file, in_scope=()):
    """The paths as one comma-separated line. A list over MAX_LISTED_PATHS is folded by directory, and the line
    names `list_file`, which holds the full list. Paths that share a directory with a path of `in_scope` are never
    folded. When nothing fits even then, the line is cut to its first MAX_LISTED_PATHS entries and `and N more`,
    and those paths come first. A list of at most MAX_LISTED_PATHS is listed whole."""
    paths = list(paths)
    entries = path_summary.collapse_paths(paths, MAX_LISTED_PATHS, in_scope)
    if entries == paths:
        return ", ".join(paths)
    list_file.parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(list_file, "\n".join(paths) + "\n")
    return f"{', '.join(entries)} (every path is listed in {list_file})"


def coder_prompt(repo, findings, small_items, files, list_dir, gate_env=(), later_phase_files=(), guidance="",
                 held_files=(), no_code_numbers=(), named_tests=(), ruled_out_files=(), adopted_numbers=()):
    """The fix coder's brief. `list_dir` is the folder that takes the full issue texts, the full small-item texts
    and each path list the brief folds."""
    body = [f"Repo root: {repo}", "", FENCE, "", "## Issues", ""]
    body += listed_texts(findings, list_dir / "issues.txt", "issue")
    body += ["", "For each issue you skip, write one line in your report "
                 f"in the form `{SKIPPED_MARKER} <n>: <reason>`, "
                 "where n is the issue's number. When you stop on a PLAN-IMPACT, write that line for each issue "
                 "you left unapplied.", "", SCOPED_TESTS]
    if adopted_numbers:
        numbers = ", ".join(map(str, adopted_numbers))
        asking = "issue " + numbers + " asks" if len(adopted_numbers) == 1 else "issues " + numbers + " ask"
        body += ["", f"When the tree already holds the change that {asking} for, write "
                     f"`{ALREADY_APPLIED_MARKER} <n>: <file:line where it is>` "
                     f"for it instead of `{SKIPPED_MARKER} <n>`."]
    if no_code_numbers:
        body += ["", "## No code change", "", NO_CODE_CODER_RULE.format(numbers=", ".join(map(str, no_code_numbers)))]
    if small_items:
        body += ["", "## Small items", "", SMALL_ITEMS, "",
                 *listed_texts(small_items, list_dir / "small-items.txt", "small item")]
    if named_tests:
        body += ["", NAMED_TESTS_RULE + path_list(named_tests, list_dir / "named-tests.txt")]
    body += ["", "Files in scope: " + path_list(files, list_dir / "files-in-scope.txt")]
    body += ["", OUT_OF_SCOPE_RULE]
    if later_phase_files:
        body += ["", LATER_PHASE_RULE + path_list(sorted(later_phase_files), list_dir / "later-phase-files.txt", files)]
    if held_files:
        body += ["", HELD_FILES_RULE + path_list(sorted(held_files), list_dir / "held-files.txt", files)]
    if ruled_out_files:
        body += ["", RULED_OUT_CODER_RULE + path_list(sorted(ruled_out_files), list_dir / "ruled-out-files.txt", files)]
    if guidance:
        body += ["", GUIDANCE_RULE + guidance]
    gate_env_text = plan_format.gate_env_text(list(gate_env))
    if gate_env_text:
        body += ["", gate_env_text]
    return "\n".join(body)
