"""Coder packet for one plan phase. Usage: coder_packet.py <plan> <phase number>

Prints the block that /code puts in the coder brief, verbatim: the plan line ranges to read, the acceptance
criteria, the existing files the phase names, the new files it names, one existing sibling per new file, the
files outside the sibling's directory that the sibling imports, and the rest of any test helper directory among
them. The coder reads all of it in its first response and does not explore. When the coder gate is set for the repo,
the rules tell the coder not to run checks."""
import json
import pathlib
import re
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import plan_format
import script_utils

MAX_IMPORTED_FILES = 15
PATH_IN_BACKTICKS = re.compile(r"`([\w.@-]+(?:/[\w.@\[\]()-]+)+\.\w+)(?::\d+(?:-\d+)?)?`")
SCRIPT_IMPORT = re.compile(r"""(?:from|import)\s*\(?\s*['"]([^'"]+)['"]""")
PYTHON_IMPORT = re.compile(r"^from\s+(\.+)([\w.]*)\s+import", re.MULTILINE)
SCRIPT_SUFFIXES = [".ts", ".tsx", ".mts", ".js", ".jsx", ".mjs"]
TEST_HELPER_DIRECTORY = re.compile(r"test|fixture|factor", re.IGNORECASE)
TEST_FILE = re.compile(r"\.(test|spec)\.|^test_|_test\.py$")


def git_output(cwd, *args):
    found = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return found.stdout.strip()


def phase_bounds(plan_lines, phase_number):
    section = plan_format.phase_section(plan_lines, phase_number)
    if section is None:
        sys.exit(f"coder-packet: no Phase {phase_number} heading in the plan")

    headings = [index for index, line in enumerate(plan_lines) if line.startswith("## ")]
    spans, _ = plan_format.phase_spans(plan_lines)
    first_phase = min(span["start"] for _, span in spans)
    return headings, section["start"], section["end"], first_phase


def cited_sections(plan_lines, headings, first_phase, phase_text):
    """Shared sections before the first phase whose heading the phase text names, singular or plural."""
    phase_lower = phase_text.lower()
    shared_headings = [index for index in headings if index < first_phase]
    cited = []
    for position, start in enumerate(shared_headings):
        title = plan_lines[start][3:].strip()
        singular = title[:-1] if title.lower().endswith("s") else title
        if title.lower() not in phase_lower and singular.lower() not in phase_lower:
            continue
        end = shared_headings[position + 1] if position + 1 < len(shared_headings) else first_phase
        cited.append((title, start + 1, end))
    return cited


def named_paths(phase_text, repo_root):
    existing, new = [], []
    for match in PATH_IN_BACKTICKS.finditer(phase_text):
        path = repo_root / match.group(1)
        bucket = existing if path.exists() else new
        if path not in existing and path not in new:
            bucket.append(path)
    return existing, new


def sibling_of(new_file):
    """An existing file with the new file's shape: same name in a sibling directory, the same name with the
    directory name swapped, or the same compound suffix in the same directory."""
    directory, name = new_file.parent, new_file.name
    sibling_directories = sorted(path for path in directory.parent.glob("*") if path.is_dir() and path != directory)

    for sibling_directory in sibling_directories:
        if (sibling_directory / name).is_file():
            return sibling_directory / name

    if directory.name in name:
        for sibling_directory in sibling_directories:
            swapped = sibling_directory / name.replace(directory.name, sibling_directory.name)
            if swapped.is_file():
                return swapped

    compound_suffix = name.split(".", 1)[1] if "." in name else None
    if compound_suffix and directory.is_dir():
        same_shape = sorted(directory.glob(f"*.{compound_suffix}"))
        if same_shape:
            return same_shape[0]
    return None


def alias_targets(source_file, repo_root):
    """Import prefix → directory, from the nearest package.json `imports` and tsconfig.json `paths` that end in `*`."""
    aliases = {}
    package_file = script_utils.nearest_file_upward(source_file.parent, "package.json", repo_root)
    if package_file is not None:
        try:
            subpath_imports = json.loads(package_file.read_text()).get("imports", {})
        except ValueError:
            subpath_imports = {}
        for pattern, target in subpath_imports.items():
            if isinstance(target, dict):
                target = target.get("default") or target.get("import") or next(iter(target.values()), None)
            if isinstance(target, str) and pattern.endswith("*") and target.endswith("*"):
                aliases[pattern[:-1]] = package_file.parent / target[:-1]

    config_file = script_utils.nearest_file_upward(source_file.parent, "tsconfig.json", repo_root)
    if config_file is not None:
        try:
            compiler_options = json.loads(config_file.read_text()).get("compilerOptions", {})
        except ValueError:
            compiler_options = {}
        base_directory = config_file.parent / compiler_options.get("baseUrl", ".")
        for pattern, targets in compiler_options.get("paths", {}).items():
            if pattern.endswith("*") and targets and targets[0].endswith("*"):
                aliases[pattern[:-1]] = base_directory / targets[0][:-1]
    return aliases


def resolve_script_import(base, specifier, aliases):
    prefix = next((prefix for prefix in aliases if specifier.startswith(prefix)), None)
    if prefix is not None:
        target = (aliases[prefix] / specifier[len(prefix):]).resolve()
    elif specifier.startswith("."):
        target = (base / specifier).resolve()
    else:
        return None
    stem = target.with_suffix("") if target.suffix in (".js", ".mjs") else target
    candidates = [target] + [stem.with_name(stem.name + suffix) for suffix in SCRIPT_SUFFIXES]
    candidates += [target / f"index{suffix}" for suffix in SCRIPT_SUFFIXES]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def resolve_python_import(base, dots, module):
    package = base
    for _ in range(len(dots) - 1):
        package = package.parent
    target = package.joinpath(*module.split(".")) if module else package
    candidates = [target.with_suffix(".py"), target / "__init__.py"]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def imports_outside_directory(source_file, repo_root):
    text = source_file.read_text(errors="replace")
    base = source_file.parent
    aliases = alias_targets(source_file, repo_root)
    resolved = [resolve_script_import(base, specifier, aliases) for specifier in SCRIPT_IMPORT.findall(text)]
    resolved += [resolve_python_import(base, dots, module) for dots, module in PYTHON_IMPORT.findall(text)]
    return [path for path in resolved if path is not None and path.parent != base]


def bullet_list(paths, repo_root):
    return "\n".join(f"- {path.relative_to(repo_root)}" for path in paths) or "- none"


plan = pathlib.Path(sys.argv[1]).resolve()
phase_argument = sys.argv[2]
repository_root = pathlib.Path(git_output(plan.parent, "rev-parse", "--show-toplevel"))
plan_file_lines = plan.read_text().splitlines()

plan_headings, phase_start, phase_end, first_phase_line = phase_bounds(plan_file_lines, phase_argument)
phase_section_text = "\n".join(plan_file_lines[phase_start:phase_end])
cited_shared_sections = cited_sections(plan_file_lines, plan_headings, first_phase_line, phase_section_text)

existing_paths, new_paths = named_paths(phase_section_text, repository_root)
patterns = []
for new_path in new_paths:
    sibling = sibling_of(new_path)
    if sibling is not None and sibling not in existing_paths and sibling not in patterns:
        patterns.append(sibling)

held = set(existing_paths) | set(patterns)
imported = []
for pattern_file in list(patterns):
    for imported_file in imports_outside_directory(pattern_file, repository_root):
        if imported_file not in held and imported_file not in imported and len(imported) < MAX_IMPORTED_FILES:
            imported.append(imported_file)

test_helper_directories = sorted({path.parent for path in imported if TEST_HELPER_DIRECTORY.search(path.parent.name)})
for helper_directory in test_helper_directories:
    for helper_file in sorted(helper_directory.iterdir()):
        is_test_file = TEST_FILE.search(helper_file.name)
        if (
            helper_file.is_file()
            and not is_test_file
            and helper_file not in imported
            and len(imported) < MAX_IMPORTED_FILES
        ):
            imported.append(helper_file)

plan_path = plan.relative_to(repository_root)
plan_ranges = [f"- {plan_path} lines {phase_start + 1}-{phase_end} (Phase {phase_argument})"]
plan_ranges += [
    f"- {plan_path} lines {start}-{end} ({title}, cited by the phase)" for title, start, end in cited_shared_sections
]
testing_start = next(
    (index for index in plan_headings if plan_file_lines[index].startswith("## Testing Strategy")), None
)
if testing_start is not None and testing_start >= first_phase_line:
    testing_end = next((index for index in plan_headings if index > testing_start), len(plan_file_lines))
    plan_ranges.append(f"- {plan_path} lines {testing_start + 1}-{testing_end} (Testing Strategy)")
criteria = plan.parent / "acceptance-criteria.md"
if criteria.is_file():
    plan_ranges.append(f"- {criteria.relative_to(repository_root)} (the requirements list)")

gate_path = git_output(repository_root, "rev-parse", "--path-format=absolute", "--git-path", "coder-gate.json")
if pathlib.Path(gate_path).exists():
    check_rule = (
        "4. Do not run typecheck, lint, tests or any other check. When you call SubagentHandback, a hook runs "
        "the checks first and returns any failures to you. Fix them, then call SubagentHandback again."
    )
else:
    check_rule = "4. Run the phase's checks once, after all edits, as your directives say."

print(f"""Packet for Phase {phase_argument}. Paths are relative to {repository_root}.

Plan text to read:
{chr(10).join(plan_ranges)}
The plan's other shared sections are lines 1-{first_phase_line}. Open one only when the phase depends on it.

Existing files the phase names:
{bullet_list(existing_paths, repository_root)}

New files the phase names (you create them):
{bullet_list(new_paths, repository_root)}

Pattern files: an existing sibling of each new file, and the shared files those siblings import. Copy their shape: how \
they are laid out, and how the tests build the app and the data.
{bullet_list(patterns + imported, repository_root)}

Rules for this packet:
1. In your first response, Read every plan range and every file above, in parallel, in that one response.
2. Do not re-read them. Do not explore with cat, rg, grep, ls or find. Open a file outside this packet only for a \
question it does not answer, such as where a field is set or whether a helper already exists.
3. Plan all edits first. Then make them with as many Edit and Write calls per response as you can, in parallel.
{check_rule}""")
