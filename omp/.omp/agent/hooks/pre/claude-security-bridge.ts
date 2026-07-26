/**
 * claude-security-bridge.ts — omp hook that delegates tool-call gating to the
 * Claude Code security hooks in ~/.claude/scripts/.
 *
 * Why a bridge instead of a port: the CB Security Hooks (bash-safety-gate,
 * block-credential-read, write-edit-safety-gate) are GENERATED and versioned —
 * any re-implementation drifts silently (see the stale ~/.pi/agent/extensions/
 * protected-paths.ts, which omp doesn't even read). Shelling out keeps the
 * bash scripts as the single source of truth for both harnesses.
 *
 * Covered gates (the "Safety Rails" set from the global CLAUDE.md):
 *   PreToolUse(Bash)        bash-safety-gate.sh, git-discipline-gate.sh, review-commit-gate.sh
 *   PreToolUse(Read|Grep)   block-credential-read.sh        (also mapped: glob)
 *   PreToolUse(Write|Edit)  write-edit-safety-gate.sh       (also mapped: ast_edit)
 *   PostToolUse(Agent)      review-commit-gate.sh           (arms on coder dispatch; omp task tool)
 *
 * Deliberately skipped:
 *   agent-model-guard.sh — resolves agent files under ~/.claude/agents and
 *     denies unpinned call-site models; meaningless against omp's bundled
 *     agents and would deny every dispatch.
 *   mechanical-check-gate.sh — PreToolUse(Agent); denies delegating /code's
 *     vacuous-green pre-flight to a subagent. Not security, and it keys off
 *     Claude's `description` field, which omp's task tool does not mirror.
 *     Consequence: under omp that pre-flight is prose-enforced only.
 *   spec-budget-gate / stub-guard / log-* / notify / formatters — not security.
 *
 * Output conventions handled:
 *   CB hooks  — stdout JSON line {"hookSpecificOutput":{"permissionDecision":"deny",...}}, exit 0
 *   custom    — stderr message + exit 2
 *
 * Session id: a per-session UUID. review-commit-gate keys its dirty/clean
 * state to it; the /review skill's `review-gate-mark clean` bash command runs
 * through this same bridge in the same session, so the mark lands correctly.
 * One-shot user override (unchanged): touch ~/.claude/state/review-gate/<uuid>.skip
 *
 * Known gaps (inherent to bridging, not fixable here):
 *   - omp's eval tool executes arbitrary JS/Python with no bash string to
 *     inspect — no Claude equivalent exists, so no gate covers it.
 *   - xd:// device tools (ast_edit etc.) are gated IF they surface under
 *     their own tool name; if one ever surfaces as a generic write with an
 *     xd:// path, its inner target paths are not inspected.
 *   CLAUDE_SKIP_HOOKS is honored by the scripts themselves (env inherited).
 */

import { spawn, type ChildProcess } from "node:child_process";
import { randomUUID } from "node:crypto";
import { homedir } from "node:os";
import { join } from "node:path";

const SCRIPTS_DIR = join(homedir(), ".claude", "scripts");
const SESSION_ID = randomUUID();
const GATE_TIMEOUT_MS = 10_000;

/** omp tool name → Claude tool name + gate scripts (PreToolUse). */
const PRE_TOOL_GATES: Record<string, { tool: string; gates: string[] }> = {
  bash: {
    tool: "Bash",
    gates: [
      "bash-safety-gate.sh",
      "git-discipline-gate.sh",
      "review-commit-gate.sh",
    ],
  },
  read: { tool: "Read", gates: ["block-credential-read.sh"] },
  grep: { tool: "Grep", gates: ["block-credential-read.sh"] },
  glob: { tool: "Glob", gates: ["block-credential-read.sh"] },
  write: { tool: "Write", gates: ["write-edit-safety-gate.sh"] },
  edit: { tool: "Edit", gates: ["write-edit-safety-gate.sh"] },
  ast_edit: { tool: "Edit", gates: ["write-edit-safety-gate.sh"] },
};

interface GateResult {
  denied: boolean;
  reason?: string;
}

/** Minimal structural slice of omp's hook event (tool_call / tool_result). */
interface ToolEvent {
  toolName: string;
  input?: Record<string, unknown>;
  isError?: boolean;
}

/** Minimal structural slice of omp's hook context. */
interface HookCtx {
  cwd?: string;
}

interface HookPi {
  on(
    event: "tool_call",
    handler: (
      event: ToolEvent,
      ctx: HookCtx,
    ) => Promise<{ block: boolean; reason?: string } | undefined>,
  ): void;
  on(
    event: "tool_result",
    handler: (event: ToolEvent, ctx: HookCtx) => Promise<undefined>,
  ): void;
}

interface HookVerdict {
  hookSpecificOutput?: {
    permissionDecision?: string;
    permissionDecisionReason?: string;
  };
}

function isHookVerdict(value: unknown): value is HookVerdict {
  return typeof value === "object" && value !== null;
}

/**
 * Run one gate script with a Claude-hook JSON payload on stdin.
 * Fails OPEN on spawn error/timeout (a hung bridge must not freeze the
 * session); the scripts themselves fail CLOSED on their own parse errors.
 */
function runGate(
  script: string,
  payload: Record<string, unknown>,
  cwd: string,
): Promise<GateResult> {
  const { promise, resolve } = Promise.withResolvers<GateResult>();
  let stdout = "";
  let stderr = "";
  let settled = false;
  let timer: ReturnType<typeof setTimeout>;
  const finish = (r: GateResult): void => {
    if (!settled) {
      settled = true;
      clearTimeout(timer);
      resolve(r);
    }
  };

  let child: ChildProcess;
  try {
    child = spawn("bash", [join(SCRIPTS_DIR, script)], {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
    });
  } catch (e) {
    console.error(`[claude-security-bridge] spawn failed for ${script}: ${e}`);
    resolve({ denied: false });
    return promise;
  }

  timer = setTimeout(() => {
    try {
      child.kill("SIGKILL");
    } catch {}
    console.error(
      `[claude-security-bridge] ${script} timed out after ${GATE_TIMEOUT_MS}ms — failing open`,
    );
    finish({ denied: false });
  }, GATE_TIMEOUT_MS);

  child.stdout?.on("data", (d: Buffer) => (stdout += d));
  child.stderr?.on("data", (d: Buffer) => (stderr += d));
  child.on("error", (e) => {
    console.error(`[claude-security-bridge] ${script} error: ${e}`);
    finish({ denied: false });
  });
  child.on("close", (code) => {
    // CB Security Hooks convention: single-line JSON verdict on stdout.
    for (const line of stdout.split("\n")) {
      const t = line.trim();
      if (!t.startsWith("{")) continue;
      try {
        const parsed: unknown = JSON.parse(t);
        if (
          isHookVerdict(parsed) &&
          parsed.hookSpecificOutput?.permissionDecision === "deny"
        ) {
          return finish({
            denied: true,
            reason:
              parsed.hookSpecificOutput.permissionDecisionReason ??
              `${script} denied`,
          });
        }
      } catch {
        // not a JSON line — keep scanning
      }
    }
    // Custom gates convention: exit 2, human reason on stderr.
    if (code === 2) {
      return finish({
        denied: true,
        reason: stderr.trim() || `${script} blocked`,
      });
    }
    finish({ denied: false });
  });

  child.stdin?.on("error", () => {});
  child.stdin?.end(JSON.stringify(payload));
  return promise;
}

/** Expand a leading ~ so gates that exact-prefix-match $HOME see the real path. */
function expandTilde(input: Record<string, unknown>): Record<string, unknown> {
  const out = { ...input };
  for (const key of ["path", "file_path"]) {
    const v = out[key];
    if (typeof v === "string" && (v === "~" || v.startsWith("~/"))) {
      out[key] = join(homedir(), v.slice(1));
    }
  }
  return out;
}

function taskAgents(input: Record<string, unknown>): string[] {
  const agents: string[] = [];
  const tasks = input.tasks;
  if (Array.isArray(tasks)) {
    for (const t of tasks) {
      if (typeof t === "object" && t !== null && "agent" in t && t.agent) {
        agents.push(String(t.agent));
      }
    }
  }
  if (input.agent) agents.push(String(input.agent));
  return agents;
}

export default function bridge(pi: HookPi): void {
  pi.on("tool_call", async (event, ctx) => {
    const mapping = PRE_TOOL_GATES[event.toolName];
    if (!mapping) return undefined;

    const cwd = ctx?.cwd ?? process.cwd();
    const input = event.input ?? {};

    // Fan out path-arrays (ast_edit-style) so per-path gates see every target.
    const inputs =
      Array.isArray(input.paths) && input.paths.length > 0
        ? input.paths.map((p: unknown) => expandTilde({ ...input, path: p }))
        : [expandTilde(input)];

    for (const toolInput of inputs) {
      const payload = {
        hook_event_name: "PreToolUse",
        session_id: SESSION_ID,
        tool_name: mapping.tool,
        tool_input: toolInput,
      };
      const results = await Promise.all(
        mapping.gates.map((g) => runGate(g, payload, cwd)),
      );
      const hit = results.find((r) => r.denied);
      if (hit) return { block: true, reason: hit.reason };
    }
    return undefined;
  });

  // review-commit-gate arming: a coder dispatch marks the session dirty.
  // omp's task tool returns launch stubs (jobs settle later) — same semantics
  // as Claude's PostToolUse(Agent), which is exactly what the gate expects.
  pi.on("tool_result", async (event, ctx) => {
    if (event.toolName !== "task" || event.isError) return undefined;
    const agents = taskAgents(event.input ?? {});
    if (agents.length === 0) return undefined;

    const cwd = ctx?.cwd ?? process.cwd();
    await Promise.all(
      agents.map((agent) =>
        runGate(
          "review-commit-gate.sh",
          {
            hook_event_name: "PostToolUse",
            session_id: SESSION_ID,
            tool_name: "Agent",
            tool_input: { subagent_type: agent },
          },
          cwd,
        ),
      ),
    );
    return undefined;
  });
}
