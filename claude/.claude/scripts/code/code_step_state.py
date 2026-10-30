"""code_step_state.py: the record of one /code run, as <git dir>/code-step/state.json holds it.

Installed beside code_step.py and imported by code_step_core. A state file loads only when it names a stage and stop
kind this code-step knows and holds no key the record does not name, except a stop record's waitAt, which loads and is
dropped. A file another version of code-step wrote stops the verb instead of being read wrong. A field holds its JSON
value as it is: the ask, ruling and snapshot payloads stay dicts."""
import dataclasses
import enum
import re


class StateFileError(Exception):
    pass


class Stage(enum.StrEnum):
    CODER = "coder"
    ASKS_CODER = "asks-coder"
    PLAN_CODER = "plan-coder"
    REVIEW = "review"
    IMPACT_CODER = "impact-coder"
    IMPACT_REVIEW = "impact-review"
    ASKS = "asks"
    SKILL = "skill"
    DONE = "done"
    STOPPED = "stopped"


class StopKind(enum.StrEnum):
    # Why a stopped run stopped. A stop with no kind waits for the user.
    CODER_RESUMABLE = "coder-resumable"
    REVIEW_RESUMABLE = "review-resumable"
    CODER_CAP = "coder-cap"
    VERIFICATION = "verification"
    PLAN_FORMAT = "plan-format"
    INVALID_PACKET = "invalid-packet"
    CAP_REACHED = "cap-reached"
    FALSE_CLEAN = "false-clean"
    TOOL_FAULT = "tool-fault"
    CRITICAL_BLOCKER = "critical-blocker"
    SETUP_FAULT = "setup-fault"
    FIX_REMOVED_CHANGE = "fix-removed-change"
    CHECK_UNVERIFIED = "check-unverified"
    CHECK_NOT_RUN = "check-not-run"
    PLAN_IMPACT_CAUSE = "plan-impact-cause"
    REVIEW_NOT_CONVERGED = "review-not-converged"


def json_key(field):
    # A field's key in state.json: its name in camelCase, unless the field names its key.
    return field.metadata.get("json") or re.sub(r"_([a-z])", lambda match: match.group(1).upper(), field.name)


def record_values(record_type, raw, source):
    # The field values of a record_type from its object in state.json.
    if not isinstance(raw, dict):
        raise StateFileError(f"{source} does not hold a JSON object")

    field_names = {json_key(field): field.name for field in dataclasses.fields(record_type)}
    unknown_keys = sorted(set(raw) - set(field_names))
    if unknown_keys:
        raise StateFileError(f"{source} has keys this code-step does not know: {', '.join(unknown_keys)}")
    return {field_names[key]: value for key, value in raw.items()}


def without_dropped_stop_keys(raw_stop):
    # The stop record without waitAt, which the code-step before the typed record wrote: a resumed agent's first wait
    # is now a run-log event.
    if not isinstance(raw_stop, dict):
        return raw_stop
    return {key: value for key, value in raw_stop.items() if key != "waitAt"}


def present_values(record):
    # Every field of the record that holds a value, by its state.json key.
    values = {json_key(field): getattr(record, field.name) for field in dataclasses.fields(record)}
    return {key: value for key, value in values.items() if value is not None}


@dataclasses.dataclass(frozen=True, slots=True)
class Stop:
    # A stopped run's record. agent_id is the coder the user can resume, coder_stage the stage that coder stopped at.
    kind: StopKind | None
    at: float
    agent_id: str | None = None
    coder_stage: str | None = None

    def __post_init__(self):
        if self.kind is not None:
            object.__setattr__(self, "kind", StopKind(self.kind))

    def to_json(self):
        return {"kind": self.kind} | present_values(self)


@dataclasses.dataclass(slots=True)
class RunState:
    # Where the run is.
    stage: Stage
    stop: Stop | None = None

    # The run, as start set it.
    plan: str | None = None
    phase: str | None = None
    title: str = ""
    lane: str = "code"
    branch: str | None = None
    modifier: str | None = None
    risk: str = "high"
    headless: bool = False
    only_phase: str | None = None
    run_notes: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    started_at: float | None = None
    gate_commands: list = dataclasses.field(default_factory=list)
    baseline: dict | None = None
    base_head: str | None = None
    phase_text: str | None = None
    criteria_guard: dict | None = None
    guidance: list | None = None
    snapshot: dict = dataclasses.field(default_factory=dict)

    # The open dispatch.
    dispatch_at: float | None = None
    review_script_pid: int | None = None
    review_script_log: str | None = None
    last_review_prompt: str | None = None

    # The coder's report.
    files: list | None = None
    behavior: list | None = None
    why: dict | None = None
    summary_why: dict | None = None
    tests_run: str | None = None
    flagged: list = dataclasses.field(default_factory=list)
    exception: bool | None = None
    coder_stage: str | None = None
    changes: dict | None = None
    gate_lines: str = ""
    handled_impacts: list | None = None
    correction_coder: bool | None = None

    # The review.
    iter: int = 0
    spec_iter: int | None = dataclasses.field(default=None, metadata={"json": "spec_iter"})
    review_status: str | None = None
    review_ran: bool | None = None
    structure_pass_skipped: bool | None = None
    check_created: list | None = None
    check_changed: list | None = None
    check_rewrote_edited: list | None = None
    carried_findings: list | None = None
    cap_carried: bool = False
    blocker_carried: bool | None = None
    plan_impact: str = "none"
    prior_issues: list | None = None

    # The asks.
    asks: list | None = None
    ask_ids: dict | None = None
    ask_ids_handback: str | None = None
    accepted_asks: list | None = None
    asks_also: str = ""
    rulings: dict | None = None
    pending_correction: dict | None = None
    ask_rounds: list = dataclasses.field(default_factory=list)

    # A plan impact the coder or the review raised.
    impact: str | None = None
    ruling: dict | None = None

    # The phase end.
    auto_advance: bool | None = None
    commit_files: list | None = None
    commit_line: str = ""

    def __setattr__(self, name, value):
        # A stage set on the record is a Stage: an unknown one raises here, not when the state is saved or routed.
        if name == "stage":
            value = Stage(value)
        object.__setattr__(self, name, value)

    @classmethod
    def from_json(cls, raw, source):
        values = record_values(cls, raw, source)
        try:
            if values.get("stop") is not None:
                raw_stop = without_dropped_stop_keys(values["stop"])
                values["stop"] = Stop(**record_values(Stop, raw_stop, f"{source} (stop record)"))
            return cls(**values)
        except (TypeError, ValueError) as error:
            raise StateFileError(f"{source} does not load: {error}") from None

    def to_json(self):
        values = present_values(self)
        if self.stop is not None:
            values["stop"] = self.stop.to_json()
        return values
