---
type: "Change"
change_type: "changed"
title: "herdr-phase-change takes a ListAgents session name or a worktree path"
description: "herdr-phase-change now accepts a ListAgents session name or a worktree path as its target, as well as a pane id or herdr agent name."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T18:44:11-06:00"}
seq: 28
kind: "fix"
components: ["script/herdr-phase-change", "script/session-pane"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_herdr_phase_change.py::HerdrPhaseChangeTest::test_a_session_name_or_a_worktree_path_reaches_the_agents_pane"
asked: ""
proof: []
unmeasured: "No count shows how often a prompt was aimed at a session name or a worktree path."
---

## Change

`herdr-phase-change` now turns its target into a pane before it sends anything. A new `resolve` verb in `session_pane.py` does the turning. An existing directory wins over a session of the same name: the one claude agent whose working folder is inside it gives the pane. Otherwise a live ListAgents session name gives the pane of the agent that runs that session. Any other word goes on as given, a pane id or a herdr agent name, as before.

A directory with no claude agent or with several, and a session with no pane, send nothing and exit 1. The message names the directory and lists each `pane_id cwd`, or names the session. A failed `herdr-api agent list` exits 2 and names the call.

## Evidence

The herdr-phase-change tests run the script against a stub herdr API. A session name and a worktree path each send the prompt to the one pane inside that folder, with a second agent outside it present. A directory with two agents, and a session with no pane, send nothing. The session_pane tests cover each resolve outcome.

## Result

The herdr-phase-change and session_pane tests pass, and lint passes.

## Watch

A prompt that lands in the wrong pane after a path or session name, or an exit 1 for a directory that does hold one claude agent.

## Back-out

Revert `session_pane.py`, `herdr-phase-change` and their tests to the version that passes the target on as given.
