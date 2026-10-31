---
type: "Change"
change_type: "added"
title: "Press Enter in herdr panes stuck at the usage-limit reset prompt"
description: "A two-minute timer presses Enter in a Claude pane that shows the usage-limit reset prompt, so a worker the laptop slept past the reset continues within minutes instead of sitting idle."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T15:24:52-05:00"}
seq: 1
kind: "fix"
components: ["script/herdr-wake-limited"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_wake_limited.py::HerdrWakeLimitedTest::test_a_pane_at_the_reset_prompt_gets_one_enter_and_one_log_line"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/.local/bin/herdr-wake-limited`: lists claude agents that herdr reports idle or done, reads each
  pane's visible screen, and presses Enter when the last six non-empty lines hold both `Your usage limit has reset`
  and `Press enter to continue`. Lines are joined before the match, so a wrapped phrase still matches. Each wake
  prints one line and appends one log line under `${XDG_STATE_HOME:-~/.local/state}`. No herdr answer exits 0.
- New `install/herdr-wake-limited`: runs it every 2 minutes (macOS LaunchAgent, Linux systemd user timer). It
  points at the stowed `~/.local/bin` link and skips when herdr or herdr-api is absent.
- `CLAUDE.md` lists the installer.

## Evidence

judgment: Claude Code continues by itself at a usage-limit reset, except when the machine slept more than about 30
minutes across the reset. Then the pane waits at a press-enter prompt that herdr reports as idle. One worker sat
there about 18 hours.

## Result

The named test fails before (no script) and passes after, with 11 more cases: other panes, working or blocked panes,
a quoted prompt above the bottom lines, a wrapped prompt, a failed send-keys, an unwritable log, no herdr, `--help`.
Full suite: 4995 tests, 0 failed.

## Watch

None. The log file names every wake.

## Back-out

Run `systemctl --user disable --now herdr-wake-limited.timer` (or unload the LaunchAgent), delete the unit files,
then delete the script, the installer, the test and the `CLAUDE.md` line.
