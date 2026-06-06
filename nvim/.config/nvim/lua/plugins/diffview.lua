-- Diffview runs in a tmux pane we zoom on open and un-zoom on close, so every
-- close path (q, <leader>dd toggle) must funnel through the same teardown.
-- When launched as the tmux review popup (prefix d), there is no surrounding
-- nvim pane to zoom - a display-popup is an overlay, not a pane, so resize-pane
-- would wrongly toggle zoom on the underlying window. Skip the zoom dance there.
local in_popup = vim.env.DIFFVIEW_POPUP ~= nil

local tmux = require("util.tmux")

local function resolve_abs_path()
  local abs_path

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
      return nil
    end
    if bufname == "" then
      vim.notify("Buffer has no file name", vim.log.levels.WARN)
      return nil
    end
    abs_path = bufname
  end

  if not abs_path:match("^/") then
    local repo_root = require("util.git").root()
    if repo_root then
      abs_path = repo_root .. "/" .. abs_path
    else
      abs_path = vim.fn.getcwd() .. "/" .. abs_path
    end
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

    local review_path = claude_dir .. "/review.md"
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

    vim.notify("Comment saved to ~/.claude/review.md")
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
  local review_path = vim.uv.os_homedir() .. "/.claude/review.md"
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

local function close_diffview()
  vim.cmd("DiffviewClose")
  if not in_popup then
    tmux.unzoom()
  end
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
    -- Positional conflict-choose keys for the merge tool: h = OURS (left pane),
    -- l = THEIRS (right pane), mirroring the diff3 layout spatially. These ADD to
    -- diffview's mnemonic <leader>co/ct (which still work). Spliced into every
    -- merge-layout context so they hold if you cycle diff3 -> diff1/diff4. Done
    -- here (not in the static opts below) so requiring diffview.actions doesn't
    -- force-load the plugin at startup; diffview merges these with its defaults.
    local actions = require("diffview.actions")

    -- Custom "keep both" (ours + theirs, NO base) for the merge tool. diffview's
    -- native conflict_choose("all") joins ours+base+theirs, dragging in the common
    -- ancestor; this mirrors diffview's internal conflict_choose but joins only
    -- ours then theirs — the usual "keep both changes". FRAGILE: it reaches into
    -- diffview internals (lib / StandardView / parse_conflicts / layout main win),
    -- so it may need updating if the plugin reshuffles those modules.
    local function conflict_choose_both()
      local lib = require("diffview.lib")
      local StandardView = require("diffview.scene.views.standard.standard_view").StandardView
      local vcs_utils = require("diffview.vcs.utils")
      local dv_utils = require("diffview.utils")

      local view = lib.get_current_view()
      if not (view and view:instanceof(StandardView)) then
        return
      end
      -- Inlined equivalent of diffview's local get_valid_main(view).
      local main = view.cur_layout and view.cur_layout:get_main_win()
      if not (main and main:is_valid() and main.file and main.file:is_valid()) then
        return
      end
      local bufnr = main.file.bufnr
      local _, cur = vcs_utils.parse_conflicts(vim.api.nvim_buf_get_lines(bufnr, 0, -1, false), main.id)
      if not cur then
        return
      end
      local content = dv_utils.vec_join(cur.ours.content, cur.theirs.content)
      vim.api.nvim_buf_set_lines(bufnr, cur.first - 1, cur.last, false, content)
      dv_utils.set_cursor(main.id, #content + cur.first - 1, 0)
    end

    -- Whole-file "keep both": ours+theirs for EVERY conflict. Mirrors diffview's
    -- resolve_all_conflicts — a forward pass with a line-offset accumulator, so
    -- each replacement's length change shifts the remaining conflicts' ranges.
    -- Same internal-API fragility caveat as conflict_choose_both above.
    local function conflict_choose_both_all()
      local lib = require("diffview.lib")
      local StandardView = require("diffview.scene.views.standard.standard_view").StandardView
      local vcs_utils = require("diffview.vcs.utils")
      local dv_utils = require("diffview.utils")

      local view = lib.get_current_view()
      if not (view and view:instanceof(StandardView)) then
        return
      end
      local main = view.cur_layout and view.cur_layout:get_main_win()
      if not (main and main:is_valid() and main.file and main.file:is_valid()) then
        return
      end
      local bufnr = main.file.bufnr
      local conflicts = vcs_utils.parse_conflicts(vim.api.nvim_buf_get_lines(bufnr, 0, -1, false), main.id)
      if not next(conflicts) then
        return
      end
      local content, first
      local offset = 0
      for _, c in ipairs(conflicts) do
        first = c.first + offset
        local last = c.last + offset
        content = dv_utils.vec_join(c.ours.content, c.theirs.content)
        vim.api.nvim_buf_set_lines(bufnr, first - 1, last, false, content)
        offset = offset + (#content - (last - first) - 1)
      end
      dv_utils.set_cursor(main.id, #content + first - 1, 0)
      view.cur_layout:sync_scroll()
    end

    local positional_conflict = {
      -- Choose (positional): h = left/ours, l = right/theirs, a = all/both.
      -- ca/cA point at the CUSTOM both (ours+theirs, no base), overriding
      -- diffview's native base-including ca/cA.
      { "n", "<leader>ch", actions.conflict_choose("ours"), { desc = "Conflict: choose ours (left)" } },
      { "n", "<leader>cl", actions.conflict_choose("theirs"), { desc = "Conflict: choose theirs (right)" } },
      { "n", "<leader>ca", conflict_choose_both, { desc = "Conflict: keep both (ours+theirs)" } },
      -- Whole-file (uppercase): apply the choice to every conflict at once.
      { "n", "<leader>cH", actions.conflict_choose_all("ours"), { desc = "Conflict: choose ours, whole file" } },
      { "n", "<leader>cL", actions.conflict_choose_all("theirs"), { desc = "Conflict: choose theirs, whole file" } },
      { "n", "<leader>cA", conflict_choose_both_all, { desc = "Conflict: keep both, whole file" } },
      -- Navigation: j = next (down), k = prev (up). Replaces the default ]x / [x.
      { "n", "<leader>cj", actions.next_conflict, { desc = "Conflict: next" } },
      { "n", "<leader>ck", actions.prev_conflict, { desc = "Conflict: prev" } },
      -- Hide diffview's mnemonic / base defaults (false disables a default) so
      -- only the scheme above remains: co/cO/ct/cT (mnemonic ours/theirs) and
      -- cb/cB (base). Native ca/cA are overridden above, not hidden. Use the
      -- positional keys, or dx/dX to delete a conflict region.
      { "n", "<leader>co", false },
      { "n", "<leader>cO", false },
      { "n", "<leader>ct", false },
      { "n", "<leader>cT", false },
      { "n", "<leader>cb", false },
      { "n", "<leader>cB", false },
      { "n", "]x", false },
      { "n", "[x", false },
    }
    opts.keymaps = opts.keymaps or {}
    for _, ctx in ipairs({ "diff1", "diff3", "diff4" }) do
      opts.keymaps[ctx] = vim.list_extend(opts.keymaps[ctx] or {}, positional_conflict)
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
        { "n", "cc", "<Cmd>Git commit<CR>", { desc = "Commit staged" } },
        { "n", "ca", "<Cmd>Git commit --amend<CR>", { desc = "Amend last commit" } },
        {
          "n",
          "<C-d>",
          function()
            local key = vim.api.nvim_replace_termcodes("<C-d>", true, false, true)
            for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
              if vim.wo[win].diff then
                vim.api.nvim_win_call(win, function()
                  vim.cmd("normal! " .. key)
                end)
                return
              end
            end
          end,
          { desc = "Scroll diff down" },
        },
        {
          "n",
          "<C-u>",
          function()
            local key = vim.api.nvim_replace_termcodes("<C-u>", true, false, true)
            for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
              if vim.wo[win].diff then
                vim.api.nvim_win_call(win, function()
                  vim.cmd("normal! " .. key)
                end)
                return
              end
            end
          end,
          { desc = "Scroll diff up" },
        },
      },
    },
    view = {
      merge_tool = {
        -- diff3_horizontal: 3 colored panes (OURS | BASE | THEIRS) with conflict
        -- highlighting — diffview's default and the proper layout for resolving.
        -- diff1_plain (the old value) is a single plain buffer with raw markers
        -- and no coloring, since there are no panes to diff against. Cycle layouts
        -- live in a merge with the cycle_layout action if you want the 1-pane view.
        layout = "diff3_horizontal",
        disable_diagnostics = true,
      },
    },
    hooks = {
      -- Soft-wrap long lines in the diff panes. Diff mode defaults to nowrap;
      -- linebreak wraps at word boundaries instead of mid-token. Note this can
      -- drift the two sides' vertical alignment when a wrapped line spans a
      -- different number of screen rows on each side - the tradeoff for not
      -- scrolling horizontally on long lines.
      diff_buf_win_enter = function(_, winid)
        vim.wo[winid].wrap = true
        vim.wo[winid].linebreak = true
        -- Collapse unchanged regions so only changed hunks (plus the diffopt
        -- `context` lines around them) show. Diff mode folds non-change text via
        -- foldmethod=diff; foldlevel=0 starts those folds closed, countering the
        -- global foldlevel=99 (options.lua) that would otherwise leave every fold
        -- open and show the whole file. Press zR in a diff to expand it all.
        vim.wo[winid].foldenable = true
        vim.wo[winid].foldmethod = "diff"
        vim.wo[winid].foldlevel = 0
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
    { "<leader>cc", "<cmd>ClaudeReviewComment<cr>", mode = "n", desc = "Leave Claude review comment" },
    -- `:` (not `<cmd>`) so vim auto-inserts `'<,'>` as the range before executing
    { "<leader>cc", ":ClaudeReviewComment<cr>", mode = "v", desc = "Leave Claude review comment" },
    {
      "<leader>cp",
      preview_review_comments,
      mode = "n",
      desc = "Preview pending Claude review comments",
    },
    {
      "<leader>dd",
      function()
        local lib = require("diffview.lib")
        if lib.get_current_view() then
          close_diffview()
        else
          if not in_popup then
            tmux.zoom()
          end
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
          if not in_popup then
            tmux.zoom()
          end
          vim.cmd("DiffviewFileHistory %")
        end
      end,
      desc = "Toggle File History",
    },
    {
      "<leader>dh",
      function()
        local lib = require("diffview.lib")
        if lib.get_current_view() then
          close_diffview()
        else
          if not in_popup then
            tmux.zoom()
          end
          vim.cmd("DiffviewFileHistory")
        end
      end,
      desc = "Toggle Repo History",
    },
    {
      "<leader>gu",
      function()
        vim.cmd("DiffviewFileHistory --range=@{upstream}..HEAD")
      end,
      desc = "Git log unpushed (diffview)",
    },
  },
}
