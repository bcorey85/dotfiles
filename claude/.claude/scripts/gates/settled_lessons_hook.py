#!/usr/bin/env python3
"""PreToolUse hook on Write|Edit|MultiEdit: before the first edit of a toolkit component in a session, show the
component's settled results.

The edited path is resolved through symlinks; the part after `claude/.claude/` names the component: agents/<n>.md is
agent/<n>, skills/_shared/<n>.md is shared/<n>, skills/<n>/... is skill/<n>, and any other file is matched against the
`resource:` line of the component pages. The lessons are the `# Settled` section of
$AGENT_EVALS_DIR/components/<id>.md (default ~/agent-evals), up to the next `# ` heading. They go out as
additionalContext only, so every other gate still decides the edit. A missing folder, page or section exits 0 with no
output; any error is named on stderr and exits 0 (fail open). Each component is shown once per session; state lives in
~/.claude/state/settled-lessons/<session>/.
"""
import json
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils

TOOLKIT_MARKER = "claude/.claude/"
RESOURCE_LINE = re.compile(r'^resource:\s*"?([^"\n]+)"?\s*$', re.MULTILINE)
HEADER = "Settled results for {component}; do not retest or reverse these without new evidence:"


def toolkit_relative_path(file_path):
    """The part of the symlink-resolved path after `claude/.claude/`, or "" for a file outside the toolkit."""
    resolved = os.path.realpath(os.path.expanduser(file_path))
    _, marker, relative = resolved.partition(TOOLKIT_MARKER)
    return relative if marker else ""


def component_by_name(relative):
    """The component id of an agent, shared skill file or skill path, or "" for any other path."""
    parts = relative.split("/")
    if len(parts) == 2 and parts[0] == "agents" and parts[1].endswith(".md"):
        return "agent/" + parts[1][:-3]
    if len(parts) == 3 and parts[:2] == ["skills", "_shared"] and parts[2].endswith(".md"):
        return "shared/" + parts[2][:-3]
    if len(parts) >= 3 and parts[0] == "skills":
        return "skill/" + parts[1]
    return ""


def component_by_resource(relative, components_dir):
    """The id of the page whose `resource:` ends in the same part after `claude/.claude/`, or ""."""
    for directory, _, names in os.walk(components_dir):
        for name in sorted(names):
            if not name.endswith(".md") or name == "index.md":
                continue
            page_path = os.path.join(directory, name)
            text = hook_input.read_file_text(page_path, "replace")
            match = RESOURCE_LINE.search(text or "")
            if match and match.group(1).partition(TOOLKIT_MARKER)[2] == relative:
                return os.path.relpath(page_path, components_dir)[:-3]
    return ""


def settled_section(page_text):
    """The text of the `Settled` section, up to the next heading of its level or higher; "" when the page has none."""
    lines = page_text.splitlines()
    body_indexes = script_utils.heading_section_indexes(lines, "Settled")
    return "\n".join(lines[index] for index in body_indexes).strip()


def already_shown(session, component):
    """Record the component for the session; True when it was recorded before."""
    state_dir = os.path.join(os.environ["HOME"], ".claude", "state", "settled-lessons", session)
    os.makedirs(state_dir, exist_ok=True)
    hook_input.prune_old_state_files(os.path.dirname(state_dir))
    marker = script_utils.state_file_path(state_dir, component, ".seen")
    if marker.exists():
        return True
    marker.touch()
    return False


def main():
    payload = json.loads(hook_input.read_stdin_text() or "{}")
    tool_input = hook_input.tool_input_of(payload)
    file_path = hook_input.edited_file_path(tool_input) if tool_input else ""
    if not file_path:
        return 0
    relative = toolkit_relative_path(file_path)
    if not relative:
        return 0

    evals_dir = os.path.expanduser(os.environ.get("AGENT_EVALS_DIR") or "~/agent-evals")
    components_dir = os.path.join(evals_dir, "components")
    if not os.path.isdir(components_dir):
        return 0

    component = component_by_name(relative) or component_by_resource(relative, components_dir)
    if not component:
        return 0
    page_text = hook_input.read_file_text(os.path.join(components_dir, component + ".md"), "replace")
    section = settled_section(page_text or "")
    if not section:
        return 0

    session = payload.get("session_id") or "unknown"
    if already_shown(str(session), component):
        return 0

    context = HEADER.format(component=component) + "\n" + section
    output = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": context}}
    sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        # Fails open: the hook only adds context, so an error must not block the edit.
        hook_input.emit_stderr(f"{hook_input.hook_name()}: {error}\n")
        sys.exit(0)
