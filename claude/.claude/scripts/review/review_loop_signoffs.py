"""review_loop_signoffs.py: sign-off lines of a decision log are never edited by a coder. A finding on one, or one
that objects to a recorded ruling, goes to the packet's asks instead of a coder; a user- or session-ruled one goes to
the packet's caller steps, which name the file, the line and the ruled text. After each coder pass, a file whose
sign-off lines changed or vanished is put back and an ask names the entry and the reviewer's objection."""
import pathlib
import typing

import hook_input
import plan_format
import protected_lines
import review_loop_coder
import signoff_lines
from finding_record import parse_finding
from review_loop_held import held_path_in_repo
from review_loop_put_back import put_back_lines
from review_loop_ruled import CODER_GATE

SIGNOFF_ASK_NOTE = "[sign-off] a recorded ruling that no coder edits; the caller routes it"
CALLER_STEP_NOTE = "[sign-off] a ruled change to a recorded ruling that no coder edits; the caller applies it. Ruled"
PUT_BACK_NOTE = "[sign-off] a coder pass changed or removed this recorded ruling; the loop put the file back"


def is_decision_log(path):
    """True for a decision log: `03-decisions.md`, or any file of a plan folder (the plan's `## Plan Deviations`
    section, an evidence file)."""
    return pathlib.PurePath(path).name == plan_format.DECISION_LOG_NAME or ("/" + plan_format.PLANS_DIR) in ("/" + path)


def recorded_signoff_lines(path, text):
    """The sign-off lines of the file `path` with text `text`, read only where a ruling is recorded."""
    return signoff_lines.signoff_lines(text, pathlib.PurePath(path).name)


def in_signoff_scope(path, text, line):
    """True when `line` of the file `path` is where a ruling is recorded. A finding with no line (0) names the file,
    so it is in scope when the file holds any sign-off line."""
    if line == 0:
        return bool(recorded_signoff_lines(path, text))
    lines = text.splitlines()
    return line - 1 in signoff_lines.signoff_scope_indexes(pathlib.PurePath(path).name, lines)


def signoff_entry_line(repo, path, line):
    """The `<path>:<line>` label of the sign-off entry a finding on `path` at `line` names: the line itself when it is
    a sign-off line or any other line the finding names, else the file's first sign-off line, else the bare path."""
    if line:
        return f"{path}:{line}"
    text = hook_input.read_file_text(pathlib.Path(repo) / path, errors="replace")
    numbers = [number for number, _text in recorded_signoff_lines(path, text)] if text is not None else []
    if numbers:
        return f"{path}:{numbers[0]}"
    return path


def finding_hits_signoff(repo, finding):
    """True when the finding is on a sign-off line of a decision log, or its text objects to a recorded ruling."""
    path = held_path_in_repo(finding.path, repo)
    if not path or not is_decision_log(path):
        return False
    text = hook_input.read_file_text(pathlib.Path(repo) / path, errors="replace")
    if text is None:
        return False
    if any(number == finding.line for number, _line in recorded_signoff_lines(path, text)):
        return True
    if not in_signoff_scope(path, text, finding.line):
        return False
    return bool(plan_format.SESSION_RULING_MARK.search(finding.text))


def signoff_ask(repo, finding):
    """The ask item for a finding a coder must not get."""
    path = held_path_in_repo(finding.path, repo)
    label = signoff_entry_line(repo, path, finding.line)
    return parse_finding(f"{label} {SIGNOFF_ASK_NOTE}. Reviewer's objection: {finding.text}")


def caller_step(repo, finding):
    """The step handed to the caller for a ruled finding on a sign-off line: the file, the line and the ruled text. The
    loop never edits the line, so the caller applies the ruled change."""
    path = held_path_in_repo(finding.path, repo)
    label = signoff_entry_line(repo, path, finding.line)
    return f"{label} {CALLER_STEP_NOTE}: {finding.text}"


class SignoffSnapshot(typing.NamedTuple):
    """The text and sign-off line texts of each file that held a sign-off line before a coder pass."""

    texts: dict
    lines: dict


def snapshot_signoffs(repo, extra_paths):
    """A SignoffSnapshot of the plan folders' markdown files and of `extra_paths` that are decision logs."""
    root = pathlib.Path(repo)
    paths = {path.relative_to(root).as_posix() for path in root.glob(f"{plan_format.PLANS_DIR}**/*.md")}
    for extra_path in extra_paths:
        repo_path = held_path_in_repo(extra_path, repo)
        if is_decision_log(repo_path):
            paths.add(repo_path)
    texts, lines = {}, {}
    for path in sorted(paths):
        text = hook_input.read_file_text(root / path)
        if text is None:
            continue
        entries = recorded_signoff_lines(path, text)
        if not entries:
            continue
        texts[path] = text
        lines[path] = entries
    return SignoffSnapshot(texts, lines)


def lost_lines(before_entries, after_text, path=""):
    """The (line number, text) entries of `before_entries` that `after_text` of the file `path` no longer holds,
    counting repeats."""
    return protected_lines.entries_missing(before_entries, recorded_signoff_lines(path, after_text or ""))


def objection_text(findings, path, repo):
    """The texts of the pass's findings that name `path`, joined; a note when none does."""
    named = [finding.text for finding in findings if held_path_in_repo(finding.path, repo) == path]
    return " | ".join(named) if named else "no finding of the pass named this file"


class SignoffRuns:
    """The LoopRun methods that keep sign-off lines out of a coder's hands."""

    def split_signoff_items(self, items):
        """Returns (kept, signoff): the items a coder may get, and those that hit a sign-off line, whose asks or caller
        steps are filed here so no later filter drops them."""
        kept, signoff = [], []
        for item in items:
            # An adopted change is the user's own ruling: no ask re-asks it.
            if item.text in self.adopted or not finding_hits_signoff(self.repo, item):
                kept.append(item)
                continue
            signoff.append(item)
            # A ruled finding is no new question: the caller applies it, so it files no ask and no coder gets it.
            if item.text in self.ruled_texts:
                self.add_caller_step(caller_step(self.repo, item))
                continue
            self.add_ask(CODER_GATE, signoff_ask(self.repo, item))
        return kept, signoff

    def add_caller_step(self, step):
        """Files `step` for the packet's caller steps once: a later round that sees the same finding adds no copy."""
        if step not in self.caller_steps:
            self.caller_steps.append(step)

    def without_put_back(self, call_name, result, put_back, findings):
        """The result with each put-back file's diff recomputed from its text before the pass to its restored text: a
        file the put-back returned to that text leaves `changed`, and one with a real fix left stays in it. The
        pass's findings that the put-back undid go to open_fixes and put_back_findings."""
        if not put_back:
            return result
        for entry in put_back:
            result = review_loop_coder.result_with_path_text(result, entry.path, entry.before_text,
                                                             entry.restored_text, self.out, call_name)
        undone = [finding for finding in findings if self.put_back_undid(finding, put_back)]
        self.put_back_findings += undone
        self.keep_open(undone)
        return result

    def put_back_undid(self, finding, put_back):
        """True when the put-back undid the fix of `finding`: its file went back to its text before the pass, or the
        line it cites is a sign-off or comment line that went back."""
        path = held_path_in_repo(finding.path, self.repo)
        for entry in put_back:
            if entry.path != path:
                continue
            return entry.unchanged or finding.line in entry.lost_numbers
        return False

    def not_put_back(self, items):
        """The items the sign-off or comment put-back did not restore: a restored finding is not fixed."""
        return [item for item in items if item not in self.put_back_findings]

    def undo_signoff_pass(self, snapshot, findings, skip):
        """After a coder pass: puts back the sign-off lines, in each snapshot file except those in `skip`, that changed
        or vanished, and files one ask per lost line. Other edits to the file stay. Returns a ProtectedPutBack for each
        file."""
        put_back = []
        for path, entries in snapshot.lines.items():
            if path in skip:
                continue
            current = hook_input.read_file_text(pathlib.Path(self.repo) / path)
            lost = lost_lines(entries, current, path)
            if not lost:
                continue
            # Only the lines the pass changed go back: a sign-off another session wrote into the file during the
            # pass stays.
            lost_numbers = [number for number, _text in lost]
            put_back.append(put_back_lines(self.repo, path, snapshot.texts[path], current or "", lost_numbers))
            objection = objection_text(findings, path, self.repo)
            for number, text in lost:
                ask = parse_finding(f"{path}:{number} {PUT_BACK_NOTE}. Line: {text.strip()!r}. "
                                    f"Reviewer's objection: {objection}")
                self.add_ask(CODER_GATE, ask)
        return put_back
