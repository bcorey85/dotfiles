-- Diffview runs in a tmux pane we zoom on open and un-zoom on close, so every
-- close path (q, <leader>dd toggle) must funnel through the same teardown.
-- When launched as the tmux review popup (prefix d), there is no surrounding
-- nvim pane to zoom - a display-popup is an overlay, not a pane, so resize-pane
-- would wrongly toggle zoom on the underlying window. Skip the zoom dance there.
local in_popup = vim.env.DIFFVIEW_POPUP ~= nil

local function tmux_unzoom()
  if in_popup then
    return
  end
  local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
  if zoomed == "1" then
    vim.fn.system("tmux resize-pane -Z")
  end
end

local function tmux_zoom()
  if in_popup then
    return
  end
  local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
  if zoomed ~= "1" then
    vim.fn.system("tmux resize-pane -Z")
  end
end

local function leave_review_comment(mode)
  local abs_path

  -- pcall so pressing <leader>cc in a random buffer never force-loads diffview
  local ok, lib = pcall(require, "diffview.lib")
  if ok then
    local view = lib.get_current_view()
    if view and view.panel and view.panel.cur_file then
      abs_path = view.panel.cur_file.path
    elseif view and view:instanceof(lib.StandardView or {}) and view.cur_entry then
      abs_path = view.cur_entry.path
    end
  end

  if not abs_path then
    local bufname = vim.api.nvim_buf_get_name(0)
    if bufname:match("^diffview://") then
      vim.notify("Could not resolve real file path", vim.log.levels.WARN)
      return
    end
    if bufname == "" then
      vim.notify("Buffer has no file name", vim.log.levels.WARN)
      return
    end
    abs_path = bufname
  end

  local line_ref
  if mode == "v" then
    local start_line = vim.fn.line("'<")
    local end_line = vim.fn.line("'>")
    if start_line == end_line then
      line_ref = tostring(start_line)
    else
      line_ref = start_line .. "-" .. end_line
    end
  else
    line_ref = tostring(vim.fn.line("."))
  end

  vim.ui.input({ prompt = "Review comment: " }, function(input)
    if not input or input == "" then
      return
    end

    if not abs_path:match("^/") then
      local repo_root = vim.fn.systemlist("git rev-parse --show-toplevel")[1]
      if repo_root and repo_root ~= "" then
        abs_path = repo_root .. "/" .. abs_path
      else
        abs_path = vim.fn.getcwd() .. "/" .. abs_path
      end
    end
    abs_path = vim.fn.fnamemodify(abs_path, ":p")

    local claude_dir = vim.uv.os_homedir() .. "/.claude"
    vim.fn.mkdir(claude_dir, "p")

    local review_path = claude_dir .. "/review.md"
    local timestamp = os.date("!%Y-%m-%dT%H:%M:%SZ")
    local entry = string.format("## %s:%s\n%s\n\n%s\n\n---\n\n", abs_path, line_ref, timestamp, input)

    local fh = io.open(review_path, "a")
    if not fh then
      vim.notify("Failed to open " .. review_path, vim.log.levels.ERROR)
      return
    end
    fh:write(entry)
    fh:close()

    vim.notify("Comment saved to ~/.claude/review.md")
  end)
end

local function close_diffview()
  vim.cmd("DiffviewClose")
  tmux_unzoom()
end

return {
  -- Maintained fork of sindrets/diffview.nvim (upstream stale since Jun 2024).
  -- Drop-in: same `diffview` module + Diffview* commands, no config changes.
  "dlyongemallo/diffview.nvim",
  cmd = { "DiffviewOpen", "DiffviewFileHistory" },
  -- Neovim 0.12 forbids Vimscript functions in fast-event/async contexts.
  -- diffview's PathLib:expand resolves `$VAR` path segments via `vim.env`
  -- (which calls getenv) from inside its async git jobs, raising E5560 and
  -- breaking every diff. Override that one method to use os.getenv (pure Lua,
  -- fast-event-safe, nil when unset - same semantics). Patching here instead of
  -- the plugin dir survives :Lazy update. Drop once upstream ships a fix.
  config = function(_, opts)
    local PathLib = require("diffview.path").PathLib
    function PathLib:expand(path)
      local segments = self:explode(path)
      local idx = 1
      if segments[1] == "~" then
        segments[1] = vim.uv.os_homedir()
        idx = 2
      end
      for i = idx, #segments do
        local env_var = segments[i]:match("^%$(%S+)$")
        if env_var then
          local value = os.getenv(env_var)
          if value ~= nil then
            segments[i] = value
          end
        end
      end
      return self:join(unpack(segments))
    end
    require("diffview").setup(opts)
  end,
  opts = {
    keymaps = {
      view = {
        { "n", "q", close_diffview, { desc = "Close Diffview" } },
      },
      file_panel = {
        { "n", "q", close_diffview, { desc = "Close Diffview" } },
        { "n", "cc", "<Cmd>Git commit<bar>wincmd J<CR>", { desc = "Commit staged" } },
        { "n", "ca", "<Cmd>Git commit --amend<bar>wincmd J<CR>", { desc = "Amend last commit" } },
        { "n", "<C-d>", function()
          local key = vim.api.nvim_replace_termcodes("<C-d>", true, false, true)
          for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
            if vim.wo[win].diff then
              vim.api.nvim_win_call(win, function() vim.cmd("normal! " .. key) end)
              return
            end
          end
        end, { desc = "Scroll diff down" } },
        { "n", "<C-u>", function()
          local key = vim.api.nvim_replace_termcodes("<C-u>", true, false, true)
          for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
            if vim.wo[win].diff then
              vim.api.nvim_win_call(win, function() vim.cmd("normal! " .. key) end)
              return
            end
          end
        end, { desc = "Scroll diff up" } },
      },
    },
    view = {
      merge_tool = {
        layout = "diff1_plain",
        disable_diagnostics = true,
      },
    },
    hooks = {
      diff_buf_read = function()
        vim.opt_local.foldenable = false
      end,
      -- Soft-wrap long lines in the diff panes. Diff mode defaults to nowrap;
      -- linebreak wraps at word boundaries instead of mid-token. Note this can
      -- drift the two sides' vertical alignment when a wrapped line spans a
      -- different number of screen rows on each side - the tradeoff for not
      -- scrolling horizontally on long lines.
      diff_buf_win_enter = function(_, winid)
        vim.wo[winid].wrap = true
        vim.wo[winid].linebreak = true
      end,
      -- In the tmux review popup, closing the diff means we're done - quit the
      -- throwaway nvim so the popup dismisses (mirrors closing lazygit). In the
      -- main editor (no env var) this is a no-op and close just returns to work.
      view_closed = function()
        if in_popup then
          vim.cmd("qa")
        end
      end,
    },
  },
  keys = {
    {
      "<leader>cc",
      function() leave_review_comment("n") end,
      mode = "n",
      desc = "Leave Claude review comment",
    },
    {
      "<leader>cc",
      function() leave_review_comment("v") end,
      mode = "v",
      desc = "Leave Claude review comment",
    },
    {
      "<leader>dd",
      function()
        local lib = require("diffview.lib")
        if lib.get_current_view() then
          close_diffview()
        else
          tmux_zoom()
          vim.cmd("DiffviewOpen")
        end
      end,
      desc = "Toggle Diff View",
    },
    {
      "<leader>dm",
      "<cmd>DiffviewOpen<cr>",
      desc = "Merge Conflicts",
    },
    {
      "<leader>df",
      function()
        local lib = require("diffview.lib")
        if lib.get_current_view() then
          close_diffview()
        else
          tmux_zoom()
          vim.cmd("DiffviewFileHistory %")
        end
      end,
      desc = "Toggle File History",
    },
  },
}
