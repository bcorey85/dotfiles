#!/usr/bin/env python3
"""review-loop-gate.py — deterministic checks on the review loop.

  SubagentStop (review-loop): blocks once, with every reason that holds, when
    - a fix coder ran after the last code-reviewer read — a fresh dispatch, or a SendMessage to a
      code-reviewer it dispatched. `no-review` in the loop prompt exempts this check only.
    - a coder step ran — a dispatch, or a SendMessage to a coder it dispatched — the loop prompt's
      `tests-run` is not a command with exit 0, and no check ran after the last coder step: a shell
      call that runs a project checker or redirects into the review-gate log.
      A second stop in a row passes (stop_hook_active), so a stuck loop cannot spin. The block
      reason reaches the loop as context and it keeps working. Register with matcher
      `review-loop`; the agent_type check below still guards an unscoped entry.
  PreToolUse (Agent): a review-loop dispatch whose prompt says `caller: code` must carry a
      `handoff:` line.

Hook JSON on stdin; on a violation, a decision JSON on stdout; exit 0 always. Any parse
failure passes (fail open) and says why on stderr: this gate adds a check, it must never
stop the loop on its own error.

Dry run for a saved transcript:  review-loop-gate.py --check <loop transcript.jsonl>
"""
import json
import os
import re
import sys

CODERS = re.compile(r"^(backend-|frontend-)?coder(-deep)?$")
REVIEWERS = re.compile(r"^code-reviewer(-deep)?$")
AGENT_ID = re.compile(r"agentId:\s*([A-Za-z0-9-]+)")
CALLER_CODE = re.compile(r"(?i)(?<![\w-])caller[`*]*\s*[:=]\s*[`\"']?code\b")
HANDOFF = re.compile(r"(?im)^[ \t]*handoff[ \t]*:")
NO_REVIEW = re.compile(r"(?<![\w-])no-review(?![\w-])")
TESTS_RUN = re.compile(r"(?im)^([ \t>*`-]*)tests[-_ ]run[`*]*[ \t]*:[ \t]*(.*)$")
EXIT_CODE = re.compile(r"\b(?:exit(?:ed)?(?:\s+with)?(?:\s*code)?|status)\s*[:=]?\s*(\d+)\b"
                       r"|(?:→|->|=>)\s*(\d+)\b(?!\s*[a-z])|\((\d+)\)", re.I)
GATE_LOG = re.compile(r"(?:>\s*|\btee\s+(?:-a\s+)?)\S*review-gate[\w.-]*\.log")
CHECKER = re.compile(r"(?:\A|[;&|(]\s*|\n\s*)(?:cd\s+\S+\s*&&\s*)?(?:[A-Za-z_]\w*=\S+\s+)*"
                     r"(?:(?:time|npx|bunx|uv\s+run|poetry\s+run|python3?\s+-m|bundle\s+exec)\s+)*"
                     r"(?:(?:npm|pnpm|yarn|bun)\s+(?:(?:-F|--filter|workspace)\s+\S+\s+)?(?:run\s+)?"
                     r"[\w:-]*(?:test|lint|typecheck|type-check|check|build)[\w:-]*"
                     r"|jest|vitest|pytest|tsc|vue-tsc|svelte-check|eslint|oxlint|ruff|mypy|pyright|golangci-lint"
                     r"|go\s+(?:test|vet)|cargo\s+(?:test|clippy|check)|make\s+[\w-]*(?:test|lint|check)[\w-]*"
                     r"|\S*quality-check|bats|shellcheck|rspec|phpunit|dotnet\s+test)(?![\w-])")

PASS_REASON = ("A fix coder ran after the last code-reviewer read of this loop, so its fix diff is unread. "
               "Run Step 5d now: dispatch one code-reviewer scoped to every unread fix diff, route its "
               "findings, then return the packet.")
GATE_REASON = ("A coder changed code in this loop, the handoff's tests-run is not a command with exit 0, and "
               "no check ran after the last coder step. Run the Step 6 execution gate now: the project's "
               "quality-check command once, redirected to /tmp/review-gate.log. Route any failure as Step 6 "
               "says, then return the packet.")
HANDOFF_REASON = ("A review-loop dispatch from /code carries no handoff block. Build it per "
                  "~/.claude/skills/_shared/handoff-block.md and dispatch again.")


def text_of(content):
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


def tests_passed(prompt):
    """True when the prompt's tests-run field reports exit codes and all of them are 0. A field with an empty first
    line takes the deeper lines under it."""
    m = TESTS_RUN.search(prompt or "")
    if not m:
        return False
    val, depth = m.group(2), len(m.group(1))
    if not val.strip():
        under = []
        for line in prompt[m.end():].split("\n")[1:]:
            if not line.strip() or len(line) - len(line.lstrip(" \t")) <= depth:
                break
            under.append(line)
        val = " ; ".join(under)
    codes = [int(a or b or c) for a, b, c in EXIT_CODE.findall(val)]
    return bool(codes) and not any(codes)


def scan(path):
    """(a coder ran after the last reviewer read, no check ran after the last coder step when one was owed,
    the loop prompt holds no-review)."""
    kinds, reviewer_ids, coder_ids = {}, set(), set()
    last_coder, last_step, last_read, last_check, prompt = -1, -1, -1, -1, None
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            rec = json.loads(line)
            msg = rec.get("message") or {}
            content = msg.get("content")
            if prompt is None and rec.get("type") == "user":
                prompt = text_of(content)
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    if b.get("name") in ("Agent", "Task"):
                        kind = inp.get("subagent_type") or ""
                        kinds[b.get("id")] = kind
                        if CODERS.match(kind):
                            last_coder = last_step = n
                        elif REVIEWERS.match(kind):
                            last_read = n
                    elif b.get("name") == "SendMessage" and inp.get("to") in reviewer_ids:
                        last_read = n
                    elif b.get("name") == "SendMessage" and inp.get("to") in coder_ids:
                        last_step = n
                    elif b.get("name") == "Bash":
                        cmd = str(inp.get("command") or "")
                        if GATE_LOG.search(cmd) or CHECKER.search(cmd):
                            last_check = n
                elif b.get("type") == "tool_result":
                    kind = kinds.get(b.get("tool_use_id"), "")
                    ids = reviewer_ids if REVIEWERS.match(kind) else coder_ids if CODERS.match(kind) else None
                    if ids is not None:
                        ids.update(AGENT_ID.findall(text_of(b.get("content"))))
    ungated = last_step >= 0 and last_check < last_step and not tests_passed(prompt)
    return last_coder > last_read, ungated, bool(NO_REVIEW.search(prompt or ""))


def reasons(path):
    unread, ungated, exempt = scan(path)
    return [r for r, hit in ((PASS_REASON, unread and not exempt), (GATE_REASON, ungated)) if hit]


def loop_transcript(hook):
    path = hook.get("agent_transcript_path")
    if path:
        return path
    aid, top = hook.get("agent_id"), hook.get("transcript_path") or ""
    return os.path.join(top[:-len(".jsonl")], "subagents", "agent-%s.jsonl" % aid) if aid and top else None


def agent_type(hook, path):
    if hook.get("agent_type"):
        return hook["agent_type"]
    if not path:
        return None
    try:
        with open(path[:-len(".jsonl")] + ".meta.json", encoding="utf-8") as fh:
            return json.load(fh).get("agentType")
    except (OSError, ValueError):
        return None


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        unread, ungated, exempt = scan(sys.argv[2])
        print(", ".join([("unread, no-review" if exempt else "unread") if unread else "read"]
                        + (["no check after the last coder step"] if ungated else [])))
        return
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return
    hook = json.load(sys.stdin)
    event = hook.get("hook_event_name")
    if event == "PreToolUse" and hook.get("tool_name") in ("Agent", "Task"):
        inp = hook.get("tool_input") or {}
        prompt = inp.get("prompt") or ""
        if inp.get("subagent_type") == "review-loop" and CALLER_CODE.search(prompt) and not HANDOFF.search(prompt):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                     "permissionDecisionReason": HANDOFF_REASON}}))
    elif event == "SubagentStop" and not hook.get("stop_hook_active"):
        path = loop_transcript(hook)
        if agent_type(hook, path) != "review-loop":
            return
        if not path or not os.path.exists(path):
            raise FileNotFoundError("no loop transcript for agent %s" % hook.get("agent_id"))
        why = reasons(path)
        if why:
            print(json.dumps({"decision": "block", "reason": " ".join(why)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail open, visibly
        print("review-loop-gate: skipped, %s: %s" % (type(e).__name__, e), file=sys.stderr)
