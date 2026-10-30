"""review_loop_prompts.py: the prompts the scripted review loop sends its reviewers and its coders."""
import json

import handback
import plan_format

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
    'correction is clear. Skip every other small item, and report each skip with its reason. A small '
    'item never widens the change: no rename, no restructure, no new abstraction.'
)

LATER_PHASE_RULE = (
    "Never edit these files: the plan gives them to a later phase. When an issue needs one of them, leave it "
    "unapplied and report it as a PLAN-IMPACT: "
)

NEW_CODE_RULE = (
    "The first review pass is over, so this pass closes the change and does not grow it. Add no new source file "
    "and no new public function outside test files. When an issue needs one, leave it unapplied and write one "
    "line in your report in the form `NEW CODE <n>: <the file or function it needs>`, where n is the issue "
    "number above. A [blocker] issue may add what it needs."
)

GUIDANCE_RULE = "Guidance from the main session. Follow it within the issues and the plan; it changes neither: "

CLASS_TAG_RULE = ("Tag each Fix, Ask and Nit item with its class in brackets, right after its file:line, or first when "
                  "it names none. One of: " + " ".join(f"[{name}]" for name in handback.CLASSES) + ".")


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


def reviewer_prompt(repo, agent, owned, prior_issues, fix_diff_path="", open_asks=(), brief=""):
    # The fix diff goes in a file the reviewer reads: inlined, a large diff runs the call past its prompt limit.
    lines = review_scope_lines(repo, owned, prior_issues, open_asks)
    lines.append("Your scope is the owned files listed under Review scope (this round).")
    lines.append(CLASS_TAG_RULE)
    if fix_diff_path:
        lines.append("Round-one fix diff (what the coder changed since the first review; read it, and review only "
                     "the owned files under Review scope (this round)): " + fix_diff_path)
    if agent == "test-reviewer":
        lines.append("Source under test: the diff's non-test files.")
    if agent == "smell-reviewer":
        lines.append("Bound: the round-one fix diff." if fix_diff_path else "Bound: the diff under first review.")
    if brief:
        lines.append(brief)
    return "\n".join(lines)


def coder_prompt(repo, findings, small_items, files, gate_env=(), later_phase_files=(), guidance="",
                 no_new_code=False):
    body = [f"Repo root: {repo}", "", FENCE, "", "## Issues", ""]
    body += [f"{index}. {finding}" for index, finding in enumerate(findings, 1)]
    body += ["", "For each issue you skip, write one line in your report in the form `SKIPPED <n>: <reason>`, "
                 "where n is the issue number above. When you stop on a PLAN-IMPACT, write that line for each issue "
                 "you left unapplied.", "", SCOPED_TESTS]
    if no_new_code:
        body += ["", NEW_CODE_RULE]
    if small_items:
        body += ["", "## Small items", "", SMALL_ITEMS, ""] + [f"- {item}" for item in small_items]
    body += ["", "Files in scope: " + ", ".join(files)]
    if later_phase_files:
        body += ["", LATER_PHASE_RULE + ", ".join(sorted(later_phase_files))]
    if guidance:
        body += ["", GUIDANCE_RULE + guidance]
    gate_env_text = plan_format.gate_env_text(list(gate_env))
    if gate_env_text:
        body += ["", gate_env_text]
    return "\n".join(body)
