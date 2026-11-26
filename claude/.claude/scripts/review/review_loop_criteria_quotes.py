"""review_loop_criteria_quotes.py: the snapshot of the criterion-quoted text that a fix pass must not remove. It holds
each file's text before the pass and the quoted spans in it, with the labels of the criteria that quote each span."""
import typing


class AcQuoteSnapshot(typing.NamedTuple):
    """The text of each file that holds quoted criterion text before a coder pass (`texts`, {path: text}), and the
    quoted spans of each (`spans`, {path: {span: [criterion labels]}})."""

    texts: dict
    spans: dict


EMPTY_AC_QUOTES = AcQuoteSnapshot({}, {})
