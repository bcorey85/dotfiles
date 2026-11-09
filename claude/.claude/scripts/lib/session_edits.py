"""session_edits.py: the file writes a `claude -p` session made through its Edit and Write tools, read from its
transcript, and the text a file holds once those writes are replayed on it. A tool call whose result is an error made
no write. A Bash write is not in the transcript as a write, so it is never replayed."""
import json
import pathlib

EDIT_TOOL = "Edit"
WRITE_TOOL = "Write"
EDIT_FIELDS = {"file_path", "old_string", "new_string"}
WRITE_FIELDS = {"file_path", "content"}


class ReplayError(ValueError):
    """A recorded write that does not apply to the text: an unknown input shape, or an old_string not in the text."""


def session_transcript(session_id):
    """The session's transcript under ~/.claude/projects, or None when it is not there."""
    if not session_id:
        return None
    projects = pathlib.Path.home() / ".claude" / "projects"
    found = sorted(projects.glob(f"*/{session_id}.jsonl"))
    return found[0] if found else None


def tool_blocks(transcript):
    """(tool_use blocks in order, the ids of the tool_results that are errors) of one transcript."""
    uses = []
    failed = set()
    for line in transcript.read_text(errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = row.get("message") if isinstance(row, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                uses.append(block)
            if block.get("type") == "tool_result" and block.get("is_error"):
                failed.add(block.get("tool_use_id"))
    return uses, failed


def file_writes(transcript, root):
    """{path relative to root: [tool input, ...]} of the Edit and Write calls that did not fail, in call order."""
    root = pathlib.Path(root).resolve()
    uses, failed = tool_blocks(transcript)
    writes = {}
    for block in uses:
        if block.get("name") not in (EDIT_TOOL, WRITE_TOOL) or block.get("id") in failed:
            continue
        tool_input = block.get("input")
        file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
        if not isinstance(file_path, str):
            continue

        target = pathlib.Path(file_path).resolve()
        if not target.is_relative_to(root):
            continue
        writes.setdefault(target.relative_to(root).as_posix(), []).append({"tool": block["name"], **tool_input})
    return writes


def replayed_text(text, writes):
    """`text` with each write applied in order. Raises ReplayError when one does not apply."""
    for write in writes:
        fields = set(write) - {"tool", "replace_all"}
        if write["tool"] == WRITE_TOOL and fields == WRITE_FIELDS:
            text = write["content"]
            continue
        if write["tool"] != EDIT_TOOL or fields != EDIT_FIELDS or write["old_string"] not in text:
            raise ReplayError(f"{write['tool']} of {write.get('file_path')} does not apply")

        count = -1 if write.get("replace_all") else 1
        text = text.replace(write["old_string"], write["new_string"], count)
    return text
