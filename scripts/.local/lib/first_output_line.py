"""The first line of a text, for a one-line reason built from a command's output."""


def first_output_line(text):
    """The first line of the stripped text, or "no output" when the text is blank."""
    lines = text.strip().splitlines()
    return lines[0] if lines else "no output"
