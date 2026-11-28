"""Runs herdr-worktree-prune against throwaway repos, each with a local bare repo as origin.

Checks that only a clean, merged, unused linked worktree is listed and removed, that every doubtful tree is kept with
a reason, and that --apply and --branches change nothing else. herdr-api is a stub; git is the real one, isolated
from the user's configuration.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from stubs import write_stub

HERDR_WORKTREE_PRUNE = pathlib.Path(os.environ.get("HERDR_WORKTREE_PRUNE") or (
    pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin" / "herdr-worktree-prune"))
LANES_CLI = pathlib.Path(__file__).resolve().parents[2] / "claude" / ".claude" / "scripts" / "tools" / "lanes.py"
REAL_GIT = shutil.which("git")

# State lives in $STATE_DIR: workspaces.json and agents.json are the answers; `fail` makes every call fail, `garbage`
# makes every call print non-JSON, `fail-workspace` and `fail-agent` fail only that list, `fail-from-call` holding N
# fails every call from the Nth on. `calls` holds one line per call. When `dirty-on-call` holds N, the Nth call writes
# an untracked file into the folder named by `dirty-target`: it dirties a tree between the list and that tree's
# re-check without a race. When `workspaces-on-call` holds N, the Nth call first copies `workspaces-late.json` over
# the workspace answer: a workspace opens between the list and a re-check. `calls` holds "call <kind>" per call.
STUB_HERDR_API = r"""
state="$STATE_DIR"
echo "call $1" >> "$state/calls"
calls=$(wc -l < "$state/calls")
if [ -f "$state/dirty-on-call" ] && [ "$calls" -eq "$(cat "$state/dirty-on-call")" ]; then
    echo late > "$(cat "$state/dirty-target")/late.txt"
fi
if [ -f "$state/workspaces-on-call" ] && [ "$calls" -eq "$(cat "$state/workspaces-on-call")" ]; then
    cp "$state/workspaces-late.json" "$state/workspaces.json"
fi
if [ -f "$state/fail" ] || [ -f "$state/fail-$1" ]; then echo "herdr is down" >&2; exit 1; fi
if [ -f "$state/fail-from-call" ] && [ "$calls" -ge "$(cat "$state/fail-from-call")" ]; then
    echo "herdr is down" >&2
    exit 1
fi
if [ -f "$state/garbage" ]; then echo "not json {"; exit 0; fi
case "$1 $2" in
    "workspace list") cat "$state/workspaces.json" ;;
    "agent list") cat "$state/agents.json" ;;
    *) exit 1 ;;
esac
"""

# `git -C <dir> worktree remove $FAIL_PATH` fails; every other call runs the real git.
STUB_GIT_FAILING_ONE_REMOVAL = r"""
if [ "$3 $4" = "worktree remove" ] && [ "$5" = "$FAIL_PATH" ]; then
    echo "fatal: simulated removal failure" >&2
    exit 1
fi
exec "$REAL_GIT" "$@"
"""

# Every git call is appended to $GIT_LOG, then runs the real git.
STUB_GIT_LOGGING_CALLS = r"""
echo "$*" >> "$GIT_LOG"
exec "$REAL_GIT" "$@"
"""

# Just before `git -C <dir> update-ref -d refs/heads/$MOVE_BRANCH ...` runs, the branch is moved to $MOVE_TO, as
# another process would do between the check and the delete. Then the real git runs the delete.
STUB_GIT_MOVING_ONE_BRANCH = r"""
if [ "$3 $4" = "update-ref -d" ] && [ "$5" = "refs/heads/$MOVE_BRANCH" ]; then
    "$REAL_GIT" -C "$2" update-ref "refs/heads/$MOVE_BRANCH" "$MOVE_TO"
fi
exec "$REAL_GIT" "$@"
"""

# `git config --remove-section` fails with a lock error; every other call runs the real git.
STUB_GIT_FAILING_CONFIG = r"""
if [ "$3 $4" = "config --remove-section" ]; then
    echo "error: could not lock config file" >&2
    exit 255
fi
exec "$REAL_GIT" "$@"
"""

# The Nth `git -C <dir> worktree list` call ($FAIL_LIST_CALL, counted in $STATE_DIR/list-calls) fails; every other
# call runs the real git. The first list of a run is the one that reads the world before the plan.
STUB_GIT_FAILING_ONE_WORKTREE_LIST = r"""
if [ "$3 $4" = "worktree list" ]; then
    echo list >> "$STATE_DIR/list-calls"
    if [ "$(wc -l < "$STATE_DIR/list-calls")" -eq "$FAIL_LIST_CALL" ]; then
        echo "fatal: simulated list failure" >&2
        exit 1
    fi
fi
exec "$REAL_GIT" "$@"
"""

# Rewrites the todo list of an interactive rebase so that its first commit stops the rebase with `edit`.
STUB_SEQUENCE_EDITOR = r"""
sed 's/^pick/edit/' "$1" > "$1.new"
mv "$1.new" "$1"
"""

STUB_LSOF = r"""
echo p4242
echo csleep
echo fcwd
echo "n$LSOF_CWD"
"""


def path_without_herdr_api():
    kept = [folder for folder in os.environ["PATH"].split(os.pathsep)
            if not (pathlib.Path(folder) / "herdr-api").exists()]
    return os.pathsep.join(kept)


def load_script_module():
    loader = importlib.machinery.SourceFileLoader("herdr_worktree_prune_under_test", str(HERDR_WORKTREE_PRUNE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    # dataclasses looks its module up by name when annotations are strings.
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def load_lib_module(name):
    """A shared module from the lib folder beside the script under test."""
    lib_folder = str(HERDR_WORKTREE_PRUNE.resolve().parent.parent / "lib")
    if lib_folder not in sys.path:
        sys.path.insert(0, lib_folder)
    return importlib.import_module(name)


class Lab:
    """A main checkout, its bare origin, and helpers that make lane worktrees."""

    def __init__(self, root, default="main"):
        self.root = root
        self.default = default
        root.mkdir(parents=True, exist_ok=True)
        self.home = root / "home"
        self.home.mkdir()
        self.bin_dir = root / "bin"
        self.bin_dir.mkdir()
        self.state_dir = root / "state"
        self.state_dir.mkdir()
        write_stub(self.bin_dir / "herdr-api", STUB_HERDR_API)
        self.set_workspaces([])
        self.set_agents([])
        self.env = self.make_env()
        self.origin = root / "origin.git"
        self.main = root / "repo"
        self.git(root, "init", "--bare", "-b", default, str(self.origin))
        self.git(root, "init", "-b", default, str(self.main))
        self.commit(self.main, "base.txt")
        self.git(self.main, "remote", "add", "origin", str(self.origin))
        self.git(self.main, "push", "-u", "origin", default)
        self.git(self.main, "remote", "set-head", "origin", "--auto")

    def make_env(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update({
            "HOME": str(self.home),
            "PATH": f"{self.bin_dir}{os.pathsep}{path_without_herdr_api()}",
            "STATE_DIR": str(self.state_dir),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        return env

    def set_workspaces(self, workspaces):
        self.write_state("workspaces.json", {"result": {"workspaces": workspaces}})

    def set_agents(self, agents):
        self.write_state("agents.json", {"result": {"agents": agents}})

    def write_state(self, name, value):
        (self.state_dir / name).write_text(json.dumps(value))

    def git(self, cwd, *args, check=True):
        done = subprocess.run([REAL_GIT, "-C", str(cwd), *args], env=self.env, capture_output=True, text=True,
                              timeout=60)
        if check and done.returncode != 0:
            raise AssertionError(f"git {args} failed in {cwd}: {done.stderr}")
        return done

    def commit(self, cwd, filename, text="x\n"):
        (pathlib.Path(cwd) / filename).write_text(text)
        self.git(cwd, "add", filename)
        self.git(cwd, "commit", "-q", "-m", f"add {filename}")

    def lane(self, name, branch=None, commits=1):
        """A worktree beside the main checkout, on its own branch, with `commits` commits."""
        branch = branch or f"feature/{name}"
        tree = self.root / name
        self.git(self.main, "worktree", "add", "-q", "-b", branch, str(tree))
        for number in range(commits):
            self.commit(tree, f"{name.replace(' ', '_')}-{number}.txt")
        return tree

    def merge(self, branch):
        self.git(self.main, "merge", "-q", "--no-ff", "--no-edit", branch)
        self.git(self.main, "push", "-q", "origin", self.default)

    def merged_lane(self, name, branch=None):
        tree = self.lane(name, branch)
        self.merge(branch or f"feature/{name}")
        return tree

    def branches(self):
        listed = self.git(self.main, "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout
        return set(listed.split())

    def worktree_list(self):
        return self.git(self.main, "worktree", "list", "--porcelain").stdout

    def herdr_calls(self, kind=None):
        """The number of herdr-api calls, or of the calls to one list (`workspace`, `agent`) when `kind` is set."""
        calls_file = self.state_dir / "calls"
        if not calls_file.exists():
            return 0
        lines = calls_file.read_text().splitlines()
        if kind is None:
            return len(lines)
        return lines.count(f"call {kind}")

    def branch_config(self):
        """The `branch.*` config lines, sorted."""
        asked = self.git(self.main, "config", "--get-regexp", r"^branch\.", check=False)
        return sorted(asked.stdout.splitlines())

    def tip(self, branch):
        return self.git(self.main, "rev-parse", f"refs/heads/{branch}").stdout.strip()

    def ahead_lane(self, name, branch):
        """A merged lane whose local tip is one commit ahead of its own upstream origin/<branch>."""
        tree = self.lane(name, branch)
        self.git(tree, "push", "-q", "-u", "origin", branch)
        self.commit(tree, "after-push.txt")
        self.merge(branch)
        return tree

    def root_commit(self):
        return self.git(self.main, "rev-list", "--max-parents=0", self.default).stdout.split()[0]

    def worktree_free_lane(self, name, branch):
        """A merged branch pushed with upstream tracking whose worktree is already gone."""
        tree = self.lane(name, branch)
        self.git(tree, "push", "-q", "-u", "origin", branch)
        self.merge(branch)
        self.git(self.main, "worktree", "remove", str(tree))
        return tree

    def lanes(self, *args):
        """Run the lanes cli against this lab's lane state folder."""
        done = subprocess.run([sys.executable, self.env["HERDR_LANES_CLI"], *args], env=self.env,
                              input="brief\n", capture_output=True, text=True, timeout=60)
        if done.returncode != 0:
            raise AssertionError(f"lanes {args} failed: {done.stderr}")
        return done

    def open_lane(self, name, tree):
        self.lanes("add", "--name", name, "--worktree", str(tree), "--main-checkout", str(self.main),
                   "--branch", f"feature/{name}")

    def prune(self, *args, cwd=None, env=None):
        return subprocess.run([str(HERDR_WORKTREE_PRUNE), *args], cwd=str(cwd or self.main), env=env or self.env,
                              capture_output=True, text=True, timeout=120)


def line_of(finished, tree):
    """The listing line for `tree`: its path is followed by two spaces and the bracketed branch."""
    for line in finished.stdout.splitlines():
        if f"  {tree}  [" in line:
            return line
    raise AssertionError(f"no line for {tree} in:\n{finished.stdout}\n{finished.stderr}")


class PruneTestCase(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(scratch.name).resolve()
        self.lab = Lab(self.root / "lab")
        lane_state = self.root / "lane-state"
        lane_state.mkdir()
        self.lab.env["XDG_STATE_HOME"] = str(lane_state)
        self.lab.env["HERDR_LANES_CLI"] = str(LANES_CLI)

    def hold_cwd(self, folder):
        holder = subprocess.Popen(["sleep", "300"], cwd=str(folder))
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        return holder

    def assert_kept_and_untouched(self, tree, branch, finished, reason):
        self.assertTrue(tree.exists(), f"{tree} was removed")
        self.assertIn(branch, self.lab.branches())
        self.assertIn(reason, line_of(finished, tree))
        self.assertTrue(line_of(finished, tree).startswith("keep"), line_of(finished, tree))


class RemovalTest(PruneTestCase):
    def test_a_merged_clean_worktree_is_listed_and_apply_removes_it_and_its_local_branch(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(tree, "push", "-q", "origin", "feature/lane-a")
        before = (self.lab.worktree_list(), self.lab.branches(), tree.exists())

        listed = self.lab.prune()

        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertTrue(listed.stdout.startswith("compare ref: origin/main ("), listed.stdout)
        self.assertTrue(line_of(listed, tree).startswith("remove  "), line_of(listed, tree))
        self.assertIn("[feature/lane-a]", line_of(listed, tree))
        self.assertIn("would remove 1,", listed.stdout)
        self.assertIn("kept 1: 1 main checkout", listed.stdout)
        self.assertEqual((self.lab.worktree_list(), self.lab.branches(), tree.exists()), before)

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertFalse(tree.exists())
        self.assertNotIn("feature/lane-a", self.lab.branches())
        self.assertNotIn(str(tree), self.lab.worktree_list())
        remote = self.lab.git(self.lab.main, "ls-remote", "--heads", "origin").stdout
        self.assertIn("refs/heads/feature/lane-a", remote)
        self.assertIn("removed 1, freed ", applied.stdout)
        self.assertIn("kept 1, failed 0", applied.stdout)

    def test_a_worktree_path_with_spaces_is_listed_and_removed(self):
        tree = self.lab.merged_lane("my lane", "feature/spaced")

        listed = self.lab.prune()
        self.assertTrue(line_of(listed, tree).startswith("remove  "), listed.stdout)
        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertFalse(tree.exists())
        self.assertNotIn("feature/spaced", self.lab.branches())

    def test_a_folder_deleted_by_hand_is_kept_and_its_entry_and_branch_stay(self):
        tree = self.lab.merged_lane("lane-a")
        shutil.rmtree(tree)
        before = self.lab.worktree_list()

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn("the folder is gone; `git worktree prune` clears the entry", line_of(applied, tree))
        self.assertIn("feature/lane-a", self.lab.branches())
        self.assertEqual(self.lab.worktree_list(), before)

    def test_ignored_files_do_not_keep_a_tree_and_plain_worktree_remove_deletes_them(self):
        tree = self.lab.lane("lane-a")
        self.lab.commit(tree, ".gitignore", "node_modules/\n")
        self.lab.merge("feature/lane-a")
        (tree / "node_modules").mkdir()
        (tree / "node_modules" / "x").write_text("ignored\n")

        listed = self.lab.prune()
        self.assertTrue(line_of(listed, tree).startswith("remove  "), listed.stdout)
        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertFalse(tree.exists(), "git worktree remove leaves the folder, ignored files and all")
        self.assertNotIn("feature/lane-a", self.lab.branches())

    def test_the_default_branch_may_be_trunk(self):
        lab = Lab(self.root / "trunk-lab", default="trunk")
        lab.env["XDG_STATE_HOME"] = self.lab.env["XDG_STATE_HOME"]
        lab.env["HERDR_LANES_CLI"] = self.lab.env["HERDR_LANES_CLI"]
        tree = lab.merged_lane("lane-a")

        applied = lab.prune("--apply")

        self.assertIn("compare ref: origin/trunk (", applied.stdout)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertFalse(tree.exists())

    def test_apply_ends_with_exit_zero_and_totals_when_nothing_is_removable(self):
        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn("removed 0, freed 0 bytes", applied.stdout)


class CheckedOutBranchMergeTest(PruneTestCase):
    """The main checkout sits on a working branch that origin's default branch does not hold."""

    def working_branch_lab(self):
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "bench-base")
        merged = self.lab.lane("lane-a")
        self.lab.git(self.lab.main, "merge", "-q", "--no-ff", "--no-edit", "feature/lane-a")
        unmerged = self.lab.lane("lane-b")
        return merged, unmerged

    def test_a_clean_worktree_merged_into_the_checked_out_branch_is_removed_with_its_branch(self):
        merged, _unmerged = self.working_branch_lab()

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertFalse(merged.exists(), applied.stdout)
        self.assertNotIn("feature/lane-a", self.lab.branches())
        self.assertIn("removed 1,", applied.stdout)

    def test_an_unmerged_worktree_is_kept_and_names_both_refs(self):
        _merged, unmerged = self.working_branch_lab()

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(unmerged, "feature/lane-b", applied, "1 commits not on origin/main")
        self.assertIn("nor on bench-base", line_of(applied, unmerged))

    def test_check_passes_a_tree_merged_into_the_checked_out_branch_and_keeps_an_unmerged_one(self):
        merged, unmerged = self.working_branch_lab()

        merged_answer = json.loads(self.lab.prune("--check", str(merged)).stdout)
        unmerged_answer = json.loads(self.lab.prune("--check", str(unmerged)).stdout)

        self.assertEqual(merged_answer["verdict"], "remove", merged_answer)
        self.assertEqual(unmerged_answer["verdict"], "keep")
        self.assertIn("nor on bench-base", unmerged_answer["reason"])

    def test_a_tree_on_a_checkout_branch_equal_to_the_compare_ref_still_removes_a_merged_lane(self):
        merged = self.lab.merged_lane("lane-a")
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "same-as-main")
        unmerged = self.lab.lane("lane-b")

        applied = self.lab.prune("--apply")

        self.assertFalse(merged.exists(), applied.stdout + applied.stderr)
        self.assertTrue(unmerged.exists())
        self.assertIn("1 commits not on origin/main nor on feature/lane-a; a squash", line_of(applied, unmerged))

    def test_a_tip_ahead_of_its_upstream_and_held_only_by_the_checked_out_branch_names_that_branch(self):
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "bench-base")
        tree = self.lab.lane("lane-a")
        self.lab.git(tree, "push", "-q", "-u", "origin", "feature/lane-a")
        self.lab.commit(tree, "after-push.txt")
        self.lab.git(self.lab.main, "merge", "-q", "--no-ff", "--no-edit", "feature/lane-a")

        listed = self.lab.prune()

        self.assertIn("ahead of its own remote branch, fully on bench-base", line_of(listed, tree))

    def test_a_failing_merge_base_on_the_compare_ref_is_cannot_check_and_blocks_a_branch_delete(self):
        module = load_script_module()
        tip = self.lab.tip("main")
        repo = module.Repo(str(self.lab.main), "main", "origin/main", "0" * 40, str(self.lab.main))
        unmerged = self.lab.git(self.lab.main, "commit-tree", "-m", "x", f"{tip}^{{tree}}").stdout.strip()
        tree = module.Worktree(path=str(self.lab.main), head=unmerged)
        world = types.SimpleNamespace(worktrees=[tree], lanes=module.LaneRead([]))

        keep = module.check_merged(repo, world, tree)

        self.assertEqual(keep.code, module.CANNOT_CHECK)
        self.lab.git(self.lab.main, "branch", "-f", "probe", unmerged)
        deletion = load_lib_module("worktree_branches").delete_branch(repo, "probe")
        self.assertTrue(deletion.failure.startswith("git merge-base failed"), deletion.failure)
        self.assertIn("probe", self.lab.branches())

    def test_delete_branch_asks_the_live_checkout_branch_not_the_start_up_hash(self):
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "bench-base")
        self.lab.commit(self.lab.main, "bench.txt")
        stale_hash = self.lab.tip("bench-base")
        self.lab.git(self.lab.main, "branch", "feature/old-lane", stale_hash)
        self.lab.git(self.lab.main, "reset", "-q", "--hard", "main")
        module = load_script_module()
        repo = module.Repo(str(self.lab.main), "main", "origin/main", self.lab.tip("main"), str(self.lab.main),
                           "bench-base", stale_hash)

        deletion = load_lib_module("worktree_branches").delete_branch(repo, "feature/old-lane")

        self.assertIn("is not on", deletion.failure)
        self.assertIn("feature/old-lane", self.lab.branches())

    def test_a_tree_at_the_checkout_branch_tip_is_kept_and_its_branch_survives(self):
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "bench-base")
        self.lab.commit(self.lab.main, "bench.txt")
        fresh = self.lab.lane("lane-fresh", commits=0)

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(fresh, "feature/lane-fresh", applied, "0 commits not on origin/main")
        self.assertIn("nor on bench-base", line_of(applied, fresh))

    def test_delete_branch_refuses_a_branch_at_the_checkout_branch_tip(self):
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "bench-base")
        self.lab.commit(self.lab.main, "bench.txt")
        self.lab.git(self.lab.main, "branch", "feature/cut-from-bench", "bench-base")
        repo = load_script_module().Repo(str(self.lab.main), "main", "origin/main", self.lab.tip("main"),
                                         str(self.lab.main), "bench-base", self.lab.tip("bench-base"))

        deletion = load_lib_module("worktree_branches").delete_branch(repo, "feature/cut-from-bench")

        self.assertIn("is not on", deletion.failure)
        self.assertIn("feature/cut-from-bench", self.lab.branches())

    def test_the_list_header_names_the_checkout_branch_when_it_is_a_second_target(self):
        self.working_branch_lab()

        listed = self.lab.prune()

        self.assertTrue(listed.stdout.startswith("compare ref: origin/main ("), listed.stdout)
        self.assertIn("also merged into: bench-base\n", listed.stdout)

    def test_a_dirty_worktree_merged_into_the_checked_out_branch_is_kept(self):
        merged, _unmerged = self.working_branch_lab()
        (merged / "scratch.txt").write_text("dirty\n")

        applied = self.lab.prune("--apply")

        self.assertTrue(merged.exists())
        self.assertTrue(line_of(applied, merged).startswith("keep"), line_of(applied, merged))
        self.assertIn("uncommitted changes", line_of(applied, merged))
        self.assertIn("feature/lane-a", self.lab.branches())

    def test_a_lane_is_kept_without_a_second_ref_when_the_main_checkout_is_detached(self):
        _merged, unmerged = self.working_branch_lab()
        self.lab.git(self.lab.main, "checkout", "-q", "--detach")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(unmerged, "feature/lane-b", applied, "commits not on origin/main")
        self.assertIn("2 commits not on origin/main nor on feature/lane-a; a squash", line_of(applied, unmerged))

    def test_branch_mode_does_not_delete_a_branch_merged_only_into_the_checked_out_branch(self):
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "bench-base")
        self.lab.commit(self.lab.main, "bench.txt")
        self.lab.git(self.lab.main, "branch", "feature/behind-bench", "bench-base")

        applied = self.lab.prune("--branches", "--apply")

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("feature/behind-bench", self.lab.branches())


class LinkedIntegrationMergeTest(PruneTestCase):
    """The main checkout is on main; an integration branch is checked out in a linked worktree."""

    def integration_lab(self):
        integration = self.root / "integration"
        self.lab.git(self.lab.main, "worktree", "add", "-q", "-b", "integration", str(integration))
        return integration

    def merge_into_integration(self, integration, branch):
        self.lab.git(integration, "merge", "-q", "--no-ff", "--no-edit", branch)

    def add_plan_file(self, tree, lane, name="00-ticket.md"):
        plan_file = tree / "docs" / "plans" / lane / name
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.write_text("plan\n")
        return plan_file

    def test_a_worktree_merged_into_a_linked_worktree_branch_is_removed_with_its_branch(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")

        checked = json.loads(self.lab.prune("--check", str(lane)).stdout)
        listed = self.lab.prune()
        applied = self.lab.prune("--apply")

        self.assertEqual(checked["verdict"], "remove", checked)
        self.assertTrue(line_of(listed, lane).startswith("remove"), listed.stdout)
        self.assertFalse(lane.exists(), applied.stdout + applied.stderr)
        self.assertNotIn("feature/lane-a", self.lab.branches())
        self.assertTrue(integration.exists())

    def test_a_fresh_lane_cut_from_the_linked_worktree_branch_is_kept(self):
        integration = self.integration_lab()
        self.lab.commit(integration, "integration.txt")
        fresh = self.lab.lane("lane-fresh", commits=0)
        self.lab.git(fresh, "reset", "-q", "--hard", "integration")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(fresh, "feature/lane-fresh", applied, "0 commits not on origin/main")
        self.assertNotIn("nor on feature/lane-fresh", line_of(applied, fresh))
        self.assertIn("nor on integration", line_of(applied, fresh))

    def test_the_branch_delete_after_a_removal_counts_a_linked_worktree_branch(self):
        integration = self.integration_lab()
        self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        self.lab.git(self.lab.main, "worktree", "remove", str(self.lab.root / "lane-a"))
        module = load_script_module()
        repo = module.Repo(str(self.lab.main), "main", "origin/main", self.lab.tip("main"), str(self.lab.main))
        linked = module.list_worktrees(str(self.lab.main))[1:]

        deletion = load_lib_module("worktree_branches").delete_branch(repo, "feature/lane-a", linked)

        self.assertIsNone(deletion.failure)
        self.assertNotIn("feature/lane-a", self.lab.branches())

    def test_a_lane_is_not_merged_into_its_own_branch_after_it_commits_again(self):
        module = load_script_module()
        lane = self.lab.lane("lane-a")
        old_head = self.lab.tip("feature/lane-a")
        self.lab.commit(lane, "more.txt")
        repo = module.Repo(str(self.lab.main), "main", "origin/main", self.lab.tip("main"), str(self.lab.main))
        world = types.SimpleNamespace(worktrees=module.list_worktrees(str(self.lab.main)), lanes=module.LaneRead([]))
        tree = module.Worktree(path=str(lane), head=old_head, branch="feature/lane-a")

        keep = module.check_merged(repo, world, tree)

        self.assertEqual(keep.code, module.NOT_MERGED)

    def test_an_integration_tree_with_an_open_child_lane_is_kept(self):
        integration = self.integration_lab()
        self.lab.commit(integration, "integration.txt")
        child = self.lab.lane("lane-child", commits=0)
        self.lab.git(child, "reset", "-q", "--hard", "integration")
        self.lab.commit(child, "child.txt")
        self.lab.open_lane("lane-child", child)

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(integration, "integration", applied, "commits not on origin/main")
        self.assert_kept_and_untouched(child, "feature/lane-child", applied, "lane lane-child is open")

    def test_a_stacked_parent_with_an_open_child_lane_is_kept(self):
        parent = self.lab.lane("lane-parent")
        child = self.lab.lane("lane-child", commits=0)
        self.lab.git(child, "reset", "-q", "--hard", "feature/lane-parent")
        self.lab.commit(child, "child.txt")
        self.lab.open_lane("lane-child", child)

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(parent, "feature/lane-parent", applied, "commits not on origin/main")
        self.assert_kept_and_untouched(child, "feature/lane-child", applied, "lane lane-child is open")

    def test_a_linked_branch_gives_no_credit_when_the_lane_list_cannot_be_read(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        self.lab.env["HERDR_LANES_CLI"] = str(self.root / "missing-lanes.py")

        checked = json.loads(self.lab.prune("--check", str(lane)).stdout)

        self.assertEqual(checked["verdict"], "keep", checked)
        self.assertEqual(checked["code"], "not merged", checked)
        self.assertIn("the lane list could not be read", checked["reason"])

    def test_apply_keeps_a_linked_lane_when_the_lane_list_cannot_be_read(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        self.lab.env["HERDR_LANES_CLI"] = str(self.root / "missing-lanes.py")

        self.lab.prune("--apply")

        self.assertTrue(lane.exists())
        self.assertIn("feature/lane-a", self.lab.branches())

    def test_apply_keeps_the_branch_when_the_lane_list_fails_after_the_tree_is_removed(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        counter = self.root / "lanes-calls"
        stub = self.root / "stub-fails-late.py"
        stub.write_text(
            "import json, pathlib, sys\n"
            f"counter = pathlib.Path({str(counter)!r})\n"
            "calls = int(counter.read_text()) if counter.exists() else 0\n"
            "counter.write_text(str(calls + 1))\n"
            "if calls >= 2:\n"
            "    sys.exit(1)\n"
            "print(json.dumps({'lanes': []}))\n")
        self.lab.env["HERDR_LANES_CLI"] = str(stub)

        applied = self.lab.prune("--apply")

        self.assertFalse(lane.exists(), applied.stdout + applied.stderr)
        self.assertIn("feature/lane-a", self.lab.branches())
        self.assertIn("The worktree is gone", applied.stdout)

    def test_apply_removes_a_merged_tree_without_force(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        self.add_plan_file(lane, "lane-a")
        git_log = self.root / "git-calls.log"
        write_stub(self.lab.bin_dir / "git", STUB_GIT_LOGGING_CALLS)
        self.lab.env.update({"GIT_LOG": str(git_log), "REAL_GIT": REAL_GIT})

        self.lab.prune("--apply")

        removals = [call for call in git_log.read_text().splitlines() if "worktree remove" in call]
        self.assertTrue(removals, "no worktree remove call was logged")
        for call in removals:
            self.assertNotIn("--force", call)

    def test_delete_plan_files_refuses_a_nested_repo_entry_and_deletes_nothing(self):
        module = load_script_module()
        lane = self.lab.lane("lane-a")
        plan_file = self.add_plan_file(lane, "lane-a")
        tree = module.Worktree(path=str(lane), branch="feature/lane-a")
        listed = ["docs/plans/lane-a/00-ticket.md", "docs/plans/lane-a/sub/"]

        with mock.patch.object(module, "untracked_plan_files", return_value=listed):
            failure = module.delete_plan_files(tree)

        self.assertIn("nested repository", failure)
        self.assertTrue(plan_file.exists())

    def test_untracked_plan_files_of_a_merged_branch_are_deleted_and_the_tree_removed(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        plan_file = self.add_plan_file(lane, "lane-a")
        nested_file = self.add_plan_file(lane, "lane-a", "sub/notes.md")

        checked = json.loads(self.lab.prune("--check", str(lane)).stdout)
        self.assertTrue(plan_file.exists())
        self.assertTrue(nested_file.exists())
        applied = self.lab.prune("--apply")

        self.assertEqual(checked["verdict"], "remove", checked)
        self.assertFalse(plan_file.exists())
        self.assertFalse(nested_file.exists())
        self.assertFalse(lane.exists(), applied.stdout + applied.stderr)
        self.assertNotIn("feature/lane-a", self.lab.branches())

    def test_a_nested_repo_under_the_plan_folder_keeps_the_tree_and_its_plan_files(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        plan_file = self.add_plan_file(lane, "lane-a")
        nested = lane / "docs" / "plans" / "lane-a" / "sub"
        nested.mkdir()
        self.lab.git(nested, "init", "-q")
        (nested / "f.txt").write_text("x\n")
        self.lab.git(nested, "add", "f.txt")
        self.lab.git(nested, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(lane, "feature/lane-a", applied, "uncommitted changes")
        self.assertTrue(plan_file.exists())

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_a_plan_file_that_cannot_be_deleted_fails_the_tree_and_keeps_it_and_its_branch(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        plan_file = self.add_plan_file(lane, "lane-a")
        plan_file.parent.chmod(0o555)
        self.addCleanup(plan_file.parent.chmod, 0o755)

        applied = self.lab.prune("--apply")

        self.assertIn("plan files stay", applied.stdout)
        self.assertIn("failed 1", applied.stdout)
        self.assertTrue(lane.exists())
        self.assertIn("feature/lane-a", self.lab.branches())

    def test_a_detached_integration_worktree_is_not_a_merge_target(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        self.lab.git(integration, "checkout", "-q", "--detach")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(lane, "feature/lane-a", applied, "commits not on origin/main")

    def test_an_unborn_linked_worktree_is_not_a_merge_target(self):
        lane = self.lab.lane("lane-a")
        orphan = self.root / "orphan"
        self.lab.git(self.lab.main, "worktree", "add", "-q", "--orphan", "-b", "orphan", str(orphan))

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(lane, "feature/lane-a", applied, "commits not on origin/main")

    def test_a_slashed_branch_names_the_plan_folder_by_its_last_segment_only(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a", branch="fix/deep/lane-a")
        self.merge_into_integration(integration, "fix/deep/lane-a")
        self.add_plan_file(lane, "lane-a")

        applied = self.lab.prune("--apply")

        self.assertFalse(lane.exists(), applied.stdout + applied.stderr)

    def test_another_untracked_file_keeps_a_merged_tree_and_its_plan_files(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        plan_file = self.add_plan_file(lane, "lane-a")
        self.add_plan_file(lane, "other-lane")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(lane, "feature/lane-a", applied, "uncommitted changes")
        self.assertTrue(plan_file.exists())

    def test_a_modified_or_staged_file_keeps_a_merged_tree_with_plan_files(self):
        integration = self.integration_lab()
        lane = self.lab.lane("lane-a")
        self.merge_into_integration(integration, "feature/lane-a")
        plan_file = self.add_plan_file(lane, "lane-a")
        (lane / "lane-a-0.txt").write_text("changed\n")
        staged = self.lab.lane("lane-b")
        self.merge_into_integration(integration, "feature/lane-b")
        self.add_plan_file(staged, "lane-b")
        (staged / "new.txt").write_text("new\n")
        self.lab.git(staged, "add", "new.txt")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(lane, "feature/lane-a", applied, "uncommitted changes")
        self.assert_kept_and_untouched(staged, "feature/lane-b", applied, "uncommitted changes")
        self.assertTrue(plan_file.exists())

    def test_plan_files_on_an_unmerged_branch_keep_the_tree(self):
        lane = self.lab.lane("lane-a")
        plan_file = self.add_plan_file(lane, "lane-a")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(lane, "feature/lane-a", applied, "commits not on origin/main")
        self.assertTrue(plan_file.exists())


class KeptTreeTest(PruneTestCase):
    def test_a_keep_on_the_default_branch_checkout_names_only_the_compare_ref(self):
        tree = self.lab.lane("lane-a", commits=1)

        applied = self.lab.prune("--apply")

        self.assertIn("commits not on origin/main", line_of(applied, tree))
        self.assertNotIn("nor on", line_of(applied, tree))

    def test_a_squash_merged_branch_is_kept_with_its_commit_count(self):
        tree = self.lab.lane("lane-a", commits=1)
        self.lab.git(self.lab.main, "merge", "-q", "--squash", "feature/lane-a")
        self.lab.git(self.lab.main, "commit", "-q", "-m", "squash")
        self.lab.git(self.lab.main, "push", "-q", "origin", "main")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "1 commits not on origin/main")
        self.assertIn("squash or rebase merge looks the same", line_of(applied, tree))

    def test_a_rebase_merged_branch_is_kept_with_its_commit_count(self):
        tree = self.lab.lane("lane-a", commits=2)
        # Main moves on first: a cherry-pick onto the commits' own parent would reuse their hashes.
        self.lab.commit(self.lab.main, "other.txt")
        self.lab.git(self.lab.main, "cherry-pick", "main..feature/lane-a")
        self.lab.git(self.lab.main, "push", "-q", "origin", "main")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "2 commits not on origin/main")

    def test_a_merged_branch_with_one_new_commit_is_kept(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.commit(tree, "later.txt")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "1 commits not on origin/main")

    def test_an_untracked_file_keeps_the_tree(self):
        tree = self.lab.merged_lane("lane-a")
        (tree / "scratch.txt").write_text("new\n")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "uncommitted changes")
        self.assertTrue((tree / "scratch.txt").exists())

    def test_a_staged_change_keeps_the_tree(self):
        tree = self.lab.merged_lane("lane-a")
        (tree / "staged.txt").write_text("new\n")
        self.lab.git(tree, "add", "staged.txt")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "uncommitted changes")

    def test_a_modified_tracked_file_keeps_the_tree(self):
        tree = self.lab.merged_lane("lane-a")
        (tree / "lane-a-0.txt").write_text("changed\n")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "uncommitted changes")

    def test_a_submodule_keeps_the_tree_and_plain_worktree_remove_would_refuse_it(self):
        sub = self.root / "sub"
        self.lab.git(self.root, "init", "-q", "-b", "main", str(sub))
        self.lab.commit(sub, "s.txt")
        tree = self.lab.lane("lane-a")
        self.lab.git(tree, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "subm")
        self.lab.git(tree, "commit", "-q", "-m", "add submodule")
        self.lab.merge("feature/lane-a")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "holds a submodule: subm")
        plain = self.lab.git(self.lab.main, "worktree", "remove", str(tree), check=False)
        self.assertNotEqual(plain.returncode, 0, "plain git worktree remove accepted a tree with a submodule")
        self.assertTrue(tree.exists())

    def test_an_untracked_nested_repo_keeps_the_tree(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(self.root, "init", "-q", str(tree / "nested"))

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "uncommitted changes")

    def test_an_ignored_nested_repo_keeps_the_tree(self):
        tree = self.lab.lane("lane-a")
        self.lab.commit(tree, ".gitignore", "vendor/\n")
        self.lab.merge("feature/lane-a")
        self.lab.git(self.root, "init", "-q", str(tree / "vendor"))

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "holds an ignored nested repository: vendor/")

    def test_a_repo_deeper_inside_an_ignored_folder_keeps_the_tree_and_names_its_folder(self):
        tree = self.lab.lane("lane-a")
        self.lab.commit(tree, ".gitignore", "vendor/\n")
        self.lab.merge("feature/lane-a")
        (tree / "vendor").mkdir()
        self.lab.git(self.root, "init", "-q", str(tree / "vendor" / "inner"))

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied,
                                       "holds an ignored nested repository: vendor/inner/")
        self.assertTrue((tree / "vendor" / "inner" / ".git").exists())

    def test_an_ignored_folder_with_no_repo_and_an_ignored_file_do_not_keep_the_tree(self):
        tree = self.lab.lane("lane-a")
        self.lab.commit(tree, ".gitignore", "vendor/\nnotes.log\n")
        self.lab.merge("feature/lane-a")
        (tree / "vendor" / "deep" / "er").mkdir(parents=True)
        (tree / "vendor" / "deep" / "er" / "x.txt").write_text("ignored\n")
        (tree / "notes.log").write_text("ignored\n")

        listed = self.lab.prune()

        self.assertTrue(line_of(listed, tree).startswith("remove  "), listed.stdout)

    def test_a_locked_tree_is_kept_with_its_lock_reason(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(self.lab.main, "worktree", "lock", "--reason", "on a usb stick", str(tree))

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "locked: on a usb stick")

    def test_a_detached_tree_is_kept(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(tree, "checkout", "-q", "--detach")

        applied = self.lab.prune("--apply")

        self.assertTrue(tree.exists())
        self.assertIn("detached HEAD", line_of(applied, tree))
        self.assertIn("feature/lane-a", self.lab.branches())

    def test_a_worktree_on_the_default_branch_is_kept(self):
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "scratch")
        tree = self.root / "on-default"
        self.lab.git(self.lab.main, "worktree", "add", "-q", str(tree), "main")

        applied = self.lab.prune("--apply")

        self.assertTrue(tree.exists())
        self.assertIn("checked out on the default branch main", line_of(applied, tree))
        self.assertIn("main", self.lab.branches())

    def test_a_stash_made_on_the_branch_keeps_the_tree_in_both_subject_forms(self):
        wip = self.lab.merged_lane("lane-a")
        (wip / "lane-a-0.txt").write_text("changed\n")
        self.lab.git(wip, "stash")
        named = self.lab.merged_lane("lane-b")
        (named / "lane-b-0.txt").write_text("changed\n")
        self.lab.git(named, "stash", "push", "-m", "my message")
        subjects = self.lab.git(self.lab.main, "stash", "list", "--format=%gs").stdout
        self.assertIn("WIP on feature/lane-a:", subjects)
        self.assertIn("On feature/lane-b: my message", subjects)

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(wip, "feature/lane-a", applied, "a stash entry was made on branch")
        self.assert_kept_and_untouched(named, "feature/lane-b", applied, "a stash entry was made on branch")

    def test_a_bare_subject_stash_keeps_only_the_tree_whose_tip_is_its_parent_and_a_note_counts_them(self):
        parented = self.lab.merged_lane("lane-a")
        (parented / "lane-a-0.txt").write_text("changed\n")
        parented_stash = self.lab.git(parented, "stash", "create").stdout.strip()
        self.lab.git(parented, "checkout", "-q", "--", ".")
        self.lab.git(parented, "stash", "store", "-m", "autostash", parented_stash)
        unrelated = self.lab.merged_lane("lane-b")
        (self.lab.main / "base.txt").write_text("changed\n")
        main_stash = self.lab.git(self.lab.main, "stash", "create").stdout.strip()
        self.lab.git(self.lab.main, "checkout", "-q", "--", ".")
        self.lab.git(self.lab.main, "stash", "store", "-m", "autostash while switching to 'x'", main_stash)

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(parented, "feature/lane-a", applied, "a stash entry sits on this branch's tip")
        self.assertFalse(unrelated.exists())
        self.assertIn("note: 2 stash entries name no branch", applied.stdout)

    def test_a_tree_that_turns_dirty_after_the_list_is_kept_and_the_others_go(self):
        first = self.lab.merged_lane("lane-a")
        second = self.lab.merged_lane("lane-b")
        third = self.lab.merged_lane("lane-c")
        # The list makes calls 1 and 2; call 3 is the first re-check, which runs before the second tree's.
        (self.lab.state_dir / "dirty-on-call").write_text("3")
        (self.lab.state_dir / "dirty-target").write_text(str(second))

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        self.assertFalse(third.exists())
        self.assertIn("changed since the list: ", applied.stdout)
        self.assertIn("removed 2, freed ", applied.stdout)
        self.assertIn("kept 2, failed 0", applied.stdout)


class LaneTest(PruneTestCase):
    def test_a_tree_with_an_open_lane_entry_is_kept_and_goes_once_the_entry_is_removed(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.open_lane("lane-a", tree)

        kept = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", kept, "lane lane-a is open")
        self.assertIn("1 open lane", kept.stdout)
        self.assertIn("herdr-lane-resume --close lane-a", line_of(kept, tree))

        self.lab.lanes("remove", "lane-a")
        removed = self.lab.prune("--apply")

        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(tree.exists())

    def test_a_folder_inside_an_open_lane_worktree_is_kept(self):
        module = load_script_module()
        world = types.SimpleNamespace(lanes=module.LaneRead([("lane-a", "/x/lane-a")]))

        inside_keep = module.check_lane_open(None, world, module.Worktree(path="/x/lane-a/sub"))
        apart_keep = module.check_lane_open(None, world, module.Worktree(path="/x/lane-ab"))

        self.assertEqual(inside_keep.code, module.LANE_OPEN)
        self.assertIsNone(apart_keep)

    def test_a_lane_list_that_cannot_be_read_keeps_every_tree_and_removes_nothing(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.env["HERDR_LANES_CLI"] = str(self.root / "missing-lanes.py")

        applied = self.lab.prune("--apply")

        self.assert_kept_and_untouched(tree, "feature/lane-a", applied, "the lane list could not be read")
        self.assertIn("cannot check", applied.stdout)
        self.assertIn("removed 0, freed 0 bytes", applied.stdout)

    def test_a_lane_list_with_an_unexpected_answer_keeps_every_tree_and_removes_nothing(self):
        answers = {"wrong shape": '{"lanes": [{"name": "x"}]}', "not json": "garbage"}
        for label, printed in answers.items():
            with self.subTest(label):
                tree = self.lab.merged_lane(f"lane-{label.split()[0]}")
                stub = self.root / f"stub-{label.split()[0]}.py"
                stub.write_text(f"print({printed!r})\n")
                self.lab.env["HERDR_LANES_CLI"] = str(stub)

                applied = self.lab.prune("--apply")

                self.assert_kept_and_untouched(
                    tree, f"feature/lane-{label.split()[0]}", applied,
                    "the lane list could not be read: lanes list has an unexpected answer")
                self.assertIn("removed 0, freed 0 bytes", applied.stdout)

    def test_a_lane_opened_after_the_listing_keeps_its_tree_at_apply_time(self):
        tree = self.lab.merged_lane("lane-a")
        counter = self.root / "lanes-calls"
        stub = self.root / "stub-late-lane.py"
        stub.write_text(
            "import json, pathlib\n"
            f"counter = pathlib.Path({str(counter)!r})\n"
            "calls = int(counter.read_text()) if counter.exists() else 0\n"
            "counter.write_text(str(calls + 1))\n"
            f"lanes = [] if calls == 0 else [{{'name': 'lane-a', 'worktree': {str(tree)!r}}}]\n"
            "print(json.dumps({'lanes': lanes}))\n")
        self.lab.env["HERDR_LANES_CLI"] = str(stub)

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue(tree.exists())
        self.assertIn("removed 0, freed 0 bytes", applied.stdout)
        self.assertGreaterEqual(int(counter.read_text()), 2)


class RunningFromTest(PruneTestCase):
    def test_the_tree_the_command_runs_from_is_kept_and_the_others_go(self):
        here = self.lab.merged_lane("lane-a")
        other = self.lab.merged_lane("lane-b")

        applied = self.lab.prune("--apply", cwd=here)

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue(here.exists())
        self.assertFalse(other.exists())
        self.assertIn("the command runs from this worktree", line_of(applied, here))

    def test_a_tree_holding_the_working_directory_in_a_subfolder_is_kept(self):
        here = self.lab.merged_lane("lane-a")
        other = self.lab.merged_lane("lane-b")
        (here / "deep").mkdir()

        applied = self.lab.prune("--apply", cwd=here / "deep")

        self.assertTrue(here.exists())
        self.assertFalse(other.exists())
        self.assertIn("the command runs from this worktree", line_of(applied, here))


class StartUpTest(PruneTestCase):
    def assert_stopped(self, tree, finished, message):
        self.assertNotEqual(finished.returncode, 0)
        self.assertIn(message, finished.stderr)
        self.assertTrue(tree.exists())
        self.assertIn("feature/lane-a", self.lab.branches())

    def test_no_origin_stops_and_removes_nothing(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(self.lab.main, "remote", "remove", "origin")

        applied = self.lab.prune("--apply")

        self.assert_stopped(tree, applied, "no origin: nothing to compare against")

    def test_an_unreachable_origin_stops_and_removes_nothing(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(self.lab.main, "remote", "set-url", "origin", str(self.root / "missing.git"))

        applied = self.lab.prune("--apply")

        self.assert_stopped(tree, applied, "git fetch origin main failed")

    def test_an_unset_origin_head_stops_and_names_the_fix(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(self.lab.main, "remote", "set-head", "origin", "--delete")

        applied = self.lab.prune("--apply")

        self.assert_stopped(tree, applied, "git remote set-head origin --auto")

    def test_a_folder_that_is_no_git_repo_stops(self):
        plain = self.root / "plain"
        plain.mkdir()

        finished = self.lab.prune(cwd=plain)

        self.assertNotEqual(finished.returncode, 0)
        self.assertIn("not in a git repository", finished.stderr)

    def test_the_branches_mode_also_stops_without_origin(self):
        self.lab.git(self.lab.main, "remote", "remove", "origin")

        finished = self.lab.prune("--branches", "--apply")

        self.assertNotEqual(finished.returncode, 0)
        self.assertIn("no origin", finished.stderr)


class ProcessTest(PruneTestCase):
    def test_two_trees_sharing_a_name_prefix_are_judged_apart(self):
        short = self.lab.merged_lane("repo-a")
        long = self.lab.merged_lane("repo-ab")
        self.hold_cwd(short)

        applied = self.lab.prune("--apply")

        self.assertTrue(short.exists())
        self.assertFalse(long.exists())
        self.assertIn("has its working directory inside", line_of(applied, short))

    def test_a_live_process_inside_the_tree_keeps_it_and_the_line_names_the_pid(self):
        tree = self.lab.merged_lane("lane-a")
        (tree / "deep").mkdir()
        holder = self.hold_cwd(tree / "deep")

        applied = self.lab.prune("--apply")

        self.assertTrue(tree.exists())
        self.assertIn(f"process {holder.pid} (sleep)", line_of(applied, tree))
        self.assertIn("kept 2: 1 process running, 1 main checkout", applied.stdout)

    def test_proc_less_hosts_read_working_directories_from_lsof(self):
        module = load_script_module()
        stub_dir = self.root / "lsof-bin"
        stub_dir.mkdir()
        write_stub(stub_dir / "lsof", STUB_LSOF)
        env = {"PATH": str(stub_dir), "LSOF_CWD": str(self.root)}

        with mock.patch.object(module, "PROC_ROOT", str(self.root / "no-proc")), mock.patch.dict(os.environ, env):
            found = module.read_processes()

        self.assertEqual(found, [module.Process(4242, "sleep", str(self.root))])

    def test_without_proc_and_lsof_every_tree_is_kept_as_unchecked(self):
        module = load_script_module()
        empty_dir = self.root / "empty-bin"
        empty_dir.mkdir()

        with mock.patch.object(module, "PROC_ROOT", str(self.root / "no-proc")), \
                mock.patch.dict(os.environ, {"PATH": str(empty_dir)}):
            found = module.read_processes()

        self.assertIsNone(found)
        world = types.SimpleNamespace(processes=None)
        keep = module.check_process(None, world, module.Worktree(path=str(self.root)))
        self.assertEqual((keep.code, keep.text), (module.CANNOT_CHECK, "cannot check running processes"))


class HerdrTest(PruneTestCase):
    def test_a_workspace_on_the_tree_keeps_it(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.set_workspaces([{"label": "elsewhere", "worktree": {"checkout_path": str(tree)}}])

        listed = self.lab.prune()

        self.assertIn("herdr workspace 'elsewhere' is on this tree", line_of(listed, tree))

    def test_a_workspace_with_the_folder_name_and_no_checkout_path_keeps_it(self):
        tree = self.lab.merged_lane("lane-a")
        other = self.lab.merged_lane("lane-b")
        self.lab.set_workspaces([{"label": "lane-a", "worktree": None},
                                 {"label": "lane-b", "worktree": {"checkout_path": "/somewhere/else"}}])

        listed = self.lab.prune()

        self.assertIn("carries this folder's name", line_of(listed, tree))
        self.assertTrue(line_of(listed, other).startswith("remove  "))

    def test_an_agent_working_inside_the_tree_keeps_it(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.set_agents([{"cwd": str(tree / "sub")}])

        listed = self.lab.prune()

        self.assertIn(f"a herdr agent works inside it ({tree / 'sub'})", line_of(listed, tree))

    def test_a_herdr_that_does_not_answer_prints_one_note_and_the_other_checks_still_run(self):
        clean = self.lab.merged_lane("lane-a")
        dirty = self.lab.merged_lane("lane-b")
        (dirty / "new.txt").write_text("new\n")
        broken = {"absent": lambda: (self.lab.bin_dir / "herdr-api").unlink(),
                  "failing": lambda: (self.lab.state_dir / "fail").write_text(""),
                  "garbage": lambda: (self.lab.state_dir / "garbage").write_text("")}
        for how, break_herdr in broken.items():
            with self.subTest(how):
                break_herdr()

                listed = self.lab.prune()

                self.assertEqual(listed.returncode, 0, listed.stderr)
                notes = [line for line in listed.stdout.splitlines() if "were not checked" in line]
                self.assertEqual(len(notes), 1, listed.stdout)
                self.assertIn("herdr workspaces and agents were not checked", notes[0])
                self.assertNotIn("process check", notes[0])
                self.assertTrue(line_of(listed, clean).startswith("remove  "))
                self.assertIn("uncommitted changes", line_of(listed, dirty))

    def test_the_note_names_only_the_list_that_failed(self):
        self.lab.merged_lane("lane-a")
        cases = {"workspace": "herdr workspaces were not checked", "agent": "herdr agents were not checked"}
        for kind, expected in cases.items():
            with self.subTest(kind):
                (self.lab.state_dir / f"fail-{kind}").write_text("")

                listed = self.lab.prune()

                notes = [line for line in listed.stdout.splitlines() if "were not checked" in line]
                self.assertEqual(len(notes), 1, listed.stdout)
                self.assertTrue(notes[0].startswith(f"note: {expected} ("), notes[0])
                (self.lab.state_dir / f"fail-{kind}").unlink()

    def test_a_herdr_that_fails_during_apply_prints_its_note_once_and_is_not_called_again(self):
        trees = [self.lab.merged_lane(name) for name in ("lane-a", "lane-b", "lane-c")]
        # The list makes calls 1 and 2 and they work; the first re-check starts at call 3 and fails from there.
        (self.lab.state_dir / "fail-from-call").write_text("3")

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        notes = [line for line in applied.stdout.splitlines() if "were not checked" in line]
        self.assertEqual(len(notes), 1, applied.stdout)
        self.assertEqual(self.lab.herdr_calls(), 4, "herdr was called again after its first failed answer")
        for tree in trees:
            self.assertFalse(tree.exists())

    def test_a_herdr_that_fails_in_the_list_is_not_called_again_during_apply(self):
        self.lab.merged_lane("lane-a")
        self.lab.merged_lane("lane-b")
        (self.lab.state_dir / "fail").write_text("")

        applied = self.lab.prune("--apply")

        notes = [line for line in applied.stdout.splitlines() if "were not checked" in line]
        self.assertEqual(len(notes), 1, applied.stdout)
        self.assertEqual(self.lab.herdr_calls(), 2, "herdr was called again after its first failed answer")

    def test_a_list_that_answered_is_asked_fresh_on_each_recheck_while_the_failed_list_is_asked_once(self):
        tree = self.lab.merged_lane("lane-a")
        (self.lab.state_dir / "fail-agent").write_text("")
        late = [{"label": "opened-late", "worktree": {"checkout_path": str(tree)}}]
        self.lab.write_state("workspaces-late.json", {"result": {"workspaces": late}})
        # The list makes calls 1 (workspaces) and 2 (agents, fails); the first re-check starts at call 3.
        (self.lab.state_dir / "workspaces-on-call").write_text("3")

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue(tree.exists(), "a workspace opened before the re-check was missed")
        self.assertIn("feature/lane-a", self.lab.branches())
        self.assertIn("changed since the list: herdr workspace 'opened-late' is on this tree", applied.stdout)
        notes = [line for line in applied.stdout.splitlines() if "were not checked" in line]
        self.assertEqual(len(notes), 1, applied.stdout)
        self.assertEqual(self.lab.herdr_calls("agent"), 1, "the failed agent list was asked again")
        self.assertEqual(self.lab.herdr_calls("workspace"), 2)


class BranchesTest(PruneTestCase):
    def test_merged_branches_without_a_worktree_are_deleted_and_nothing_else(self):
        done = self.lab.merged_lane("done")
        self.lab.git(self.lab.main, "worktree", "remove", str(done))
        unmerged = self.lab.lane("unmerged")
        self.lab.git(self.lab.main, "worktree", "remove", "--force", str(unmerged))
        self.lab.merged_lane("intree")
        gone = self.lab.merged_lane("gone")
        shutil.rmtree(gone)
        self.lab.git(self.lab.main, "update-ref", "refs/review-snapshots/x", "HEAD")

        listed = self.lab.prune("--branches")

        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual([line for line in listed.stdout.splitlines() if line.startswith("delete")],
                         ["delete  branch feature/done"])
        self.assertIn("feature/done", self.lab.branches())

        applied = self.lab.prune("--branches", "--apply")
        worktrees = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(worktrees.returncode, 0, worktrees.stderr)
        self.assertIn("deleted 1, kept 0, failed 0", applied.stdout)
        self.assertEqual(self.lab.branches() & {"feature/done"}, set())
        for kept in ("main", "feature/unmerged", "feature/gone"):
            self.assertIn(kept, self.lab.branches())
        refs = self.lab.git(self.lab.main, "for-each-ref", "refs/review-snapshots").stdout
        self.assertIn("refs/review-snapshots/x", refs)

    def test_a_branch_a_worktree_has_checked_out_is_never_listed(self):
        self.lab.merged_lane("intree")

        listed = self.lab.prune("--branches")

        self.assertNotIn("feature/intree", listed.stdout)
        self.assertIn("would delete 0 merged branches", listed.stdout)


class InProgressBranchTest(PruneTestCase):
    """A rebase or bisect leaves the worktree's HEAD detached; its branch is still in use."""

    def sequence_editor_env(self):
        editor = self.lab.bin_dir / "edit-first-commit"
        write_stub(editor, STUB_SEQUENCE_EDITOR)
        return dict(self.lab.env, GIT_SEQUENCE_EDITOR=str(editor))

    def assert_branch_survives_branches_apply(self, branch):
        listed = self.lab.prune("--branches")
        applied = self.lab.prune("--branches", "--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertNotIn(f"delete  branch {branch}", listed.stdout)
        self.assertIn(branch, self.lab.branches())
        self.assertIn("deleted 0, kept 0, failed 0", applied.stdout)

    def test_a_bisect_in_a_worktree_keeps_its_branch(self):
        tree = self.lab.lane("lane-a", commits=3)
        self.lab.merge("feature/lane-a")
        self.lab.git(tree, "bisect", "start", "HEAD", self.lab.root_commit())
        head = self.lab.git(tree, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.assertEqual(head, "HEAD", "the bisect did not detach the worktree")

        self.assert_branch_survives_branches_apply("feature/lane-a")

    def test_an_interactive_rebase_stopped_on_edit_keeps_its_branch(self):
        tree = self.lab.lane("lane-a", commits=2)
        self.lab.merge("feature/lane-a")
        subprocess.run([REAL_GIT, "-C", str(tree), "rebase", "-q", "-i", "HEAD~1"], env=self.sequence_editor_env(),
                       capture_output=True, text=True, timeout=60, check=True)
        self.assertTrue(list(pathlib.Path(self.lab.git(tree, "rev-parse", "--absolute-git-dir").stdout.strip(),
                                          "rebase-merge").iterdir()), "no rebase is in progress")

        self.assert_branch_survives_branches_apply("feature/lane-a")

    def test_a_rebase_stopped_on_a_conflict_keeps_its_branch(self):
        tree = self.lab.lane("lane-a")
        self.lab.commit(tree, "base.txt", "lane\n")
        self.lab.merge("feature/lane-a")
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "other", self.lab.root_commit())
        self.lab.commit(self.lab.main, "base.txt", "other\n")
        self.lab.git(self.lab.main, "checkout", "-q", self.lab.default)
        stopped = self.lab.git(tree, "rebase", "--apply", "other", check=False)
        self.assertNotEqual(stopped.returncode, 0, "the rebase did not stop on a conflict")
        git_dir = self.lab.git(tree, "rev-parse", "--absolute-git-dir").stdout.strip()
        self.assertTrue(pathlib.Path(git_dir, "rebase-apply", "head-name").is_file())

        self.assert_branch_survives_branches_apply("feature/lane-a")

    def test_a_detached_worktree_with_no_rebase_or_bisect_does_not_protect_an_unrelated_branch(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(tree, "checkout", "-q", "--detach")

        applied = self.lab.prune("--branches", "--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertNotIn("feature/lane-a", self.lab.branches())
        self.assertIn("deleted 1, kept 0, failed 0", applied.stdout)

    def test_the_kept_reason_names_the_rebase_or_bisect_and_its_worktree(self):
        tree = self.lab.lane("lane-a", commits=3)
        self.lab.merge("feature/lane-a")
        self.lab.git(tree, "bisect", "start", "HEAD", self.lab.root_commit())
        module = load_script_module()

        taken = load_lib_module("worktree_branches").checked_out_branches(module.list_worktrees(str(self.lab.main)))

        self.assertIn("rebase or bisect", taken["feature/lane-a"])
        self.assertIn(str(tree), taken["feature/lane-a"])
        self.assertEqual(taken["main"], "a worktree has it checked out now")

    def test_a_bisect_started_on_a_commit_hash_protects_no_branch_name(self):
        module = load_script_module()
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(tree, "checkout", "-q", "--detach")
        git_dir = self.lab.git(tree, "rev-parse", "--absolute-git-dir").stdout.strip()
        pathlib.Path(git_dir, "BISECT_START").write_text(self.lab.tip("feature/lane-a") + "\n")

        taken = load_lib_module("worktree_branches").checked_out_branches(module.list_worktrees(str(self.lab.main)))

        self.assertNotIn("feature/lane-a", taken)


AHEAD_TEXT = "ahead of its own remote branch, fully on origin/main"


def delete_lines(finished):
    return [line for line in finished.stdout.splitlines() if line.startswith("delete  ")]


class BranchDeletionTest(PruneTestCase):
    def test_a_branch_ahead_of_its_own_upstream_is_listed_with_the_text_and_deleted_after_its_worktree(self):
        ahead = self.lab.ahead_lane("lane-a", "feature/ahead")
        level = self.lab.lane("lane-b", "feature/level")
        self.lab.git(level, "push", "-q", "-u", "origin", "feature/level")
        self.lab.merge("feature/level")
        local_only = self.lab.merged_lane("lane-c")

        listed = self.lab.prune()

        self.assertIn(AHEAD_TEXT, line_of(listed, ahead))
        self.assertNotIn("ahead of", line_of(listed, level))
        self.assertNotIn("ahead of", line_of(listed, local_only))
        applied = self.lab.prune("--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(self.lab.branches(), {"main"})
        self.assertIn("deleted branch feature/ahead", applied.stdout)
        self.assertIn("kept 1, failed 0", applied.stdout)

    def test_a_branch_ahead_of_its_own_upstream_is_listed_with_the_text_and_deleted_in_branches_mode(self):
        ahead = self.lab.ahead_lane("lane-a", "feature/ahead")
        self.lab.git(self.lab.main, "worktree", "remove", str(ahead))
        self.lab.worktree_free_lane("lane-b", "feature/level")

        listed = self.lab.prune("--branches")

        self.assertEqual(delete_lines(listed), [f"delete  branch feature/ahead  {AHEAD_TEXT}",
                                                "delete  branch feature/level"])
        applied = self.lab.prune("--branches", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn("deleted 2, kept 0, failed 0", applied.stdout)
        self.assertEqual(self.lab.branches(), {"main"})

    def test_the_branch_config_goes_with_the_branch_and_a_prefix_named_branch_keeps_its_own(self):
        self.lab.worktree_free_lane("lane-a", "fix/a")
        other = self.lab.lane("lane-b", "fix/a-b")
        self.lab.git(other, "push", "-q", "-u", "origin", "fix/a-b")
        self.lab.git(self.lab.main, "worktree", "remove", str(other))
        self.assertIn("branch.fix/a.remote origin", self.lab.branch_config())

        applied = self.lab.prune("--branches", "--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(self.lab.branches(), {"main", "fix/a-b"})
        remaining = [line for line in self.lab.branch_config() if line.startswith("branch.fix/")]
        self.assertEqual(remaining, ["branch.fix/a-b.merge refs/heads/fix/a-b", "branch.fix/a-b.remote origin"])

    def test_a_branch_with_no_config_section_is_deleted_without_a_warning(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(self.lab.main, "worktree", "remove", str(tree))
        self.assertEqual([line for line in self.lab.branch_config() if "lane-a" in line], [])

        applied = self.lab.prune("--branches", "--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(applied.stderr, "")
        self.assertNotIn("warning", applied.stdout)
        self.assertNotIn("feature/lane-a", self.lab.branches())

    def test_a_config_section_that_cannot_be_removed_is_a_warning_and_the_branch_still_counts_as_deleted(self):
        self.lab.worktree_free_lane("lane-a", "feature/lane-a")
        write_stub(self.lab.bin_dir / "git", STUB_GIT_FAILING_CONFIG)
        self.lab.env["REAL_GIT"] = REAL_GIT

        applied = self.lab.prune("--branches", "--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn("warning: branch feature/lane-a is deleted but its config section stays", applied.stdout)
        self.assertIn("deleted 1, kept 0, failed 0", applied.stdout)
        self.assertNotIn("feature/lane-a", self.lab.branches())

    def test_a_deleted_branch_can_be_created_again_and_leaves_no_old_reflog(self):
        self.lab.worktree_free_lane("lane-a", "feature/lane-a")
        old_tip = self.lab.tip("feature/lane-a")

        applied = self.lab.prune("--branches", "--apply")
        self.lab.git(self.lab.main, "branch", "feature/lane-a", "main")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        reflog = self.lab.git(self.lab.main, "reflog", "show", "feature/lane-a").stdout.splitlines()
        self.assertEqual(len(reflog), 1, reflog)
        self.assertNotIn(old_tip[:7], reflog[0].split(" ")[0])

    def test_the_branches_delete_never_touches_the_default_branch_or_a_checked_out_branch(self):
        module = load_script_module()
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(self.lab.main, "checkout", "-q", "-b", "scratch")
        repo = module.Repo(str(self.lab.main), "main", "origin/main", self.lab.tip("main"), str(self.root))
        tally = module.Tally()

        with contextlib.redirect_stdout(io.StringIO()):
            load_lib_module("worktree_branches").delete_one_branch(repo, "main", tally)
            load_lib_module("worktree_branches").delete_one_branch(repo, "feature/lane-a", tally)

        self.assertEqual((tally.kept, tally.removed, tally.failed), (2, 0, 0))
        self.assertEqual(self.lab.branches(), {"main", "scratch", "feature/lane-a"})
        self.assertTrue(tree.exists())

    def test_a_branch_that_moved_between_the_check_and_the_delete_fails_alone_in_worktree_mode(self):
        moved = self.lab.merged_lane("lane-a")
        other = self.lab.merged_lane("lane-b")
        write_stub(self.lab.bin_dir / "git", STUB_GIT_MOVING_ONE_BRANCH)
        moved_to = self.lab.root_commit()
        self.lab.env.update({"REAL_GIT": REAL_GIT, "MOVE_BRANCH": "feature/lane-a", "MOVE_TO": moved_to})

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 1)
        self.assertFalse(moved.exists())
        self.assertFalse(other.exists())
        self.assertEqual(self.lab.branches(), {"main", "feature/lane-a"})
        self.assertEqual(self.lab.tip("feature/lane-a"), moved_to)
        self.assertIn("failed  branch feature/lane-a stays: git update-ref -d refused", applied.stdout)
        self.assertIn("removed 2, freed ", applied.stdout)
        self.assertIn("failed 1", applied.stdout)

    def test_a_branch_that_moved_between_the_check_and_the_delete_fails_alone_in_branches_mode(self):
        moved = self.lab.merged_lane("lane-a")
        other = self.lab.merged_lane("lane-b")
        for tree in (moved, other):
            self.lab.git(self.lab.main, "worktree", "remove", str(tree))
        self.lab.git(self.lab.main, "update-ref", "refs/review-snapshots/x", "HEAD")
        write_stub(self.lab.bin_dir / "git", STUB_GIT_MOVING_ONE_BRANCH)
        moved_to = self.lab.root_commit()
        self.lab.env.update({"REAL_GIT": REAL_GIT, "MOVE_BRANCH": "feature/lane-a", "MOVE_TO": moved_to})

        applied = self.lab.prune("--branches", "--apply")

        self.assertEqual(applied.returncode, 1)
        self.assertEqual(self.lab.branches(), {"main", "feature/lane-a"})
        self.assertIn("failed  branch feature/lane-a: git update-ref -d refused", applied.stdout)
        self.assertIn("deleted 1, kept 0, failed 1", applied.stdout)
        refs = self.lab.git(self.lab.main, "for-each-ref", "refs/review-snapshots").stdout
        self.assertIn("refs/review-snapshots/x", refs)

    def test_a_tip_that_is_no_longer_on_the_compare_ref_is_not_deleted(self):
        module = load_script_module()
        tree = self.lab.merged_lane("lane-a")
        self.lab.git(self.lab.main, "worktree", "remove", str(tree))
        self.lab.commit(self.lab.main, "other.txt")
        stray = self.lab.git(self.lab.main, "rev-parse", "HEAD").stdout.strip()
        self.lab.git(self.lab.main, "update-ref", "refs/heads/feature/lane-a", stray)
        self.lab.git(self.lab.main, "reset", "-q", "--hard", "HEAD~1")
        repo = module.Repo(str(self.lab.main), "main", "origin/main", self.lab.tip("main"), str(self.root))

        outcome = module.delete_branch(repo, "feature/lane-a")

        self.assertIn("is not on origin/main", outcome.failure)
        self.assertIn("feature/lane-a", self.lab.branches())


class FailureTest(PruneTestCase):
    def test_one_failed_removal_is_reported_and_the_run_goes_on(self):
        first = self.lab.merged_lane("lane-a")
        failing = self.lab.merged_lane("lane-b")
        last = self.lab.merged_lane("lane-c")
        write_stub(self.lab.bin_dir / "git", STUB_GIT_FAILING_ONE_REMOVAL)
        self.lab.env.update({"FAIL_PATH": str(failing), "REAL_GIT": REAL_GIT})

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 1)
        self.assertFalse(first.exists())
        self.assertTrue(failing.exists())
        self.assertFalse(last.exists())
        self.assertIn("feature/lane-b", self.lab.branches())
        self.assertIn(f"failed  {failing}: git worktree remove refused", applied.stdout)
        self.assertIn("fatal: simulated removal failure", applied.stderr)
        self.assertIn("removed 2, freed ", applied.stdout)
        self.assertIn("failed 1", applied.stdout)

    def fail_one_worktree_list(self, call_number):
        write_stub(self.lab.bin_dir / "git", STUB_GIT_FAILING_ONE_WORKTREE_LIST)
        self.lab.env.update({"FAIL_LIST_CALL": str(call_number), "REAL_GIT": REAL_GIT})

    def test_a_failed_re_read_of_the_worktree_list_fails_that_tree_alone_and_the_run_goes_on(self):
        first = self.lab.merged_lane("lane-a")
        second = self.lab.merged_lane("lane-b")
        # Call 1 reads the world for the plan; call 2 is the first tree's re-check.
        self.fail_one_worktree_list(2)

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 1, applied.stderr)
        self.assertTrue(first.exists())
        self.assertIn("feature/lane-a", self.lab.branches())
        self.assertFalse(second.exists())
        self.assertIn(f"failed  {first}: the re-check could not read git state: git worktree list failed: "
                      "fatal: simulated list failure", applied.stdout)
        self.assertIn("removed 1, freed ", applied.stdout)
        self.assertIn("kept 1, failed 1", applied.stdout)

    def test_a_failed_re_read_of_the_worktree_list_fails_that_branch_alone_in_branches_mode(self):
        self.lab.worktree_free_lane("lane-a", "feature/a")
        self.lab.worktree_free_lane("lane-b", "feature/b")
        # Call 1 lists the branches without a worktree; call 2 is the first branch's re-check.
        self.fail_one_worktree_list(2)

        applied = self.lab.prune("--branches", "--apply")

        self.assertEqual(applied.returncode, 1, applied.stderr)
        self.assertIn("feature/a", self.lab.branches())
        self.assertNotIn("feature/b", self.lab.branches())
        self.assertIn("failed  branch feature/a: the re-check could not read git state: git worktree list failed: "
                      "fatal: simulated list failure", applied.stdout)
        self.assertIn("deleted 1, kept 0, failed 1", applied.stdout)

    def test_a_local_default_branch_behind_origin_does_not_stop_the_branch_delete(self):
        tree = self.lab.lane("lane-a")
        # origin's main gains the commit, the local main does not: the compare ref is origin/main, not the local main.
        self.lab.git(tree, "push", "-q", "origin", "HEAD:main")

        applied = self.lab.prune("--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertFalse(tree.exists())
        self.assertNotIn("feature/lane-a", self.lab.branches())
        self.assertNotIn("Update the local main", applied.stdout)


class CheckVerbTest(PruneTestCase):
    def check(self, tree):
        finished = self.lab.prune("--check", str(tree))
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return json.loads(finished.stdout)

    def test_the_verdict_matches_list_mode_for_merged_dirty_unmerged_and_squash_merged_trees(self):
        clean = self.lab.merged_lane("lane-clean")
        dirty = self.lab.merged_lane("lane-dirty")
        (dirty / "scratch.txt").write_text("not committed\n")
        unmerged = self.lab.lane("lane-unmerged")
        squashed = self.lab.lane("lane-squash")
        self.lab.git(self.lab.main, "merge", "-q", "--squash", "feature/lane-squash")
        self.lab.git(self.lab.main, "commit", "-q", "-m", "squash")
        self.lab.git(self.lab.main, "push", "-q", "origin", "main")
        listed = self.lab.prune()
        expected = {clean: ("remove", None, None), dirty: ("keep", "uncommitted changes", "uncommitted changes"),
                    unmerged: ("keep", "not merged", "commits not on origin/main"),
                    squashed: ("keep", "not merged", "commits not on origin/main")}

        for tree, (verdict, code, reason_part) in expected.items():
            with self.subTest(tree.name):
                answer = self.check(tree)

                self.assertEqual((answer["verdict"], answer["code"]), (verdict, code))
                self.assertEqual(answer["path"], str(tree))
                self.assertEqual(answer["branch"], f"feature/{tree.name}")
                line = line_of(listed, tree)
                self.assertTrue(line.startswith(verdict), line)
                if verdict == "keep":
                    self.assertIn(reason_part, answer["reason"])
                    self.assertTrue(line.endswith(answer["reason"]), line)
                else:
                    self.assertIsNone(answer["reason"])

    def test_a_workspace_agent_or_open_lane_on_a_merged_clean_tree_does_not_keep_it(self):
        tree = self.lab.merged_lane("lane-a")
        self.lab.set_workspaces([{"label": "lane-a", "worktree": {"checkout_path": str(tree)}}])
        self.lab.set_agents([{"cwd": str(tree)}])
        self.lab.open_lane("lane-a", tree)
        self.hold_cwd(tree)

        answer = self.check(tree)

        self.assertEqual(answer["verdict"], "remove")
        self.assertTrue(line_of(self.lab.prune(), tree).startswith("keep"))

    def test_a_path_that_is_not_a_worktree_exits_1_with_the_message(self):
        finished = self.lab.prune("--check", str(self.root / "nowhere"))

        self.assertEqual(finished.returncode, 1)
        self.assertEqual(finished.stdout, "")
        self.assertIn("is not a worktree of this repository", finished.stderr)

    def test_check_without_exactly_one_path_prints_usage_and_exits_2(self):
        for arguments in (("--check",), ("--check", "a", "b")):
            with self.subTest(arguments):
                finished = self.lab.prune(*arguments)

                self.assertEqual(finished.returncode, 2)
                self.assertIn("usage: herdr-worktree-prune", finished.stderr)


class UsageTest(PruneTestCase):
    def test_help_prints_the_usage_block_and_says_list_mode_fetches(self):
        finished = self.lab.prune("--help")

        self.assertEqual(finished.returncode, 0)
        self.assertIn("Usage: herdr-worktree-prune", finished.stdout)
        self.assertIn("list mode too: it\nupdates only the remote-tracking ref", finished.stdout)

    def test_an_unknown_flag_or_extra_argument_prints_usage_on_stderr_and_exits_2(self):
        for argument in ("--force", "extra"):
            with self.subTest(argument):
                finished = self.lab.prune(argument)

                self.assertEqual(finished.returncode, 2)
                self.assertIn("usage: herdr-worktree-prune", finished.stderr)
                self.assertEqual(finished.stdout, "")


class ParserTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        environment = mock.patch.dict(os.environ, {"XDG_STATE_HOME": scratch.name, "HERDR_LANES_CLI": str(LANES_CLI)})
        environment.start()
        self.addCleanup(environment.stop)
        self.module = load_script_module()

    def test_stash_subjects_name_a_branch_only_in_the_two_forms_that_carry_one(self):
        cases = {
            "WIP on feature/x: 1a2b3c4 a subject: with a colon": "feature/x",
            "On feature/x: my message": "feature/x",
            "WIP on (no branch): 1a2b3c4 a subject": None,
            "On (no branch): my message": None,
            "autostash": None,
            "autostash while switching to 'main'": None,
        }
        for subject, expected in cases.items():
            with self.subTest(subject):
                self.assertEqual(self.module.parse_stash_subject(subject), expected)

    def test_porcelain_entries_keep_paths_with_spaces_and_newlines_whole(self):
        listing = ("worktree /x/a b\0HEAD 1\0branch refs/heads/f/a\0\0"
                   "worktree /x/line\nbreak\0HEAD 2\0detached\0locked why not\0\0"
                   "worktree /x/gone\0HEAD 3\0branch refs/heads/g\0prunable gitdir file\0\0")

        found = load_lib_module("worktree_git").parse_worktrees(listing)

        self.assertEqual([tree.path for tree in found], ["/x/a b", "/x/line\nbreak", "/x/gone"])
        self.assertEqual(found[0].branch, "f/a")
        self.assertTrue(found[1].detached and found[1].locked)
        self.assertEqual(found[1].lock_reason, "why not")
        self.assertTrue(found[2].prunable)

    def test_an_unknown_porcelain_field_stops_loudly(self):
        with self.assertRaises(self.module.PruneError):
            load_lib_module("worktree_git").parse_worktrees("worktree /x\0HEAD 1\0surprise yes\0\0")

    def test_sizes_above_a_tebibyte_print_in_tib(self):
        cases = {512: "512 B", 2048: "2.0 KiB", 3 * 1024 ** 3: "3.0 GiB", 1500 * 1024 ** 3: "1.5 TiB",
                 3 * 1024 ** 4: "3.0 TiB", None: "size unknown"}
        for size, expected in cases.items():
            with self.subTest(size):
                self.assertEqual(self.module.human_size(size), expected)

    def test_inside_compares_whole_path_components(self):
        self.assertTrue(self.module.inside("/x/repo-a", "/x/repo-a"))
        self.assertTrue(self.module.inside("/x/repo-a/sub", "/x/repo-a"))
        self.assertFalse(self.module.inside("/x/repo-ab", "/x/repo-a"))


if __name__ == "__main__":
    unittest.main()
