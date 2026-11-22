"""review_loop_comment_removal.py: a fix pass never removes a code comment on its own. After each coder pass, a comment
line that is gone from a file and that no finding names is put back, and an ask carries the removal for the user. A
finding names a comment when it cites its line, or a line in the same changed stretch or the same run of comment
lines."""
import pathlib
import typing

import hook_input
import protected_lines
import script_utils
import source_text
from finding_record import parse_finding
from review_loop_findings import inert_change_marks
from review_loop_held import held_path_in_repo
from review_loop_put_back import put_back_lines
from review_loop_ruled import CODER_GATE

COMMENT_ASK_NOTE = "[comment] a fix pass removed this code comment and no finding names it; the loop put it back"


class CommentSnapshot(typing.NamedTuple):
    """The text and comment lines (line number, stripped text) of each file with comments before a coder pass."""

    texts: dict
    lines: dict


def snapshot_comments(repo, paths):
    """A CommentSnapshot of the files in `paths` that hold comment lines."""
    texts, lines = {}, {}
    for path in dict.fromkeys(paths):
        text = hook_input.read_file_text(pathlib.Path(repo) / path)
        if text is None:
            continue
        entries = source_text.file_comment_entries(path, text)
        if not entries:
            continue
        texts[path] = text
        lines[path] = entries
    return CommentSnapshot(texts, lines)


def named_locations(findings, repo):
    """The (repo-relative path, line) pairs the findings name, each part of a merged finding included."""
    locations = set()
    for finding in findings:
        for part in finding.each_part:
            locations.add((held_path_in_repo(part.path, repo), part.line))
    return locations


def quoted_comment(text):
    """The comment `text` as an ask quotes it: on one line, with any `change:` marker made inert. An accepted ask's text
    is built the same way, so the two match."""
    return inert_change_marks(script_utils.one_line(text, None))


def delete_change_text(path, text):
    """The change an ask carries for the comment line `text` of `path`; an accepted ask sends it to the coder."""
    return f"delete the comment line {quoted_comment(text)!r} from {path}"


def unnamed_comments(path, removed, spans, named, accepted_text):
    """The (number, text) entries of `removed` that no finding names: not by line, by span, or by an accepted ask."""
    named_lines = {line for named_path, line in named if named_path == path and line}
    accepted_one_line = script_utils.one_line(accepted_text, None)
    unnamed = []
    for number, text in removed:
        if protected_lines.in_span_with(number, spans, named_lines):
            continue
        if delete_change_text(path, text) in accepted_one_line:
            continue
        unnamed.append((number, text))
    return unnamed


class CommentRemovalRuns:
    """The LoopRun method that keeps a fix pass from removing comments no finding names."""

    def undo_protected_edits(self, signoffs, comments, findings):
        """After a coder pass: puts back the sign-off lines (see `undo_signoff_pass`) and the comment lines the pass
        removed. Returns the ProtectedPutBack of each file."""
        held = self.coder_held_files()
        put_back = self.undo_signoff_pass(signoffs, findings, held)
        return put_back + self.undo_comment_pass(comments, findings, held)

    def undo_comment_pass(self, snapshot, findings, skip=()):
        """After a coder pass: puts back each comment line of the snapshot's files that is gone and that no finding
        names (a line the pass rewrote counts as gone), and files one ask per line. A file the pass deleted is left
        alone, and so is a path in `skip` (a file another session holds). Other edits to the file stay. Returns a
        ProtectedPutBack for each file changed."""
        named = named_locations(findings, self.repo)
        accepted_text = " ".join(finding.text for finding in findings)
        put_back = []
        for path, entries in snapshot.lines.items():
            if path in skip:
                continue
            current = hook_input.read_file_text(pathlib.Path(self.repo) / path)
            if current is None:
                continue
            current_entries = source_text.file_comment_entries(path, current)
            removed = protected_lines.entries_missing(entries, current_entries)
            spans = protected_lines.changed_stretches(snapshot.texts[path], current)
            spans += protected_lines.consecutive_runs(entries)
            unnamed = unnamed_comments(path, removed, spans, named, accepted_text)
            if not unnamed:
                continue
            numbers = [number for number, _text in unnamed]
            # Only a comment line can stand in for a lost comment: a line of code the pass wrote is never replaced.
            comment_texts = {text for _number, text in current_entries}
            put_back.append(put_back_lines(self.repo, path, snapshot.texts[path], current, numbers,
                                           whole_stretch=False,
                                           may_replace=lambda line, texts=comment_texts: line.strip() in texts))
            for number, text in unnamed:
                ask_text = (f"{path}:{number} {COMMENT_ASK_NOTE}. Line: {quoted_comment(text)!r}. "
                            f"Change: {delete_change_text(path, text)}")
                self.add_ask(CODER_GATE, parse_finding(ask_text))
        return put_back
