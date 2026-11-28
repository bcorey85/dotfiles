"""Plain-text helpers for gates that read a final message."""
import re

from script_utils import closed_fence_indexes

# A span in double quotes (straight or curly) or backticks on one line.
QUOTED_SPAN = re.compile(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`')


BLOCKQUOTE_LINE = re.compile(r"^\s*>")


def without_draft_blocks(text):
    """The text with closed fenced blocks (fence grammar: `script_utils.closed_fence_indexes`) and blockquote lines
    removed. A fence that is never closed stays, with the text after it: a stray fence hides nothing."""
    lines = text.split("\n")
    fenced = closed_fence_indexes(lines)
    kept_lines = []
    for index, line in enumerate(lines):
        if index in fenced or BLOCKQUOTE_LINE.match(line):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def without_quoted_spans(pattern, text):
    """The text with each quoted span removed whose inner text, stripped, the pattern finds. A pattern that must open
    the span anchors itself with `\\A`."""
    def drop_span(span):
        inner = span.group()[1:-1].strip()
        return "" if pattern.search(inner) else span.group()

    return QUOTED_SPAN.sub(drop_span, text)
