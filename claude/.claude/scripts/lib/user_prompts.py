"""user_prompts.py: the prompts the user typed in a session's main transcript. A tool result, a meta record (command
expansions, reminders), a subagent record, a record with an origin other than the human (a peer message, a task
notification), a compaction summary and a shell or command echo are not the user's words. `starts_turn` is wider: it
marks every main-session record that begins a turn, typed or not (a shell echo, a task notification, a peer
message). `turn_launched_background` reads whether the current turn launched background work. Not a hook itself."""
import re

import script_utils
import tool_call_flags

# Text inside a typed prompt that the user did not write: a paste, and a reminder the harness appends.
NOT_USER_WORDS = re.compile(r"<(pasted_content|system-reminder)\b.*?</\1[^>]*>", re.S | re.I)
# Records a user prompt never is: a peer session's message and a task notification (old forms) and Claude Code's own
# shell and command echoes.
NOT_TYPED_PREFIXES = ("<bash-input>", "<bash-stdout>", "<bash-stderr>", "<local-command-", "<cross-session-message",
                      "Another Claude session sent a message", "<task-notification>")


def prompt_text(record):
    """The text of a transcript record when it is a prompt the user typed in the main session, else None."""
    if record.get("type") != "user" or record.get("isMeta") or record.get("isSidechain"):
        return None
    origin = record.get("origin")
    if record.get("isCompactSummary") or (isinstance(origin, dict) and origin.get("kind") != "human"):
        return None
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list) and all(isinstance(block, dict) and block.get("type") == "text"
                                         for block in content):
        content = "".join(str(block.get("text", "")) for block in content)
    if not isinstance(content, str) or content.lstrip().startswith(NOT_TYPED_PREFIXES):
        return None
    return content


def starts_turn(record):
    """Whether a transcript record begins a turn of the main session: a user record that is no subagent, meta or
    compaction record and carries no tool result. A typed prompt, a shell echo, a task notification and a peer message
    all start one."""
    if record.get("type") != "user":
        return False
    if record.get("isSidechain") or record.get("isMeta") or record.get("isCompactSummary"):
        return False
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    return not any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content)


def turn_launched_background(transcript_path):
    """Whether the current turn of a transcript launched a background Bash or Agent call. A turn start clears it.
    False for an empty or unreadable path; a torn line is skipped."""
    if not transcript_path:
        return False

    launched = False
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as transcript:
            for line in transcript:
                record = script_utils.transcript_record(line)
                if record is None:
                    continue
                if starts_turn(record):
                    launched = False
                for name, tool_input in script_utils.record_tool_calls(record):
                    if tool_call_flags.launches_background(name, tool_input):
                        launched = True
    except OSError:
        return False
    return launched


def user_words(prompt):
    """The prompt without the pasted blocks and appended reminders the user did not write."""
    return NOT_USER_WORDS.sub(" ", prompt)


def latest_prompt(transcript_path):
    """The newest non-blank prompt the user typed in the transcript, or None when there is none or it cannot be read.
    Records that are not the user's prompt are skipped, so a message that arrives later does not replace it."""
    latest = None
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                record = script_utils.transcript_record(line)
                if record is None:
                    continue
                text = prompt_text(record)
                if text is not None and text.strip():
                    latest = text
    except OSError:
        return None
    return latest
