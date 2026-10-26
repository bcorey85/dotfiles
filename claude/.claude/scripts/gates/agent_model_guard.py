#!/usr/bin/env python3
"""PreToolUse hook on Agent: guard Agent tool calls against silent Opus inheritance.

  1. CLAUDE_SKIP_HOOKS set to any non-empty value: exit 0.
  2. Non-Agent tools pass.
  3. A subagent_type with characters outside [A-Za-z0-9_-] is denied.
  4. A call-site model containing "opus" or "inherit" (case-insensitive) is denied, opus checked first.
  5. Any other explicit model passes.
  6. An empty model passes only when the agent file (CLAUDE_PROJECT_DIR first, then HOME) has a `model:` line.

Invalid JSON or a non-object payload exits 5, as the bash original did through jq.
"""
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
from hook_input import index, parse_documents, present

SUBAGENT_PATTERN = re.compile(r"[A-Za-z0-9_-]+\Z")


def jq_deny(reason):
    return hook_input.decision_line("deny", reason)


def bash_lower(text):
    """Case-fold like bash `nocasematch`: one character per character. Python lowers U+0130 to two characters,
    bash to `i`."""
    return "".join(character.lower()[:1] for character in text)


def write_hook_output(stdout_text, stderr_text=""):
    if stderr_text:
        sys.stderr.buffer.write(stderr_text.encode("utf-8", "replace"))
        sys.stderr.buffer.flush()
    if stdout_text:
        sys.stdout.buffer.write(stdout_text.encode("utf-8", "replace"))
        sys.stdout.buffer.flush()


def payload_field(documents, extract, newlines):
    """What `printf '%s' "$input" | jq -r <extract>` leaves in a shell variable, which cannot hold a NUL."""
    return hook_input.jq_output(documents, extract, newlines).replace("\x00", "")


def find_agent_file(subagent):
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        project_file = f"{project_dir}/.claude/agents/{subagent}.md"
        if os.path.isfile(project_file):
            return project_file
    home_file = "{}/.claude/agents/{}.md".format(os.environ.get("HOME", ""), subagent)
    if os.path.isfile(home_file):
        return home_file
    return ""


def has_model_line(agent_file):
    try:
        with open(agent_file, "rb") as handle:
            for line in handle:
                if line.startswith(b"model:"):
                    return True
    except OSError:
        return False
    return False


def decide(text):
    newlines = text.count("\n")
    try:
        documents = parse_documents(text)
    except ValueError:
        sys.stderr.write(f"jq: error (at <stdin>:{newlines}): parse error\n")
        return 5, "", ""

    tool_name = payload_field(documents, lambda d: present(index(d, "tool_name")), newlines)
    if tool_name != "Agent":
        return 0, "", ""

    model = payload_field(documents, lambda d: present(index(index(d, "tool_input"), "model")), newlines)
    subagent = payload_field(documents, lambda d: present(index(index(d, "tool_input"), "subagent_type")), newlines)

    if subagent and not SUBAGENT_PATTERN.match(subagent):
        reason = (f"Agent call to subagent_type='{subagent}' is invalid. subagent_type must contain only alphanumeric "
                  "characters, hyphens, and underscores.")
        return 0, jq_deny(reason), ""

    lowered = bash_lower(model)
    if "opus" in lowered:
        stderr_text = (
            "[agent-model-guard] BLOCKED: Agent call sets model containing 'opus' at the call site.\n"
            "Call-site Opus is forbidden. The only legitimate way to run a subagent on Opus\n"
            "is a 'model: opus' line in the agent file's own frontmatter.\n"
            "Use 'haiku' (read-only/lookup) or 'sonnet' (fan-out implementation) at the call site.\n")
        reason = ("Agent call sets model containing 'opus' at the call site. Call-site Opus is forbidden "
                  "— add a 'model: opus' pin in the agent file frontmatter instead.")
        return 0, jq_deny(reason), stderr_text
    if "inherit" in lowered:
        stderr_text = (
            "[agent-model-guard] BLOCKED: Agent call sets model containing 'inherit' at the call site.\n"
            "Call-site 'inherit' resolves to the orchestrator's model at runtime.\n"
            "When the orchestrator is on Opus this silently fans out Opus subagents.\n"
            "Use 'haiku' (read-only/lookup) or 'sonnet' (fan-out implementation) at the call site.\n")
        reason = ("Agent call sets model containing 'inherit' at the call site. 'inherit' resolves to the "
                  "orchestrator model at runtime, silently fanning out Opus subagents.")
        return 0, jq_deny(reason), stderr_text

    if model:
        return 0, "", ""

    agent_file = find_agent_file(subagent)
    if agent_file and has_model_line(agent_file):
        return 0, "", ""

    stderr_text = (
        f"[agent-model-guard] BLOCKED: Agent call to subagent_type='{subagent}' has no model pin.\n"
        "No 'model:' frontmatter was found in the agent file (or the agent file does not exist).\n"
        "Without a pin the subagent inherits the orchestrator's model — silently running Opus\n"
        "when dispatched from an Opus orchestrator.\n"
        "Either:\n"
        "  - Add 'model: <opus|sonnet|haiku>' to the agent file's frontmatter, OR\n"
        "  - Pass an explicit model at the call site:\n"
        "      model: \"haiku\"  - read-only / lookup work\n"
        "      model: \"sonnet\" - fan-out implementation or analysis\n")
    reason = (f"Agent call to subagent_type='{subagent}' has no model pin. No 'model:' frontmatter found in the agent "
              "file (or the file does not exist). Add a 'model:' line to the agent frontmatter or pass an "
              "explicit model at the call site.")
    return 0, jq_deny(reason), stderr_text


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    text = hook_input.read_stdin_text().rstrip("\n")
    code, stdout_text, stderr_text = decide(text)
    write_hook_output(stdout_text, stderr_text)
    return code


if __name__ == "__main__":
    hook_input.run_gate(main)
