"""code_guidance.py: the main session's implementation guidance for a running /code. The `guide` verb records it in
state.json, so it survives a resume; every later coder and review dispatch carries it. It never changes the task or
the plan."""
import script_utils

GUIDANCE_HEADING = "## Guidance from the main session"
GUIDANCE_RULE = "Follow it within the task and the plan. It changes neither."


def record_guidance(state, text):
    state.guidance = [*(state.guidance or []), text.strip()]


def coder_guidance_lines(state):
    """The prompt section that carries the run's guidance to a coder, or [] when there is none."""
    guidance = state.guidance or []
    if not guidance:
        return []
    return ["", GUIDANCE_HEADING, "", GUIDANCE_RULE, ""] + [f"- {text}" for text in guidance]


def guidance_header_line(state):
    """The review prompt's `guidance:` header line, or None when the run has no guidance. The header is one line per
    key, so each text is put on one line and the texts are joined with ` | `."""
    guidance = state.guidance or []
    if not guidance:
        return None
    one_line_texts = [script_utils.one_line(text, limit=None) for text in guidance]
    return "guidance: " + " | ".join(one_line_texts)
