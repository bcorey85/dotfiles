---
type: "Change"
change_type: "fixed"
title: "The MCP server-name test ignores downloaded caches, plugins and synced skills"
description: "The MCP server-name test scans only git-tracked toolkit files, so it passes on the live checkout with its caches, plugins and synced skills."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T20:38:37-06:00"}
seq: 37
kind: "fix"
components: ["script/test-suite"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_mcp_server_names.py::McpServerNames.test_untracked_cache_and_plugin_files_are_ignored"
asked: ""
proof: []
unmeasured: ""
---

## Change

The test lists files with `git ls-files` instead of walking the folder, so untracked downloads (cache, plugins, skills/synced) are never read.

## Evidence

Before: the test failed on the live checkout, naming third-party servers found in cache and synced skills.

## Result

Passes on the live checkout and on a fresh worktree; a new test shows untracked cache, plugins and synced files naming an unknown server are ignored.

## Watch

None: a test-only change.

## Back-out

Revert the test file.

