#!/usr/bin/env node
// Deterministic diff staging: classify every working-tree change (staged +
// unstaged + untracked, vs HEAD) into tiers, so human review attention goes
// where agent-written code actually fails. No model judgment anywhere in this
// script — every SAFE verdict is an invariant a reviewer could re-check
// mechanically, which is the whole point: the agent that wrote the code never
// gets a vote on what you don't read.
//
//   ESCALATE — read FIRST: hot paths, CI/enforcement-config edits, and
//              tripwire patterns agents produce under pressure (skipped
//              tests, removed assertions, lint/type suppressions,
//              lockfile drift without a manifest change).
//   READ     — normal human review. Test files get their changed assertion
//              lines extracted so the highest-value read needs no navigation.
//   SKIM     — cheap, high-signal-per-line reads (types, styles, docs).
//   SAFE     — invariant-verified mechanical changes; --stage stages them.
//
// Usage: stage.mjs [--json] [--stage]
// Config: optional .stage.json at repo root:
//   { "hotPaths": ["regex", ...], "skim": ["regex", ...] }
// Cache: reads <git-dir>/stage-verdicts.json (path -> { hash, verdict }); each
//   entry gets a `hash` of its exact diff and `cachedClean` if a prior `clean`
//   verdict still matches, so the skill can skip re-review of unchanged files.
//   The skill flow writes the cache back; this script only reads it.
// Exit: 0 ok, 1 not a repo / git error.

import { execFileSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";

const argv = process.argv.slice(2);
const asJson = argv.includes("--json");
const doStage = argv.includes("--stage");

function git(args, opts = {}) {
  return execFileSync("git", args, {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
    ...opts,
  });
}

let root;
try {
  root = git(["rev-parse", "--show-toplevel"]).trim();
} catch {
  console.error("stage: not inside a git repository");
  process.exit(1);
}

// ---------------------------------------------------------------- config
const defaults = {
  // Paths where being wrong is expensive — always escalated, never skipped,
  // regardless of how mechanical the diff looks.
  hotPaths: [
    "(^|/)(auth|authn|authz|login|session|token)s?(/|\\.|-)",
    "(^|/)(payment|billing|invoice|checkout)s?(/|\\.|-)",
    "(^|/)migrations?(/|\\.)",
    "(^|/)(secrets?|credentials?)(/|\\.|-)",
    "^\\.github/workflows/",
    "(^|/)Dockerfile",
    "(^|/)(helm|terraform|deploy)(/|$)",
    "\\.tf$",
  ],
  // Enforcement/verification config: anything that decides what CI lets
  // through. Agents weaken these to get green — gradient descent finds the
  // cheapest path — so every edit here is a mandatory human read.
  enforcementConfig:
    "(^|/)((jest|vitest|playwright|cypress)\\.config\\.[cm]?[jt]s|\\.eslintrc(\\.[a-z]+)?|eslint\\.config\\.[cm]?js|tsconfig([.-][a-z]+)?\\.json|codecov\\.ya?ml|\\.husky/|lefthook\\.ya?ml|\\.pre-commit-config\\.ya?ml)",
  skim: [
    "\\.types\\.[jt]sx?$",
    "\\.d\\.ts$",
    "\\.module\\.(s?css|less)$",
    "\\.(s?css|less)$",
    "\\.mdx?$",
  ],
};
let config = { ...defaults };
const cfgPath = join(root, ".stage.json");
if (existsSync(cfgPath)) {
  try {
    const user = JSON.parse(readFileSync(cfgPath, "utf8"));
    config.hotPaths = [...defaults.hotPaths, ...(user.hotPaths ?? [])];
    config.skim = [...defaults.skim, ...(user.skim ?? [])];
  } catch {
    console.error(`stage: could not parse ${cfgPath}, using defaults`);
  }
}
const hotPathRes = config.hotPaths.map((r) => new RegExp(r));
const skimRes = config.skim.map((r) => new RegExp(r));
const enforcementRe = new RegExp(config.enforcementConfig);

const BARREL_RE = /(^|\/)index\.[jt]sx?$/;
const TEST_RE = /(\.(test|spec|specs)\.[jt]sx?$|(^|\/)__tests__\/)/;
const LOCKFILE_RE = /(^|\/)(pnpm-lock\.yaml|package-lock\.json|yarn\.lock|Cargo\.lock|poetry\.lock|Gemfile\.lock)$/;
const MANIFEST_RE = /(^|\/)(package\.json|Cargo\.toml|pyproject\.toml|Gemfile)$/;

// A barrel line that needs no human read: re-export, blank, or comment.
const REEXPORT_LINE_RE =
  /^\s*(export\s+(type\s+)?(\*|\{[^}]*\})\s*(from\s+['"][^'"]+['"])?\s*;?|import\s+.*;?|\/\/.*|\/\*.*|\*.*|)\s*$/;

// Tripwires on ADDED lines, any file type.
const ADDED_TRIPWIRES = [
  [/\b(it|test|describe)\s*\.\s*(skip|only)\s*\(|\bx(it|describe|test)\s*\(/, "test skip/only added"],
  [/eslint-disable|biome-ignore/, "lint suppression added"],
  [/@ts-ignore|@ts-nocheck|@ts-expect-error/, "type suppression added"],
  [/--no-verify|SKIP=|\bset\s+-\s*e\b.*#\s*removed/, "hook/verify bypass added"],
];
// Tripwires on REMOVED lines, test files only.
const REMOVED_TEST_TRIPWIRES = [
  [/\bexpect\s*\(|\bassert\w*\s*[.(]/, "assertions removed"],
  [/\b(it|test)\s*\(\s*['"`]/, "test cases removed"],
];
const ASSERTION_RE = /\bexpect\s*\(|\bassert\w*\s*[.(]|\.to(Be|Equal|Match|Throw|Contain|Have)\w*\(/;

// Strip comment content so "assertions/test cases removed" tripwires and the
// assertion extractor fire on real code, not prose. A removed `// expect(...)`
// or a JSDoc line mentioning `it(...)` is churn, not lost coverage — that class
// of false ESCALATE forced clean files into the human queue. Deterministic
// per-line heuristic: kills // line comments, inline /* */, and JSDoc `*`/`*/`
// lines. It does NOT track multi-line block-comment state (a diff's added and
// removed lines aren't contiguous, so there's no reliable state to carry), so
// prose inside a /* */ block that doesn't start with `*` can still read as
// code — acceptable, since the common churn is caught. NOT applied to the
// ADDED suppression tripwires (eslint-disable, @ts-ignore, --no-verify), which
// legitimately live in comments and must still trip.
function codeResidue(line) {
  const s = line.replace(/\/\*.*?\*\//g, "").replace(/\/\/.*$/, "");
  const t = s.trim();
  if (t === "" || t === "*/" || t.startsWith("*") || t.startsWith("/*")) return "";
  return s;
}

// ---------------------------------------------------------------- collect
// Tracked changes (staged + unstaged) vs HEAD, plus untracked files.
const changed = new Map(); // path -> { status }
{
  // -z gives STATUS \0 path (\0 newpath for renames), flattened; walk it.
  const parts = git(["diff", "HEAD", "--name-status", "-M", "-z"], { cwd: root }).split("\0").filter(Boolean);
  for (let i = 0; i < parts.length; ) {
    const status = parts[i][0];
    if (status === "R" || status === "C") {
      changed.set(parts[i + 2], { status, oldPath: parts[i + 1] });
      i += 3;
    } else {
      changed.set(parts[i + 1], { status });
      i += 2;
    }
  }
}
for (const p of git(["ls-files", "-o", "--exclude-standard", "-z"], { cwd: root }).split("\0").filter(Boolean)) {
  changed.set(p, { status: "A", untracked: true });
}

if (changed.size === 0) {
  if (asJson) console.log(JSON.stringify({ escalate: [], read: [], skim: [], safe: [], staged: [] }, null, 2));
  else console.log("stage: working tree clean vs HEAD — nothing to stage");
  process.exit(0);
}

const manifestChanged = [...changed.keys()].some((p) => MANIFEST_RE.test(p));

// Diff lines for one file: { added: [...], removed: [...], raw }. `raw` is the
// exact change text, hashed to key the verdict cache — same diff ⇒ a prior
// reviewer verdict still holds, so a re-run can skip re-review.
function diffLines(path, meta) {
  if (meta.untracked) {
    try {
      const body = readFileSync(join(root, path), "utf8");
      return { added: body.split("\n"), removed: [], raw: body };
    } catch {
      return { added: [], removed: [], binary: true };
    }
  }
  const out = git(["diff", "HEAD", "--", path], { cwd: root });
  if (/^Binary files /m.test(out)) return { added: [], removed: [], binary: true, raw: out };
  const added = [], removed = [];
  for (const l of out.split("\n")) {
    if (l.startsWith("+++") || l.startsWith("---")) continue;
    if (l.startsWith("+")) added.push(l.slice(1));
    else if (l.startsWith("-")) removed.push(l.slice(1));
  }
  return { added, removed, raw: out };
}

// Verdict cache: <git-dir>/stage-verdicts.json, keyed path -> { hash, verdict }.
// Lives inside .git so it is per-repo and never committed. --absolute-git-dir
// resolves correctly inside worktrees. The reviewer verdict is written back by
// the skill flow (the model owns it); this script only reads it to mark files
// whose diff is byte-identical to a prior `clean` verdict as cachedClean.
let cacheFile = null;
let cache = {};
try {
  cacheFile = join(git(["rev-parse", "--absolute-git-dir"], { cwd: root }).trim(), "stage-verdicts.json");
  if (existsSync(cacheFile)) cache = JSON.parse(readFileSync(cacheFile, "utf8"));
} catch {
  cache = {};
}
const hashChange = (status, lines) =>
  createHash("sha256")
    .update(status + "\0" + (lines && !lines.binary ? lines.raw ?? "" : "\0BINARY"))
    .digest("hex")
    .slice(0, 16);

// ------------------------------------------------- dangling-reference check
// A deleted or renamed module that some surviving file still imports is a
// build break hiding in a change that otherwise looks safe to suppress — the
// escape a correctness reviewer structurally misses: it reads the deleted
// file's diff (empty/clean) and never looks at who imported it. Heuristic, not
// a compiler: grep tracked source for an import specifier ending in the removed
// module's path tail. Bias is toward flagging — a false positive escalates a
// file that was fine (cheap: one human read), a miss lets a break through (the
// type-checker still catches it downstream, just later).
const IMPORT_EXT_RE = /\.[cm]?[jt]sx?$/;
const GENERIC_LEAF_RE = /^(utils|types|constants|helpers|styles|config|hooks|index)$/;
function importTail(p) {
  const segs = p.replace(IMPORT_EXT_RE, "").split("/");
  if (segs[segs.length - 1] === "index") segs.pop();
  const tail = segs[segs.length - 1] ?? "";
  // Generic leaf names (utils/types/…) are ambiguous alone — anchor with the
  // parent segment so `foo/utils` doesn't match every `./utils` in the tree.
  return GENERIC_LEAF_RE.test(tail) && segs.length >= 2 ? segs.slice(-2).join("/") : tail;
}
function stillImported(removedPath, alsoRemoved) {
  const tail = importTail(removedPath);
  if (!tail) return [];
  const esc = tail.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // TAIL anchored as a path segment (start of specifier or after a slash),
  // preceded by from / import( / require(. POSIX ERE — `[[:space:]]`, not
  // `\s`: git grep's default engine (e.g. macOS libc) does not honour `\s`,
  // which silently made this check never fire.
  const pat = `(from|import\\(|require\\()[[:space:]]*['"]([^'"]*/)?${esc}(\\.[cm]?[jt]sx?)?['"]`;
  let hits;
  try {
    hits = git(["grep", "-lE", pat, "--", "*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs", "*.cjs"], { cwd: root });
  } catch {
    return []; // git grep exits 1 on no match
  }
  return hits.split("\n").filter(Boolean).filter((h) => h !== removedPath && !alsoRemoved.has(h));
}
// Current-tree paths being deleted — an importer that is itself deleted is not
// a live dangling reference, so it must not count against another deletion.
const deletedPaths = new Set([...changed].filter(([, m]) => m.status === "D").map(([p]) => p));

// ---------------------------------------------------------------- classify
const tiers = { escalate: [], read: [], skim: [], safe: [] };

for (const [path, meta] of changed) {
  const entry = { path, status: meta.status, reasons: [] };
  const isTest = TEST_RE.test(path);
  const hot = hotPathRes.find((re) => re.test(path));

  if (hot) entry.reasons.push(`hot path (${hot.source})`);
  if (enforcementRe.test(path)) entry.reasons.push("CI/enforcement config");
  if (isTest && meta.status === "D") entry.reasons.push("test file deleted");
  if (LOCKFILE_RE.test(path) && !manifestChanged)
    entry.reasons.push("lockfile changed without a manifest change");

  // Deleted/renamed module still imported somewhere → not safe to suppress.
  if (meta.status === "D" || meta.status === "R") {
    const removed = meta.status === "R" ? meta.oldPath : path;
    if (removed) {
      const importers = stillImported(removed, deletedPaths);
      if (importers.length)
        entry.reasons.push(
          `deleted/renamed module still imported by ${importers.length} file(s): ` +
            `${importers.slice(0, 2).join(", ")}${importers.length > 2 ? ", …" : ""}`,
        );
    }
  }

  // Content tripwires — skip pure deletions of non-test files (nothing added).
  const lines = meta.status === "D" && !isTest ? null : diffLines(path, meta);

  // Hash the exact change and check the verdict cache. cachedClean means a
  // prior reviewer pass cleared this identical diff — the skill can skip
  // re-review on a re-run (e.g. after /fix touched other files). Never
  // overrides a tier: an ESCALATE file that is cachedClean is still ESCALATE.
  entry.hash = hashChange(meta.status, lines);
  const cached = cache[path];
  if (cached && cached.hash === entry.hash && cached.verdict === "clean")
    entry.cachedClean = true;

  // Changed-line count, used to size the review set (single vs fan-out).
  entry.churn = lines && !lines.binary ? lines.added.length + lines.removed.length : 0;

  if (lines && !lines.binary) {
    for (const [re, why] of ADDED_TRIPWIRES)
      if (lines.added.some((l) => re.test(l))) entry.reasons.push(why);
    // Removed-coverage tripwires fire only on NET removal: count matches in
    // removed vs added (on code residue, so comments don't count). A retitled
    // `it('...')` or a moved `expect()` shows up as one removed + one added —
    // net zero, not lost coverage — and must not escalate. Only removed > added
    // (coverage actually dropped) trips. This is the common false-ESCALATE
    // class: agents retitle tests constantly; they rarely net-delete them.
    if (isTest)
      for (const [re, why] of REMOVED_TEST_TRIPWIRES) {
        const rm = lines.removed.filter((l) => re.test(codeResidue(l))).length;
        const add = lines.added.filter((l) => re.test(codeResidue(l))).length;
        if (rm > add) entry.reasons.push(`${why} (net ${rm - add})`);
      }
  }

  if (entry.reasons.length > 0) {
    tiers.escalate.push(entry);
    continue;
  }

  // SAFE: invariant-verified mechanical classes. Deletions of barrels are
  // safe too — a broken import is the type-checker's catch, not a human's.
  if (BARREL_RE.test(path)) {
    const ok =
      meta.status === "D" ||
      (lines && !lines.binary && lines.added.every((l) => REEXPORT_LINE_RE.test(l)));
    if (ok) {
      entry.verified = "every added line is a bare re-export/import/comment";
      tiers.safe.push(entry);
      continue;
    }
    entry.reasons.push("index file contains non-re-export code");
    tiers.read.push(entry); // failed its invariant → real code hiding in a barrel
    continue;
  }
  if (LOCKFILE_RE.test(path)) {
    entry.verified = "manifest changed in the same diff";
    tiers.safe.push(entry);
    continue;
  }

  if (skimRes.some((re) => re.test(path))) {
    tiers.skim.push(entry);
    continue;
  }

  // READ. For tests, extract changed assertion lines — that's where the
  // review minutes actually go, so hand them over without navigation.
  if (isTest && lines && !lines.binary) {
    const grab = (arr, sign) =>
      arr.filter((l) => ASSERTION_RE.test(codeResidue(l))).slice(0, 40).map((l) => sign + l.trim());
    entry.assertions = [...grab(lines.removed, "- "), ...grab(lines.added, "+ ")];
  }
  tiers.read.push(entry);
}

// ---------------------------------------------------------------- stage
let staged = [];
if (doStage && tiers.safe.length > 0) {
  staged = tiers.safe.map((e) => e.path);
  git(["add", "--", ...staged], { cwd: root });
}

// ------------------------------------------------------------- review sizing
// Files the reviewer will actually re-derive a verdict for: every non-SAFE
// tier minus anything a prior pass already cleared (cachedClean). SAFE never
// reaches the reviewer; ESCALATE does (it is cleared-but-queued, not skipped).
// One Opus pass over a big set is shallow per file, so the classifier — not
// the model — decides when to fan out one reviewer per subsystem.
const FANOUT_FILES = 25;
const FANOUT_LINES = 1500;
const reviewSet = [...tiers.escalate, ...tiers.read, ...tiers.skim].filter((e) => !e.cachedClean);
const review = {
  files: reviewSet.length,
  lines: reviewSet.reduce((n, e) => n + (e.churn || 0), 0),
  strategy: reviewSet.length > FANOUT_FILES ? "fan-out" : "single",
};
if (review.strategy === "single" && review.lines > FANOUT_LINES) review.strategy = "fan-out";

// ---------------------------------------------------------------- output
if (asJson) {
  console.log(JSON.stringify({ ...tiers, staged, cacheFile, review }, null, 2));
  process.exit(0);
}
const fmt = (e) =>
  `  ${e.status}  ${e.path}${e.cachedClean ? "  ⟳ cached-clean" : ""}` +
  (e.reasons.length ? `\n       ↳ ${e.reasons.join("; ")}` : "") +
  (e.verified ? `\n       ✓ ${e.verified}` : "") +
  (e.assertions?.length ? `\n       changed assertions:\n${e.assertions.map((a) => "         " + a).join("\n")}` : "");
const section = (title, arr) => (arr.length ? `\n${title} (${arr.length})\n${arr.map(fmt).join("\n")}\n` : "");
process.stdout.write(
  section("ESCALATE — read these first", tiers.escalate) +
    section("READ", tiers.read) +
    section("SKIM", tiers.skim) +
    section(doStage ? "SAFE — staged" : "SAFE — stageable (--stage)", tiers.safe) +
    `\nreview set: ${review.files} file(s), ${review.lines} changed line(s) → ${review.strategy}\n` +
    (changed.size ? "" : "nothing to stage\n"),
);
