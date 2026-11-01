"""user_prompts.py: the prompts the user typed in a session's main transcript. A tool result, a meta record (command
expansions, reminders), a subagent record, a record with an origin other than the human (a peer message, a task
notification), a compaction summary and a shell or command echo are not the user's words. Not a hook itself."""
import json
import re

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
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                text = prompt_text(record) if isinstance(record, dict) else None
                if text is not None and text.strip():
                    latest = text
    except OSError:
        return None
    return latest
