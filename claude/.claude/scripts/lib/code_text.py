"""code_text.py: plain-text readers for source code held in a string, with no rule of any one script.

Toolkit scripts import it after putting scripts/lib on sys.path."""
import re

SP = " \t\n\r\f\v"


def top_level_positions(code, start=0):
    """(index, char) for each char of code from start that sits outside quotes at bracket depth 0, including the
    brackets that open at depth 0. Ends after the first close bracket with no open one, which it yields. A newline
    ends an unclosed quote and is yielded when it sits at depth 0."""
    depth = 0
    quote = None
    index = start
    while index < len(code):
        char = code[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
            elif char == "\n":
                quote = None
                if depth == 0:
                    yield index, char
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


def split_arguments(code, start, multiline=False):
    """The comma-separated parts of code from start to the close of the bracket open before it, or to the end of the
    line or the `;` at bracket depth 0; with multiline, a newline at depth 0 does not end the parts, so a call
    whose arguments sit on several lines is read whole. Quoted text is skipped."""
    parts = []
    part_start = start
    end = len(code)
    for index, char in top_level_positions(code, start):
        if char in ")]};" or (char == "\n" and not multiline):
            end = index
            break
        if char == ",":
            parts.append(code[part_start:index])
            part_start = index + 1
    parts.append(code[part_start:end])
    return parts


def statement_around(code, match):
    """(statement, its start index) for the `;`-separated part of the line that holds the regex match, extended
    through the close of any bracket the match opens, so a call split over several lines is one statement. The end is
    measured from the match, so a bracket opened earlier in the part does not hide its `;`."""
    line_start = code.rfind("\n", 0, match.start()) + 1
    statement_start = code.rfind(";", line_start, match.start()) + 1 or line_start
    statement_end = next((index for index, char in top_level_positions(code, match.start())
                          if char in ")]};\n"), len(code))
    return code[statement_start:statement_end], statement_start


STRING_LITERAL = re.compile(r"""(['"])((?:\\.|[^'"\\\n]){1,512})\1""")
INTERPOLATION = re.compile(r"\{([^{}]*)\}|\$(\w+)")
# The prefix letters of python (`f`, `r`, `b`, `u`) that belong to a string literal.
STRING_PREFIX = r"(?<![\w$])[rRbBuUfF]{1,2}"
PREFIXED_STRING_LITERAL = re.compile(r"(?:" + STRING_PREFIX + r")?" + STRING_LITERAL.pattern)
STRING_PREFIX_BEFORE_QUOTE = re.compile(STRING_PREFIX + r"""(?=['"])""")
IMPORT = re.compile(r"^[ \t]*(?:from\s+[\w.]+\s+)?import\s+([^\n#;]+)", re.M)


def interpolated_code(literal):
    return " ".join(braced or bare for braced, bare in INTERPOLATION.findall(literal.group(2)))


def code_outside_strings(text):
    """text with each string literal, and the prefix letters before it, cut to the code it interpolates
    (`{x}` or `$x` in any literal); a literal that interpolates nothing names no variable and is emptied."""
    return PREFIXED_STRING_LITERAL.sub(interpolated_code, text)


QUOTED_STRING = re.compile(r"""(\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')""")


def sub_outside_strings(pattern, replacement, text):
    """text with each match of the compiled regex pattern replaced (as `pattern.sub` does), except a match inside a
    string literal, which stays as written. A literal is a one-line quoted string or a triple-quoted string that
    spans lines."""
    pieces = QUOTED_STRING.split(text)
    # split puts the code at even indexes and the string literals it captured at odd ones.
    return "".join(piece if index % 2 else pattern.sub(replacement, piece) for index, piece in enumerate(pieces))


def imported_names(code):
    """The names a python `import` or `from ... import` line, or a JS `import ... from '...'` line, binds."""
    names = set()
    for found in IMPORT.finditer(code):
        imported = found.group(1).split(" from ")[0]
        for part in imported.strip(" ()").split(","):
            names.add(part.split(" as ")[-1].strip(" (){}").split(".")[0])
    return names


def without_comments(code):
    """code with each `#` comment cut from its line. A `#` starts a comment outside quotes, at the line's start or
    after whitespace or one of `,([{:;`, so perl's `$#x`, a JS `.#x` and a `#` inside a string stay.
    A `#` on a later line of a multi-line string is cut, since each line is read alone."""
    return "\n".join(line_without_comment(line) for line in code.split("\n"))


def line_without_comment(line):
    quote = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in SP + ",([{:;"):
            return line[:index]
        index += 1
    return line


def tuple_fields(source, position):
    """The element at `position` of each tuple in a list or tuple literal, or of each `key: value` pair in a dict
    literal; an element that is neither, or text with no literal, stays whole. A quote or bracket inside a comment
    cuts the literal short, so strip comments from source first."""
    source = source.replace("\n", " ")
    opening = next((index for index, char in top_level_positions(source) if char in "([{"), None)
    if opening is None:
        return [source]

    is_dict = source[opening] == "{"
    fields = []
    for element in split_arguments(source, opening + 1):
        element = element.strip(SP)
        if is_dict:
            parts = dict_entry(element)
        elif element[:1] in ("(", "["):
            parts = split_arguments(element, 1)
        else:
            parts = []
        fields.append(parts[position] if position < len(parts) else element)
    return fields


def dict_entry(element):
    """The key and the value of a `key: value` dict element, split at its first top-level colon; an empty list when
    it has none."""
    for index, char in top_level_positions(element):
        if char == ":":
            return [element[:index], element[index + 1:]]
    return []
