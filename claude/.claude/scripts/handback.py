#!/usr/bin/env python3
"""handback.py: the one reader of the review-loop hand-back packet, and the per-session store of hand-backs.

  handback.py check < packet            exit 0 and one `ok` line for a packet that parses and validates; exit 1 and the
                                        problems on stderr for a bad one
  handback.py hook [dispatch|handback] < hook event JSON
                                        PreToolUse hook. Matcher Agent records each review-loop dispatch; matcher
                                        SubagentHandback validates and records each review-loop hand-back, and denies a
                                        bad packet once per agent so the loop can repair it. With no argument the kind
                                        comes from the event's tool_name; any other argument does nothing.
  handback.py latest <session id>       print the session's latest dispatch and hand-back rows as JSON

Importers use parse, validate, load, render, record, latest, hand_back_gap and false_clean_reason. The store is one
append-only JSON-lines file per
session under $HANDBACK_STORE_DIR (default ~/.claude/state/handback), keyed by the hook event's session_id, which is
the value of CLAUDE_CODE_SESSION_ID inside a Bash call."""
import json
import os
import pathlib
import re
import sys
import textwrap
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import script_utils
from script_utils import first_number, one_line, unquote

STATUSES = ["converged", "deferred", "plan-impact", "critical-blocker", "cap-reached"]
CLEAN_STATUSES = ("converged", "deferred")
PACKET_KEYS = ["status", "iter", "spec_iter", "fixed", "skipped_fp", "blockers", "findings_remaining", "plan_impact",
               "ask", "class_closure", "files_touched", "nit", "load_bearing_clean", "perf", "smell", "principle"]
LIST_KEYS = ["fixed", "skipped_fp", "blockers", "findings_remaining", "ask", "nit", "perf", "files_touched", "smell"]
SCALAR_KEYS = ("status", "iter", "spec_iter", "load_bearing_clean")
ITEM_KEYS = [
    "disposition",
    "smell",
    "finding_id",
    "finding",
    "file_line",
    "blocker",
    "question",
    "gate",
    "class",
    "reason",
    "item",
    "phase",
    "principle",
]
NONE_VALUE = re.compile(r"^\[\s*\]|^\(?\s*(none|n/a|null)\b", re.I)
BLOCK_INDICATOR = re.compile(r"^[|>][+-]?$")
NUMBERED_ITEM = re.compile(r"^\s*\d+[.)]\s")
ITEM_START = re.compile(r"^\s*(?:-|\d+[.)])\s+", re.M)
CLASSES = ["bug", "smell", "duplication", "complexity", "plan-drift", "test-gap", "weak-assertion", "security", "perf",
           "correctness", "docs", "other"]
REVIEW_LOOP = "review-loop"
DEFAULT_GATE = "code-reviewer"
FENCE_OPEN = "```"
BLOCKER_TEXT = re.compile(r"\[blocker\]|\bblocker\s*[:=]\s*(?:yes|true)\b", re.I)
INLINE_KEY_AT = re.compile(r"(?:^|\n\s*|([,.;|?!)])\s+)(" + "|".join(ITEM_KEYS) + r")\s*:\s*")
KEPT_DELIMITERS = "?!)"
ITEM_KEY_START = re.compile(r"(?:{})\s*:".format("|".join(ITEM_KEYS)))
STALE_STORE_SECONDS = 7 * 86400
FINDING_ID_PATTERN = re.compile(r"[0-9a-f]{16}")


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
    it stays inside its parent item. Chunk 0 is the lead prose before the first marker."""
    markers = list(ITEM_START.finditer(body))
    if not markers:
        return [body]

    def indent_of(marker):
        marker_line = marker.group(0).rsplit("\n", 1)[-1]
        return len(marker_line) - len(marker_line.lstrip())

    shallowest = min(indent_of(marker) for marker in markers)
    top_level = [marker for marker in markers if indent_of(marker) == shallowest]
    chunks = []
    position = 0
    for marker in top_level:
        chunks.append(body[position:marker.start()])
        position = marker.end()
    chunks.append(body[position:])
    return chunks


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


def item_field(item, key, default=""):
    """A mapping entry's field; a plain-text entry has none."""
    return item.get(key, default) if isinstance(item, dict) else default


def ask_finding_id(item):
    """The entry's finding_id when it is an id the ledger writer mints (16 lowercase hex chars); otherwise None.
    A placeholder such as "none logged" or "-", or a damaged id, is not an id."""
    finding_id = item_field(item, "finding_id", None)
    if isinstance(finding_id, str) and FINDING_ID_PATTERN.fullmatch(finding_id.strip()):
        return finding_id.strip()
    return None


def entry_paths(item):
    """Every normalized path that a list entry names: its file_line plus each path:line in its finding text."""
    if not isinstance(item, dict):
        return script_utils.paths_named(item)
    return script_utils.paths_named(item.get("file_line"), item.get("finding"), item.get("item"))


def entry_locations(item):
    """Every (path, line) that a list entry names."""
    if not isinstance(item, dict):
        return [script_utils.split_location(hit) for hit in script_utils.PATH_LINE.findall(str(item))]
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

def validate(raw):
    """Typed packet from the raw fields. Raises PacketError listing every problem; never guesses a missing field."""
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

    packet = {"status": status, "iter": iter_round, "spec_iter": spec_iter,
              "class_closure": raw.get("class_closure", "").strip(),
              "load_bearing_clean": raw.get("load_bearing_clean", "").strip(),
              "plan_impact": raw.get("plan_impact", "").strip()}
    trailer = [raw.get("trailer", "")]
    for key in LIST_KEYS:
        lead, packet[key] = read_list(raw.get(key, ""))
        if lead:
            trailer.append(lead)
    packet["trailer"] = "\n".join(part for part in trailer if part).strip()
    for key, text_key in (("fixed", "finding"), ("findings_remaining", "finding"), ("ask", "question")):
        packet[key] = [entry_from_text(item, text_key) if isinstance(item, str) else item for item in packet[key]]
    for item in packet["ask"]:
        if not isinstance(item, dict):
            continue
        if item.get("from_text"):
            item["finding"] = item["question"]
        elif item.get("finding") and not item.get("question"):
            item["question"] = item["finding"]
        item["gate"] = first_token(item.get("gate")) or DEFAULT_GATE
        ask_class = str(item.get("class") or "").strip()
        if ask_class not in CLASSES:
            item["class"] = "other"
            if ask_class:
                item["class_raw"] = ask_class
    for item in packet["fixed"]:
        if isinstance(item, dict) and not item.get("finding") and item.get("smell"):
            item["finding"] = item["smell"]

    if "fixed" not in raw and status in ("converged", "deferred"):
        problems.append("fixed is missing: the packet must always carry fixed, even as []")
    for item in packet["fixed"]:
        if not (isinstance(item, dict) and item.get("finding")):
            problems.append(f"fixed entry has no finding: {one_line(item, 80)!r}")
    if raw.get("ask", "").strip() and not packet["ask"] and not NONE_VALUE.match(raw["ask"].strip()):
        problems.append(f"ask holds text but yields no ask entries: {one_line(raw['ask'], 80)!r}")
    for item in packet["ask"]:
        if not isinstance(item, dict) or not item.get("question"):
            problems.append(f"ask entry has no question: {one_line(item, 80)!r}")
        elif not item.get("file_line") and not item.get("from_text"):
            problems.append(f"ask entry has no file_line: {one_line(item.get('question'), 80)!r}")
    if status == "plan-impact" and not packet["plan_impact"]:
        problems.append("status is plan-impact but plan_impact is empty")
    if status == "critical-blocker" and not packet["blockers"]:
        problems.append("status is critical-blocker but blockers is empty")
    if status == "cap-reached" and "findings_remaining" in raw and not packet["findings_remaining"]:
        problems.append("status is cap-reached but findings_remaining is empty")
    if status == "cap-reached" and "findings_remaining" not in raw:
        problems.append("status is cap-reached but findings_remaining is missing")
    if status == "deferred" and not packet["findings_remaining"]:
        problems.append("status is deferred but findings_remaining is missing or empty")
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
    load_bearing = packet["load_bearing_clean"]
    if load_bearing and load_bearing.lower() not in ("none", "omitted"):
        lines.append("Load-bearing: " + load_bearing)

    skipped = packet["skipped_fp"]
    if skipped:
        lines.append("### Skipped as false positives")
        lines += [f"- {item_text(item, 'item', 'finding', 'file_line')}: {item.get('reason', 'no reason given')}"
                  if isinstance(item, dict) else f"- {item}" for item in skipped]
    if packet["nit"]:
        lines.append("### Nits")
        lines.append("- " + "; ".join(item_text(item, "finding", "item") for item in packet["nit"]))
    if packet["perf"]:
        lines.append("### Perf findings")
        for item in packet["perf"]:
            principle = item_field(item, "principle")
            lines.append(
                f"- {item_text(item, 'finding', 'file_line')}" + (f"\n  Principle: {principle}" if principle else "")
            )
    if packet["findings_remaining"]:
        lines.append("### Deferred to branch exit" if packet["status"] == "deferred" else "### Findings remaining")
        lines += [f"- [{item.get('disposition', 'open')}] {item_text(item, 'finding', 'file_line')}"
                  if isinstance(item, dict) else f"- {item}" for item in packet["findings_remaining"]]
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
    """{"dispatch": last review-loop dispatch row or None, "handback": last hand-back row or None, "unanswered": the
    number of dispatches after the last hand-back (all of them when there is none), "pending": unanswered > 0}. A
    hand-back clears every dispatch before it, so a dispatch that another hook denied blocks nothing once a later
    dispatch hands back. A row holds kind, ts, session_id; a hand-back row also agent_id, status, problems, message.
    Rows are ordered by append, not by clock."""
    standing = {"dispatch": None, "handback": None, "unanswered": 0, "pending": False}
    if not session_id:
        return standing
    try:
        stored_rows = script_utils.read_jsonl(session_file(session_id))
    except ValueError:
        return standing
    for row in stored_rows:
        if row.get("kind") == "dispatch":
            standing["dispatch"] = row
            standing["unanswered"] += 1
        elif row.get("kind") == "handback":
            standing["handback"] = row
            standing["unanswered"] = 0
    standing["pending"] = standing["unanswered"] > 0
    return standing


NO_DISPATCH = "no-dispatch"
NO_HANDBACK = "no-handback"
REDISPATCHED = "redispatched"


def hand_back_gap(seen):
    """Why the session has no current hand-back, from a `latest` result: NO_DISPATCH (the session never dispatched a
    review-loop), NO_HANDBACK (dispatched, nothing came back), REDISPATCHED (dispatched again after a hand-back), or
    None when the latest hand-back is current. The one rule that /review, /fix and the commit gate share."""
    if seen["dispatch"] is None:
        return NO_DISPATCH
    if seen["handback"] is None:
        return NO_HANDBACK
    if seen["pending"]:
        return REDISPATCHED
    return None


def false_clean_reason(session_id):
    """Why `review-gate-mark clean` is refused for the session, or None when its latest review-loop hand-back is
    current and converged or deferred. Takes the hook event's session_id, the value of CLAUDE_CODE_SESSION_ID in a Bash
    call. An empty session id is refused."""
    seen = latest(session_id)
    gap = hand_back_gap(seen)
    if seen["handback"] is None:
        return "no review-loop hand-back is stored for this session"
    if gap == NO_DISPATCH:
        return "a hand-back is stored but this session has no review-loop dispatch on record"
    if gap == REDISPATCHED:
        return "the review-loop was dispatched again and has not handed back"
    status = seen["handback"].get("status")
    if status not in CLEAN_STATUSES:
        return f"the latest review-loop hand-back is {status}"
    return None


def was_rejected(session_id, agent_id):
    stored_rows = script_utils.read_jsonl(session_file(session_id))
    return any(row.get("kind") == "rejected" and row.get("agent_id") == agent_id for row in stored_rows)


# ---------- hook ----------

def deny_line(reason):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}})


def handle_hook(event, kind=None):
    """Record a review-loop dispatch or hand-back. Returns the deny reason for a bad packet seen the first time from
    its agent, else None."""
    session_id = event.get("session_id")
    if not session_id:
        return None
    tool_input = event.get("tool_input") or {}
    kind = kind or {"Agent": "dispatch", "SubagentHandback": "handback"}.get(event.get("tool_name"))
    if kind == "dispatch":
        if tool_input.get("subagent_type") == REVIEW_LOOP:
            record(session_id, "dispatch")
        return None
    if kind != "handback" or event.get("agent_type") != REVIEW_LOOP:
        return None
    message = str(tool_input.get("message", ""))
    agent_id = event.get("agent_id") or "unknown"
    try:
        status, problems = load(message)["status"], []
    except PacketError as error:
        status, problems = "invalid", error.problems
    if problems and not was_rejected(session_id, agent_id):
        record(session_id, "rejected", agent_id=agent_id, problems=problems)
        return ("The review-loop packet does not parse: " + "; ".join(problems) +
                ". Fix the packet to the schema in your instructions and hand back again.")
    record(session_id, "handback", agent_id=agent_id, status=status, problems=problems, message=message)
    return None


def command_hook(argv):
    """Never blocks on its own error."""
    try:
        if len(argv) > 1 or (argv and argv[0] not in ("dispatch", "handback")):
            print(f"handback hook: unknown kind {' '.join(argv)!r}; want dispatch or handback", file=sys.stderr)
            return 0
        reason = handle_hook(json.load(sys.stdin), argv[0] if argv else None)
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
    if argv[:1] == ["latest"] and len(argv) == 2:
        print(json.dumps(latest(argv[1])))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
