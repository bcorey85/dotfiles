"""Transcript text for tests: assistant lines that each hold one Edit call."""
import json

AFTER_HEAD = "2099-01-01T00:00:00Z"


def edit_lines(edited_paths, timestamp=AFTER_HEAD):
    """The transcript text with one Edit call, recorded at `timestamp`, on each of `edited_paths` (absolute)."""
    lines = []
    for edited_path in edited_paths:
        block = {"type": "tool_use", "id": "t", "name": "Edit", "input": {"file_path": str(edited_path)}}
        lines.append(json.dumps({"type": "assistant", "timestamp": timestamp, "message": {"content": [block]}}))
    return "\n".join(lines) + "\n"
