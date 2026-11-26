"""review_loop_comment_removal.py: a fix pass never removes a code comment on its own. After each coder pass, a comment
line that is gone from a file and that no finding names is put back, and an ask carries the removal for the user. A
finding names a comment when it cites its line, or a line in the same changed stretch or the same run of comment
lines, or when it names the file and quotes the comment's text inside backticks or quote marks (marker dropped,
whitespace collapsed, the whole quoted span equal to the comment's text). A comment line reworded in place is no
removal. A restored block files one ask, unless the session rejected an ask that quotes the same block of the same
file (any line) or an ask for the same quoted block of the same file is already filed."""
import dataclasses
import pathlib
import typing

import hook_input
import protected_lines
import script_utils
import source_text
from finding_record import parse_finding
from review_asks import ask_question
from review_loop_findings import REJECTED_ASK_REASON, inert_change_marks
from review_loop_held import held_path_in_repo
from review_loop_put_back import put_back_lines
from review_loop_ruled import CODER_GATE

COMMENT_ASK_NOTE = ("[comment] a fix pass removed this code comment (the lines quoted after) and no finding names it; "
                    "the loop put it back")


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


def comment_block_texts(entries):
    """The texts of the (number, text) comment `entries` of one block."""
    return [text for _number, text in entries]


def delete_block_change_text(path, texts):
    """The change an ask carries for the comment block whose lines are `texts`; a one-line block reads as
    `delete_change_text`."""
    if len(texts) == 1:
        return delete_change_text(path, texts[0])
    block_text = "\n".join(texts)
    quoted = quoted_comment(block_text)
    return f"delete the comment block {quoted!r} from {path}"


def quoted_by_finding(path, text, quotes):
    """Whether a finding of `path` quotes the comment `text`: the whole text of a backtick or quote span of the
    finding's whitespace-normalized text is the comment's body, so a short comment is not named by a longer quote."""
    body = source_text.comment_body(text)
    if not body:
        return False
    for quote_path, finding_text in quotes:
        if quote_path != path:
            continue
        spans = script_utils.FINDING_QUOTED_SPAN.findall(finding_text)
        for span in spans:
            quote = span[1:-1]
            # A quote that left out the marker is compared as it stands: `comment_body` would strip a `*` or `#`
            # that belongs to the comment's own text.
            if quote == body or source_text.comment_body(quote) == body:
                return True
    return False


def finding_quotes(findings, repo):
    """The (repo-relative path, whitespace-normalized text) pairs of the findings, each part of a merged one."""
    return [(held_path_in_repo(part.path, repo), script_utils.one_line(part.text, None))
            for finding in findings for part in finding.each_part]


def unnamed_removals(path, removed, spans, named, quotes):
    """The (number, text) entries of `removed` that no finding names: not by line, not by a span that holds one and not
    by quoting the comment's text in a finding of the file."""
    named_lines = {line for named_path, line in named if named_path == path and line}
    # A line a finding quotes names its span the way a line number does.
    quoted_lines = {number for number, text in removed if quoted_by_finding(path, text, quotes)}
    named_lines |= quoted_lines
    return [(number, text) for number, text in removed
            if not protected_lines.in_span_with(number, spans, named_lines)]


def without_reworded(removed, entries, current_entries, rewrites):
    """`removed` without the entries lying in a rewritten stretch that still holds as many comment lines as it did
    before: a comment line reworded in place is no removal."""
    reworded_ranges = []
    for rewrite in rewrites:
        before_first, before_last = rewrite.before
        after_first, after_last = rewrite.after
        comments_before = [number for number, _text in entries if before_first <= number <= before_last]
        comments_after = [number for number, _text in current_entries if after_first <= number <= after_last]
        if len(comments_after) >= len(comments_before):
            reworded_ranges.append(rewrite.before)
    return [(number, text) for number, text in removed
            if not any(first <= number <= last for first, last in reworded_ranges)]


def without_accepted_blocks(path, unnamed, accepted_text):
    """`unnamed` without the blocks an accepted ask already deletes, matched by the block's change text wherever the
    line has moved."""
    accepted_one_line = script_utils.one_line(accepted_text, None)
    kept = []
    for block in protected_lines.consecutive_entry_runs(unnamed):
        kept += without_accepted_runs(path, block, accepted_one_line)
    return kept


def without_accepted_runs(path, block, accepted_one_line):
    """The entries of `block` left after each contiguous run an accepted ask deletes is cut out, longest run first. A
    block that grew since the ask still loses the run the ask names."""
    for length in range(len(block), 0, -1):
        for start in range(len(block) - length + 1):
            run = block[start:start + length]
            if delete_block_change_text(path, comment_block_texts(run)) not in accepted_one_line:
                continue
            before_run = without_accepted_runs(path, block[:start], accepted_one_line)
            after_run = without_accepted_runs(path, block[start + length:], accepted_one_line)
            return before_run + after_run
    return block


def restored_entries(unnamed, current_entries, restored_text, path):
    """The `unnamed` entries the put-back actually restored: in the restored text and not in the text before it."""
    restored_comments = source_text.file_comment_entries(path, restored_text)
    added = protected_lines.entries_missing(restored_comments, current_entries)
    not_restored = protected_lines.entries_missing(unnamed, added)
    return [entry for entry in unnamed if entry not in not_restored]


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
        names (a line the pass rewrote counts as gone, unless the rewrite kept as many comment lines as it replaced,
        which is left as it is), and files one ask for each block of comment lines it restored, unless the session
        rejected an ask that quotes the same block of the same file (a rejected ask keeps the put-back and files none)
        or an ask for the same quoted block of the same file is already filed. A file the pass deleted is left alone,
        and so is a path in `skip` (a file another session holds). Other edits to the file stay. Returns a
        ProtectedPutBack for each file changed."""
        named = named_locations(findings, self.repo)
        quotes = finding_quotes(findings, self.repo)
        accepted_text = " ".join(finding.text for finding in findings)
        put_back = []
        for path, entries in snapshot.lines.items():
            if path in skip:
                continue
            current = hook_input.read_file_text(pathlib.Path(self.repo) / path)
            if current is None:
                continue
            current_entries = source_text.file_comment_entries(path, current)
            spans = protected_lines.changed_stretches(snapshot.texts[path], current)
            removed = protected_lines.entries_missing_in_stretches(entries, current_entries, spans)
            spans += protected_lines.consecutive_runs(entries)
            unnamed = unnamed_removals(path, removed, spans, named, quotes)
            rewrites = protected_lines.rewritten_stretches(snapshot.texts[path], current)
            unnamed = without_reworded(unnamed, entries, current_entries, rewrites)
            unnamed = without_accepted_blocks(path, unnamed, accepted_text)
            if not unnamed:
                continue
            numbers = [number for number, _text in unnamed]
            # Only a comment line can stand in for a lost comment: a line of code the pass wrote is never replaced.
            comment_texts = {text for _number, text in current_entries}
            entry = put_back_lines(self.repo, path, snapshot.texts[path], current, numbers,
                                   whole_stretch=False,
                                   may_replace=lambda line, texts=comment_texts: line.strip() in texts)
            put_back.append(entry)
            restored = restored_entries(unnamed, current_entries, entry.restored_text, path)
            self.file_block_asks(path, restored)
        return put_back

    def file_block_asks(self, path, restored):
        """Files one ask for each block of the `restored` comment entries of `path`, whose change deletes the block. A
        block whose ask the session rejected (same path and question, any line) files none: the rejection means the
        comment stays. A block whose ask is already filed (same path and question, whatever its line) files none."""
        for block in protected_lines.consecutive_entry_runs(restored):
            texts = comment_block_texts(block)
            quoted = quoted_comment("\n".join(texts))
            change = delete_block_change_text(path, texts)
            # The text names no line, so the ask's question is the same wherever the block sits; the location is set
            # from `path` and the block's first line.
            ask = parse_finding(f"{COMMENT_ASK_NOTE}. Lines of {path}: {quoted!r}. Change: {change}")
            ask = dataclasses.replace(ask, path=path, line=block[0][0])
            question = ask_question(ask)
            if any(ask_question(filed) == question for filed in self.asks):
                continue
            if self.rejected_block(ask):
                self.drop_asks([ask], REJECTED_ASK_REASON)
                continue
            self.add_ask(CODER_GATE, ask)

    def rejected_block(self, ask):
        """Whether the session rejected an ask for this exact block of this file: a stored `question` field equals
        the ask's, wherever the block sits (the question names the file). The title is no match: it folds case and
        punctuation, so it would also drop an ask for a block that differs in those only."""
        return ask_question(ask) in self.rejected_questions
