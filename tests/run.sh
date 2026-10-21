#!/usr/bin/env bash
# Runs every unit test under tests/, one process per test file, nproc at a time. Exits non-zero on any failure.
set -euo pipefail

repoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repoRoot"

python3 "$repoRoot/tests/parallel_tests.py"
