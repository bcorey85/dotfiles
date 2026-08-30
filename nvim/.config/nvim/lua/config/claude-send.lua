-- Send file/selection references to a running Claude Code pane.
-- The terminal-first replacement for claudecode.nvim's context bridge: no
-- in-process WebSocket server, just `herdr pane send-text` of an @-mention into
-- the pane's prompt (VS Code extension format: @path or @path#L10-20). Nothing is
-- submitted — you compose the prompt around the mention and hit Enter yourself.
--
-- Pane discovery: current workspace first, then all workspaces. Matches panes
-- whose agent is "claude" or whose process name looks like a claude binary.

local M = {}

-- Run herdr, synchronously; returns trimmed stdout or nil on failure.
local function herdr(args)
  local cmd = { "herdr" }
  vim.list_extend(cmd, args)
  local res = vim.system(cmd, { text = true }):wait()
  if res.code ~= 0 or not res.stdout or res.stdout == "" then
    return nil
  end
  return vim.trim(res.stdout)
end

-- Run herdr and decode JSON; returns the `result` object or nil.
local function herdr_json(args)
  local out = herdr(args)
  if not out then
    return nil
  end
  local ok, data = pcall(vim.json.decode, out)
  if not ok or not data or not data.result then
    return nil
  end
  return data.result
end

-- First pane running claude: current workspace, then any workspace. Returns
-- the pane object or nil.
local function find_claude_pane()
  local current = herdr_json({ "pane", "current" })
  local current_ws = current and current.pane and current.pane.workspace_id

  local data = herdr_json({ "pane", "list" })
  local panes = data and data.panes or {}

  local function match(p)
    local agent = p.agent
    local cmd = p.process or p.command or p.pane_title or ""
    return agent == "claude" or cmd:match("^claude") or cmd:match("^%d+%.%d+%.%d+$")
  end

  if current_ws then
    for _, p in ipairs(panes) do
      if p.workspace_id == current_ws and match(p) then
        return p
      end
    end
  end

  for _, p in ipairs(panes) do
    if match(p) then
      return p
    end
  end

  return nil
end

-- @-mention for the current buffer, relative to the target pane's cwd when the
-- file lives under it (claude resolves mentions against its own cwd), absolute
-- otherwise. line1/line2 optional.
local function mention(pane, line1, line2)
  local buf = require("util.buf")
  -- Same guard as review.lua's resolve_abs_path, for the same reason: special
  -- buffers have names, so path() happily returns "<cwd>/NeogitStatus" and we'd
  -- send claude an @-mention of a file that doesn't exist with line numbers from
  -- the wrong buffer. An @-mention must point at something claude can read.
  if not buf.is_file() then
    vim.notify("@-mentions need a real file buffer", vim.log.levels.WARN)
    return nil
  end
  local abs = buf.path()
  if not abs then
    vim.notify("Buffer has no file", vim.log.levels.WARN)
    return nil
  end
  local pane_cwd = pane.cwd
  local path = abs
  if pane_cwd and abs:sub(1, #pane_cwd + 1) == pane_cwd .. "/" then
    path = abs:sub(#pane_cwd + 2)
  end
  local ref = "@" .. path
  if line1 then
    ref = ref .. "#L" .. line1 .. (line2 and line2 ~= line1 and ("-" .. line2) or "")
  end
  return ref
end

-- Send an @-mention (whole file, or line1-line2 when given) into the claude
-- pane's prompt.
function M.send(line1, line2)
  if not vim.env.HERDR_PANE_ID then
    vim.notify("Not inside herdr", vim.log.levels.WARN)
    return
  end
  local pane = find_claude_pane()
  if not pane then
    vim.notify("No claude pane found (C-' spawns one)", vim.log.levels.WARN)
    return
  end
  local ref = mention(pane, line1, line2)
  if not ref then
    return
  end
  local res = vim.system({ "herdr", "pane", "send-text", pane.pane_id, ref .. " " }):wait()
  if res.code ~= 0 then
    vim.notify("herdr pane send-text failed: " .. (res.stderr or ""), vim.log.levels.ERROR)
    return
  end
  vim.notify("Sent " .. ref .. " to claude")
end

vim.api.nvim_create_user_command("ClaudeSend", function(args)
  if args.range == 0 then
    M.send()
  else
    M.send(args.line1, args.line2)
  end
end, { range = true, desc = "Send file/selection @-mention to Claude pane" })

-- <leader>cm ("mention") sits in the Claude corner of <leader>c alongside
-- <leader>cc (review comment) and <leader>cp (preview) — cs/cr/etc. belong to
-- gitsigns staging. `:` (not `<cmd>`) in visual mode so vim auto-inserts the
-- '<,'> range, same as :ClaudeReviewComment.
vim.keymap.set("n", "<leader>cm", "<cmd>ClaudeSend<cr>", { desc = "Send file @-mention to Claude pane" })
vim.keymap.set("v", "<leader>cm", ":ClaudeSend<cr>", { desc = "Send selection @-mention to Claude pane" })

return M
