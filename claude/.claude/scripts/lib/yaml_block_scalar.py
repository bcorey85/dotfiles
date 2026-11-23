"""yaml_block_scalar.py: the text of a YAML block scalar (`|` literal or `>` folded) read from lines."""
import re

# The header of a block scalar: literal `|` or folded `>`, then `-` when the last line break is cut, or `+`, which
# is read like no mark.
BLOCK_HEADER = re.compile(r"^(?P<style>[|>])(?P<chomp>[+-]?)$")


def block_scalar_text(lines, index, key_column, header):
    """The text of the block scalar whose key stands at column `key_column` on `lines[index]`; `header` is the
    BLOCK_HEADER match of its value. The body is the lines after `lines[index]` that stand right of the key. The first
    body line sets the block's indent; a line indented further keeps the extra spaces, as in YAML. The text keeps
    the last line break unless the header ends in `-`; a `+` header keeps one line break, not the blank lines after
    the body. "" when the body holds no line."""
    body = []
    block_indent = None
    for line in lines[index + 1:]:
        line_indent = len(line) - len(line.lstrip(" "))
        if not line.strip():
            body.append("")
            continue
        if line_indent <= key_column:
            break
        if block_indent is None:
            block_indent = line_indent
        body.append(line[block_indent:].rstrip())
    while body and not body[-1]:
        body.pop()
    if not body:
        return ""

    text = "\n".join(body) if header.group("style") == "|" else fold_lines(body)
    last_break = "" if header.group("chomp") == "-" else "\n"
    return text + last_break


def fold_lines(body):
    """The text of a folded (`>`) block scalar's lines: neighbouring lines join with one space, and each blank line
    between two lines stays one line break, as YAML folds them. A line indented further than the block keeps the
    line break on each side of it."""
    text = ""
    blank_lines = 0
    previous_line = ""
    for line in body:
        if not line:
            blank_lines += 1
            continue
        kept_break = 1 if text and " " in (line[0], previous_line[0]) else 0
        if blank_lines or kept_break:
            text += "\n" * (blank_lines + kept_break)
        elif text:
            text += " "
        text += line
        blank_lines = 0
        previous_line = line
    return text
