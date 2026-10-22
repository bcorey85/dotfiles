import json
import os
import pathlib
import subprocess
import tempfile
import unittest

import fake_ledger

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = REPO_ROOT / "claude" / ".claude"
SCRIPT = pathlib.Path(os.environ.get("STAGE_SCRIPT") or REAL_CLAUDE / "skills" / "stage" / "scripts" / "stage.mjs")
LOG_SCRIPT = pathlib.Path(os.environ.get("STAGE_LOG_SCRIPT") or REAL_CLAUDE / "skills" / "review" / "log-review-metrics")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


class StageRunTest(unittest.TestCase):
    def setUp(self):
        tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(tempDir.cleanup)
        self.tempRoot = pathlib.Path(tempDir.name)
        self.home = self.tempRoot / "home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "toolkit-telemetry").touch()
        self.repo = self.tempRoot / "myrepo"
        self.repo.mkdir()
        self.ledgerEnv = fake_ledger.install(self.tempRoot)
        self.git("init", "-q")
        self.write("README.md", "hello\n")
        self.git("add", "README.md")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run(["git", *args], cwd=self.repo, env=env, check=True, capture_output=True, text=True).stdout

    def write(self, relPath, body):
        target = self.repo / relPath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    def runStage(self, *args, logScript=None):
        env = {
            **os.environ,
            **GIT_ENV,
            "HOME": str(self.home),
            **self.ledgerEnv,
            "STAGE_LOG_SCRIPT": str(logScript or LOG_SCRIPT),
        }
        return subprocess.run(["node", str(SCRIPT), *args], cwd=self.repo, env=env, capture_output=True, text=True)

    def stagedPaths(self):
        out = self.git("-c", "core.quotepath=off", "diff", "--cached", "--name-only")
        return [line for line in out.split("\n") if line]

    def metricsRows(self):
        return fake_ledger.recorded_rows(self.ledgerEnv, "review_metrics")

    def jumpRows(self, stdout):
        inside = stdout.split("```jump-queue\n", 1)[1].split("```", 1)[0]
        return [json.loads(line) for line in inside.splitlines() if line]

    def addBarrel(self):
        self.write("src/index.ts", "export * from './a';\n")

    def test_empty_diff_is_clean_and_logs_a_row(self):
        result = self.runStage("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## Stage", result.stdout)
        self.assertIn("nothing left to read", result.stdout)
        self.assertEqual(self.jumpRows(result.stdout), [])
        rows = self.metricsRows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lane"], "stage")
        self.assertNotIn("repo", rows[0])
        self.assertEqual(rows[0]["suppressed"], "0")
        self.assertEqual(rows[0]["queue"], "0")
        self.assertEqual(rows[0]["result"], "clean")

    def test_stages_safe_tier_and_queues_the_rest(self):
        self.addBarrel()
        self.write("src/service.ts", "export const a = 1;\n")
        self.write(".github/workflows/ci.yml", "on: push\n")
        result = self.runStage("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stagedPaths(), ["src/index.ts"])
        self.assertIn("Staged mechanically (1)", result.stdout)
        self.assertIn("Read (2), in blast-radius order:", result.stdout)
        self.assertLess(result.stdout.index(".github/workflows/ci.yml"), result.stdout.index("src/service.ts"))
        self.assertIn("hot path", result.stdout)
        rows = self.jumpRows(result.stdout)
        self.assertEqual([row["tier"] for row in rows], ["ESCALATE", "READ"])
        self.assertEqual(rows[1], {"tier": "READ", "path": "src/service.ts", "line": 1, "reason": "semantic change, no tripwire"})
        self.assertIn("hot path", rows[0]["reason"])
        logged = self.metricsRows()[0]
        self.assertEqual((logged["suppressed"], logged["queue"], logged["result"]), ("1", "2", "residue"))
        self.assertIn("Still yours:", result.stdout.strip().splitlines()[-1])

    def test_classifies_once(self):
        self.addBarrel()
        result = self.runStage("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("## Stage"), 1)
        self.assertEqual(len(self.metricsRows()), 1)

    def test_deleted_file_is_queued_without_a_jump_row(self):
        self.write("lib/auth/session.ts", "export const s = 1;\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "add auth")
        (self.repo / "lib/auth/session.ts").unlink()
        result = self.runStage("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("`lib/auth/session.ts`", result.stdout)
        self.assertEqual(self.jumpRows(result.stdout), [])
        self.assertEqual(self.metricsRows()[0]["queue"], "1")

    def test_renamed_file(self):
        self.write("src/old.ts", "export const value = 1;\nexport const other = 2;\nexport const third = 3;\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "add old")
        self.git("mv", "src/old.ts", "src/renamed.ts")
        result = self.runStage("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("`src/renamed.ts`", result.stdout)
        self.assertNotIn("`src/old.ts`", result.stdout)

    def test_space_and_non_ascii_paths(self):
        self.write("docs/my notes.md", "# notes\n")
        self.write("src/café/日本語.ts", "export const x = 1;\n")
        self.write("src/ok dir/index.ts", "export * from './a';\n")
        result = self.runStage("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stagedPaths(), ["src/ok dir/index.ts"])
        rows = {row["path"]: row for row in self.jumpRows(result.stdout)}
        self.assertEqual(set(rows), {"docs/my notes.md", "src/café/日本語.ts"})
        self.assertEqual(rows["docs/my notes.md"]["tier"], "SKIM")
        self.assertIn("`src/café/日本語.ts`", result.stdout)

    def test_bad_stage_json_warns_and_uses_defaults(self):
        self.write(".stage.json", "{ not json")
        self.addBarrel()
        result = self.runStage("--run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("could not parse", result.stderr)
        self.assertIn("src/index.ts", self.stagedPaths())

    def test_no_stage_stages_nothing(self):
        self.addBarrel()
        self.write("src/service.ts", "export const a = 1;\n")
        result = self.runStage("--run", "--no-stage")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stagedPaths(), [])
        self.assertIn("Staged mechanically (0)", result.stdout)
        logged = self.metricsRows()[0]
        self.assertEqual((logged["suppressed"], logged["queue"]), ("0", "1"))

    def test_classifier_error_exits_nonzero_and_stages_nothing(self):
        self.addBarrel()
        self.write(".stage.json", json.dumps({"hotPaths": ["(unclosed"]}))
        result = self.runStage("--run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage: --run failed", result.stderr)
        self.assertIn("nothing staged", result.stderr)
        self.assertNotIn("    at ", result.stderr)
        self.assertEqual(self.stagedPaths(), [])
        self.assertEqual(self.metricsRows(), [])

    def test_repo_without_commits_is_a_clear_error(self):
        emptyRepo = self.tempRoot / "fresh"
        emptyRepo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=emptyRepo, check=True, env={**os.environ, **GIT_ENV})
        (emptyRepo / "index.ts").write_text("export * from './a';\n")
        env = {**os.environ, **GIT_ENV, **self.ledgerEnv, "STAGE_LOG_SCRIPT": str(LOG_SCRIPT)}
        result = subprocess.run(["node", str(SCRIPT), "--run"], cwd=emptyRepo, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage: --run failed", result.stderr)
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=emptyRepo, capture_output=True, text=True).stdout
        self.assertEqual(staged, "")

    def test_not_a_repo_exits_nonzero(self):
        plainDir = self.tempRoot / "plain"
        plainDir.mkdir()
        env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(self.tempRoot)}
        result = subprocess.run(["node", str(SCRIPT), "--run"], cwd=plainDir, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not inside a git repository", result.stderr)

    def test_logging_failure_warns_and_keeps_exit_zero(self):
        self.addBarrel()
        failingLog = self.tempRoot / "failing-log"
        failingLog.write_text("#!/usr/bin/env bash\necho boom >&2\nexit 3\n")
        result = self.runStage("--run", logScript=failingLog)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("metrics row not logged", result.stderr)
        self.assertIn("boom", result.stderr)
        self.assertEqual(self.stagedPaths(), ["src/index.ts"])
        self.assertIn("## Stage", result.stdout)

    def test_json_mode_unchanged(self):
        self.addBarrel()
        result = self.runStage("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual([e["path"] for e in data["safe"]], ["src/index.ts"])
        self.assertEqual(data["staged"], [])
        self.assertEqual(self.stagedPaths(), [])
        self.assertEqual(self.metricsRows(), [])

    def test_stage_mode_unchanged(self):
        self.addBarrel()
        result = self.runStage("--stage")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stagedPaths(), ["src/index.ts"])
        self.assertIn("SAFE — staged", result.stdout)
        self.assertNotIn("## Stage", result.stdout)
        self.assertEqual(self.metricsRows(), [])

    def test_json_empty_diff_unchanged(self):
        result = self.runStage("--json")
        self.assertEqual(json.loads(result.stdout), {"escalate": [], "read": [], "skim": [], "safe": [], "staged": []})


if __name__ == "__main__":
    unittest.main()
