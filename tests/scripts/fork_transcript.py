"""Builders for a /code fork transcript in tests: records in the shape Claude Code writes, and the captured fork that
coded a phase and ended with no review."""
import json
import pathlib

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "code_fork_no_review.jsonl"
REVIEW_START_COMMAND = ("python3 ~/.claude/scripts/code/code_review_start.py lane - 1 /tmp/run/handoff.txt "
                        "--base abc123 --detach")
WAIT_REVIEW_COMMAND = "python3 ~/.claude/scripts/code/code_wait.py review"
WAIT_AGENT_COMMAND = "python3 ~/.claude/scripts/code/code_wait.py agent a1"
PHASE_START_NEW_RUN_COMMAND = "python3 ~/.claude/scripts/code/phase_start.py --new-run"
PHASE_START_COMMAND = "python3 ~/.claude/scripts/code/phase_start.py"
STOP_FILE_PATH = "/tmp/repo/.git/code-phase/stop.md"


def skill_record(skill="code"):
    text = f"Base directory for this skill: /home/user/.claude/skills/{skill}\n\n# Title\n"
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool_record(name, tool_input):
    block = {"type": "tool_use", "id": "toolu_1", "name": name, "input": tool_input}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


def bash_record(command):
    return tool_record("Bash", {"command": command})


def coder_record(subagent_type="coder"):
    return tool_record("Agent", {"subagent_type": subagent_type, "prompt": "do the phase"})


def stop_write_record(file_path=STOP_FILE_PATH):
    return tool_record("Write", {"file_path": file_path, "content": "stopped"})


def text_record(text="done"):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def jsonl_text(records, torn_tail=""):
    lines = [json.dumps(record) for record in records]
    return "\n".join(lines) + "\n" + torn_tail


def fixture_lines():
    return FIXTURE.read_text().splitlines()


def fixture_text_with(*extra_records):
    """The captured fork transcript with records appended after its last record."""
    extra_lines = [json.dumps(record) for record in extra_records]
    return "\n".join(fixture_lines() + extra_lines) + "\n"
