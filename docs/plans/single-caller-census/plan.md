# Single-caller census: dead weight a branch adds, listed for the smell-reviewer

A script reads a branch diff and lists three kinds of dead weight the branch added. The review loop's smell-reviewer
prompt and `/refactor` branch-prep carry the list. Scripts live in `claude/.claude/scripts/` (paths below are relative
to it unless they start with `claude/`, `docs/` or `tests/`); tests in `tests/scripts/`, paths from
`tests/scripts/toolkit_paths.py`. Follow `docs/toolkit-script-rules.md` and `claude/.claude/scripts/CLAUDE.md`.

## Scope

- In: a new `lib/single_caller_census.py`, `review/review_loop_prompts.py`, the branch-prep path of
  `claude/.claude/skills/refactor/scripts/refactor_flow.py` (`_print_branch_report` only), their tests.
- Out: `review/review_loop_script.py`, `review/review_loop_packet.py`, the put-back scripts and the simplify section of
  `refactor_flow.py` (other lanes edit them). No SKILL.md or agent prose.
- Python only. Reference counts come from the standard library `ast` over every Python file git lists in the repo.
  jedi, rope and vulture are not installed; pyright is, but answers one symbol per LSP request. A TypeScript file in
  the diff gets a note that it was not read.

## Phase Status

- [ ] Phase 1: `lib/single_caller_census.py` lists the three kinds, with a CLI that prints JSON (risk: medium)
- [ ] Phase 2: the smell-reviewer prompt of the review loop and of branch-prep carries the list (risk: low)

## Phase 1: the census

`lib/single_caller_census.py`, standard library plus `lib/source_text.py` and `lib/script_utils.py`:

- Added lines: `git diff -U0 --no-prefix <base>` of the work tree (base default `HEAD`), read with
  `source_text.parse_unified_diff`, plus every line of each untracked file (`script_utils.untracked_paths`). A git
  failure raises `CensusError` naming the command.
- Index: every `.py` file `script_utils.repo_file_paths` lists that exists, parsed with `ast`. A file that does not
  parse is counted in a note, never skipped silently.
- References of a name: every `ast.Name` in Load context with that id and every `ast.Attribute` with that attr,
  except the def's own name. A reference that is the `func` of an `ast.Call` is a call site.
- Kind `single-caller-forwarder`: a def whose every line the branch added, with no decorator and no dunder name,
  whose body (docstring left out) is one `return` or one expression statement that is a call, and that has exactly
  one reference, a call site.
- Kind `unread-field`: an annotated name (`AnnAssign` with a `Name` target) on an added line in the body of a class
  that subclasses `NamedTuple`, `TypedDict` or `Protocol` or carries a `dataclass` decorator, with no read: no
  `ast.Attribute` in Load context with that attr and no string constant equal to the name anywhere in the index
  (covers `row["field"]`, `.get("field")` and `getattr(x, "field")`).
- Kind `superseded-helper`: an added def F with at least one call site, where each function that calls F also calls
  another branch-touched def H, newer than F, with every argument of the F call among the H call's arguments
  (compared by `ast.dump`). Newer: the newest `git blame` time of H's lines is later than the blame time of F's def
  line; an uncommitted line is newest. The entry names F, H and the callers; the smell-reviewer judges whether H's
  output is the same.
- `census(repo, base="HEAD")` returns a `Census` (entries, notes). Each entry: kind, path, line, name, detail.
  `census_lines(result, paths=None)` gives the prompt lines, filtered to `paths` when given.
- CLI: `single_caller_census.py [--repo DIR] [--base REF]` prints `{"entries": [...], "notes": [...]}`; exit 2 with
  the error on `CensusError`.

Tests: `tests/scripts/test_single_caller_census.py` builds a git repo with a committed base, then a branch commit and
an uncommitted change that add one forwarder called once, one NamedTuple field no code reads, and one helper whose
only caller also calls a newer widened helper with the same argument. The CLI lists exactly three entries, one of
each kind; on the base commit alone (before the branch change) it lists none. Negatives: a forwarder called twice, a
field read through an attribute and one read through a string key, a helper whose caller calls the newer helper with
other arguments.

**File**: `claude/.claude/scripts/lib/single_caller_census.py`
**Test**: `tests/scripts/test_single_caller_census.py`

## Phase 2: the smell-reviewer gets the list

- `review/review_loop_prompts.py` `reviewer_prompt`: for `smell-reviewer` in round one (no fix diff), add the census
  lines of `census(repo, census_base or "HEAD")` filtered to the owned files, under one heading line. A
  `CensusError` adds a line that says the census did not run and why. A new keyword `census_base=""`; the loop's
  call keeps the default (work tree against HEAD), which matches its own default review base.
- `refactor_flow.py` `_print_branch_report`: in work-tree mode, print the census lines for the merge base after the
  shape-clone candidates; with `--head`, print a line that the census reads only the work tree.

Tests: `test_review_loop_prompts.py` (or the existing prompts test file): a smell-reviewer prompt in a repo with a
forwarder lists it; a code-reviewer prompt does not. `test_refactor_flow.py`: branch-prep on a fixture branch prints
the census entry.

**File**: `claude/.claude/scripts/review/review_loop_prompts.py`, `claude/.claude/skills/refactor/scripts/refactor_flow.py`
**Test**: `tests/scripts/test_review_loop_prompts.py`, `tests/scripts/test_refactor_flow.py`
