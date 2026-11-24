---
type: "Change"
change_type: "fixed"
title: "pull_keep_index pulls beside a session whose only edits are built pages"
description: "A pull before push no longer refuses when the other live session's only dirty files are built pages the merge driver owns: the pages are set aside, the branch is pulled, and the driver rebuilds them."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T12:09:59-06:00"}
seq: 1
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_peer_dirty_built_page_alone_is_pulled_and_rebuilt"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

When another live session works in the checkout and the tree has tracked changes, the run takes the shared route and
refuses a diverged branch. That route now applies only when some dirty path is not a built page (`merge=built-page`)
or the built-page driver is not configured. When every dirty path is a built page and the driver is set, the run takes
the solo route: set aside, pull, put back, with the driver rebuilding each page. The built-page list comes from the
same gitattributes lookup the put-back uses. Any other dirty file of a peer still refuses, unchanged.

## Evidence

Judgment from one shared checkout where any queue build dirties the two queue pages, because the build lists untracked
items. A peer session left them dirty and every push failed until the branch sat 10 commits ahead and 6 behind.

## Result

The new test fails on the old script (exit 1, "also works in ... Dirty files: QUEUE.md") and passes now. Two more
tests pin the refusals that stay: a peer-dirty source file beside a built page, and a built page with no driver
configured. All 88 tests of the file pass.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
