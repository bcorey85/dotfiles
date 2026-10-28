#!/usr/bin/env python3
"""handback.py: the one reader of the review-loop hand-back packet, and the per-session store of hand-backs.

  handback.py check < packet            exit 0 and one `ok` line for a packet that parses and validates; exit 1 and the
                                        problems on stderr for a bad one
  handback.py hook dispatch|handback < hook event JSON
                                        PreToolUse hook. Matcher Agent records each review-loop dispatch; matcher
                                        SubagentHandback validates and records each review-loop hand-back, and denies a
                                        bad packet once per agent so the loop can repair it, denies a hand-back (any
                                        status but plan-impact, in a repo whose CLAUDE.md does not say
                                        `Full suite: CI`) whose own transcript shows no full check after its
                                        last code change (once per code change), and denies any call from an agent
                                        whose report is already stored. Any other argument does nothing.

Importers use parse, validate, load, render, record, latest, hand_back_gap, false_clean_reason,
ended_on_unreviewed_fix, fixed_paths, unreviewed_streak and unreviewed_fix_section. The store also holds
a `stop` row that review_loop_gate.py writes at each review-loop stop (agent_id, open_dispatches). `latest` keeps the
last one after the last dispatch; while it shows open_dispatches > 0 and no hand-back is current, hand_back_gap returns
LOOP_WAITING, and a later stop with none open, a hand-back or a new dispatch ends the wait. A validated packet's
fixed, skipped_fp, findings_remaining and ask entries are all mappings. The store is one append-only JSON-lines file per
session under $HANDBACK_STORE_DIR (default ~/.claude/state/handback), keyed by the hook event's session_id, which is
the value of CLAUDE_CODE_SESSION_ID inside a Bash call."""
import json
import os
import pathlib
import re
import secrets
import sys
import textwrap
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import script_utils
from script_utils import first_number, one_line, unquote

STATUSES = ["converged", "deferred", "plan-impact", "critical-blocker", "cap-reached", "setup-fault"]
CLEAN_STATUSES = ("converged", "deferred")
PACKET_KEYS = ["status", "iter", "spec_iter", "fixed", "skipped_fp", "blockers", "findings_remaining", "plan_impact",
               "ask", "class_closure", "full_check", "files_touched", "nit", "load_bearing_clean",
               "tool_fault"]
LIST_KEYS = ["fixed", "skipped_fp", "blockers", "findings_remaining", "ask", "nit", "files_touched"]
SCALAR_KEYS = ("status", "iter", "spec_iter", "full_check", "load_bearing_clean", "tool_fault")
# The list fields whose entries validate turns into mappings, and the key a plain-text entry's text goes under.
ENTRY_TEXT_KEYS = {"fixed": "finding", "skipped_fp": "item", "findings_remaining": "finding", "ask": "question"}
# The field each status requires, and the word for its absence. cap-reached says "missing" when the key is absent.
STATUS_REQUIRES = {"plan-impact": ("plan_impact", "empty"), "critical-blocker": ("blockers", "empty"),
                   "setup-fault": ("blockers", "empty"), "cap-reached": ("findings_remaining", "empty"),
                   "deferred": ("findings_remaining", "missing or empty")}
BLOCKER_STATUSES = {status for status, (field, _) in STATUS_REQUIRES.items() if field == "blockers"}
ITEM_KEYS = [
    "disposition",
    "smell",
    "finding_id",
    "finding",
    "file_line",
    "blocker",
    "question",
    "change",
    "gate",
    "class",
    "reason",
    "item",
    "phase",
]
NONE_VALUE = re.compile(r"^\[\s*\]|^\(?\s*(none|n/a|null)\b", re.I)
BLOCK_INDICATOR = re.compile(r"^[|>][+-]?$")
NUMBERED_ITEM = re.compile(r"^\s*\d+[.)]\s")
ITEM_START = re.compile(r"^\s*(?:-|\d+[.)])\s+", re.M)
CLASSES = ["bug", "smell", "duplication", "complexity", "plan-drift", "test-gap", "weak-assertion", "security", "perf",
           "correctness", "docs", "other"]
REVIEW_LOOP = "review-loop"
NO_REVIEW_MODE = re.compile(r"(?im)^[ \t>*`-]*no-review\b")
REPO_LINE = re.compile(r"(?m)^[ \t]*repo:[ \t]*(\S[^\n]*?)[ \t]*$")
ABSOLUTE_PATH = re.compile(r"(?<![\w.~-])/[^\s`'\"<>|;:,()]+")
GIT_TIMEOUT_SECONDS = 10
DEFAULT_GATE = "code-reviewer"
FENCE_OPEN = "```"
BLOCKER_TEXT = re.compile(r"\[blocker\]|\bblocker\s*[:=]\s*(?:yes|true)\b", re.I)
INLINE_KEY_AT = re.compile(r"(?:^|\n\s*|([,.;|?!)])\s+)(" + "|".join(ITEM_KEYS) + r")\s*:\s*")
KEPT_DELIMITERS = "?!)"
ITEM_KEY_START = re.compile(r"(?:{})\s*:".format("|".join(ITEM_KEYS)))
STALE_STORE_SECONDS = 7 * 86400
FINDING_ID_HEX_LEN = 16
FINDING_ID_PATTERN = re.compile(rf"[0-9a-f]{{{FINDING_ID_HEX_LEN}}}")
# A line `log-review-finding` prints for each finding row it writes.
PRINTED_FINDING_ID = re.compile(r"(?m)^finding_id=(" + FINDING_ID_PATTERN.pattern + r")\s*$")


class PacketError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems
        self.raw = ""


# ---------- parsing ----------

def is_block_scalar(value_lines):
    return BLOCK_INDICATOR.match(value_lines[0].strip()) is not None


def is_item_line(line):
    return line.lstrip().startswith("-") or NUMBERED_ITEM.match(line) is not None


def ends_packet_value(key, value_lines, line, next_line=""):
    # A scalar key owns one line. A list key owns its item lines and their indented continuations; the first
    # unindented prose line after them is the loop's closing note, not another item.
    if key in SCALAR_KEYS:
        return True
    unindented = line[:1] not in (" ", "\t")
    if is_block_scalar(value_lines):
        return unindented
    is_none_list = key in LIST_KEYS and len(value_lines) == 1 and NONE_VALUE.match(value_lines[0].strip()) is not None
    if is_none_list:
        return unindented
    is_list = any(is_item_line(value_line) for value_line in value_lines[1:])
    is_empty_list_key = key in LIST_KEYS and value_lines == [""]
    if is_empty_list_key and is_item_line(next_line):
        return False
    starts_item = is_item_line(line) or line[:1] in ("[", "{", "]", "}")
    return (is_list or is_empty_list_key) and unindented and not starts_item


def packet_value(value_lines):
    if is_block_scalar(value_lines):
        return textwrap.dedent("\n".join(value_lines[1:])).strip()
    first = value_lines[0].strip()
    rest = "\n".join(value_lines[1:]).rstrip()
    if first:
        return (first + "\n" + rest).strip() if rest.strip() else first
    return rest.strip("\n")


def parse(message):
    """The packet's raw fields as text, plus `trailer` (prose outside any field)."""
    lines = [line.rstrip() for line in message.splitlines() if not line.strip().startswith(FENCE_OPEN)]
    text_lines = textwrap.dedent("\n".join(lines)).splitlines()
    next_lines = [""] * len(text_lines)
    following = ""
    for index in range(len(text_lines) - 1, -1, -1):
        next_lines[index] = following
        following = text_lines[index] if text_lines[index].strip() else following
    fields = {}
    trailer = []
    key = None
    for index, line in enumerate(text_lines):
        match = re.match(r"^([a-z_]+)(?:[ \t]*\([^)]*\))?:[ \t]*(.*)$", line)
        is_packet_key = match is not None and match.group(1) in PACKET_KEYS
        if is_packet_key and match.group(1) not in fields:
            key = match.group(1)
            fields[key] = [match.group(2)]
        elif is_packet_key:
            key = None
            trailer.append(line)
        elif key and not line.strip() and is_block_scalar(fields[key]):
            fields[key].append("")
        elif key and not line.strip():
            if key in LIST_KEYS and fields[key][0] == "":
                continue
            key = None
            trailer.append("")
        elif key and ends_packet_value(key, fields[key], line, next_lines[index]):
            key = None
            trailer.append(line)
        elif key:
            fields[key].append(line)
        else:
            trailer.append(line)
    packet = {name: packet_value(value) for name, value in fields.items()}
    packet["trailer"] = "\n".join(trailer).strip()
    return packet


def parse_flow_mapping(chunk):
    # The loop writes items as `{finding: "...", file_line: a.ts:1, blocker: false}`: YAML flow style, not JSON.
    return parse_inline_pairs(chunk.strip()[1:-1])


def parse_inline_pairs(body):
    # A key starts a field at the start of the body, after a newline, or after `, ` `. ` `; ` `| ` `? ` `! ` `) `.
    # A key word after a bare space is part of the previous value.
    masked_body = script_utils.unquoted_mask(body)
    matches = list(INLINE_KEY_AT.finditer(masked_body))
    if not matches:
        return None
    fields = {}
    lead_text = body[:matches[0].start()].strip().rstrip(".;|,").strip()
    if lead_text:
        fields["finding"] = unquote(lead_text)
    for position, match in enumerate(matches):
        end = len(body)
        if position + 1 < len(matches):
            following = matches[position + 1]
            keeps_delimiter = following.group(1) is not None and following.group(1) in KEPT_DELIMITERS
            end = following.start() + (1 if keeps_delimiter else 0)
        fields[match.group(2)] = unquote(body[match.end():end].strip().rstrip(".;|").strip())
    return fields


def flow_item(chunk):
    return parse_flow_mapping(chunk) or unquote(chunk)


def split_top_level_items(body):
    """Split a list body at its item markers. A marker indented deeper than the shallowest one is a sub-bullet:
    it stays inside its parent item, and so does a marker of the other kind (bullet or numbered) at the shallowest
    indent. Chunk 0 is the lead prose before the first marker."""
    markers = list(ITEM_START.finditer(body))
    if not markers:
        return [body]

    def indent_of(marker):
        marker_line = marker.group(0).rsplit("\n", 1)[-1]
        return len(marker_line) - len(marker_line.lstrip())

    def is_bullet(marker):
        return marker.group(0).lstrip().startswith("-")

    shallowest = min(indent_of(marker) for marker in markers)
    first_kind = is_bullet(next(marker for marker in markers if indent_of(marker) == shallowest))
    top_level = [marker for marker in markers if indent_of(marker) == shallowest and is_bullet(marker) == first_kind]
    chunks = []
    position = 0
    for marker in top_level:
        chunks.append(body[position:marker.start()])
        position = marker.end()
    chunks.append(body[position:])
    return chunks


def mapping_with_trailing_lines(chunk):
    """A mapping followed by more lines of the same item: the lines add to its question,
    or to its finding when it has no question."""
    groups = script_utils.top_level_braces(chunk)
    trailing = chunk[len(groups[0]):].strip() if groups and chunk.startswith(groups[0]) else ""
    flow_fields = parse_flow_mapping(groups[0]) if trailing else None
    if flow_fields:
        key = "question" if "question" in flow_fields else "finding"
        flow_fields[key] = f"{flow_fields.get(key, '')}\n{trailing}".strip()
    return flow_fields


def read_list(raw):
    """(lead prose, items) of a list field. Lead prose is text before the first item marker: it is not an item."""
    indented = raw.strip("\n").rstrip()
    raw = raw.strip()
    has_items = ITEM_START.search(raw) is not None or "{" in raw
    if raw == "" or (not has_items and NONE_VALUE.match(raw)):
        return "", []
    try:
        loaded = json.loads(raw)
        return "", loaded if isinstance(loaded, list) else [loaded]
    except ValueError:
        pass
    bracketed = raw.startswith("[") and raw.endswith("]") and raw.count("{") > 0
    if bracketed:
        return "", [flow_item(chunk) for chunk in script_utils.top_level_braces(raw[1:-1])]
    chunks = split_top_level_items(indented)
    lead = ""
    if len(chunks) > 1:
        lead = chunks[0].strip()
        chunks = chunks[1:]
    list_entries = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        flow_fields = parse_flow_mapping(chunk) if chunk.startswith("{") and chunk.endswith("}") else None
        if chunk.startswith("{") and not flow_fields:
            flow_fields = mapping_with_trailing_lines(chunk)
        if flow_fields:
            list_entries.append(flow_fields)
            continue
        inline_fields = parse_inline_pairs(chunk) if ITEM_KEY_START.match(chunk) else None
        if inline_fields and len(inline_fields) > 1 and "\n" not in chunk:
            list_entries.append(inline_fields)
            continue
        pairs = dict(re.findall(r"^\s*(\w+):\s*(.+)$", chunk, re.M))
        list_entries.append({name: unquote(value) for name, value in pairs.items()}
                           if pairs and all(name in ITEM_KEYS for name in pairs) else unquote(chunk))
    return lead, list_entries


# ---------- items ----------

def is_blocker(item):
    return isinstance(item, dict) and str(item.get("blocker", "")).strip().lower() in ("true", "yes")


def item_text(item, *keys):
    if isinstance(item, dict):
        return " - ".join(str(item[key]) for key in keys if item.get(key))
    return str(item)


def ask_finding_id(item):
    """The entry's finding_id when it is an id the ledger writer mints (16 lowercase hex chars); otherwise None.
    A placeholder such as "none logged" or "-", or a damaged id, is not an id."""
    finding_id = item.get("finding_id")
    if isinstance(finding_id, str) and FINDING_ID_PATTERN.fullmatch(finding_id.strip()):
        return finding_id.strip()
    return None


def is_same_file(path, logged_path):
    """True when two paths name one file, or one is the other's tail after a `/`: the loop logs the path its command
    line spelled, which may be shorter than the ask's."""
    if not path or not logged_path:
        return False
    return path == logged_path or path.endswith("/" + logged_path) or logged_path.endswith("/" + path)


def claim_logged_ask_id(item, logged_rows):
    """The finding_id of the logged ask row at the ask's file and line, or None. A claimed row leaves logged_rows, so
    two asks never share one id. Each row is {file, line, finding_id}."""
    path, line = script_utils.split_location(item.get("file_line") or "")
    for row in logged_rows:
        if row["line"] == line and is_same_file(path, row["file"]):
            logged_rows.remove(row)
            return row["finding_id"]
    return None


def ask_row_fields(context, item):
    """The log-review-finding fields that an ask's row and its outcome row share. context holds the run's branch, lane,
    scope and iter, and a phase when the run has one (the writer takes phase as a token, so a run with none sends
    none)."""
    path, line = script_utils.split_location(item.get("file_line") or "-")
    phase_fields = [f"phase={context['phase']}"] if context.get("phase") else []
    return [f"branch={context['branch']}", f"lane={context['lane']}", f"scope={context['scope']}", *phase_fields,
            f"iter={context['iter']}", f"gate={item.get('gate', 'code-reviewer')}", "disposition=ask",
            f"class={item.get('class', 'other')}", f"file={path}", f"line={line}", "actioned=ask"]


def log_ask_row(logger, context, item, cwd=None):
    """The finding_id that the log helper at `logger` printed for a new ask row, or None when the row was not logged."""
    code, output = script_utils.run_command(["bash", str(logger), "kind=finding", *ask_row_fields(context, item)], cwd)
    printed_ids = PRINTED_FINDING_ID.findall(output)
    return printed_ids[0] if code == 0 and printed_ids else None


def supply_ask_finding_ids(asks, session_id, logger, context, cwd=None):
    """Give every ask in `asks` without a valid finding_id the id of the ask row the loop logged for it (the stop row's
    ask_rows of this session, matched on file and line), or of an ask row logged here when the loop logged none. A
    valid id on an ask stays and its logged row is never given to another ask. An ask whose row cannot be logged gets
    none; the outcome is then logged under a new id. The caller saves the asks so a repeat logs no ask row twice."""
    stop_row = latest(session_id)["stop"] or {}
    written_ids = {ask_finding_id(item) for item in asks}
    logged_rows = [dict(row) for row in stop_row.get("ask_rows") or [] if row["finding_id"] not in written_ids]
    for item in asks:
        if ask_finding_id(item):
            continue

        finding_id = claim_logged_ask_id(item, logged_rows) or log_ask_row(logger, context, item, cwd)
        if finding_id:
            item["finding_id"] = finding_id


def ask_outcome_finding_id(item):
    """(the finding_id an ask's outcome row is logged under, a stderr note or None). A valid id, which the script
    supplied from the ask's logged row, supersedes that row. An ask the script could not match or log has no valid id:
    its outcome row gets a new id in the ledger writer's shape and stands as that ask's only row, so the user's answer
    is never dropped."""
    finding_id = ask_finding_id(item)
    if finding_id is not None:
        return finding_id, None

    new_finding_id = secrets.token_hex(8)
    ignored_value = item.get("finding_id")
    ignored_text = "no finding_id" if ignored_value is None else f"ignored {ignored_value!r}"
    note = f"ask outcome without a valid finding_id ({ignored_text}), logged under new finding_id {new_finding_id}"
    return new_finding_id, note


def entry_paths(item):
    """Every normalized path that a list entry names: its file_line plus each path:line in its finding text."""
    return script_utils.paths_named(item.get("file_line"), item.get("finding"), item.get("item"))


def entry_locations(item):
    """Every (path, line) that a list entry names."""
    finding_text = str(item.get("finding") or "")
    item_summary = str(item.get("item") or "")
    texts = [str(item.get("file_line") or ""), *script_utils.PATH_LINE.findall(finding_text),
             *script_utils.PATH_LINE.findall(item_summary)]
    return [script_utils.split_location(text) for text in texts if text.strip()]


def entry_from_text(text, text_key):
    """A plain-text list entry (`- text | path:line | blocker: no`) as the mapping the loop's flow style gives."""
    found = script_utils.PATH_LINE.search(text)
    entry = {text_key: text, "blocker": "yes" if BLOCKER_TEXT.search(text) else "no", "from_text": True}
    if found:
        entry["file_line"] = found.group(1)
    return entry


def first_token(text):
    tokens = [token for token in re.split(r"[\s,;|/]+", str(text or "")) if token]
    return tokens[0] if tokens else ""


# ---------- validation ----------

def read_header(raw):
    """(the packet's scalar fields, their problems)."""
    problems = []
    status_words = raw.get("status", "").strip().strip("`'\"").lower().split()
    status = status_words[0] if status_words else ""
    if status not in STATUSES:
        problems.append(f"status is {raw.get('status', 'missing')!r}; want one of {', '.join(STATUSES)}")
    iter_round = first_number(raw.get("iter"))
    if iter_round is None:
        problems.append("iter is missing or has no number")
    spec_iter = first_number(raw.get("spec_iter"))
    if raw.get("spec_iter", "").strip() and spec_iter is None:
        problems.append("spec_iter has no number")

    header = {"status": status, "iter": iter_round, "spec_iter": spec_iter,
              "class_closure": raw.get("class_closure", "").strip(),
              "full_check": raw.get("full_check", "").strip(),
              "load_bearing_clean": raw.get("load_bearing_clean", "").strip(),
              "tool_fault": raw.get("tool_fault", "").strip(),
              "plan_impact": raw.get("plan_impact", "").strip()}
    return header, problems


def normalize_ask(item):
    if item.get("from_text"):
        item["finding"] = item["question"]
    elif item.get("finding") and not item.get("question"):
        item["question"] = item["finding"]
    item["gate"] = first_token(item.get("gate")) or DEFAULT_GATE

    ask_class = str(item.get("class") or "").strip()
    if ask_class in CLASSES:
        return
    item["class"] = "other"
    if ask_class:
        item["class_raw"] = ask_class


def normalize_items(key, entries):
    """The entries of list field `key`, a text entry made a mapping when the field is in ENTRY_TEXT_KEYS. Any other
    entry stays as it is, for item_problems to refuse."""
    text_key = ENTRY_TEXT_KEYS.get(key)
    if text_key is None:
        return entries
    items = [entry_from_text(item, text_key) if isinstance(item, str) else item for item in entries]
    for item in items:
        if not isinstance(item, dict):
            continue
        if key == "ask":
            normalize_ask(item)
        elif key == "fixed" and not item.get("finding") and item.get("smell"):
            item["finding"] = item["smell"]
    return items


def item_problems(raw, packet):
    problems = [f"fixed entry has no finding: {one_line(item, 80)!r}" for item in packet["fixed"]
                if not (isinstance(item, dict) and item.get("finding"))]
    if raw.get("ask", "").strip() and not packet["ask"] and not NONE_VALUE.match(raw["ask"].strip()):
        problems.append(f"ask holds text but yields no ask entries: {one_line(raw['ask'], 80)!r}")
    for item in packet["ask"]:
        if not isinstance(item, dict) or not item.get("question"):
            problems.append(f"ask entry has no question: {one_line(item, 80)!r}")
            continue
        question = one_line(item.get("question"), 80)
        if not item.get("file_line") and not item.get("from_text"):
            problems.append(f"ask entry has no file_line: {question!r}")
        elif not item.get("change") and not item.get("from_text"):
            problems.append(f"ask entry has no change, the one edit an accepted answer makes: {question!r}")
    return problems


def status_problems(raw, packet):
    status = packet["status"]
    problems = []
    if "fixed" not in raw and status in CLEAN_STATUSES:
        problems.append("fixed is missing: the packet must always carry fixed, even as []")

    field, absence = STATUS_REQUIRES.get(status, (None, ""))
    if field is None or packet[field]:
        return problems
    if status == "cap-reached" and field not in raw:
        absence = "missing"
    problems.append(f"status is {status} but {field} is {absence}")
    return problems


def validate(raw):
    """Typed packet from the raw fields. Raises PacketError listing every problem; never guesses a missing field."""
    packet, problems = read_header(raw)

    trailer = [raw.get("trailer", "")]
    for key in LIST_KEYS:
        lead, entries = read_list(raw.get(key, ""))
        packet[key] = normalize_items(key, entries)
        if lead:
            trailer.append(lead)
    packet["trailer"] = "\n".join(part for part in trailer if part).strip()

    problems += item_problems(raw, packet) + status_problems(raw, packet)
    if problems:
        raise PacketError(problems)
    return packet


def load(message):
    """parse then validate. PacketError carries the raw message."""
    try:
        return validate(parse(message))
    except PacketError as error:
        error.raw = message
        raise


# ---------- rendering ----------

def receipt_is_missing(closure):
    if not closure:
        return True
    return re.fullmatch(r"(none|n/a)?[\s.]*", closure.strip().lower()) is not None


def skipped_line(item):
    if item.get("from_text"):
        return f"- {item['item']}"
    return f"- {item_text(item, 'item', 'finding', 'file_line')}: {item.get('reason', 'no reason given')}"


def remaining_line(item):
    return f"- [{item.get('disposition', 'open')}] {item_text(item, 'finding', 'file_line')}"


def render_items(lines, heading, items, item_line):
    if not items:
        return
    lines.append(f"### {heading}")
    lines += [item_line(item) for item in items]


def fixed_paths(packet):
    """Every path the packet's fixed[] entries name, once each, in order."""
    paths = []
    for item in packet["fixed"]:
        paths += [path for path in entry_paths(item) if path not in paths]
    return paths


def unreviewed_fix_section(packet):
    """The (heading, lines) section for a clean hand-back whose last step was a coder: no reviewer read that fix."""
    named_paths = ", ".join(fixed_paths(packet)) or "none named in fixed[]"
    return ("Last fix not reviewed",
            [f"- No reviewer ran after the loop's last fix. Its files are among: {named_paths}"])


def render(packet, skill, sections=()):
    """The user-facing text. `sections` are (heading, lines) pairs placed before the trailer."""
    lines = ["### Fixed"]
    fixed = sorted(packet["fixed"], key=lambda item: not is_blocker(item))
    for item in fixed:
        lines.append(f"- {'[blocker] ' if is_blocker(item) else ''}{item_text(item, 'finding', 'file_line')}")
    if not fixed:
        lines.append("- none")

    closure = packet["class_closure"]
    if skill == "review" or closure:
        lines.append(f"Class closure: {closure or 'MISSING'}")
        owes_receipt = bool(fixed) or not closure
        if skill == "review" and packet["status"] == "converged" and owes_receipt and receipt_is_missing(closure):
            lines.append("The class-closure receipt is missing or names no repaired finding. Do not present this "
                         "run as clean.")
    if packet["full_check"].startswith("not run"):
        lines.append("Full check: " + packet["full_check"])
    load_bearing = packet["load_bearing_clean"]
    if load_bearing and load_bearing.lower() not in ("none", "omitted"):
        lines.append("Load-bearing: " + load_bearing)

    render_items(lines, "Skipped as false positives", packet["skipped_fp"], skipped_line)
    if packet["nit"]:
        lines.append("### Nits")
        lines.append("- " + "; ".join(item_text(item, "finding", "item") for item in packet["nit"]))
    remaining_heading = "Deferred to branch exit" if packet["status"] == "deferred" else "Findings remaining"
    render_items(lines, remaining_heading, packet["findings_remaining"], remaining_line)
    for heading, section_lines in sections:
        lines.append(f"### {heading}")
        lines += section_lines
    if packet["trailer"]:
        lines.append(packet["trailer"])
    return "\n".join(lines)


# ---------- per-session store ----------

def store_dir():
    override = os.environ.get("HANDBACK_STORE_DIR")
    return pathlib.Path(override) if override else pathlib.Path.home() / ".claude" / "state" / "handback"


def session_file(session_id):
    safe = re.sub(r"[^\w.-]", "_", str(session_id))
    if not safe.strip("._"):
        raise ValueError("session id is empty")
    return store_dir() / (safe + ".jsonl")


def prune_stale():
    cutoff = time.time() - STALE_STORE_SECONDS
    directory = store_dir()
    if not directory.is_dir():
        return
    for path in directory.glob("*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def record(session_id, kind, **fields):
    """Append one row to the session's own file. Other sessions' files are never touched."""
    row = {"kind": kind, "ts": time.time(), "session_id": session_id, **fields}
    prune_stale()
    script_utils.append_jsonl(session_file(session_id), row)
    return row


def latest(session_id):
    """{"dispatch": last review-loop dispatch row or None, "handback": last hand-back row or None, "stop": the last
    review-loop stop row after the last dispatch or None, "unanswered": the number of dispatches after the last
    hand-back (all of them when there is none), "pending": unanswered > 0}. A hand-back clears every dispatch before
    it, so a dispatch that another hook denied blocks nothing once a later dispatch hands back. A row holds kind, ts,
    session_id; a dispatch row also no_review and repo (the top level of the repo it reviews, or None); a hand-back
    row also agent_id, status, problems, message, no_reviewer, unreviewed_fix; a stop row also agent_id,
    open_dispatches (the background agents and shells the loop still waited on when it stopped) and ask_rows. A
    stop the gate blocked is not a stop: the loop went on, so such a row is skipped. Rows are ordered by append, not by
    clock."""
    standing = {"dispatch": None, "handback": None, "stop": None, "unanswered": 0, "pending": False}
    if not session_id:
        return standing
    try:
        stored_rows = script_utils.read_jsonl(session_file(session_id))
    except ValueError:
        return standing
    for row in stored_rows:
        if row.get("kind") == "dispatch":
            standing["dispatch"] = row
            standing["stop"] = None
            standing["unanswered"] += 1
        elif row.get("kind") == "stop" and not row.get("blocked"):
            standing["stop"] = row
        elif row.get("kind") == "handback":
            standing["handback"] = row
            standing["unanswered"] = 0
    standing["pending"] = standing["unanswered"] > 0
    return standing


def stop_rows_after(session_id, agent_id, since):
    """The stop rows of agent_id written at or after `since`, blocked or not, in append order."""
    if not session_id:
        return []
    try:
        stored_rows = script_utils.read_jsonl(session_file(session_id))
    except ValueError:
        return []
    return [row for row in stored_rows
            if row.get("kind") == "stop" and row.get("agent_id") == agent_id and row.get("ts", 0) >= since]


def settled_stop_row(session_id, agent_id, since):
    """The newest stop row of agent_id written at or after `since` that the gate did not block, or None. The hand-back
    row lands before the stop row of the same loop, so a reader of the hand-back looks here for the stop that
    follows it."""
    settled = [row for row in stop_rows_after(session_id, agent_id, since) if not row.get("blocked")]
    return settled[-1] if settled else None


NO_DISPATCH = "no-dispatch"
NO_HANDBACK = "no-handback"
REDISPATCHED = "redispatched"
LOOP_WAITING = "loop-waiting"


def hand_back_gap(seen):
    """Why the session has no current hand-back, from a `latest` result: NO_DISPATCH (the session never dispatched a
    review-loop), LOOP_WAITING (the loop's latest stop left a background agent or shell running, so it will resume and
    may still hand back), NO_HANDBACK (dispatched, nothing came back), REDISPATCHED (dispatched again after a
    hand-back), or None when the latest hand-back is current. The one rule that /review, /fix and the commit gate
    share."""
    if seen["dispatch"] is None:
        return NO_DISPATCH
    if seen["handback"] is not None and not seen["pending"]:
        return None
    if seen["stop"] is not None and seen["stop"].get("open_dispatches", 0) > 0:
        return LOOP_WAITING
    if seen["handback"] is None:
        return NO_HANDBACK
    return REDISPATCHED


def false_clean_reason(session_id):
    """Why `review-gate-mark clean` is refused for the session, or None when its latest review-loop hand-back is
    current and converged or deferred. Takes the hook event's session_id, the value of CLAUDE_CODE_SESSION_ID in a Bash
    call. An empty session id is refused."""
    seen = latest(session_id)
    gap = hand_back_gap(seen)
    if gap == LOOP_WAITING:
        return "the review-loop is waiting on a background agent or shell it started and has not handed back"
    if seen["handback"] is None:
        return "no review-loop hand-back is stored for this session"
    if gap == NO_DISPATCH:
        return "a hand-back is stored but this session has no review-loop dispatch on record"
    if gap == REDISPATCHED:
        return "the review-loop was dispatched again and has not handed back"
    status = seen["handback"].get("status")
    if status not in CLEAN_STATUSES:
        return f"the latest review-loop hand-back is {status}"
    if seen["handback"].get("no_reviewer"):
        return "the review-loop handed back clean with no reviewer run"
    return None


def loop_steps(session_id, agent_id):
    """The review-loop agent `agent_id`'s coder and reviewer dispatches, in order. Coders resumed with SendMessage are
    not counted: the hook sees only the recipient's id, not its type."""
    stored_rows = script_utils.read_jsonl(session_file(session_id))
    return [row["step"] for row in stored_rows if row.get("kind") == "step" and row.get("agent_id") == agent_id]


def unreviewed_streak(session_id):
    """How many of the session's latest hand-backs in a row were clean with no reviewer run. 0 when the latest one had
    a reviewer."""
    stored_rows = script_utils.read_jsonl(session_file(session_id))
    hand_backs = [row for row in stored_rows if row.get("kind") == "handback"]

    streak = 0
    for row in reversed(hand_backs):
        if not row.get("no_reviewer"):
            break
        streak += 1
    return streak


def ended_on_unreviewed_fix(session_id, agent_id):
    """True when the latest stored hand-back of `agent_id` was clean and its last step was a coder after a reviewer."""
    stored_rows = script_utils.read_jsonl(session_file(session_id))
    hand_backs = [row for row in stored_rows if row.get("kind") == "handback" and row.get("agent_id") == agent_id]
    return bool(hand_backs) and bool(hand_backs[-1].get("unreviewed_fix"))


def claim_no_review(session_id, agent_id):
    """True when `agent_id` is exempt from the reviewer rule: it was exempted before, or the session holds more
    no-review dispatches than exemptions, and this claims one. A dispatch row has no agent id, so a normal loop that
    skips review while an unclaimed no-review loop runs in parallel can take that exemption."""
    stored_rows = script_utils.read_jsonl(session_file(session_id))
    exempted = [row for row in stored_rows if row.get("kind") == "no-review-exempt"]
    if any(row.get("agent_id") == agent_id for row in exempted):
        return True
    no_review_dispatches = [row for row in stored_rows if row.get("kind") == "dispatch" and row.get("no_review")]
    if len(no_review_dispatches) <= len(exempted):
        return False
    record(session_id, "no-review-exempt", agent_id=agent_id)
    return True


def was_recorded(session_id, agent_id, kind):
    """True when the session's file holds a row of this kind from this agent."""
    stored_rows = script_utils.read_jsonl(session_file(session_id))
    return any(row.get("kind") == kind and row.get("agent_id") == agent_id for row in stored_rows)


# ---------- hook ----------

def deny_line(reason):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}})


ALREADY_DELIVERED_REASON = ("Your report was already delivered; a second hand-back cannot reach the caller. Use "
                            "SendMessage for anything further, then stop.")
UNCHECKED_KIND = "unchecked-code"


def last_unchecked_step(session_id, agent_id):
    """The last code step the hook saw when it denied agent_id for an unchecked change, or None."""
    stored_rows = script_utils.read_jsonl(session_file(session_id))
    steps = [row.get("last_code_step", 0) for row in stored_rows
             if row.get("kind") == UNCHECKED_KIND and row.get("agent_id") == agent_id]
    return max(steps, default=None)


def unchecked_code_reason(event, session_id, agent_id, message):
    """The deny reason when the loop's own transcript shows no full check after its last code change, else None.
    The denial is recorded with the last code step it saw and repeats only after a later code change, so a loop that
    hands back again on the same state passes. A transcript that cannot be read never blocks."""
    try:
        import review_loop_gate  # imports this module at its top, so it loads here, not at ours
        transcript = review_loop_gate.LoopTranscript(script_utils.agent_transcript_path(event))
        in_ci = review_loop_gate.full_suite_in_ci(transcript, event.get("cwd"))
        ungated, _open_dispatches = review_loop_gate.scan(transcript, message, in_ci)
        last_step = review_loop_gate.last_code_step(transcript)
    except Exception as error:
        print(f"handback hook: full-check gate skipped, {type(error).__name__}: {error}", file=sys.stderr)
        return None
    if not ungated:
        return None
    denied_at = last_unchecked_step(session_id, agent_id)
    if denied_at is not None and last_step <= denied_at:
        return None
    record(session_id, UNCHECKED_KIND, agent_id=agent_id, last_code_step=last_step)
    return review_loop_gate.GATE_REASON


def handle_dispatch(event, session_id, tool_input):
    """Record a review-loop dispatch, or a coder or reviewer step inside one."""
    subagent_type = str(tool_input.get("subagent_type") or "")
    if event.get("agent_type") == REVIEW_LOOP:
        step = "coder" if script_utils.CODERS.match(subagent_type) else "reviewer"
        if step == "coder" or script_utils.REVIEWERS.match(subagent_type):
            record(session_id, "step", agent_id=event.get("agent_id") or "unknown", step=step)
    elif subagent_type == REVIEW_LOOP:
        prompt = str(tool_input.get("prompt") or "")
        record(session_id, "dispatch", no_review=NO_REVIEW_MODE.search(prompt) is not None,
               repo=reviewed_repo(prompt, event.get("cwd")))


def reviewed_repo(prompt, cwd):
    """The top level of the repo a review-loop dispatch reviews, by the rule the loop itself follows: the prompt's
    `repo:` line, read from cwd, else the first absolute path the prompt names, else cwd. None when that lies in no
    work tree."""
    named = REPO_LINE.search(prompt)
    first_path = ABSOLUTE_PATH.search(prompt)
    if named:
        directory = os.path.join(cwd or "", os.path.expanduser(named.group(1)))
    elif first_path:
        directory = script_utils.nearest_existing_folder(first_path.group(0))
    else:
        directory = cwd
    if not directory:
        return None
    top = script_utils.repo_root(directory, timeout=GIT_TIMEOUT_SECONDS)
    return str(top) if top else None


def handle_hook(event, kind):
    """Record a review-loop dispatch or hand-back. Returns a deny reason, else None: ALREADY_DELIVERED_REASON for an
    agent whose report is stored, the parse problems for a bad packet seen the first time from its agent, the
    unreviewed reason for a clean packet with no reviewer run, or review_loop_gate.GATE_REASON when no full check ran
    after the last code change."""
    session_id = event.get("session_id")
    if not session_id:
        return None
    tool_input = event.get("tool_input") or {}
    if kind == "dispatch":
        handle_dispatch(event, session_id, tool_input)
        return None
    if kind != "handback" or event.get("agent_type") != REVIEW_LOOP:
        return None
    message = str(tool_input.get("message", ""))
    agent_id = event.get("agent_id") or "unknown"
    if was_recorded(session_id, agent_id, "handback"):
        return ALREADY_DELIVERED_REASON
    try:
        packet = load(message)
        status, problems = packet["status"], []
    except PacketError as error:
        status, problems = "invalid", error.problems
    if problems and not was_recorded(session_id, agent_id, "rejected"):
        record(session_id, "rejected", agent_id=agent_id, problems=problems)
        return ("The review-loop packet does not parse: " + "; ".join(problems) +
                ". Fix the packet to the schema in your instructions and hand back again.")
    steps = loop_steps(session_id, agent_id)
    unreviewed = (status in CLEAN_STATUSES and "reviewer" not in steps
                  and not claim_no_review(session_id, agent_id))
    if unreviewed and not was_recorded(session_id, agent_id, "unreviewed"):
        record(session_id, "unreviewed", agent_id=agent_id)
        return ("This review-loop hand-back is clean but no reviewer ran. Dispatch the code-reviewer on the diff, fix "
                "what it finds, then hand back again.")
    unchecked_reason = unchecked_code_reason(event, session_id, agent_id, message)
    if unchecked_reason:
        return unchecked_reason

    unreviewed_fix = (status in CLEAN_STATUSES and "reviewer" in steps
                      and steps[-1:] == ["coder"])
    record(session_id, "handback", agent_id=agent_id, status=status, problems=problems, message=message,
           no_reviewer=unreviewed, unreviewed_fix=unreviewed_fix)
    return None


def command_hook(argv):
    """Never blocks on its own error."""
    try:
        if argv not in (["dispatch"], ["handback"]):
            print(f"handback hook: unknown kind {' '.join(argv)!r}; want dispatch or handback", file=sys.stderr)
            return 0
        reason = handle_hook(json.load(sys.stdin), argv[0])
        if reason:
            print(deny_line(reason))
    except Exception as error:
        print(f"handback hook: {error}", file=sys.stderr)
    return 0


def command_check():
    message = sys.stdin.read()
    try:
        packet = load(message)
    except PacketError as error:
        print("handback check: the packet does not parse:", file=sys.stderr)
        for problem in error.problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"ok: status={packet['status']} fixed={len(packet['fixed'])} ask={len(packet['ask'])}")
    return 0


def main(argv):
    if argv[:1] == ["check"]:
        return command_check()
    if argv[:1] == ["hook"]:
        return command_hook(argv[1:])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
