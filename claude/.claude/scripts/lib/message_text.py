"""Plain-text helpers for gates that read a final message."""
import re

# A span in double quotes (straight or curly) or backticks on one line.
QUOTED_SPAN = re.compile(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`')


def without_quoted_spans(pattern, text):
    """The text with each quoted span removed whose inner text, stripped, the pattern finds. A pattern that must open
    the span anchors itself with `\\A`."""
    def drop_span(span):
        inner = span.group()[1:-1].strip()
        return "" if pattern.search(inner) else span.group()

    return QUOTED_SPAN.sub(drop_span, text)
