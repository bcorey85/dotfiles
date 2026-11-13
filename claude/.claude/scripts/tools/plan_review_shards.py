"""Cut a long plan into the two extracts eng-spec's fresh-eyes review dispatches, in a temp folder outside the plan's.

Usage: plan_review_shards.py cut <spec.md>
       plan_review_shards.py clean <shard folder>

`cut` prints the paths to hand the plan-reviewer dispatches, one per line. A plan of at most 400 lines, or one with
fewer than two phases, prints its own path: one dispatch at the whole file. A longer plan prints two paths in a new
temp folder: shard A holds every line outside a phase section plus the phases up to the boundary nearest the midpoint;
shard B holds the same outside lines plus the remaining phases. Each shard ends with a `## Phases in the other extract`
section: a line telling the reviewer not to review those phases and to grep the full plan, whose path it gives, before
raising a gap that spans phases; then one bullet per phase the shard leaves out, in file order, with its title and the
paths its Files entries name (`files: none named` when it has none). A reviewer reads it to tell a gap from work the
other extract does. The section adds no phase section to the shard. A phase id with two sections stops the cut with
exit 1.

`clean` deletes a folder `cut` made, once both hand-backs are written; it refuses any other folder."""
import pathlib
import shutil
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS_DIR / "lib")]
import plan_format

MAX_WHOLE_LINES = 400
SHARD_DIR_PREFIX = "plan-review-shards-"
SHARD_NAMES = ("review-shard-a.md", "review-shard-b.md")
OTHER_EXTRACT_HEADING = "## Phases in the other extract"


def split_index(spans):
    """How many phases go to shard A: the count whose phase lines come nearest half of all phase lines."""
    sizes = [section["end"] - section["start"] for _, section in spans]
    half = sum(sizes) / 2
    return min(range(1, len(sizes)), key=lambda count: abs(sum(sizes[:count]) - half))


def shard_lines(lines, spans, count):
    """(shard A lines, shard B lines): each holds every line outside a phase section, in file order, and its half of
    the phases: the first `count` phases go to shard A, the rest to shard B."""
    owner = {}
    for position, (_, section) in enumerate(spans):
        shard = 0 if position < count else 1
        for index in range(section["start"], section["end"]):
            owner[index] = shard

    shards = ([], [])
    for index, line in enumerate(lines):
        shard = owner.get(index)
        for target in (0, 1):
            if shard is None or shard == target:
                shards[target].append(line)
    return shards


def other_extract_section(plan, lines, omitted):
    """The lines that end a shard: the plan path and one bullet for each omitted (id, section) phase."""
    section_lines = ["", OTHER_EXTRACT_HEADING, "",
                     "These phases are reviewed in the other extract; do not review them here. "
                     f"Before you raise a gap that spans phases, grep the full plan: {plan.resolve()}", ""]
    for phase_id, section in omitted:
        paths = sorted(plan_format.file_entry_paths(lines, section))
        files = ", ".join(f"`{path}`" for path in paths) if paths else "none named"
        title = f": {section['title']}" if section["title"] else ""
        section_lines.append(f"- Phase {phase_id}{title} — files: {files}")
    return section_lines


def cut_shards(plan):
    lines = plan.read_text().splitlines()
    spans, failures = plan_format.phase_spans(lines)
    if failures:
        for failure in failures:
            print(f"{plan}:{failure['line']}: {failure['detail']}", file=sys.stderr)
        return 1

    if len(lines) <= MAX_WHOLE_LINES or len(spans) < 2:
        print(plan)
        return 0

    shard_dir = pathlib.Path(tempfile.mkdtemp(prefix=SHARD_DIR_PREFIX))
    count = split_index(spans)
    omitted_by_shard = (spans[count:], spans[:count])
    shards = shard_lines(lines, spans, count)
    for name, text_lines, omitted in zip(SHARD_NAMES, shards, omitted_by_shard, strict=True):
        text_lines = text_lines + other_extract_section(plan, lines, omitted)
        shard = shard_dir / name
        shard.write_text("\n".join(text_lines) + "\n")
        print(shard)
    return 0


def clean_shards(shard_dir):
    made_by_cut = shard_dir.parent == pathlib.Path(tempfile.gettempdir()) and shard_dir.name.startswith(
        SHARD_DIR_PREFIX)
    if not made_by_cut:
        print(f"{shard_dir}: not a folder plan_review_shards.py cut made; expected "
              f"{tempfile.gettempdir()}/{SHARD_DIR_PREFIX}<id>.", file=sys.stderr)
        return 1
    if not shard_dir.is_dir():
        print(f"{shard_dir}: no such folder; nothing to clean.", file=sys.stderr)
        return 1
    shutil.rmtree(shard_dir)
    return 0


def main(argv):
    if len(argv) != 3 or argv[1] not in ("cut", "clean"):
        print(__doc__, file=sys.stderr)
        return 2
    target = pathlib.Path(argv[2])
    if argv[1] == "cut":
        return cut_shards(target)
    return clean_shards(target)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
