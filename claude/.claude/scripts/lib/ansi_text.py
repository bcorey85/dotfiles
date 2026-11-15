"""Plain-text helpers for terminal output."""
import re

# A CSI escape sequence: colour, bold and cursor codes such as `\x1b[1m` or `\x1b[32m`.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text):
    """The text with every ANSI CSI escape sequence removed."""
    return _ANSI_ESCAPE.sub("", text)
