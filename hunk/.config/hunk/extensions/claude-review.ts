/**
 * claude-review — GitHub-style "viewed" marks for hunk, plus the bridge into the
 * /cc skill.
 *
 * `v` marks the selected file viewed and collapses it in place to a single
 * summary row; `v` again reopens it. `V` also drops viewed files from the review
 * entirely, `S` stages them, `X` clears the marks. Inline review notes (built-in
 * `c`) are mirrored to a JSONL the /cc skill reads and resolves.
 *
 * Collapsing is a registered file view, selected per file through
 * `ctx.fileViews`, so it lands on the keypress. Hiding and staging both change
 * what the changeset contains, which `transformChangeset` and the git index only
 * reflect at load time — so those two drive a reload through the session daemon
 * rather than telling the user to press `r`.
 *
 * Marks are file-level, not hunk-level: a transform may filter `files`, but a
 * file's hunks live in opaque `metadata` the renderer owns, so there is no
 * supported way to drop one hunk from a file.
 */

import { execFile, execFileSync, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

// Declared locally rather than imported from `hunkdiff/extension`: this file is
// a single-file extension with no node_modules to resolve that package from.
type NotifyType = "info" | "warning" | "error";

interface DiffHunk {
  index: number;
}

interface DiffFile {
  id: string;
  path: string;
  patch: string;
  stats: { additions: number; deletions: number };
  hunks?: readonly DiffHunk[];
}

interface Changeset {
  files: DiffFile[];
}

interface Ctx {
  cwd: string;
  notify(message: string, type?: NotifyType): void;
}

interface CommandCtx extends Ctx {
  readonly selection: { readonly file: DiffFile | null };
  readonly fileViews: {
    select(viewId: string | null): void;
    isActive(viewId: string): boolean;
  };
  readonly dialogs: {
    confirm(options: { title: string; body?: string }): Promise<boolean>;
  };
}

type Tone =
  "muted" | "accent" | "accent-muted" | "syntax" | "added" | "removed";

interface FileViewInput {
  readonly file: DiffFile;
  readonly width: number;
}

interface ReviewNote {
  id: string;
  filePath: string;
  hunkIndex: number;
  side: "old" | "new";
  line: number;
  body: string;
  draft: boolean;
}

interface HunkApi {
  registerCommand(
    command: { id: string; title: string; key?: string | readonly string[] },
    handler: (ctx: CommandCtx) => void | Promise<void>,
  ): void;
  registerFileView(view: {
    id: string;
    title: string;
    matches(file: DiffFile): boolean;
    layout(input: FileViewInput): unknown;
  }): void;
  transformChangeset(fn: (changeset: Changeset, ctx: Ctx) => Changeset): void;
  on(event: string, handler: (payload: any, ctx: Ctx) => void): void;
  log(message: string): void;
}

interface State {
  repoRoot: string;
  hideViewed: boolean;
  /** path -> patch hash the mark was taken against */
  viewed: Record<string, string>;
}

const VIEW_ID = "collapsed";

const STATE_DIR = join(
  process.env.XDG_STATE_HOME || join(homedir(), ".local", "state"),
  "hunk-claude",
);

/** Repo root for a cwd, or null outside a git checkout. Cached per cwd. */
const repoRoots = new Map<string, string | null>();
function repoRootFor(cwd: string): string | null {
  if (!repoRoots.has(cwd)) {
    let root: string | null = null;
    try {
      root = execFileSync("git", ["-C", cwd, "rev-parse", "--show-toplevel"], {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      }).trim();
    } catch {
      root = null;
    }
    repoRoots.set(cwd, root || null);
  }
  return repoRoots.get(cwd) ?? null;
}

/**
 * The repo the session is reviewing.
 *
 * A file view's `matches` receives only the file, so the repo cannot be derived
 * per call; it is captured from the first context that carries a cwd.
 */
let activeRepoRoot: string | null = null;
function rememberRepo(ctx: Ctx): string | null {
  const root = repoRootFor(ctx.cwd);
  if (root) activeRepoRoot = root;
  return root;
}

function sha(text: string, length: number): string {
  return createHash("sha256").update(text).digest("hex").slice(0, length);
}

/** Stable, collision-free, human-recognizable file stem for one repo root. */
function slugFor(repoRoot: string): string {
  const name = repoRoot.split("/").filter(Boolean).pop() || "repo";
  return `${name.replace(/[^A-Za-z0-9._-]/g, "-")}-${sha(repoRoot, 12)}`;
}

const statePath = (repoRoot: string) =>
  join(STATE_DIR, `${slugFor(repoRoot)}.json`);
const commentsPath = (repoRoot: string) =>
  join(STATE_DIR, `${slugFor(repoRoot)}.comments.jsonl`);

/**
 * In-memory mirror of each repo's state file.
 *
 * `matches` runs on every file for every layout pass, so it must not hit the
 * disk; the cache is written through on every mutation and refreshed when a
 * changeset loads.
 */
const stateCache = new Map<string, State>();

function loadState(repoRoot: string): State {
  try {
    const raw = JSON.parse(readFileSync(statePath(repoRoot), "utf8"));
    return {
      repoRoot,
      hideViewed: raw.hideViewed === true,
      viewed: raw.viewed && typeof raw.viewed === "object" ? raw.viewed : {},
    };
  } catch {
    return { repoRoot, hideViewed: false, viewed: {} };
  }
}

function readState(repoRoot: string, fresh = false): State {
  if (fresh || !stateCache.has(repoRoot)) {
    stateCache.set(repoRoot, loadState(repoRoot));
  }
  return stateCache.get(repoRoot)!;
}

function writeState(state: State): void {
  stateCache.set(state.repoRoot, state);
  mkdirSync(STATE_DIR, { recursive: true });
  writeFileSync(
    statePath(state.repoRoot),
    `${JSON.stringify(state, null, 2)}\n`,
  );
}

/**
 * How to re-invoke the hunk CLI from inside the running hunk process.
 *
 * `argv[1]` is hunk's own entry script when it was started through the wrapper;
 * falling back to the bare name covers a packaged binary on PATH.
 */
function hunkCli(): { command: string; args: string[] } {
  const entry = process.argv[1];
  if (entry && /hunk[^/]*\.(c?js|mjs)$/.test(entry)) {
    return { command: process.execPath, args: [entry] };
  }
  return { command: "hunk", args: [] };
}

/**
 * Drop staged files out of the live review without the user pressing `r`.
 *
 * Everything here is async on purpose: the reload is an RPC the daemon turns
 * around and delivers back to this same process, so blocking on it while
 * handling a keypress would deadlock the UI.
 *
 * Only a plain working-tree review can be reloaded — the RPC takes a diff spec
 * rather than "whatever this session already had", and any other spec would
 * silently swap what the user is looking at. `hunk diff --staged` in particular
 * would grow the very files we just staged.
 */
function reloadWorkingTreeReview(
  repoRoot: string,
  onError: (message: string) => void,
): void {
  const { command, args } = hunkCli();
  execFile(
    command,
    [...args, "session", "list", "--json"],
    { encoding: "utf8" },
    (error, stdout) => {
      if (error) {
        onError(`could not reach the hunk session daemon — press r to reload`);
        return;
      }
      let sessions: any[] = [];
      try {
        sessions = JSON.parse(stdout).sessions ?? [];
      } catch {
        sessions = [];
      }
      // Prefer pid, since `--repo` is ambiguous the moment two panes review the
      // same checkout. hunk's launcher re-execs a native binary, so the pid the
      // daemon registered is not guaranteed to be ours; fall back to the repo
      // when it identifies exactly one session.
      const inRepo = sessions.filter(
        (session) => session?.repoRoot === repoRoot,
      );
      const own =
        sessions.find((session) => session?.pid === process.pid) ??
        (inRepo.length === 1 ? inRepo[0] : undefined);
      if (!own) {
        onError(
          inRepo.length > 1
            ? "several hunk sessions share this repo — press r to reload"
            : "could not identify this hunk session — press r to reload",
        );
        return;
      }
      if (!String(own.title ?? "").endsWith("working tree")) {
        // A piped patch (the lazygit pager path) has no source to re-read at
        // all, so it cannot refresh itself even on `r`.
        onError(
          own.inputKind === "patch"
            ? "a piped patch review cannot refresh — reopen to see the result"
            : "this review is not the working tree — press r to reload",
        );
        return;
      }
      const child = spawn(
        command,
        [...args, "session", "reload", own.sessionId, "--", "diff"],
        { detached: true, stdio: "ignore" },
      );
      child.on("error", () =>
        onError("reload failed to launch — press r to reload"),
      );
      child.unref();
    },
  );
}

/**
 * Paths the loaded changeset contains, per repo.
 *
 * Marks outlive a changeset: a file can be staged, discarded, or deleted
 * elsewhere and its mark stays behind. `git add` is atomic over its pathspec, so
 * one such path makes the whole stage fail — staging is restricted to this set.
 */
const activePaths = new Map<string, Set<string>>();

/** A mark is only live while the file still hashes to what it did when marked. */
const patchHash = (file: DiffFile) => sha(file.patch, 16);
const isViewed = (state: State, file: DiffFile) =>
  state.viewed[file.path] === patchHash(file);

export default function claudeReview(hunk: HunkApi): void {
  /** Resolve repo + state, or explain why the command cannot run. */
  function withState(ctx: Ctx): State | null {
    const root = rememberRepo(ctx);
    if (!root) {
      ctx.notify("claude-review: not inside a git repository", "error");
      return null;
    }
    return readState(root);
  }

  // ── Collapsed presentation ────────────────────────────────────────────────
  // Registered for viewed files only, so it also serves as the indicator: a
  // file offering this presentation under View → File presentation is viewed.
  hunk.registerFileView({
    id: VIEW_ID,
    title: "Viewed (collapsed)",
    matches(file) {
      if (!activeRepoRoot) return false;
      return isViewed(readState(activeRepoRoot), file);
    },
    layout(input) {
      const { additions, deletions } = input.file.stats;
      const hunks = input.file.hunks ?? [];
      const row = {
        id: "claude-review-collapsed",
        spans: [
          { text: "✓ viewed", tone: "accent" as Tone, attributes: ["bold"] },
          { text: "  ", tone: "muted" as Tone },
          { text: `+${additions}`, tone: "added" as Tone },
          { text: " ", tone: "muted" as Tone },
          { text: `-${deletions}`, tone: "removed" as Tone },
          {
            text: `  ${hunks.length} hunk${hunks.length === 1 ? "" : "s"} collapsed · v to reopen`,
            tone: "muted" as Tone,
          },
        ],
      };
      return {
        rows: [row],
        // Every hunk maps onto the one row: hunk navigation still lands on the
        // file, and the validator requires one bound per hunk.
        hunkRows: hunks.map(() => ({ startRow: 0, endRow: 0 })),
      };
    },
  });

  hunk.registerCommand(
    {
      id: "toggleViewed",
      title: "Toggle viewed on the selected file",
      key: "v",
    },
    (ctx) => {
      const file = ctx.selection.file;
      if (!file) {
        ctx.notify("claude-review: no file selected", "warning");
        return;
      }
      const state = withState(ctx);
      if (!state) return;

      if (isViewed(state, file)) {
        delete state.viewed[file.path];
        writeState(state);
        // Restore raw diff before the view stops matching the file.
        ctx.fileViews.select(null);
        ctx.notify(`reopened ${file.path}`);
        return;
      }

      state.viewed[file.path] = patchHash(file);
      writeState(state);
      // The mark is on disk first, so `matches` is already true here.
      ctx.fileViews.select(VIEW_ID);
      const count = Object.keys(state.viewed).length;
      ctx.notify(`viewed ${file.path} · ${count} marked`);
    },
  );

  hunk.registerCommand(
    {
      id: "toggleHideViewed",
      title: "Drop viewed files from the review entirely",
      key: "V",
    },
    (ctx) => {
      const state = withState(ctx);
      if (!state) return;
      state.hideViewed = !state.hideViewed;
      writeState(state);
      const count = Object.keys(state.viewed).length;
      ctx.notify(
        state.hideViewed
          ? `dropping ${count} viewed file(s) from the review`
          : "viewed files will stay in the review, collapsed",
      );
      // The filter itself only runs at changeset load, so ask for one.
      reloadWorkingTreeReview(state.repoRoot, (message) =>
        ctx.notify(`claude-review: ${message}`, "warning"),
      );
    },
  );

  hunk.registerCommand(
    { id: "stageViewed", title: "Stage every viewed file", key: "S" },
    async (ctx) => {
      const state = withState(ctx);
      if (!state) return;
      const marked = Object.keys(state.viewed).sort();
      if (marked.length === 0) {
        ctx.notify("claude-review: nothing marked viewed", "warning");
        return;
      }

      // Stage what this review shows, not every mark on file. A review can also
      // be narrower than the whole working tree (a path-filtered diff), so the
      // difference is skipped rather than pruned — those marks are still good.
      const inReview = activePaths.get(state.repoRoot);
      const paths = inReview
        ? marked.filter((path) => inReview.has(path))
        : marked;
      const skipped = marked.length - paths.length;
      const tail = skipped > 0 ? ` · ${skipped} not in this review` : "";
      if (paths.length === 0) {
        ctx.notify(
          `claude-review: no viewed file is in this review — ${skipped} stale mark(s), X to clear`,
          "warning",
        );
        return;
      }

      const ok = await ctx.dialogs.confirm({
        title: `git add ${paths.length} viewed file${paths.length === 1 ? "" : "s"}?${tail}`,
        body:
          paths.slice(0, 10).join("\n") +
          (paths.length > 10 ? `\n… and ${paths.length - 10} more` : ""),
      });
      if (!ok) return;

      try {
        execFileSync("git", ["-C", state.repoRoot, "add", "--", ...paths], {
          stdio: ["ignore", "ignore", "pipe"],
        });
      } catch (error) {
        // git's stderr says which pathspec failed; the Error message is the
        // whole command line, which the notice bar truncates before reaching it.
        const stderr = String((error as { stderr?: unknown }).stderr ?? "")
          .split("\n")
          .filter(
            (line) => line.startsWith("fatal:") || line.startsWith("error:"),
          )
          .join(" ");
        const detail =
          stderr || (error instanceof Error ? error.message : String(error));
        ctx.notify(`claude-review: git add failed — ${detail}`, "error");
        return;
      }

      // Staged files leave the working-tree diff, so their marks have nothing
      // left to describe. Marks outside this review keep theirs.
      for (const path of paths) delete state.viewed[path];
      writeState(state);
      ctx.fileViews.select(null);
      ctx.notify(`staged ${paths.length} file(s)${tail}`);
      reloadWorkingTreeReview(state.repoRoot, (message) =>
        ctx.notify(`claude-review: ${message}`, "warning"),
      );
    },
  );

  hunk.registerCommand(
    { id: "clearViewed", title: "Clear every viewed mark", key: "X" },
    async (ctx) => {
      const state = withState(ctx);
      if (!state) return;
      const count = Object.keys(state.viewed).length;
      if (count === 0) {
        ctx.notify("claude-review: nothing marked viewed", "warning");
        return;
      }
      const ok = await ctx.dialogs.confirm({
        title: `Clear ${count} viewed mark${count === 1 ? "" : "s"}?`,
      });
      if (!ok) return;
      state.viewed = {};
      writeState(state);
      ctx.fileViews.select(null);
      ctx.notify(`cleared ${count} mark(s)`);
    },
  );

  hunk.transformChangeset((changeset, ctx) => {
    const root = rememberRepo(ctx);
    if (!root) return changeset;
    const state = readState(root, true);
    // Recorded before any filtering: what `S` may stage is what the review was
    // given, not what is left visible after viewed files are dropped.
    activePaths.set(root, new Set(changeset.files.map((file) => file.path)));

    // Drop marks whose file is present but no longer hashes the same — the file
    // changed under the mark, so it needs reviewing again.
    let pruned = false;
    for (const file of changeset.files) {
      if (
        state.viewed[file.path] &&
        state.viewed[file.path] !== patchHash(file)
      ) {
        delete state.viewed[file.path];
        pruned = true;
      }
    }
    if (pruned) writeState(state);

    const marked = changeset.files.filter((file) => isViewed(state, file));
    if (marked.length === 0) return changeset;

    if (!state.hideViewed) {
      ctx.notify(
        `claude-review: ${marked.length} viewed file(s) — select one and press v to reopen`,
      );
      return changeset;
    }

    const visible = changeset.files.filter((file) => !isViewed(state, file));
    if (visible.length === 0) {
      // Hiding everything leaves nothing to review and no way back from inside
      // the stream; show the changeset and let the user stage or clear.
      ctx.notify(
        "claude-review: every file is viewed — S to stage, X to clear",
      );
      return changeset;
    }
    ctx.notify(`claude-review: ${marked.length} viewed file(s) dropped`);
    return { ...changeset, files: visible };
  });

  // ── Inline notes → /cc queue ──────────────────────────────────────────────
  // Hunk's own notes (`c`) are the comment surface; this only mirrors them into
  // a queue the /cc skill lists and resolves. We own the file, so /cc gets a
  // real resolve rather than a consumed-ids sidecar.
  function readComments(repoRoot: string): any[] {
    try {
      return readFileSync(commentsPath(repoRoot), "utf8")
        .split("\n")
        .filter((line) => line.trim().length > 0)
        .map((line) => JSON.parse(line));
    } catch {
      return [];
    }
  }

  function writeComments(repoRoot: string, entries: any[]): void {
    mkdirSync(STATE_DIR, { recursive: true });
    writeFileSync(
      commentsPath(repoRoot),
      entries.map((entry) => JSON.stringify(entry)).join("\n") +
        (entries.length > 0 ? "\n" : ""),
    );
  }

  function recordNote(note: ReviewNote, ctx: Ctx): void {
    if (!note || note.draft) return;
    const root = rememberRepo(ctx);
    if (!root) return;
    const entries = readComments(root);
    const entry = {
      id: note.id,
      path: note.filePath,
      line: note.line,
      side: note.side,
      hunk_index: note.hunkIndex,
      body: note.body,
      timestamp: new Date().toISOString(),
    };
    const existing = entries.findIndex((e) => e.id === note.id);
    if (existing >= 0) entries[existing] = { ...entries[existing], ...entry };
    else entries.push(entry);
    try {
      writeComments(root, entries);
    } catch (error) {
      hunk.log(`failed to record note ${note.id}: ${String(error)}`);
    }
  }

  hunk.on("startup", (_payload, ctx) => rememberRepo(ctx));
  hunk.on("note_created", ({ note }, ctx) => recordNote(note, ctx));
  hunk.on("note_edited", ({ note }, ctx) => recordNote(note, ctx));
}
