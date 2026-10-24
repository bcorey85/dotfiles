#!/usr/bin/env python3
"""PostToolUse hook on Agent: per-dispatch token telemetry.

Appends one line per completed subagent dispatch to AGENT_USAGE_FILE
(default ~/.claude/agent-usage.jsonl):
  {ts, repo, agent, model, desc, tokens, toolUses, durationMs, reportChars, noResult, respKeys}

The token fields probe several candidate paths because the Agent tool_response schema is not contractual;
respKeys is the self-diagnostic. reportChars and noResult are null on the async schema (no inline content).
Writes nothing while the metrics switch is off (CLAUDE_TOOLKIT_TELEMETRY=1).
Never emits hook output. Exits 0, except 5 on a payload that is not valid JSON or not an object, as the
bash original did through jq.
"""
import json
import os
import re
import sys
import time

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + "/lib"]
import hook_input
from hook_input import (
    JqError,
    bash_basename,
    current_directory,
    first_truthy,
    index,
    jq_type,
    parse_documents,
    raw_text,
    report_open_failure,
    truthy,
)

try:
    from telemetry_enabled import telemetry_enabled
except ImportError:
    def telemetry_enabled():
        return False

NO_RESULT = re.compile(
    "no results|not found|no matches|could not find|couldn.t find|nothing (found|to report)|no relevant|no such|"
    "unable to find|found no |no occurrences|does not (exist|appear)")
ASCII_LOWER = {ord(c): ord(c) + 32 for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}


def join_text(content):
    pieces = []
    for element in content:
        text = element.get("text") if isinstance(element, dict) else None
        if not truthy(text):
            text = ""
        if isinstance(text, (list, dict)):
            raise JqError(f"Cannot join with {jq_type(text)}")
        pieces.append(raw_text(text))
    return " ".join(pieces)


def usage_row(document, repo):
    response = index(document, "tool_response")
    responder = response if isinstance(response, dict) else {}
    tool_input = index(document, "tool_input")

    content = responder.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = join_text(content)
    else:
        text = None

    description = index(tool_input, "description")
    if not truthy(description):
        description = ""
    if isinstance(description, (str, list)):
        description = description[0:80]
    else:
        raise JqError(f"Cannot index {jq_type(description)} with object")

    usage = responder.get("usage")
    tokens = first_truthy(
        lambda: responder.get("totalTokens"),
        lambda: index(usage, "total_tokens"),
        lambda: responder.get("total_tokens"),
        lambda: index(usage, "output_tokens"),
        lambda: None)
    tool_uses = first_truthy(lambda: responder.get("totalToolUseCount"), lambda: responder.get("tool_uses"),
                             lambda: None)
    duration = first_truthy(lambda: responder.get("totalDurationMs"), lambda: responder.get("duration_ms"),
                            lambda: None)

    if isinstance(response, dict):
        response_keys = sorted(response.keys())
    elif isinstance(response, list):
        response_keys = list(range(len(response)))
    else:
        response_keys = jq_type(response)

    agent = first_truthy(lambda: index(tool_input, "subagent_type"), lambda: "general-purpose")
    model = first_truthy(lambda: index(tool_input, "model"), lambda: "inherit")

    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": repo,
        "agent": agent,
        "model": model,
        "desc": description,
        "tokens": tokens,
        "toolUses": tool_uses,
        "durationMs": duration,
        "reportChars": len(text) if isinstance(text, str) else None,
        "noResult": bool(NO_RESULT.search(text.translate(ASCII_LOWER))) if isinstance(text, str) else None,
        "respKeys": response_keys,
    }


def main():
    text = hook_input.read_stdin_text().rstrip("\n")
    newlines = text.count("\n")
    try:
        documents = parse_documents(text)
    except ValueError:
        sys.stderr.write(f"jq: error (at <stdin>:{(newlines + 1)}): parse error\n")
        return 5

    events = []
    for document in documents:
        try:
            events.append(raw_text(first_truthy(lambda d=document: index(d, "hook_event_name"), lambda: "")))
        except JqError as error:
            sys.stderr.write(f"jq: error (at <stdin>:{(newlines + 1)}): {error}\n")
            return 5
    event = "\n".join(events).rstrip("\n")
    if event != "PostToolUse":
        return 0

    if not telemetry_enabled():
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    repo = bash_basename(project_dir if project_dir else current_directory())
    out = os.environ.get("AGENT_USAGE_FILE") or os.path.join(os.environ.get("HOME", ""), ".claude",
                                                             "agent-usage.jsonl")
    try:
        handle = open(out, "a", encoding="utf-8", errors="replace")
    except OSError as error:
        report_open_failure(error, out)
        return 0
    with handle:
        for document in documents:
            try:
                row = usage_row(document, repo)
            except JqError:
                return 0
            encoded = json.dumps(row, separators=(",", ":"), ensure_ascii=False)
            handle.write(encoded.replace("\x7f", "\\u007f") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
