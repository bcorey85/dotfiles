-- Claude review-comment feature — extracted from plugins/diffview.lua (which is
-- now removed). This module is independent of any plugin: it writes entries to
-- ~/.claude/claude-comments.md and exposes :ClaudeReviewComment plus preview keymaps.

local function resolve_abs_path()
  local bufname = vim.api.nvim_buf_get_name(0)
  if bufname == "" then
    vim.notify("Buffer has no file name", vim.log.levels.WARN)
    return nil
  end
  local abs_path = bufname
  if not abs_path:match("^/") then
    local repo_root = require("util.git").root()
    abs_path = (repo_root or vim.fn.getcwd()) .. "/" .. abs_path
  end
  return vim.fn.fnamemodify(abs_path, ":p")
end

local function write_review_entry(line_ref, snippet_lines)
  local abs_path = resolve_abs_path()
  if not abs_path then
    return
  end

  vim.ui.input({ prompt = "Review comment: " }, function(input)
    if not input or input == "" then
      return
    end

    local claude_dir = vim.uv.os_homedir() .. "/.claude"
    vim.fn.mkdir(claude_dir, "p")

    local review_path = claude_dir .. "/claude-comments.md"
    local timestamp = os.date("!%Y-%m-%dT%H:%M:%SZ")

    local entry
    if snippet_lines then
      local ft = vim.bo.filetype
      local fence_open = "````" .. ft
      local fence_close = "````"
      local snippet = table.concat(snippet_lines, "\n")
      entry = string.format(
        "## %s:%s\n%s\n\n%s\n%s\n%s\n\n%s\n\n---\n\n",
        abs_path,
        line_ref,
        timestamp,
        fence_open,
        snippet,
        fence_close,
        input
      )
    else
      entry = string.format("## %s:%s\n%s\n\n%s\n\n---\n\n", abs_path, line_ref, timestamp, input)
    end

    local fh = io.open(review_path, "a")
    if not fh then
      vim.notify("Failed to open " .. review_path, vim.log.levels.ERROR)
      return
    end
    fh:write(entry)
    fh:close()

    vim.notify("Comment saved to ~/.claude/claude-comments.md")
  end)
end

local function leave_review_comment_normal()
  local line_ref = tostring(vim.fn.line("."))
  write_review_entry(line_ref, nil)
end

local function leave_review_comment_range(line1, line2)
  local line_ref
  if line1 == line2 then
    line_ref = tostring(line1)
  else
    line_ref = line1 .. "-" .. line2
  end
  local snippet_lines = vim.api.nvim_buf_get_lines(0, line1 - 1, line2, false)
  write_review_entry(line_ref, snippet_lines)
end

vim.api.nvim_create_user_command("ClaudeReviewComment", function(args)
  if args.range == 0 then
    leave_review_comment_normal()
  else
    leave_review_comment_range(args.line1, args.line2)
  end
end, { range = true, desc = "Leave Claude review comment" })

local function preview_review_comments()
  local review_path = vim.uv.os_homedir() .. "/.claude/claude-comments.md"
  local fh = io.open(review_path, "r")
  if not fh then
    vim.notify("No pending Claude review comments", vim.log.levels.INFO)
    return
  end
  local content = fh:read("*a")
  fh:close()

  if not content or content == "" then
    vim.notify("No pending Claude review comments", vim.log.levels.INFO)
    return
  end

  local repo_root = require("util.git").root()

  local entries = {}
  local current = {}
  for line in (content .. "\n"):gmatch("([^\n]*)\n") do
    if line:match("^## ") then
      if #current > 0 then
        entries[#entries + 1] = table.concat(current, "\n")
      end
      current = { line }
    else
      current[#current + 1] = line
    end
  end
  if #current > 0 then
    entries[#entries + 1] = table.concat(current, "\n")
  end

  local filtered = {}
  for _, entry in ipairs(entries) do
    local header = entry:match("^## ([^\n]+)")
    if header then
      local path = header:match("^(.-):%S+$") or header
      if not repo_root or path:sub(1, #repo_root) == repo_root then
        filtered[#filtered + 1] = entry
      end
    end
  end

  local lines = {}
  if repo_root then
    lines[#lines + 1] = "# Claude Review Comments — " .. repo_root
  else
    lines[#lines + 1] = "# Claude Review Comments"
  end
  lines[#lines + 1] = ""

  if #filtered == 0 then
    local label = repo_root and ("# No pending comments in " .. repo_root) or "# No pending comments"
    lines = { label }
  else
    for _, entry in ipairs(filtered) do
      for line in (entry .. "\n"):gmatch("([^\n]*)\n") do
        lines[#lines + 1] = line
      end
      lines[#lines + 1] = ""
    end
  end

  vim.cmd("new")
  vim.bo.buftype = "nofile"
  vim.bo.bufhidden = "wipe"
  vim.bo.filetype = "markdown"
  vim.api.nvim_buf_set_name(0, "ClaudeReview")
  vim.api.nvim_buf_set_lines(0, 0, -1, false, lines)
  vim.bo.modifiable = false
  vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = true })
end

vim.keymap.set("n", "<leader>cc", "<cmd>ClaudeReviewComment<cr>", { desc = "Leave Claude review comment" })
-- `:` (not `<cmd>`) so vim auto-inserts `'<,'>` as the range before executing
vim.keymap.set("v", "<leader>cc", ":ClaudeReviewComment<cr>", { desc = "Leave Claude review comment" })
vim.keymap.set("n", "<leader>cp", preview_review_comments, { desc = "Preview pending Claude review comments" })
