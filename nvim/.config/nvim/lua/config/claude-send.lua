-- Send file/selection references to a running Claude Code tmux pane.
-- The terminal-first replacement for claudecode.nvim's context bridge: no
-- in-process WebSocket server, just `tmux send-keys` of an @-mention into the
-- pane's prompt (VS Code extension format: @path or @path#L10-20). Nothing is
-- submitted — you compose the prompt around the mention and hit Enter yourself.
--
-- Pane discovery matches the claude-companion / .tmux.conf convention
-- (pane_current_command == "claude"): current window first, then any window
-- in the session (catches the stashed _claude companion and workmux agents).

local M = {}

-- tmux, synchronously; returns trimmed stdout or nil on failure.
local function tmux(args)
  local cmd = { "tmux" }
  vim.list_extend(cmd, args)
  local res = vim.system(cmd, { text = true }):wait()
  if res.code ~= 0 or not res.stdout or res.stdout == "" then
    return nil
  end
  return vim.trim(res.stdout)
end

-- First pane running claude: current window, then session-wide. Returns
-- pane_id or nil.
local function find_claude_pane()
  for _, scope in ipairs({ {}, { "-s" } }) do
    local args = { "list-panes" }
    vim.list_extend(args, scope)
    vim.list_extend(args, { "-F", "#{pane_id} #{pane_current_command}" })
    local out = tmux(args)
    for _, line in ipairs(out and vim.split(out, "\n") or {}) do
      local id, command = line:match("^(%S+) (%S+)$")
      if command == "claude" then
        return id
      end
    end
  end
  return nil
end

-- @-mention for the current buffer, relative to the target pane's cwd when the
-- file lives under it (claude resolves mentions against its own cwd), absolute
-- otherwise. line1/line2 optional.
local function mention(pane, line1, line2)
  local abs = require("util.buf").path()
  if not abs then
    vim.notify("Buffer has no file", vim.log.levels.WARN)
    return nil
  end
  local pane_cwd = tmux({ "display-message", "-p", "-t", pane, "#{pane_current_path}" })
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
-- pane's prompt. `-l --` = literal keys, so the text is typed, not interpreted.
function M.send(line1, line2)
  if not vim.env.TMUX then
    vim.notify("Not inside tmux", vim.log.levels.WARN)
    return
  end
  local pane = find_claude_pane()
  if not pane then
    vim.notify("No claude pane in this session (C-' spawns one)", vim.log.levels.WARN)
    return
  end
  local ref = mention(pane, line1, line2)
  if not ref then
    return
  end
  local res = vim.system({ "tmux", "send-keys", "-t", pane, "-l", "--", ref .. " " }):wait()
  if res.code ~= 0 then
    vim.notify("tmux send-keys failed: " .. (res.stderr or ""), vim.log.levels.ERROR)
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
