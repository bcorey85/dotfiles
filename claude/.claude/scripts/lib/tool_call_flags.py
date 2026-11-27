"""Reads of a tool call's `run_in_background` flag. Standard library only: PreToolUse gates import it on every call."""


def _flag_is(value, word):
    return isinstance(value, str) and value.strip().lower() == word


def runs_in_background(tool_input):
    """Whether a tool call's input asks for a background run: `run_in_background` is true, or the string "true"."""
    value = tool_input.get("run_in_background")
    if value is True:
        return True
    return _flag_is(value, "true")


def launches_background(name, tool_input):
    """Whether one tool call launches background work. Bash does when `run_in_background` is true; Agent does
    unless `run_in_background` is explicitly false (it runs in the background by default)."""
    if name == "Bash":
        return runs_in_background(tool_input)
    if name != "Agent":
        return False
    value = tool_input.get("run_in_background")
    explicit_foreground = value is False or _flag_is(value, "false")
    return not explicit_foreground
