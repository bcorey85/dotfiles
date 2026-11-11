#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny unbounded waits in subagent Bash calls, with the bounded form to use.

A subagent that waits on a condition that never comes true runs until the 10-minute Bash ceiling. This hook denies
six shapes, only when the payload shows a subagent (agent_type or agent_id is set). The main session is exempt.

  1. an until or while loop that runs sleep
  2. a for loop that runs sleep, unless its count is literal and count x sleep seconds <= 120
  3. follow mode (tail -f, docker logs -f, docker compose logs -f, kubectl logs -f, journalctl -f, watch),
     unless the whole call starts with `timeout N` and N <= 120
  4. a standalone sleep longer than 30 seconds
  5. any background job from review-loop (run_in_background, a lone &, nohup, setsid, detach, disown): it ends its turn
     waiting on jobs whose results never come back
  6. pkill, killall, and kill with any target that is not a literal pid or `$!` (a job spec, a variable, a
     substitution, a process group, or targets fed by xargs). Only agent_id marks a subagent here: agent_type alone
     is the main session's `--agent` seat.

Heredoc bodies, quoted strings and comments are ignored. Fail-open: any error exits 0 with no decision and names the
gate on stderr.
"""
import json
import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(_SCRIPT_DIR), "lib")]
from shell_command import resolved_command_words, wrapper_chain
from shell_statements import clean, statements

MAX_TOTAL_WAIT = 120
MAX_STANDALONE_SLEEP = 30
LOOP_WORDS = {"for", "while", "until", "select"}
DURATION = re.compile(r"^(\d+(?:\.\d+)?)([smhd]?)$")
BRACE_RANGE = re.compile(r"^\{(\d+)\.\.(\d+)\}$")
FOLLOW_FLAGS = re.compile(r"^-[A-Za-z0-9]*[fF][A-Za-z0-9]*$")
LOG_COMMANDS = {"docker", "docker-compose", "podman", "podman-compose", "kubectl"}
TIMEOUT_FLAGS_WITH_VALUE = {"-s", "-k", "--signal", "--kill-after"}

LOOP_REASON = ("This loop has no time limit. If the check never passes, the call runs until the 10-minute limit. "
               "Use a counted loop, for example `for i in $(seq 30); do <check> && break; sleep 3; done`. "
               "Keep the total wait at most 120 seconds. If the check still fails, stop waiting and report it "
               "in your hand-back.")
FOR_REASON = ("This for loop can wait longer than 120 seconds, or its count is not a fixed number. Use a counted "
              "loop, for example `for i in $(seq 30); do <check> && break; sleep 3; done`. Keep count times sleep "
              "at most 120 seconds. If the check still fails, stop waiting and report it in your hand-back.")
FOLLOW_REASON = ("Follow mode never ends, so the call runs until the 10-minute limit. Read a fixed slice instead, "
                 "for example `docker logs --tail 200 <name>` or `--since 2m`. If you must follow, start the call "
                 "with `timeout 120` or less.")
SLEEP_REASON = ("A long sleep wastes the call. Sleep 30 seconds or less. To wait on a condition, use a counted loop, "
                "for example `for i in $(seq 30); do <check> && break; sleep 3; done`. If the check still fails, "
                "stop waiting and report it in your hand-back.")
BACKGROUND_REASON = ("Review-loop runs every check in the foreground. A background job's result does not come back "
                     "to this loop, so it waits for nothing. Run the same command without run_in_background, a "
                     "trailing &, nohup, setsid, detach or disown, and set the Bash timeout up to 600000 ms.")
BACKGROUND_AGENT = "review-loop"
# A lone & that sends a job to the background; &&, |&, 2>&1 and &> are not one.
SHELL_BACKGROUND = re.compile(r"(?<![&>|<])&(?![&>])")
DETACH_WORDS = {"nohup", "setsid", "detach", "disown"}
KILL_REASON = ("Other sessions run on this machine, so a kill by name, pattern, job spec or variable can end a "
               "process you did not start. Kill only a pid you started and recorded, by its number: `kill 4242`.")
PATTERN_KILLERS = {"pkill", "killall"}
KILL_VALUE_OPTIONS = {"-s", "-n", "--signal"}
KILL_LIST_OPTIONS = {"-l", "-L", "--list", "--table"}
LITERAL_PID = re.compile(r"^[1-9]\d*$")
LAST_BACKGROUND_PID = "$!"


def seconds_of(word):
    found = DURATION.match(word or "")
    if not found:
        return None
    unit = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[found.group(2)]
    return float(found.group(1)) * unit


def loop_spans(parsed):
    # Returns (start, end) statement indexes for each loop, end being the matching `done`.
    spans = []
    for start, words in enumerate(parsed):
        if words[0] not in LOOP_WORDS:
            continue
        depth = 0
        end = len(parsed) - 1
        for index in range(start, len(parsed)):
            if parsed[index][0] in LOOP_WORDS:
                depth += 1
            elif parsed[index][0] == "done":
                depth -= 1
                if depth == 0:
                    end = index
                    break
        spans.append((start, end))
    return spans


def sleep_statements(parsed, start, end):
    return [parsed[index] for index in range(start, end + 1) if parsed[index][0] == "sleep"]


def for_count(header):
    # Returns the iteration count of a `for x in ...` header, or None when it is not a literal.
    if len(header) < 4 or header[2] != "in":
        return None
    items = header[3:]
    if len(items) == 1:
        brace = BRACE_RANGE.match(items[0])
        if brace:
            return abs(int(brace.group(2)) - int(brace.group(1))) + 1
        seq = re.match(r"^\$<seq\x00([^>]*)>$", items[0])
        if seq:
            numbers = seq.group(1).split("\x00")
            if not all(re.match(r"^-?\d+$", number) for number in numbers):
                return None
            numbers = [int(number) for number in numbers]
            if len(numbers) == 1:
                return max(numbers[0], 0)
            if len(numbers) == 2:
                return max(numbers[1] - numbers[0] + 1, 0)
            if len(numbers) == 3 and numbers[1] != 0:
                return max((numbers[2] - numbers[0]) // numbers[1] + 1, 0)
            return None
    if any(re.search(r"[$*?`<>{}\x00]", item) for item in items):
        return None
    return len(items)


def bad_loop(parsed, start, end):
    keyword = parsed[start][0]
    sleeps = sleep_statements(parsed, start, end)
    if not sleeps:
        return None
    if keyword in ("until", "while"):
        return LOOP_REASON
    if keyword == "select":
        return None

    count = for_count(parsed[start])
    sleep_seconds = [seconds_of(words[1] if len(words) > 1 else None) for words in sleeps]
    if count is None or None in sleep_seconds:
        return FOR_REASON
    if count * sum(sleep_seconds) > MAX_TOTAL_WAIT:
        return FOR_REASON
    return None


def strip_timeout(words):
    # Returns (timeout seconds or None, the words of the wrapped command).
    if not words or words[0] != "timeout":
        return None, words
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in TIMEOUT_FLAGS_WITH_VALUE else 1
    if index >= len(words):
        return None, []
    return seconds_of(words[index]), words[index + 1:]


def is_follow(words):
    if not words:
        return False
    name = words[0]
    if name == "watch":
        return True
    if name in ("tail", "journalctl"):
        return any(FOLLOW_FLAGS.match(word) or word.startswith("--follow") for word in words[1:])
    if name in LOG_COMMANDS and "logs" in words:
        after = words[words.index("logs") + 1:]
        return any(FOLLOW_FLAGS.match(word) or word.startswith("--follow") for word in after)
    return False


def deny_reason(command):
    parsed = statements(command)
    if not parsed:
        return None

    spans = loop_spans(parsed)
    for start, end in spans:
        reason = bad_loop(parsed, start, end)
        if reason:
            return reason

    first_timeout, _ = strip_timeout(parsed[0])
    call_bounded = first_timeout is not None and first_timeout <= MAX_TOTAL_WAIT
    for words in parsed:
        _, wrapped = strip_timeout(words)
        if is_follow(wrapped) and not call_bounded:
            return FOLLOW_REASON

    in_loop = set()
    for start, end in spans:
        in_loop.update(range(start, end + 1))
    for index, words in enumerate(parsed):
        if words[0] != "sleep" or index in in_loop:
            continue
        sleep_seconds = seconds_of(words[1] if len(words) > 1 else None)
        if sleep_seconds is not None and sleep_seconds > MAX_STANDALONE_SLEEP:
            return SLEEP_REASON
    return None


def kill_targets(words):
    # Returns the target words of a kill command, or None when it only lists signals.
    targets = []
    index = 1
    while index < len(words):
        word = words[index]
        if word == "--":
            return targets + words[index + 1:]
        if word in KILL_LIST_OPTIONS:
            return None
        if word in KILL_VALUE_OPTIONS:
            index += 2
            continue
        if not word.startswith("-"):
            targets.append(word)
        index += 1
    return targets


def kills_unrecorded_process(words):
    name = os.path.basename(words[0])
    if name == "xargs":
        return any(os.path.basename(word) in PATTERN_KILLERS | {"kill"} for word in words[1:])
    if name in PATTERN_KILLERS:
        return True
    if name != "kill":
        return False
    targets = kill_targets(words)
    if targets is None:
        return False
    if not targets:
        return True
    return not all(LITERAL_PID.match(target) or target == LAST_BACKGROUND_PID for target in targets)


def kill_reason(command):
    if any(kills_unrecorded_process(words) for words in resolved_command_words(command)):
        return KILL_REASON
    return None


def starts_detached_job(command):
    if SHELL_BACKGROUND.search(clean(command)):
        return True
    return any(DETACH_WORDS & set(wrapper_chain(words)) for words in statements(command))


def subagent_reason(payload, tool_input, command):
    in_background = tool_input.get("run_in_background") is True or starts_detached_job(command)
    if in_background and payload.get("agent_type") == BACKGROUND_AGENT:
        return BACKGROUND_REASON
    if payload.get("agent_id"):
        reason = kill_reason(command)
        if reason:
            return reason
    return deny_reason(command)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        is_subagent = bool(payload.get("agent_type") or payload.get("agent_id"))
        tool_input = payload.get("tool_input") or {}
        command = tool_input.get("command")
        if not os.environ.get("CLAUDE_SKIP_HOOKS") and is_subagent and isinstance(command, str):
            reason = subagent_reason(payload, tool_input, command)
            if reason:
                sys.stdout.write(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "permissionDecision": "deny",
                    "permissionDecisionReason": reason}}))
    except Exception as error:  # fail-open: a gate bug never blocks a Bash call
        sys.stderr.write(f"wait_loop_gate: {type(error).__name__}: {error}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
