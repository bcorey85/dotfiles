"""shell_write_denial.py: the deny text of the shell write gate. Every deny it makes is built here, as
`[shell-write-gate] [<tag>] <message>`.

The gate imports it after putting scripts/lib on sys.path. The tags are read by the work review queue."""

GATE_NAME = "shell-write-gate"
SCRIPT_WRITE_REL_CD = "script_write_rel_cd"
SCRIPT_WRITE = "script_write"
INPLACE_EDIT = "inplace_edit"
TRACKED_TARGET = "tracked_target"
REL_TARGET_UNREAD_CD = "rel_target_unread_cd"
CODER_REL_TARGET_CD = "coder_rel_target_cd"
CODER_UNRESOLVED_VAR = "coder_unresolved_var"
CODER_VAR_OUTSIDE_TEMP = "coder_var_outside_temp"
CODER_NEW_FILE = "coder_new_file"
INPUT_PARSE_FAIL = "input_parse_fail"
INTERNAL_ERROR = "internal_error"
TAGS = (SCRIPT_WRITE_REL_CD, SCRIPT_WRITE, INPLACE_EDIT, TRACKED_TARGET, REL_TARGET_UNREAD_CD, CODER_REL_TARGET_CD,
        CODER_UNRESOLVED_VAR, CODER_VAR_OUTSIDE_TEMP, CODER_NEW_FILE, INPUT_PARSE_FAIL, INTERNAL_ERROR)

DIRECTORY_CHANGE_HINT = ("This gate checks a relative path against the session cwd and each cd folder before it; "
                         "use an absolute path for the file you mean.")
ESCAPE_HINT = (" If this deny is wrong (for example a command wrapper this gate does not recognize), re-run the "
               "command with a trailing #skip-shell-write-gate comment — it disarms this gate for that one command.")
RESTORE_HINT = "Restore a tracked file from a revision with `git restore --source=<rev> -- <path>`."


class DenyError(Exception):
    pass


def tagged_message(tag, message):
    """The one form of every deny: `[shell-write-gate] [<tag>] <message>`."""
    return f"[{GATE_NAME}] [{tag}] {message}"


def deny_text(tag, subject, cannot_skip):
    """The deny text for a subject: the way to write the file, and for an agent that may skip the gate, how."""
    if cannot_skip:
        return tagged_message(tag, f"{subject} Use the Edit tool for an in-place change, or the Write tool for a new "
                                   "file. This agent has no way to skip this gate.")
    return tagged_message(tag, f"{subject} Use the Write or Edit tool.") + ESCAPE_HINT
