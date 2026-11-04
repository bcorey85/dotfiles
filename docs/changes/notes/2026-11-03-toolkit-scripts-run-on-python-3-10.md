---
type: "Change"
change_type: "fixed"
title: "Toolkit scripts run on Python 3.10"
description: "The review, code and eng-spec scripts no longer crash on a Python 3.10 python3: a TOML file there reads as empty and each caller takes its no-config path."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T19:20:10-06:00"}
seq: 6
kind: "fix"
components: ["script/toml-file", "script/full-check", "script/format-files", "script/pytest-config", "script/worktree-snapshot", "script/full-check-receipt", "script/hook-python"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_toml_file.py::Python310Test::test_every_toolkit_script_imports_without_what_python_3_11_added"
asked: ""
proof: []
unmeasured: "One work machine; no intake number counts the crashed runs."
---

## Change

- New `lib/toml_file.py` `read_toml` is the only tomllib importer. On a Python with no tomllib it prints one stderr note and returns `{}`, as it does for a missing or invalid file. `full_check.py`, `format_files.py` and `pytest_config.py` read TOML through it.
- Other 3.11+ APIs on the same paths: `worktree_snapshot.file_hash` hashes with `hashlib.sha256` in place of `hashlib.file_digest`; `full_check_receipt.append` uses `datetime.timezone.utc` in place of `datetime.UTC`. A syntax sweep at 3.10 (ast `feature_version` and ruff `--target-version py310`) found nothing else.
- `ruff.toml` `target-version` is now `py310` and `hook-python` `MIN_MINOR=10`, so `test_oldest_python_syntax.py` parses every script at 3.10. `extra-standard-library = ["tomllib"]` keeps isort's order for the tests that import it.
- The rule owner list in `scripts/CLAUDE.md` and the lib lists in `docs/toolkit-script-rules.md` name `toml_file.py`.
- Not in scope: the queue item's third bullet (a review-loop resumed by SendMessage after a spend-limit stop returns its handback as a message) is a separate bug and stays open.

## Evidence

On the work machine the default python3 is 3.10. `review_fix.py packet`, `gate_commands.py`, `code_review_start.py` and `plan_check.py` crashed with ModuleNotFoundError: tomllib on every /review and /code run.

## Result

No 3.10 interpreter is installed here, so the test runs a child Python with tomllib blocked and `hashlib.file_digest` and `datetime.UTC` deleted. On the base commit it reports 14 scripts that fail to import (review_fix, gate_commands, code_review_start, plan_check, full_check, check_discovery and others); after the change none fail. `test_a_repo_with_toml_config_takes_the_no_config_path_with_a_note` fails on the base commit and passes after: pyproject options read as none, ruff reads as not configured, the stderr note prints, and `file_hash` works.

## Watch

None.

## Back-out

Restore the three tomllib imports, `hashlib.file_digest` and `datetime.UTC`, delete `lib/toml_file.py`, and set `target-version = "py312"` and `MIN_MINOR=12`.
