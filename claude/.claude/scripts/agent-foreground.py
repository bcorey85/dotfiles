#!/usr/bin/env python3
"""PreToolUse hook on Agent: inside a subagent, force run_in_background:false on every Agent dispatch.

Port of agent-foreground.sh. A nested caller is a payload carrying agent_id or agent_type. For those the hook
answers allow plus updatedInput = the call's tool_input plus run_in_background:false. Top-level dispatches are
untouched. CLAUDE_SKIP_HOOKS set to any non-empty value exits 0. Never blocks: any failure exits 0 with no output.
"""
import json
import os
import sys

from hook_input import JqError, parse_documents, present, raw_text


def top_level(document, key):
    if document is None:
        return None
    if isinstance(document, dict):
        return document.get(key)
    raise JqError(key)


def field(documents, extract):
    pieces = [raw_text(extract(document)) for document in documents]
    return "\n".join(pieces).rstrip("\n")


def answer(text):
    documents = parse_documents(text)
    if field(documents, lambda d: present(top_level(d, "tool_name"))) != "Agent":
        return ""

    caller = field(documents, lambda d: present(top_level(d, "agent_id"), present(top_level(d, "agent_type"))))
    if caller == "":
        return ""

    # jq -c over every document: the only output is for documents that carry a tool_input object or null.
    lines = []
    for document in documents:
        tool_input = top_level(document, "tool_input")
        if tool_input is None:
            merged = {}
        elif isinstance(tool_input, dict):
            merged = dict(tool_input)
        else:
            raise JqError("tool_input")
        merged["run_in_background"] = False
        encoded = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                                     "updatedInput": merged}},
                             separators=(",", ":"), ensure_ascii=False)
        lines.append(encoded.replace("\x7f", "\\u007f") + "\n")
    return "".join(lines)


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    try:
        text = sys.stdin.buffer.read().decode("utf-8", "replace").rstrip("\n")
        output = answer(text)
    except Exception:
        return 0
    if output:
        sys.stdout.buffer.write(output.encode("utf-8", "replace"))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
