"""The words of code_step's asks route: the pre-set outcome, the asks-done arguments, the asks coder's
prompt and the prior issues it leaves for the next review."""
import os

from code_step_core import state_dir
from code_step_report import CODER_CHECKS_LINE, eng_spec_brief
from review_asks import ASK_OUTCOMES
from script_utils import ask_text

ASKS_DONE_USAGE = ("asks-done needs one outcome per ask: accepted, rejected or modified. Each modified ask needs the "
                   "user's change after it as `--change \"<text>\"`. `--by user` or `--by session` says who ruled. "
                   "`--also \"<text>\"` carries any other work the user named alongside the outcomes.")


def prior_issues(accepted_asks):
    issues = []
    for item, _outcome, change_text in accepted_asks:
        file_line = item.get("file_line", "")
        issue_text = ask_text(item)
        if change_text:
            issue_text += f" (user's change: {change_text})"
        issues.append({"issue": issue_text, "file": file_line.partition(":")[0]})
    return issues


def preset_ask_outcome(repo_dir):
    # A pre-answered outcome for every review ask, for runs with no user (claude -p, bench): env var or a file in the
    # state dir.
    word = os.environ.get("CODE_STEP_ASKS_OUTCOME", "").strip().lower()
    preset_file = state_dir(repo_dir) / "asks-outcome"
    if not word and preset_file.exists():
        word = preset_file.read_text().strip().lower()
    return word if word in ASK_OUTCOMES else None


def asks_coder_prompt(accepted_asks, also_text=""):
    lines = []
    if accepted_asks:
        lines += ["Apply these review asks. The user accepted them. Make the change each one names and nothing else.",
                  ""]
    for number, (item, outcome, change_text) in enumerate(accepted_asks, 1):
        location = item.get("file_line", "")
        lines.append(f"{number}. [{outcome}] {ask_text(item)}"
                     + (f" ({location})" if location else ""))
        if change_text:
            lines.append(f"   The user's change: {change_text}")
        elif item.get("change"):
            lines.append(f"   The proposed change: {item['change']}")
    if also_text:
        lines += ["", "Also do this, as the user instructed alongside the asks:", also_text]
    lines += [
        "",
        f"{CODER_CHECKS_LINE} {eng_spec_brief('an ask')}",
        "For each ask whose change the code already makes, so that it needs no edit, add one line to your report: "
        "`ALREADY-DONE: <ask number> — <file:line>`. For an ask that only asks you to run checks, when they pass "
        "with no edit, the line is `ALREADY-DONE: <ask number> — `<command>` -> exit 0`. Add that line for no "
        "other ask.",
    ]
    return "\n".join(lines)


def ruling_text(outcome, change_text):
    return f"{outcome} (the user's change: {change_text})" if change_text else outcome


def changed_ruling_indexes(old_rulings, new_rulings):
    # The positions of the asks whose outcome or change text differs. A ruling is {"outcomes": [...], "changes":
    # [...]} in the order of the asks.
    old_pairs = zip(old_rulings["outcomes"], old_rulings["changes"], strict=True)
    new_pairs = zip(new_rulings["outcomes"], new_rulings["changes"], strict=True)
    return [index for index, (old, new) in enumerate(zip(old_pairs, new_pairs, strict=True)) if old != new]


def accepted_asks_of(asks, outcomes, change_texts):
    # The [item, outcome, change text] rows of the asks the rulings did not reject.
    return [[item, outcome, change_text]
            for item, outcome, change_text in zip(asks, outcomes, change_texts, strict=False)
            if outcome != "rejected"]


def correction_coder_prompt(asks, old_rulings, new_rulings, changed_indexes, also_text="", old_also_text=""):
    lines = ["The user corrected the rulings while the asks coder worked. The phase coder's and the asks coder's "
             "changes are in the working tree."]
    if changed_indexes:
        lines += ["For each ask below, undo the work done for the old ruling where the new ruling is rejected or "
                  "modified, and make the new ruling's change. Change nothing else.", ""]
    for number, index in enumerate(changed_indexes, 1):
        item = asks[index]
        location = item.get("file_line", "")
        old_text = ruling_text(old_rulings["outcomes"][index], old_rulings["changes"][index])
        new_text = ruling_text(new_rulings["outcomes"][index], new_rulings["changes"][index])
        lines.append(f"{number}. {ask_text(item)}" + (f" ({location})" if location else ""))
        lines.append(f"   Old ruling: {old_text}")
        lines.append(f"   New ruling: {new_text}")
        if item.get("change"):
            lines.append(f"   The proposed change: {item['change']}")
    if also_text and old_also_text:
        lines += ["", "The user changed the instruction given alongside the asks.",
                  "Old instruction:", old_also_text, "New instruction:", also_text,
                  "Undo the old instruction's work where the new one drops it, and do the new instruction."]
    elif also_text:
        lines += ["", "Also do this, as the user instructed alongside the rulings:", also_text]
    elif old_also_text:
        lines += ["", "The user dropped the instruction given alongside the asks:", old_also_text,
                  "Undo the work done for it."]
    lines += ["", f"{CODER_CHECKS_LINE} {eng_spec_brief('an ask')}"]
    return "\n".join(lines)


def split_asks_done_args(args):
    # Outcome words in order, the text after each `--change` flag (one per modified ask, in order), and the text of
    # `--also` joined by blank lines ("" when none). A flag with no text after it makes the change texts None.
    outcomes = []
    change_texts = []
    also_texts = []
    position = 0
    while position < len(args):
        if args[position] in ("--change", "--also"):
            if position + 1 >= len(args):
                return outcomes, None, ""
            target = change_texts if args[position] == "--change" else also_texts
            target.append(args[position + 1])
            position += 2
            continue
        outcomes.append(args[position])
        position += 1
    return outcomes, change_texts, "\n\n".join(also_texts)
