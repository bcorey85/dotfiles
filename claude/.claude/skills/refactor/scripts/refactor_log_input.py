"""The input grammar of `refactor_flow.py log` and `handoff`, and the template that `log --help` prints.

Plain functions over parsed JSON; nothing here reads repo state. A bad input raises RefactorFlowError.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "lib"))
import plan_format

FINDERS = {"smell-reviewer", "complexity-reviewer"}
PLAN_STRUCTURE_TAG = "[plan-structure]"

TEMPLATE_START = "--- log input template (branch mode, JSON) ---"
TEMPLATE_END = "--- end of log input template ---"

LOG_TEMPLATE = {
    "finder": "smell-reviewer",
    "lane": "code",
    "result": "NEEDS CHANGES",
    "findings": [
        {
            "class": "duplication",
            "disposition": "fix",
            "actioned": "fixed",
            "file": "src/orders.py",
            "line": 3,
            "desc": "the same parse in two handlers",
            "severity": "medium",
            "escape": True,
            "miss_reason": "overlooked",
        }
    ],
    "guards": {"duplication": "convention"},
    "handoff": {
        "files": [{"path": "src/orders.py", "change": "one parse helper for both handlers"}],
        "tests_run": "pytest tests/test_orders.py -> exit 0",
        "flagged": "none",
        "plan_impact": "none",
    },
}

FIELD_NOTES = f"""Input file: one JSON object. `log` reads all of it; `handoff` reads only `handoff` and `modifier`.

  finder       smell-reviewer or complexity-reviewer; omit it in targeted mode (no finder is dispatched).
  lane         required whenever there is a finder.
  result       optional; defaults to NEEDS CHANGES with findings, PASS without.
  target       list of paths. audit: dirs. simplify: the files the prep listed. Required with a finder in
               audit and simplify mode.
  findings     one object per finder finding, with class, disposition, actioned, file, line and desc.
               line is 0 when the finding names no line. desc is one line.
  escape       true on a finding that escaped review; it also needs severity and miss_reason (a label from
               escape-ratchet.md, never `unknown`). Escape rows are refused in audit and targeted mode;
               in simplify mode the class is complexity.
  plan_structure  true on a {PLAN_STRUCTURE_TAG} finding; it needs disposition=ask.
  ruled_by     user or session; disposition=ask only. It lets a plan_structure finding be logged as fixed.
  guards       object of class -> guard, one entry per escape class.
  handoff      optional; never in audit mode. Keys: files (optional; a list of {{path, change}}, one line each;
               the printed file list is what git shows changed against HEAD, untracked included; a listed
               path keeps its `change`, any other gets a stock line), tests_run (one line: the exact
               command and exit code, or `none`), flagged (one line, `none` when nothing is flagged),
               plan_impact (optional string, may span lines).
  modifier     optional string, passed on to /review.
"""


class RefactorFlowError(Exception):
    """Bad input: print it, write nothing, exit 1."""


def log_help_epilog():
    """The field notes, then the template between its two marker lines."""
    template_text = json.dumps(LOG_TEMPLATE, indent=2)
    return "\n".join([FIELD_NOTES, TEMPLATE_START, template_text, TEMPLATE_END])


def require_text(container, key, where):
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RefactorFlowError(f"{where}: `{key}` must be a non-empty string")
    return value


def single_line(container, key, where):
    value = require_text(container, key, where)
    if "\n" in value or "\r" in value:
        raise RefactorFlowError(f"{where}: `{key}` must be one line")
    return value.strip()


SWALLOWED_PAIR = re.compile(r"[ \t\n\r\f\v][A-Za-z_][A-Za-z0-9_]*=")


def one_line_path(value, key, where):
    """A path may hold spaces: the writers get it as one argument. It must not hold a line break, or a
    ` name=` that the writers read as a second field swallowed into this one."""
    if "\n" in value or "\r" in value:
        raise RefactorFlowError(f"{where}: `{key}` must be one line")
    if SWALLOWED_PAIR.search(value):
        raise RefactorFlowError(f"{where}: `{key}` must not contain a space followed by `name=` (got {value!r})")


def validate_finding(finding, index, mode):
    where = f"findings[{index}]"
    if not isinstance(finding, dict):
        raise RefactorFlowError(f"{where}: must be an object")

    for key in ("class", "disposition", "actioned", "file"):
        require_text(finding, key, where)
    one_line_path(finding["file"], "file", where)

    line = finding.get("line")
    if isinstance(line, bool) or not isinstance(line, int):
        raise RefactorFlowError(f"{where}: `line` must be an integer (0 when the finding names no line)")

    finding["desc"] = single_line(finding, "desc", where)
    plan_structure = finding.get("plan_structure", False)
    if not isinstance(plan_structure, bool):
        raise RefactorFlowError(f"{where}: `plan_structure` must be true or false (got {plan_structure!r})")
    ruled_by = finding.get("ruled_by")
    if ruled_by is not None and not plan_format.is_ruling_by(ruled_by):
        raise RefactorFlowError(f"{where}: `ruled_by` must be `user` or `session` (got {ruled_by!r})")
    if plan_structure and finding["disposition"] != "ask":
        raise RefactorFlowError(f"{where}: a {PLAN_STRUCTURE_TAG} finding is an ask the user answers: "
                                f"disposition=ask")
    if ruled_by is not None and finding["disposition"] != "ask":
        raise RefactorFlowError(f"{where}: `ruled_by` names who ruled on an ask: disposition=ask")
    if plan_structure and finding["actioned"] == "fixed" and ruled_by is None:
        raise RefactorFlowError(f"{where}: a {PLAN_STRUCTURE_TAG} finding is an ask the user answers: "
                                f"never actioned=fixed without `ruled_by` (`user` or `session`)")
    if not isinstance(finding.get("escape", False), bool):
        raise RefactorFlowError(f"{where}: `escape` must be true or false (got {finding['escape']!r})")
    if finding.get("escape"):
        validate_escape_finding(finding, where, mode)


def validate_escape_finding(finding, where, mode):
    """The extra checks for a finding marked as an escape."""
    if mode in ("audit", "targeted"):
        raise RefactorFlowError(f"{where}: escape rows are not logged in {mode} mode")
    if mode == "simplify" and finding["class"] != "complexity":
        raise RefactorFlowError(f"{where}: simplify escape rows must be class=complexity")
    require_text(finding, "severity", where)
    # The writer's --check owns the label list; a model writes this input, so `unknown` is refused here.
    miss_reason = finding.get("miss_reason")
    if not isinstance(miss_reason, str) or miss_reason in ("", "unknown"):
        raise RefactorFlowError(f"{where}: an escape finding needs `miss_reason`, a label from "
                                f"escape-ratchet.md other than `unknown` (got {miss_reason!r})")


def validate_handoff(handoff):
    if not isinstance(handoff, dict):
        raise RefactorFlowError("`handoff` must be an object")
    files = handoff.get("files", [])
    if not isinstance(files, list):
        raise RefactorFlowError("handoff.files must be a list of {path, change}; the file list comes from git")

    for entry in files:
        if not isinstance(entry, dict):
            raise RefactorFlowError("handoff.files entries must be objects")
        single_line(entry, "path", "handoff.files")
        single_line(entry, "change", "handoff.files")
    single_line(handoff, "tests_run", "handoff")
    single_line(handoff, "flagged", "handoff")

    plan_impact = handoff.get("plan_impact", "none")
    if not isinstance(plan_impact, str) or not plan_impact.strip():
        raise RefactorFlowError("handoff.plan_impact must be a non-empty string (`none` when there is none)")


def require_escape_guards(findings, guards):
    escape_classes = sorted({finding["class"] for finding in findings if finding.get("escape")})
    for escape_class in escape_classes:
        if not isinstance(guards.get(escape_class), str) or not guards[escape_class]:
            raise RefactorFlowError(f"escape class `{escape_class}` needs guards[\"{escape_class}\"] (run the ratchet)")


def validated_targets(refactor_log, finder, mode):
    targets = refactor_log.get("target") or []
    if not isinstance(targets, list) or not all(isinstance(item, str) and item for item in targets):
        raise RefactorFlowError("`target` must be a list of paths")
    if finder and mode in ("audit", "simplify") and not targets:
        raise RefactorFlowError("`target` (list of dirs or files) is required in audit and simplify mode")
    return targets


def validate_log(mode, refactor_log):
    finder = refactor_log.get("finder") or None
    if mode == "targeted":
        if finder:
            raise RefactorFlowError("`finder` must be omitted in targeted mode (no finder is dispatched)")
    elif not isinstance(finder, str) or finder not in FINDERS:
        raise RefactorFlowError(f"`finder` must be one of {sorted(FINDERS)}")

    lane = None
    if finder:
        lane = require_text(refactor_log, "lane", "log input")

    findings = refactor_log.get("findings", [])
    if not isinstance(findings, list):
        raise RefactorFlowError("`findings` must be a list")
    for index, finding in enumerate(findings):
        validate_finding(finding, index, mode)

    guards = refactor_log.get("guards", {})
    if not isinstance(guards, dict):
        raise RefactorFlowError("`guards` must be an object")
    require_escape_guards(findings, guards)

    verdict = refactor_log.get("result") or ("NEEDS CHANGES" if findings else "PASS")
    if not isinstance(verdict, str):
        raise RefactorFlowError("`result` must be a string")

    targets = validated_targets(refactor_log, finder, mode)

    handoff = refactor_log.get("handoff")
    if mode == "audit" and handoff:
        raise RefactorFlowError("audit mode never hands off to /review")
    if handoff:
        validate_handoff(handoff)

    return {"finder": finder, "lane": lane, "findings": findings, "guards": guards, "verdict": verdict,
            "targets": targets, "handoff": handoff}


def read_refactor_log(path):
    try:
        refactor_log = json.loads(Path(path).read_text())
    except (OSError, ValueError) as err:
        raise RefactorFlowError(f"cannot read --input {path}: {err}") from err
    if not isinstance(refactor_log, dict):
        raise RefactorFlowError(f"--input {path} must hold a JSON object")
    return refactor_log


def read_modifier(refactor_log):
    modifier = refactor_log.get("modifier")
    if modifier is not None and not isinstance(modifier, str):
        raise RefactorFlowError("`modifier` must be a string")
    return modifier
