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

local function close_diffview()
  vim.cmd("DiffviewClose")
  tmux_unzoom()
end

return {
  -- Maintained fork of sindrets/diffview.nvim (upstream stale since Jun 2024).
  -- Drop-in: same `diffview` module + Diffview* commands, no config changes.
  "dlyongemallo/diffview.nvim",
  cmd = { "DiffviewOpen", "DiffviewFileHistory" },
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
