"""A toolkit script finds its sibling code (scripts, hooks, agents, skills) from its own file location, never from
the home folder, so a script edited in a worktree runs the worktree's siblings. State, logs and settings stay
under the home folder.

The rule is broad: a code line that holds a home reference and `.claude` is a hit unless the path after `.claude`
is a data path. Each remaining hit is printed text or a deliberate check of the live install, and has an entry in
ALLOWED_HITS."""
import pathlib
import re
import unittest

import toolkit_paths

TREE_CLAUDE_DIR = pathlib.Path(__file__).resolve().parents[2] / "claude" / ".claude"
SCANNED_FOLDERS = ("scripts", "hooks", "skills", "commands", "rules")

HOME_REFERENCE = re.compile(r"~|home|expanduser|getenv", re.IGNORECASE)
CLAUDE_FOLDER = re.compile(r"\.claude(?![\w-])")
# What follows `.claude`: an optional closing quote, then optionally a separator (slash, comma or plus) and the next
# path segment. No segment means the line names the `.claude` folder itself.
NEXT_SEGMENT = re.compile(r"""["']?\s*(?:[/,+]\s*["']?\s*/?\s*([\w.\-]*))?""")
DATA_SEGMENTS = {"state", "logs", "projects", "settings.json", "settings.local.json"}
DATA_SUFFIXES = (".jsonl", ".json", ".log", ".lock")


def is_data_segment(segment):
    return segment in DATA_SEGMENTS or segment.endswith(DATA_SUFFIXES)


def locates_code_through_home(line):
    code = line.strip()
    if code.startswith("#") or not HOME_REFERENCE.search(code):
        return False
    for claude_folder in CLAUDE_FOLDER.finditer(code):
        segment = NEXT_SEGMENT.match(code, claude_folder.end()).group(1) or ""
        if not is_data_segment(segment):
            return True
    return False


# Each entry is (file under claude/.claude, a substring of the hit line, why the hit is allowed). A hit with no entry
# fails the test, and an entry that matches no hit fails it too.
PRINTED = "command or message printed to a person, not a lookup"
LIVE_AGENTS = "reads the user's own agent definitions for the live session; its tests build that home in a temp dir"
DATA_FILE = "data file under the home folder"
LEDGER_DIR = "makes the folder that holds the ledger files"
ALLOWED_HITS = [
    ("scripts/code/code_step_core.py", "INSTALLED_COMMAND = ", PRINTED),
    ("scripts/code/code_step_core.py", "RESUME_LINE = ", PRINTED),
    ("scripts/gates/agent_model_guard.py", "home_file = ", LIVE_AGENTS),
    ("scripts/gates/calibration_refs_guard.py", "calibration_path = ", LIVE_AGENTS),
    ("scripts/gates/calibration_refs_guard.py", "agents_dir = ", LIVE_AGENTS),
    ("scripts/gates/emit_orchestration.py", "SessionStart hook: inject", "docstring text"),
    ("scripts/gates/emit_orchestration.py", "MISSING_WARNING = ", PRINTED),
    ("scripts/gates/emit_orchestration.py", "os.path.join(os.environ.get", "injects the user's own rules file"),
    ("scripts/lib/script_utils.py", "Installed as ~/.claude/scripts/lib/script_utils.py", "docstring text"),
    ("scripts/lib/script_utils.py", "under ~/.claude, where the ledger's readers", PRINTED),
    ("scripts/review/review_fix.py", "DECIDE_SCRIPT = ", PRINTED),
    ("scripts/review/review_fix.py", "MARK_CLEAN = ", PRINTED),
    ("scripts/review/review_fix.py", "MARK_DIRTY = ", PRINTED),
    ("scripts/review/review_fix.py", "After the user answers, run once", PRINTED),
    ("scripts/review/review_loop_gate.py", "handoff-block.md and dispatch again", PRINTED),
    ("scripts/telemetry/log-escape", "Run the ratchet (", PRINTED),
    ("scripts/telemetry/log-escape-check", 'mkdir -p "$HOME/.claude"', LEDGER_DIR),
    ("scripts/telemetry/log_agent_usage.py", "os.path.join(os.environ.get", DATA_FILE + ", name on the next line"),
    ("scripts/telemetry/log_skill_use.py", "os.path.join(os.environ.get", DATA_FILE + ", name on the next line"),
    ("scripts/tools/claude-doctor.sh", "CLAUDE.md is newer than opencode", PRINTED),
    ("scripts/tools/claude-doctor.sh", "shellcheck reported issues", PRINTED),
    ("scripts/tools/rule-anchors.sh", 'rel="${rel#"$HOME"/.claude/}"', "strips the home prefix to print a path"),
    ("skills/cc/claude-comments-consume", "REVIEW_FILE=", DATA_FILE + " (claude-comments.md)"),
    ("skills/review/log-perf-finding", "out=", DATA_FILE + " (backend-perf-findings.md)"),
    ("skills/review/log-review-check", 'mkdir -p "$HOME/.claude"', LEDGER_DIR),
    ("skills/review/log-review-check", "fallback_lines()", "names ledger data files under a fallback home"),
    ("skills/review/log-review-check", 'wc -l <"$fallback_home', "reads ledger data files under a fallback home"),
    ("skills/review/log-review-check", "row appended to $fallback_home", PRINTED),
    ("skills/review/log-review-check", '[ ! -e "$HOME/.claude/$retired" ]', "checks a retired data file is absent"),
    ("skills/review/review-scope-check", 'mkdir -p "$fakehome/.claude"', "builds a temp home for the check"),
]


def scanned_files():
    for folder in SCANNED_FOLDERS:
        for path in sorted((TREE_CLAUDE_DIR / folder).rglob("*")):
            if not path.is_file() or path.suffix == ".md" or "__pycache__" in path.parts:
                continue

            relative = path.relative_to(TREE_CLAUDE_DIR).as_posix()
            if relative in toolkit_paths.WORK_HOOKS:
                continue
            yield path


def hits_in_tree():
    hits = []
    for path in scanned_files():
        relative = path.relative_to(TREE_CLAUDE_DIR).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if locates_code_through_home(line):
                hits.append((relative, number, line.strip()))
    return hits


class LocateCodeThroughHomeRuleTest(unittest.TestCase):
    def test_the_rule_flags_home_lookups_and_spares_data_paths(self):
        cases = [
            ('CLAUDE_DIR = pathlib.Path(os.environ.get("X", pathlib.Path.home() / ".claude"))', True),
            ('HOME_CLAUDE = pathlib.Path.home() / ".claude"', True),
            ('s = pathlib.Path.home() / ".claude" / "scripts" / "lib"', True),
            ('s = os.path.join(os.environ["HOME"], ".claude", "skills", "x")', True),
            ('source "$HOME/.claude/scripts/lib/_kv.sh"', True),
            ('agents = home + "/.claude/agents"', True),
            ('s = os.path.expanduser("~/.claude/scripts/x")', True),
            ("source ~/.claude/scripts/lib/_kv.sh", True),
            ('. "$HOME/.claude/scripts/lib/_kv.sh"', True),
            ("[ -x ~/.claude/scripts/tools/branch-base ] && run", True),
            ('base="${CLAUDE_DIR:-$HOME/.claude}"', True),
            ('root = os.path.join(os.environ["HOME"], ".claude")', True),
            ('commands = home + "/.claude/commands"', True),
            ('s = join(homedir(), ".claude", "skills", "review", "x")', True),
            ("bash ~/.claude/scripts/tools/x --flag", True),
            ('CLAUDE="$HOME/.claude"', True),
            ('root = os.environ["HOME"] + "/.claude"', True),
            ('root = Path(os.environ["HOME"]) / ".claude"', True),
            ('s = Path("~").expanduser() / ".claude" / "scripts"', True),
            ('root = os.path.join(os.path.expanduser("~"), ".claude")', True),
            ('root = os.getenv("HOME") + "/.claude/hooks"', True),
            ('log = pathlib.Path.home() / ".claude" / "review-findings.jsonl"', False),
            ('log = pathlib.Path.home() / ".claude" / "skills-usage.jsonl"', False),
            ('state = pathlib.Path.home() / ".claude" / "state" / "handback"', False),
            ('lock = os.path.join(home, ".claude", "calibration-lock.json")', False),
            ('out="${X:-$HOME/.claude/backend-perf.log}"', False),
            ('cfg = Path.home() / ".claude" / "settings.json"', False),
            ('d = Path.home() / ".claude" / "projects" / name', False),
            ('d = "$HOME/.claude/logs/run.txt"', False),
            ('s = pathlib.Path.home() / ".claude" / "skills-extra"', True),
            ("# reads $HOME/.claude/scripts/x", False),
            ('name = "no home folder named here"', False),
        ]
        for line, flagged in cases:
            with self.subTest(line=line):
                self.assertEqual(flagged, locates_code_through_home(line))


class ToolkitSelfLocationTest(unittest.TestCase):
    def test_every_home_lookup_of_toolkit_code_is_allowed_by_name(self):
        offenders = []
        for relative, number, line in hits_in_tree():
            allowed = any(file == relative and substring in line for file, substring, _ in ALLOWED_HITS)
            if not allowed:
                offenders.append(f"{relative}:{number}: {line}")

        self.assertEqual([], offenders, "find sibling code through Path(__file__).resolve(), not the home folder")

    def test_every_allowlist_entry_matches_a_hit(self):
        hits = hits_in_tree()
        stale = [
            f"{file}: {substring}"
            for file, substring, _ in ALLOWED_HITS
            if not any(file == relative and substring in line for relative, _, line in hits)
        ]

        self.assertEqual([], stale, "remove the allowlist entries that match no line")


if __name__ == "__main__":
    unittest.main()
