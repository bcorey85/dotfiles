#!/usr/bin/env python3
"""PostToolUse hook: after three main-session responses in a row that each made one read, tell the model to batch.

Reads the hook input on stdin and the last 512 KB of the transcript. Keeps no state: it fires when the run of
single-read responses, the running call's response included, is exactly 3, so it fires once per run. Any error
exits 0 with no output.
"""
import json
import os
import re
import sys

TAIL = 512 * 1024
RUN = 3
TEXT = ("Your last three responses each made one read. If you already know other files or searches you need, "
        "request them all in your next response as parallel tool calls, or chain them in one Bash command. "
        "Do not add reads you do not need.")
READ_TOOLS = {"Read", "Grep", "Glob"}
READ_PROGRAMS = {"grep", "rg", "sed", "cat", "head", "tail", "ls", "find", "wc", "awk", "jq"}
GIT_READS = {"show", "log", "diff", "grep", "blame"}
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
STEP = re.compile(r";|&&|\|\||\n")
ASSIGN = re.compile(r"\w+=\S*")


def program(command):
    """(program, rest of its words) of a Bash command's first step that is not a cd, past variable assignments."""
    for step in STEP.split(QUOTED.sub("_", command)):
        words = step.split("|")[0].split()
        while words and ASSIGN.fullmatch(words[0]):
            words = words[1:]
        if words and words[0] != "cd":
            return os.path.basename(words[0]), words[1:]
    return "", []


def is_read(name, tool_input):
    if name in READ_TOOLS:
        return True
    if name != "Bash" or not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        return False
    prog, rest = program(tool_input["command"])
    if prog == "git":
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
        return bool(rest) and rest[0] in GIT_READS
    return prog in READ_PROGRAMS


def tail_records(path):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL))
        data = f.read()
    lines = data.split(b"\n")
    if size > TAIL:
        lines = lines[1:]                   # the first line is cut
    return [json.loads(x) for x in lines if x.strip()]


def responses(records):
    """The main session's turns in order: a list of tool calls (name, input, id) per assistant response, grouped by
    message id, since each parallel call is its own record; None for a human prompt, which ends any run."""
    out, at = [], {}
    for d in records:
        if d.get("isSidechain"):
            continue
        m = d.get("message") or {}
        if d.get("type") == "assistant":
            key = m.get("id") or d.get("uuid")
            if key not in at:
                at[key] = len(out)
                out.append([])
            out[at[key]] += [(b.get("name"), b.get("input"), b.get("id")) for b in m.get("content") or []
                             if isinstance(b, dict) and b.get("type") == "tool_use"]
        elif d.get("type") == "user" and not d.get("isMeta"):
            c = m.get("content")
            if isinstance(c, str) or (isinstance(c, list) and not any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in c)):
                out.append(None)
    return out


def run_length(turns, current):
    """Single-read responses in a row, ending at the response that holds the running call. The transcript can lag,
    so a call it does not hold yet is taken as a new response of its own."""
    name, tool_input, use_id = current
    end = next((i for i in range(len(turns) - 1, -1, -1) if turns[i] and any(c[2] == use_id for c in turns[i])), None)
    turns = turns[:end + 1] if end is not None else turns + [[current]]
    n = 0
    for t in reversed(turns):               # a human prompt is None, and a response with no call is empty
        if not t or len(t) != 1 or not is_read(t[0][0], t[0][1]):
            break
        n += 1
    return n


def decide(payload):
    """The additionalContext to emit, or None."""
    if not isinstance(payload, dict) or payload.get("agent_id") or payload.get("hook_event_name") != "PostToolUse":
        return None
    current = (payload.get("tool_name"), payload.get("tool_input"), payload.get("tool_use_id"))
    if not is_read(current[0], current[1]):
        return None
    return TEXT if run_length(responses(tail_records(payload["transcript_path"])), current) == RUN else None


def main():
    try:
        text = decide(json.loads(sys.stdin.read()))
        if text:
            sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
