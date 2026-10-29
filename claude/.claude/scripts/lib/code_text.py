"""code_text.py: plain-text readers for source code held in a string, with no rule of any one script.

Toolkit scripts import it after putting scripts/lib on sys.path."""
import re

SP = " \t\n\r\f\v"


def top_level_positions(code, start=0):
    """(index, char) for each char of code from start that sits outside quotes at bracket depth 0, including the
    brackets that open at depth 0. Ends after the first close bracket with no open one, which it yields. A newline
    ends an unclosed quote."""
    depth = 0
    quote = None
    index = start
    while index < len(code):
        char = code[index]
        if quote:
            if char == "\\":
                index += 1
            elif char in (quote, "\n"):
                quote = None
        elif char in "'\"":
            quote = char
        elif char in "([{":
            if depth == 0:
                yield index, char
            depth += 1
        elif char in ")]}":
            if depth == 0:
                yield index, char
                return
            depth -= 1
        elif depth == 0:
            yield index, char
        index += 1


def receiver_text(text):
    """The receiver of a method call: text after the last top-level `=` of an assignment, and without a leading
    `with` or `return`."""
    cut = 0
    for index, char in top_level_positions(text):
        if char == "=" and text[index - 1:index] not in tuple("=!<>:") and text[index + 1:index + 2] != "=":
            cut = index + 1
    return re.sub(r"^\s*(?:with|return)\b", "", text[cut:])


def split_arguments(code, start):
    """The comma-separated parts of code from start to the close of the bracket open before it, or to the end of the
    line or the `;` at bracket depth 0. Quoted text is skipped."""
    parts = []
    part_start = start
    end = len(code)
    for index, char in top_level_positions(code, start):
        if char in ")]}\n;":
            end = index
            break
        if char == ",":
            parts.append(code[part_start:index])
            part_start = index + 1
    parts.append(code[part_start:end])
    return parts


def tuple_fields(source, position):
    """The element at `position` of each tuple in a list or tuple literal; an element that is no tuple, or text with
    no literal, stays whole."""
    source = source.replace("\n", " ")
    brackets = [at for at in (source.find("["), source.find("(")) if at != -1]
    if not brackets:
        return [source]
    fields = []
    for element in split_arguments(source, min(brackets) + 1):
        element = element.strip(SP)
        if not element or element[0] not in "([":
            fields.append(element)
            continue
        parts = split_arguments(element, 1)
        fields.append(parts[position] if position < len(parts) else element)
    return fields
