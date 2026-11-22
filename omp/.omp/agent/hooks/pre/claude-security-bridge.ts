/**
 * claude-security-bridge.ts — omp hook that delegates tool-call gating to the
 * Claude Code security hooks in ~/.claude/scripts/.
 *
 * The CB gates are generated and versioned, so a port drifts silently; the
 * bash scripts stay the single source of truth for both harnesses.
 *
 * Covered gates (the "Safety Rails" set from the global CLAUDE.md):
 *   PreToolUse(Bash)        bash-safety-gate.sh, gates/git_discipline_gate.py, gates/shell_write_gate.py, gates/quality_check_cap.py
 *   PreToolUse(Read|Grep)   block-credential-read.sh        (also mapped: glob)
 *   PreToolUse(Write|Edit)  write-edit-safety-gate.sh       (also mapped: ast_edit)
 *   PostToolUse(Bash)       gates/quality_check_cap.py      (records a check that ran, failing or not)
 *   PostToolUse(Write|Edit) gates/quality_check_cap.py      (marks an edit that landed; also ast_edit)
 *
 * Deliberately skipped: agent-model-guard.sh (would deny every omp dispatch —
 * it resolves ~/.claude/agents); spec-budget-gate / log-* / notify /
 * formatters (not security).
 *
 * Output conventions handled:
 *   CB hooks  — stdout JSON line {"hookSpecificOutput":{"permissionDecision":"deny"|"ask",...}}, exit 0
 *   custom    — stderr message + exit 2; the three Python gates (quality-check-cap,
 *               git-discipline-gate, shell-write-gate) deny through the JSON permissionDecision line and use exit 2
 *               with stderr only when they crash (import_guard, run_gate)
 *
 * Session id: a per-session UUID that quality-check-cap keys its state to.
 *
 * Known gaps (inherent to bridging, not fixable here):
 *   - omp's eval tool executes arbitrary JS/Python with no bash string to
 *     inspect — no Claude equivalent exists, so no gate covers it.
 *   - omp's event carries no agent_type, so shell-write-gate's test-ownership
 *     half (and test-ownership-gate itself) is inert here, as under any
 *     harness that does not name the dispatched agent.
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
      "gates/git_discipline_gate.py",
      "gates/shell_write_gate.py",
      "gates/quality_check_cap.py",
    ],
  },
  read: { tool: "Read", gates: ["block-credential-read.sh"] },
  grep: { tool: "Grep", gates: ["block-credential-read.sh"] },
  glob: { tool: "Glob", gates: ["block-credential-read.sh"] },
  write: { tool: "Write", gates: ["write-edit-safety-gate.sh"] },
  edit: { tool: "Edit", gates: ["write-edit-safety-gate.sh"] },
  ast_edit: { tool: "Edit", gates: ["write-edit-safety-gate.sh"] },
};

const EDIT_TOOLS: Record<string, string> = {
  write: "Write",
  edit: "Edit",
  ast_edit: "Edit",
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
 * A gate that crashes (spawn error, timeout, or an exit other than 0 or 2
 * with no verdict) is a deny when `failClosed` is set, which every PreToolUse
 * gate sets: a gate that died let the call run un-gated. The PostToolUse
 * calls pass false: they record state and gate nothing, so a crash there
 * fails open on purpose.
 */
function runGate(
  script: string,
  payload: Record<string, unknown>,
  cwd: string,
  failClosed = false,
): Promise<GateResult> {
  const { promise, resolve } = Promise.withResolvers<GateResult>();
  function crashed(why: string): GateResult {
    console.error(`[claude-security-bridge] ${script} ${why}`);
    if (!failClosed) {
      return { denied: false };
    }
    return {
      denied: true,
      reason: `[claude-security-bridge] ${script} ${why} - blocking the call. Fix the gate, then retry.`,
    };
  }
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
    // A .py gate runs through hook-python, as settings.json runs it, so an old python3 cannot crash it into a deny.
    const scriptPath = join(SCRIPTS_DIR, script);
    const [interpreter, interpreterArgs]: [string, string[]] = script.endsWith(".py")
      ? ["sh", [join(SCRIPTS_DIR, "tools", "hook-python"), scriptPath]]
      : ["bash", [scriptPath]];
    child = spawn(interpreter, interpreterArgs, {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
    });
  } catch (e) {
    resolve(crashed(`spawn failed: ${e}`));
    return promise;
  }

  timer = setTimeout(() => {
    try {
      child.kill("SIGKILL");
    } catch {}
    finish(crashed(`timed out after ${GATE_TIMEOUT_MS}ms`));
  }, GATE_TIMEOUT_MS);

  child.stdout?.on("data", (d: Buffer) => (stdout += d));
  child.stderr?.on("data", (d: Buffer) => (stderr += d));
  child.on("error", (e) => {
    finish(crashed(`error: ${e}`));
  });
  child.on("close", (code) => {
    // CB Security Hooks convention: single-line JSON verdict on stdout.
    for (const line of stdout.split("\n")) {
      const t = line.trim();
      if (!t.startsWith("{")) continue;
      try {
        const parsed: unknown = JSON.parse(t);
        const verdict = isHookVerdict(parsed)
          ? parsed.hookSpecificOutput
          : undefined;
        // omp has no confirm prompt, so "ask" stops the call like "deny".
        if (
          verdict?.permissionDecision === "deny" ||
          verdict?.permissionDecision === "ask"
        ) {
          return finish({
            denied: true,
            reason: verdict.permissionDecisionReason ?? `${script} denied`,
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
    if (code === 0) {
      return finish({ denied: false });
    }
    // Any other exit (1 from an uncaught error, 127 for a missing gate file, a
    // signal) is a crash: Claude Code runs the call on it, the bridge does not.
    finish(crashed(`exited ${code ?? "on a signal"} with no verdict`));
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
        mapping.gates.map((g) => runGate(g, payload, cwd, true)),
      );
      const hit = results.find((r) => r.denied);
      if (hit) return { block: true, reason: hit.reason };
    }
    return undefined;
  });

  pi.on("tool_result", async (event, ctx) => {
    const cwd = ctx?.cwd ?? process.cwd();
    if (event.toolName === "bash") {
      await runGate(
        "gates/quality_check_cap.py",
        {
          hook_event_name: "PostToolUse",
          session_id: SESSION_ID,
          tool_name: "Bash",
          tool_input: { command: event.input?.command ?? "" },
        },
        cwd,
      );
      return undefined;
    }

    if (!event.isError && EDIT_TOOLS[event.toolName]) {
      await runGate(
        "gates/quality_check_cap.py",
        {
          hook_event_name: "PostToolUse",
          session_id: SESSION_ID,
          tool_name: EDIT_TOOLS[event.toolName],
          tool_input: {},
        },
        cwd,
      );
    }
    return undefined;
  });
}
