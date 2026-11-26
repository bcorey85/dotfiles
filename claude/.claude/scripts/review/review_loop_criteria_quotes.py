"""review_loop_criteria_quotes.py: a fix pass never removes text a criterion quotes from a file under review. Before the
pass the loop records each file's text and the quoted spans in it, with the labels of the criteria that quote each
span. After the pass, a span that is gone is put back where its line stands (the pass's other edits stay), and one ask
names the criterion, the file and the text. An accepted ask lets the removal stand; a rejected one keeps the
put-back and files no ask. With no plan on disk the guard does nothing; a criteria file that does not parse turns it
off for each pass that reads it, with one note per distinct error for the packet's tool_fault."""
import dataclasses
import pathlib
import typing

import hook_input
import plan_format
import script_utils
from finding_record import parse_finding
from review_loop_findings import ask_quoted_text
from review_loop_put_back import put_back_lines

AC_QUOTE_ASK_NOTE = ("[criterion] a fix pass removed text that a criterion quotes (the text quoted after) and no "
                     "accepted ask removes it; the loop put it back")

AC_QUOTE_FAULTS = []
"""Notes for the packet's tool_fault: the guard was off for a pass, with the reason; one note per distinct error."""


class AcQuoteSnapshot(typing.NamedTuple):
    """The text of each file that holds quoted criterion text before a coder pass (`texts`, {path: text}), and the
    quoted spans of each (`spans`, {path: {span: [criterion labels]}})."""

    texts: dict
    spans: dict


EMPTY_AC_QUOTES = AcQuoteSnapshot({}, {})


def never_replace(_line):
    """The `may_replace` callback that accepts no stretch line. In a rewrite that changes the line count, no line the
    pass wrote is replaced. A rewrite with the same line count still gets the lost line back at its own offset (see
    `in_place`)."""
    return False


def remove_text_change(path, span):
    """The change an ask carries for the quoted `span` of `path`; an accepted ask sends it to the coder."""
    return f"remove the text {ask_quoted_text(span)!r} from {path}"


class AcQuoteRuns:
    """The LoopRun methods that keep a fix pass from removing text a criterion quotes."""

    def ac_quote_snapshot(self, files_in_scope):
        """An AcQuoteSnapshot of the files in scope (outside the plan's folder, not held) that hold a quoted span of
        the plan's criteria. With no plan on disk it is EMPTY_AC_QUOTES. A criteria file that does not parse turns
        the guard off for this pass (the file is read again before the next): a note naming the file goes to
        AC_QUOTE_FAULTS, once per distinct error, and the snapshot is empty."""
        plan_path = self.plan_path_on_disk()
        if plan_path is None:
            return EMPTY_AC_QUOTES
        try:
            quotes = plan_format.plan_ac_quotes(plan_path)
        except (plan_format.PlanFormatError, OSError) as error:
            # Fail-open on purpose: a criteria file the loop cannot read must not stop a review, so the guard is off
            # and the packet says why.
            note = f"the AC-quote guard was off for each pass that read this file: {error}"
            if note not in AC_QUOTE_FAULTS:
                AC_QUOTE_FAULTS.append(note)
            return EMPTY_AC_QUOTES
        if not quotes:
            return EMPTY_AC_QUOTES
        held = self.coder_held_files()
        paths = [path for path in plan_format.outside_plan_folder(files_in_scope, self.plan) if path not in held]
        texts, spans = {}, {}
        for path in paths:
            text = hook_input.read_file_text(pathlib.Path(self.repo) / path)
            if text is None:
                continue
            in_file = {span: labels for span, labels in quotes.items() if span in text}
            if not in_file:
                continue
            texts[path] = text
            spans[path] = in_file
        return AcQuoteSnapshot(texts, spans)

    def undo_ac_quote_pass(self, snapshot, findings, skip=()):
        """After a coder pass: puts back each quoted span of the snapshot's files that is gone, in place of the line the
        pass rewrote (its other edits stay), and files one ask for each span, naming the criterion, the file and the
        text. A span whose removal an accepted ask carries (its change text is in the findings' text) stays removed. A
        file the pass deleted is left alone, and so is a path in `skip`. Returns a ProtectedPutBack for each file
        changed."""
        accepted_text = script_utils.one_line(" ".join(finding.text for finding in findings), None)
        put_back = []
        for path, before_text in snapshot.texts.items():
            if path in skip:
                continue
            current = hook_input.read_file_text(pathlib.Path(self.repo) / path)
            if current is None:
                continue
            spans = [span for span in snapshot.spans[path]
                     if span not in current and remove_text_change(path, span) not in accepted_text]
            if not spans:
                continue
            first_lines = script_utils.first_lines_holding(before_text, spans)
            numbers = sorted(set(first_lines.values()))
            put_back.append(put_back_lines(self.repo, path, before_text, current, numbers, whole_stretch=False,
                                           may_replace=never_replace, in_place=True))
            for span in spans:
                self.file_span_ask(path, span, snapshot.spans[path][span], first_lines[span])
        return put_back

    def file_span_ask(self, path, span, labels, line):
        """Files the ask for one put-back `span` of `path` (first at `line`): its change removes the text."""
        quoted = ask_quoted_text(span)
        change = remove_text_change(path, span)
        text = f"{AC_QUOTE_ASK_NOTE}. {', '.join(labels)} quotes {quoted!r} in {path}. Change: {change}"
        ask = parse_finding(text)
        ask = dataclasses.replace(ask, path=path, line=line)
        self.file_put_back_ask(ask)
