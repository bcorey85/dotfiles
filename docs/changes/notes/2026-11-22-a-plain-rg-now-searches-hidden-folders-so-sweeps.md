---
type: "Change"
change_type: "fixed"
title: "A plain rg now searches hidden folders, so sweeps over claude/.claude stop reporting false clean"
description: "A stowed ripgrep config turns on hidden files and RIPGREP_CONFIG_PATH reaches every zsh, so a plain rg sweep finds files under claude/.claude."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T15:12:29-06:00"}
seq: 23
kind: "fix"
components: ["method/rg-hidden-sweep"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_ripgrep_config.py::RipgrepConfigTest::test_config_finds_word_under_hidden_folder_and_skips_git"
asked: ""
proof: []
unmeasured: "the intake has no count of rg sweeps that missed a hidden file"
---

## Change

A plain `rg word claude opencode tests` skipped hidden folders, so a sweep over `claude/.claude` reported clean while stale references sat there. A new `ripgrep` stow package links `~/.config/ripgrep/config` (`--hidden`, `--glob=!.git`), and the `zsh` package now stows `~/.zshenv`, which exports `RIPGREP_CONFIG_PATH`. The export sits in `.zshenv`, not `.zshrc`: `.zshrc` is read only by interactive shells, while `.zshenv` is read by every zsh, including the non-interactive shells that Claude Code's Bash tool and hooks start.

## Evidence

Blast radius: no toolkit script, hook or test starts `rg` as a subprocess. Every `rg` in `claude/.claude/scripts` (`rg_path_gate.py`, `batch_reads_nudge.py`, `check_scope.py`, `criteria_dry_run.py`, `criteria_verdict.py`, `bash-safety-gate.sh`) only parses command text that names rg, so `--hidden` changes none of their results. Tests that name rg do so in command strings they parse. The one live effect is the criteria and plan check commands that a session itself runs with a bare `rg`: they now also match hidden folders.

## Result

`test_config_finds_word_under_hidden_folder_and_skips_git` fails without the config (`test_plain_rg_without_config_skips_hidden_folder` shows the miss) and passes with it; `test_zshenv_exports_config_path_to_non_interactive_zsh` shows a non-interactive zsh gets the variable.

## Watch

None: no intake number reads missed hidden-file matches.

## Back-out

Delete `zsh/.zshenv`, the `ripgrep` package and its entry in `install/stow`.
