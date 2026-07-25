-- Agent findings as jump targets, not as a chat transcript.
--
-- The inbound half of the Claude review loop. review.lua is the outbound half
-- (you leave comments, /cc reads them); this is the return path: skills like
-- /stage and /review append findings to ~/.claude/review-queue.jsonl, and
-- <leader>cf turns them into quickfix entries plus inline virtual text.
--
-- Why this exists at all: a findings list rendered into the chat pane is a
-- transcript — you read it once, in a context you can't act from, and the
-- attention it needs competes with spawning another agent. As quickfix it
-- becomes ]q/[q navigation over real code (same pipeline as <leader>tq test
-- failures), and the virtual text puts the finding at the line it's about, so
-- flagged code stays visible while you move around normally instead of only
-- while you're looking at a report.
--
-- Producer contract — one JSON object per line, unknown fields ignored:
--   file  (required) absolute, or relative to `repo` / the current repo root
--   line  (required) 1-indexed
--   text  (required) one line; the finding itself
--   tier  ESCALATE | READ | SKIM   (default READ) — severity + sort order
--   col   1-indexed (default 1)
--   repo  absolute repo root; entries for other repos are filtered out
--   date  ISO8601 (`date -u +%Y-%m-%dT%H:%M:%SZ`) — when the finding was made
-- A malformed line costs that line only, never the whole queue.
--
-- `date` is optional but producers should always send it: without it a finding
-- can't be aged or drift-checked, and an un-aged row is indistinguishable from
-- a fresh one. See the staleness note on annotate() below for why that matters.
--
-- Producers MUST append (>>), one finding per line, and keep the line short.
-- Concurrent agents all write this one file; a single `>>` write under 4KB is
-- atomic on a local filesystem, so short lines cannot interleave — a multi-
-- kilobyte `text` can. Set `repo` when the producer knows its root (workmux
-- worktrees each have their own), so reads and clears scope correctly.

local M = {}

local QUEUE_PATH = vim.uv.os_homedir() .. "/.claude/review-queue.jsonl"
local ns = vim.api.nvim_create_namespace("claude_review_queue")

-- ESCALATE/READ/SKIM map onto quickfix's type field so quicker.nvim renders
-- them with the signs and colours it already uses for E/W/I, and onto the
-- Diagnostic* highlight groups so the virtual text tracks the active theme
-- (same reasoning as the ANSI palette names in the tmux segment).
local TIERS = {
  ESCALATE = { rank = 1, qftype = "E", hl = "DiagnosticVirtualTextError" },
  READ = { rank = 2, qftype = "W", hl = "DiagnosticVirtualTextWarn" },
  SKIM = { rank = 3, qftype = "I", hl = "DiagnosticVirtualTextInfo" },
}
local DEFAULT_TIER = "READ"

-- Findings for the current repo, keyed by absolute path, so the BufReadPost
-- autocmd below can mark files opened after the queue was loaded.
local by_path = {}

local function read_lines()
  local fh = io.open(QUEUE_PATH, "r")
  if not fh then
    return nil
  end
  local content = fh:read("*a")
  fh:close()
  local lines = {}
  for line in ((content or "") .. "\n"):gmatch("([^\n]*)\n") do
    if line:match("%S") then
      lines[#lines + 1] = line
    end
  end
  return lines
end

-- Absolute path for a decoded entry: `repo` when the producer set it, else the
-- current repo root. Returns nil when the entry is unusable.
local function entry_abs(e, repo_root)
  if type(e) ~= "table" or not e.file or not e.line or not e.text then
    return nil
  end
  local abs = e.file
  if not abs:match("^/") then
    abs = (e.repo or repo_root or vim.fn.getcwd()) .. "/" .. abs
  end
  return vim.fn.fnamemodify(abs, ":p")
end

-- True when `abs` belongs to the repo we're looking at. The queue file is
-- global and several agents append to it concurrently (each workmux worktree
-- is its own repo root), so every read and every write has to be scoped —
-- otherwise one project's findings show up in another's list, or get destroyed
-- by its clear.
local function in_repo(abs, repo_root)
  return not repo_root or abs:sub(1, #repo_root + 1) == repo_root .. "/"
end

-- ISO8601 (UTC, as `date -u +%Y-%m-%dT%H:%M:%SZ` emits) -> epoch seconds.
-- os.time interprets its table in LOCAL time, so subtract the local UTC offset
-- rather than trusting the result — otherwise every age is off by the timezone
-- and a finding made minutes ago can read as "stale" or as being in the future.
local function iso_to_epoch(s)
  if type(s) ~= "string" then
    return nil
  end
  local y, mo, d, h, mi, sec = s:match("^(%d+)-(%d+)-(%d+)[T ](%d+):(%d+):(%d+)")
  if not y then
    return nil
  end
  local t = { year = y, month = mo, day = d, hour = h, min = mi, sec = sec, isdst = false }
  local as_local = os.time(t)
  if not as_local then
    return nil
  end
  return as_local + os.difftime(as_local, os.time(os.date("!*t", as_local)))
end

local function age_label(secs)
  if secs < 3600 then
    return math.max(math.floor(secs / 60), 0) .. "m"
  elseif secs < 86400 then
    return math.floor(secs / 3600) .. "h"
  end
  return math.floor(secs / 86400) .. "d"
end

-- Age and drift for one entry, computed at load time (never stored).
--
-- Forgetting <leader>cF is the expected case, so the queue accumulates rows
-- whose line numbers no longer mean anything. The clamp in mark_buffer keeps
-- those from erroring, which is exactly the hazard: a finding pointing at code
-- that moved under it renders identically to a live one. File mtime newer than
-- the finding's timestamp is the cheap, dependency-free signal that a row may
-- have drifted — not proof (any unrelated edit trips it), so it's surfaced as a
-- warning to distrust the line number, not as grounds to drop the finding.
local function annotate(e)
  local at = iso_to_epoch(e.date)
  if not at then
    return nil, false
  end
  local age = age_label(os.time() - at)
  local st = vim.uv.fs_stat(e.path)
  return age, st ~= nil and st.mtime.sec > at
end

local function read_entries()
  local lines = read_lines()
  if not lines then
    return nil
  end

  local repo_root = require("util.git").root()
  local entries, skipped = {}, 0
  for _, line in ipairs(lines) do
    local ok, e = pcall(vim.json.decode, line)
    local abs = ok and entry_abs(e, repo_root) or nil
    if not abs then
      skipped = skipped + 1
    elseif in_repo(abs, repo_root) then
      entries[#entries + 1] = {
        path = abs,
        lnum = tonumber(e.line) or 1,
        col = tonumber(e.col) or 1,
        text = e.text,
        tier = TIERS[e.tier] and e.tier or DEFAULT_TIER,
        date = e.date,
      }
    end
  end
  return entries, skipped, #lines
end

-- Place virtual text for one buffer, if the queue has anything for its file.
-- Clamped to the buffer's length: the file may have been edited since the
-- finding was written, and an out-of-range extmark is a hard error.
local function mark_buffer(buf)
  if not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  local name = vim.api.nvim_buf_get_name(buf)
  local entries = name ~= "" and by_path[vim.fn.fnamemodify(name, ":p")]
  if not entries then
    return
  end
  vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  local last = vim.api.nvim_buf_line_count(buf)
  for _, e in ipairs(entries) do
    local row = math.min(math.max(e.lnum, 1), last) - 1
    pcall(vim.api.nvim_buf_set_extmark, buf, ns, row, 0, {
      virt_text = { { "  ◆ " .. e.text .. (e.suffix or ""), TIERS[e.tier].hl } },
      virt_text_pos = "eol",
      hl_mode = "combine",
    })
  end
end

local function mark_all_loaded()
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_loaded(buf) then
      mark_buffer(buf)
    end
  end
end

-- <leader>cf — load the queue into quickfix and mark the open buffers.
function M.load()
  local entries, skipped, total = read_entries()
  if not entries then
    vim.notify("No review queue at " .. QUEUE_PATH, vim.log.levels.INFO)
    return
  end
  -- Name the root when the queue has rows but none of them ours: "empty" is
  -- otherwise indistinguishable from "scoped to a repo you didn't expect",
  -- which is the actual failure when cwd is somewhere surprising.
  if #entries == 0 then
    local msg = "Review queue is empty for this repo"
    if total > 0 then
      msg = total .. " findings in the queue, none for " .. (require("util.git").root() or vim.fn.getcwd())
    end
    vim.notify(msg, vim.log.levels.INFO)
    return
  end

  -- ESCALATE first: the tier IS the dig-here-first ordering, so the list must
  -- open sorted by it rather than by whatever order the producer appended in.
  table.sort(entries, function(a, b)
    if TIERS[a.tier].rank ~= TIERS[b.tier].rank then
      return TIERS[a.tier].rank < TIERS[b.tier].rank
    end
    if a.path ~= b.path then
      return a.path < b.path
    end
    return a.lnum < b.lnum
  end)

  by_path = {}
  local items, stale = {}, 0
  for _, e in ipairs(entries) do
    local age, drifted = annotate(e)
    e.suffix = age and ("  [" .. age .. (drifted and ", stale" or "") .. "]") or ""
    if drifted then
      stale = stale + 1
    end
    by_path[e.path] = by_path[e.path] or {}
    table.insert(by_path[e.path], e)
    items[#items + 1] = {
      filename = e.path,
      lnum = e.lnum,
      col = e.col,
      type = TIERS[e.tier].qftype,
      text = e.tier .. ": " .. e.text .. e.suffix,
    }
  end

  vim.fn.setqflist({}, " ", { items = items, title = "Claude review queue" })
  mark_all_loaded()
  vim.cmd("botright copen")

  local msg = #items .. " findings"
  if stale > 0 then
    msg = msg .. ", " .. stale .. " stale (file edited since — distrust the line)"
  end
  if skipped and skipped > 0 then
    msg = msg .. " (" .. skipped .. " malformed lines skipped)"
  end
  vim.notify(msg, stale > 0 and vim.log.levels.WARN or vim.log.levels.INFO)
end

-- <leader>cF — queue worked; drop the marks and remove THIS repo's entries.
-- Same consume-on-read contract /cc has with claude-comments.md: findings are a
-- worklist, and a stale one that never empties gets ignored wholesale.
--
-- Scoped, not truncating: with several agents running, another repo's findings
-- are sitting in the same file and a blind `> file` would delete work you never
-- saw. Lines that fail to decode are kept, not dropped — an unparseable row is
-- someone else's problem to diagnose, and silently eating it loses the evidence.
--
-- The read-modify-write does race a concurrent append (a row landing between
-- the read and the write is lost). Not worth locking for: the window is a few
-- milliseconds on one machine, and the failure mode is one missed finding on a
-- worklist you re-run, not corruption.
function M.clear()
  by_path = {}
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_valid(buf) then
      vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
    end
  end

  local lines = read_lines()
  local repo_root = require("util.git").root()
  local kept, removed = {}, 0
  for _, line in ipairs(lines or {}) do
    local ok, e = pcall(vim.json.decode, line)
    local abs = ok and entry_abs(e, repo_root) or nil
    if abs and in_repo(abs, repo_root) then
      removed = removed + 1
    else
      kept[#kept + 1] = line
    end
  end

  local fh = io.open(QUEUE_PATH, "w")
  if not fh then
    vim.notify("Failed to write " .. QUEUE_PATH, vim.log.levels.ERROR)
    return
  end
  for _, line in ipairs(kept) do
    fh:write(line, "\n")
  end
  fh:close()

  vim.fn.setqflist({}, "r", { items = {}, title = "Claude review queue" })
  local msg = "Cleared " .. removed .. " findings"
  if #kept > 0 then
    msg = msg .. " (" .. #kept .. " kept for other repos)"
  end
  vim.notify(msg)
end

vim.api.nvim_create_user_command("ClaudeQueue", M.load, { desc = "Load Claude review queue into quickfix" })
vim.api.nvim_create_user_command("ClaudeQueueClear", M.clear, { desc = "Clear Claude review queue" })

-- Mark files opened after the queue was loaded — you jump through quickfix
-- into buffers that did not exist at load time, and those are exactly the
-- ones the virtual text is for.
vim.api.nvim_create_autocmd("BufReadPost", {
  group = vim.api.nvim_create_augroup("ClaudeReviewQueue", { clear = true }),
  callback = function(args)
    if next(by_path) then
      mark_buffer(args.buf)
    end
  end,
})

-- Claude corner of <leader>c, alongside cc (comment), cp (preview), cm (mention).
-- cf/cF, not cq/cQ: gitsigns already owns those for its hunk quickfix, and it
-- sets them buffer-locally from on_attach, so a global map here would look bound
-- (:map shows it) and silently never fire in any git-tracked buffer.
vim.keymap.set("n", "<leader>cf", M.load, { desc = "Load Claude findings queue (quickfix)" })
vim.keymap.set("n", "<leader>cF", M.clear, { desc = "Clear Claude findings queue" })

return M
