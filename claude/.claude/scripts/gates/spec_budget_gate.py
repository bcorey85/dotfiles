#!/usr/bin/env python3
"""PreToolUse hook on Write|Edit|MultiEdit|NotebookEdit: hard word budget on the eng-spec planning tree.

Two ceilings. RESIDENT is SKILL.md plus the single largest file in phases/ (what is in context during a run and has
to survive compaction). TOTAL is every guarded file at once (eng-spec, its spec-* agents, the _shared files it
consumes). An edit that grows past a ceiling is denied; growth only by displacement. Ceiling changes need the
user's explicit sign-off: never raise one to make an edit fit. CLAUDE_SKIP_HOOKS skips the gate. Any error allows.
"""
import contextlib
import json
import os
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input

RESIDENT_CEILING = 1500
TOTAL_CEILING = 8700

AGENT_FILES = ("spec-questions.md", "spec-leak-check.md", "spec-research.md", "spec-criteria.md",
               "goal-blind-researcher.md")
SHARED_FILES = ("design-decision-format.md", "plan-format.md", "closing-phases.md")
SHARED_PREFIX = "/skills/_shared/"


def guarded_target(file_path):
    """True when the edited file is one of the files the budget covers."""
    if "/skills/eng-spec/templates/" in file_path:
        return False
    if "/skills/eng-spec/" in file_path:
        return True
    if any(file_path.endswith("/agents/" + name) for name in AGENT_FILES):
        return True
    return any(file_path.endswith(SHARED_PREFIX + name) for name in SHARED_FILES)


def tree_base(file_path):
    base = file_path.rpartition("/skills/")[0] if "/skills/" in file_path else file_path
    if base == file_path:
        base = file_path.rpartition("/agents/")[0] if "/agents/" in file_path else file_path
    return None if base == file_path else base


def word_count(text):
    """Words in decoded text, split on Unicode whitespace like `wc -w` in a UTF-8 locale."""
    return len(text.split())


def read_text(path):
    return hook_input.read_file_text(path, "replace") or ""


def words_in_file(path):
    return word_count(read_text(path)) if os.path.isfile(path) else 0


def jq_string(value):
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value)


def edited_words(tool_input, key):
    """Words in the `key` strings of every edit, like the jq join over `.edits // [.tool_input]`."""
    edits = tool_input.get("edits")
    if edits is None or edits is False:
        edits = [tool_input]
    if not isinstance(edits, list):
        return 0
    pieces = []
    for edit in edits:
        if not isinstance(edit, dict):
            return 0
        value = edit.get(key)
        pieces.append("" if value is None or value is False else jq_string(value))
    return word_count(" ".join(pieces))


def eng_spec_files(base):
    """Regular files under skills/eng-spec outside any templates/ path, like `find -type f -not -path`."""
    top = base + "/skills/eng-spec"
    if os.path.islink(top) or not os.path.isdir(top):
        return []
    found = []
    for directory, _, names in os.walk(top):
        for name in names:
            path = os.path.join(directory, name)
            if "/templates/" in path or os.path.islink(path) or not os.path.isfile(path):
                continue
            found.append(path)
    return found


def phase_paths(base):
    """Names ending .md under skills/eng-spec/phases, like `find -name '*.md'`."""
    top = base + "/skills/eng-spec/phases"
    if os.path.islink(top) or not os.path.isdir(top):
        return []
    found = []
    for directory, directories, names in os.walk(top):
        for name in directories + names:
            if name.endswith(".md"):
                found.append(os.path.join(directory, name))
    return found


def deny(reason):
    line = ('{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",'
            f'"permissionDecisionReason":"{reason}"}}}}\n')
    sys.stdout.buffer.write(line.encode("utf-8", "surrogateescape"))
    sys.stdout.buffer.flush()


def check(raw):
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return
    payload = json.loads(raw)
    tool_input = hook_input.tool_input_of(payload)
    if tool_input is None:
        return
    file_path = hook_input.edited_file_path(tool_input)
    if not file_path or not guarded_target(file_path):
        return
    base = tree_base(file_path)
    if base is None:
        return

    tool = payload.get("tool_name")
    tool = tool if isinstance(tool, str) else ""
    old_words = words_in_file(file_path)
    if tool == "Write":
        content = tool_input.get("content")
        new_words = word_count("" if content is None or content is False else jq_string(content))
    elif tool in ("Edit", "MultiEdit"):
        new_words = old_words + edited_words(tool_input, "new_string") - edited_words(tool_input, "old_string")
    else:
        return

    def prospective(path):
        return new_words if path == file_path else words_in_file(path)

    guarded = "\n".join(eng_spec_files(base))
    for name in AGENT_FILES:
        extra = base + "/agents/" + name
        if os.path.exists(extra):
            guarded += "\n" + extra
    for name in SHARED_FILES:
        extra = base + SHARED_PREFIX + name
        if os.path.exists(extra):
            guarded += "\n" + extra
    # Unquoted `cat $GUARDED`: paths split on whitespace, files are concatenated before counting.
    total = word_count("".join(read_text(path) for path in guarded.split() if os.path.isfile(path)))
    new_total = total - old_words + new_words

    spine = prospective(base + "/skills/eng-spec/SKILL.md")
    phases = "\n".join(phase_paths(base))
    if "/skills/eng-spec/phases/" in file_path and file_path.endswith(".md"):
        phases += "\n" + file_path
    max_phase = 0
    for phase in phases.split():
        max_phase = max(max_phase, prospective(phase))
    resident = spine + max_phase

    if resident > RESIDENT_CEILING and new_words > old_words:
        deny(
            f"spec-budget-gate: this edit puts eng-spec's resident load at ~{resident} words (ceiling "
            f"{RESIDENT_CEILING}) — SKILL.md ({spine}) "
            f"plus its largest phase file ({max_phase}). That is what is actually in context during a run and what has "
            "to "
            f"survive compaction. Cut words from the spine or from that phase file in the same change, or move a "
            f"rule into the agent that is the only one who applies it. Splitting a phase file only helps if it is "
            f"a real phase boundary. Ask the user to raise RESIDENT_CEILING; never raise it yourself."
        )
        return

    if new_total > TOTAL_CEILING and new_total > total:
        deny(
            f"spec-budget-gate: this edit grows the planning tree to ~{new_total} words (ceiling {TOTAL_CEILING}, "
            f"currently {total}). The "
            f"planning system grows only by displacement — delete words elsewhere in the guarded set (eng-spec, "
            f"spec-* agents, its _shared files) in the same change, or ask the user to raise TOTAL_CEILING in "
            f"spec_budget_gate.py. Never raise it yourself."
        )


def main():
    with contextlib.suppress(Exception):
        check(hook_input.read_stdin_text())
    return 0


if __name__ == "__main__":
    hook_input.run_gate(main)
