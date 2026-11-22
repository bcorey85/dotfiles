/**
 * jump-list — nvim's jump list for hunk.
 *
 * `ctrl+o` goes back to where the review was before the last jump, and `ctrl+i`
 * goes forward again. Both keys are bound because a terminal with the kitty
 * keyboard protocol (hunk turns it on) sends `ctrl+i` as its own key, and one
 * without it sends tab. The tab key is free only because the user config unbinds
 * `hunk.app.toggleFocusArea`; the file filter moves to `ctrl+f` there.
 *
 * A jump is any selection change except a step to the next or previous hunk in
 * the same file: a search hit, a file switch, `g`/`G`, a note jump, a filter pick.
 * Like nvim, a new jump after going back drops the entries ahead of it.
 */

// Declared locally rather than imported from `hunkdiff/extension`: this file is
// a single-file extension with no node_modules to resolve that package from.
type NotifyType = "info" | "warning" | "error";

interface Navigation {
  selectFile(fileId: string): void;
  selectHunk(fileId: string, hunkIndex: number): void;
}

interface CommandCtx {
  notify(message: string, type?: NotifyType): void;
  readonly navigation: Navigation;
}

interface SelectionChanged {
  fileId: string | null;
  hunkIndex: number | null;
}

interface HunkApi {
  registerCommand(
    command: { id: string; title: string; key?: string | readonly string[] },
    handler: (ctx: CommandCtx) => void | Promise<void>,
  ): void;
  on(event: "selection_changed", handler: (payload: SelectionChanged) => void): void;
}

interface Location {
  fileId: string;
  hunkIndex: number | null;
}

const MAX_ENTRIES = 100;

function sameLocation(a: Location, b: Location): boolean {
  return a.fileId === b.fileId && a.hunkIndex === b.hunkIndex;
}

/** A step to the neighbouring hunk of the same file is motion, not a jump. */
function isJump(from: Location, to: Location): boolean {
  if (from.fileId !== to.fileId) return true;
  if (from.hunkIndex === null || to.hunkIndex === null) return false;
  return Math.abs(from.hunkIndex - to.hunkIndex) > 1;
}

function goTo(ctx: CommandCtx, location: Location): void {
  if (location.hunkIndex === null) {
    ctx.navigation.selectFile(location.fileId);
    return;
  }
  ctx.navigation.selectHunk(location.fileId, location.hunkIndex);
}

export default function jumpList(hunk: HunkApi): void {
  let entries: Location[] = [];
  // Points into `entries` while stepping back and forth; equals its length at the live position.
  let index = 0;
  let current: Location | null = null;
  // The location this extension is moving to, so its own move is not recorded as a jump.
  let pending: Location | null = null;

  function record(from: Location): void {
    entries = entries.slice(0, index);
    const last = entries[entries.length - 1];
    if (!last || !sameLocation(last, from)) entries.push(from);
    if (entries.length > MAX_ENTRIES) entries = entries.slice(-MAX_ENTRIES);
    index = entries.length;
  }

  hunk.on("selection_changed", ({ fileId, hunkIndex }) => {
    if (fileId === null) return;
    const next: Location = { fileId, hunkIndex };
    const ours = pending !== null && sameLocation(pending, next);
    pending = null;
    if (!ours && current && isJump(current, next)) record(current);
    current = next;
  });

  /** True when back has no older entry to reach from where the review is now. */
  function nothingBehind(atLive: boolean, here: Location): boolean {
    if (!atLive) return index === 0;
    if (entries.length === 0) return true;
    return entries.length === 1 && sameLocation(entries[0], here);
  }

  function step(ctx: CommandCtx, target: Location): void {
    pending = target;
    goTo(ctx, target);
  }

  hunk.registerCommand({ id: "back", title: "Jump back", key: "ctrl+o" }, (ctx) => {
    const atLive = index === entries.length;
    if (!current || nothingBehind(atLive, current)) {
      ctx.notify("jump-list: at the oldest jump", "info");
      return;
    }
    // Leaving the live position: keep it so forward can return to it.
    if (atLive) {
      record(current);
      index = entries.length - 1;
    }
    index -= 1;
    step(ctx, entries[index]);
  });

  hunk.registerCommand({ id: "forward", title: "Jump forward", key: ["ctrl+i", "tab"] }, (ctx) => {
    if (index >= entries.length - 1) {
      ctx.notify("jump-list: at the newest jump", "info");
      return;
    }
    index += 1;
    step(ctx, entries[index]);
  });
}
