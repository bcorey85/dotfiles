"""Coder packet for one plan phase. Usage: coder-packet.py <plan> <phase number>

Prints the block that /code puts in the coder brief, verbatim: the plan line ranges to read, the acceptance
criteria, the existing files the phase names, the new files it names, one existing sibling per new file, the
files outside the sibling's directory that the sibling imports, and the rest of any test helper directory among
them. The coder reads all of it in its first response and does not explore. When the coder gate is set for the repo, the rules tell the coder not to run checks."""
import json
import pathlib
import re
import subprocess
import sys

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


def phase_bounds(planLines, phaseNumber):
    headings = [index for index, line in enumerate(planLines) if line.startswith("## ")]
    phaseStart = next((index for index in headings if re.match(rf"## Phase {phaseNumber}\b", planLines[index])), None)
    if phaseStart is None:
        sys.exit(f"coder-packet: no '## Phase {phaseNumber}' heading in the plan")

    phaseEnd = next((index for index in headings if index > phaseStart), len(planLines))
    firstPhase = next(index for index in headings if re.match(r"## Phase \d", planLines[index]))
    return headings, phaseStart, phaseEnd, firstPhase


def cited_sections(planLines, headings, firstPhase, phaseText):
    """Shared sections before the first phase whose heading the phase text names, singular or plural."""
    phaseLower = phaseText.lower()
    sharedHeadings = [index for index in headings if index < firstPhase]
    cited = []
    for position, start in enumerate(sharedHeadings):
        title = planLines[start][3:].strip()
        singular = title[:-1] if title.lower().endswith("s") else title
        if title.lower() not in phaseLower and singular.lower() not in phaseLower:
            continue
        end = sharedHeadings[position + 1] if position + 1 < len(sharedHeadings) else firstPhase
        cited.append((title, start + 1, end))
    return cited


def named_paths(phaseText, repoRoot):
    existing, new = [], []
    for match in PATH_IN_BACKTICKS.finditer(phaseText):
        path = repoRoot / match.group(1)
        bucket = existing if path.exists() else new
        if path not in existing and path not in new:
            bucket.append(path)
    return existing, new


def sibling_of(newFile):
    """An existing file with the new file's shape: same name in a sibling directory, the same name with the
    directory name swapped, or the same compound suffix in the same directory."""
    directory, name = newFile.parent, newFile.name
    siblingDirectories = sorted(path for path in directory.parent.glob("*") if path.is_dir() and path != directory)

    for siblingDirectory in siblingDirectories:
        if (siblingDirectory / name).is_file():
            return siblingDirectory / name

    if directory.name in name:
        for siblingDirectory in siblingDirectories:
            swapped = siblingDirectory / name.replace(directory.name, siblingDirectory.name)
            if swapped.is_file():
                return swapped

    compoundSuffix = name.split(".", 1)[1] if "." in name else None
    if compoundSuffix and directory.is_dir():
        sameShape = sorted(directory.glob(f"*.{compoundSuffix}"))
        if sameShape:
            return sameShape[0]
    return None


def nearest_file(start, name, repoRoot):
    for directory in [start, *start.parents]:
        if (directory / name).is_file():
            return directory / name
        if directory == repoRoot:
            return None
    return None


def alias_targets(sourceFile, repoRoot):
    """Import prefix → directory, from the nearest package.json `imports` and tsconfig.json `paths` that end in `*`."""
    aliases = {}
    packageFile = nearest_file(sourceFile.parent, "package.json", repoRoot)
    if packageFile is not None:
        try:
            subpathImports = json.loads(packageFile.read_text()).get("imports", {})
        except ValueError:
            subpathImports = {}
        for pattern, target in subpathImports.items():
            if isinstance(target, dict):
                target = target.get("default") or target.get("import") or next(iter(target.values()), None)
            if isinstance(target, str) and pattern.endswith("*") and target.endswith("*"):
                aliases[pattern[:-1]] = packageFile.parent / target[:-1]

    configFile = nearest_file(sourceFile.parent, "tsconfig.json", repoRoot)
    if configFile is not None:
        try:
            compilerOptions = json.loads(configFile.read_text()).get("compilerOptions", {})
        except ValueError:
            compilerOptions = {}
        baseDirectory = configFile.parent / compilerOptions.get("baseUrl", ".")
        for pattern, targets in compilerOptions.get("paths", {}).items():
            if pattern.endswith("*") and targets and targets[0].endswith("*"):
                aliases[pattern[:-1]] = baseDirectory / targets[0][:-1]
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


def imports_outside_directory(sourceFile, repoRoot):
    text = sourceFile.read_text(errors="replace")
    base = sourceFile.parent
    aliases = alias_targets(sourceFile, repoRoot)
    resolved = [resolve_script_import(base, specifier, aliases) for specifier in SCRIPT_IMPORT.findall(text)]
    resolved += [resolve_python_import(base, dots, module) for dots, module in PYTHON_IMPORT.findall(text)]
    return [path for path in resolved if path is not None and path.parent != base]


def bullet_list(paths, repoRoot):
    return "\n".join(f"- {path.relative_to(repoRoot)}" for path in paths) or "- none"


plan = pathlib.Path(sys.argv[1]).resolve()
phaseNumber = sys.argv[2]
repoRoot = pathlib.Path(git_output(plan.parent, "rev-parse", "--show-toplevel"))
planLines = plan.read_text().splitlines()

headings, phaseStart, phaseEnd, firstPhase = phase_bounds(planLines, phaseNumber)
phaseText = "\n".join(planLines[phaseStart:phaseEnd])
cited = cited_sections(planLines, headings, firstPhase, phaseText)

existing, new = named_paths(phaseText, repoRoot)
patterns = []
for newFile in new:
    sibling = sibling_of(newFile)
    if sibling is not None and sibling not in existing and sibling not in patterns:
        patterns.append(sibling)

held = set(existing) | set(patterns)
imported = []
for pattern in list(patterns):
    for importedFile in imports_outside_directory(pattern, repoRoot):
        if importedFile not in held and importedFile not in imported and len(imported) < MAX_IMPORTED_FILES:
            imported.append(importedFile)

testHelperDirectories = sorted({path.parent for path in imported if TEST_HELPER_DIRECTORY.search(path.parent.name)})
for helperDirectory in testHelperDirectories:
    for helperFile in sorted(helperDirectory.iterdir()):
        isTestFile = TEST_FILE.search(helperFile.name)
        if helperFile.is_file() and not isTestFile and helperFile not in imported and len(imported) < MAX_IMPORTED_FILES:
            imported.append(helperFile)

planPath = plan.relative_to(repoRoot)
planRanges = [f"- {planPath} lines {phaseStart + 1}-{phaseEnd} (Phase {phaseNumber})"]
planRanges += [f"- {planPath} lines {start}-{end} ({title}, cited by the phase)" for title, start, end in cited]
testingStart = next((index for index in headings if planLines[index].startswith("## Testing Strategy")), None)
if testingStart is not None and testingStart >= firstPhase:
    testingEnd = next((index for index in headings if index > testingStart), len(planLines))
    planRanges.append(f"- {planPath} lines {testingStart + 1}-{testingEnd} (Testing Strategy)")
criteria = plan.parent / "acceptance-criteria.md"
if criteria.is_file():
    planRanges.append(f"- {criteria.relative_to(repoRoot)} (the requirements list)")

gatePath = git_output(repoRoot, "rev-parse", "--path-format=absolute", "--git-path", "coder-gate.json")
if pathlib.Path(gatePath).exists():
    checkRule = ("4. Do not run typecheck, lint, tests or any other check. When you call SubagentHandback, a hook runs "
                 "the checks first and returns any failures to you. Fix them, then call SubagentHandback again.")
else:
    checkRule = "4. Run the phase's checks once, after all edits, as your directives say."

print(f"""Packet for Phase {phaseNumber}. Paths are relative to {repoRoot}.

Plan text to read:
{chr(10).join(planRanges)}
The plan's other shared sections are lines 1-{firstPhase}. Open one only when the phase depends on it.

Existing files the phase names:
{bullet_list(existing, repoRoot)}

New files the phase names (you create them):
{bullet_list(new, repoRoot)}

Pattern files: an existing sibling of each new file, and the shared files those siblings import. Copy their shape: how they are laid out, and how the tests build the app and the data.
{bullet_list(patterns + imported, repoRoot)}

Rules for this packet:
1. In your first response, Read every plan range and every file above, in parallel, in that one response.
2. Do not re-read them. Do not explore with cat, rg, grep, ls or find. Open a file outside this packet only for a question it does not answer, such as where a field is set or whether a helper already exists.
3. Plan all edits first. Then make them with as many Edit and Write calls per response as you can, in parallel.
{checkRule}""")
