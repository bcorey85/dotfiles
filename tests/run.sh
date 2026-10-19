#!/usr/bin/env bash
# Runs every unit test under tests/. Exits non-zero on any failure.
set -euo pipefail

repoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repoRoot"

python3 -m unittest discover -s tests/scripts -p 'test_*.py' -v
