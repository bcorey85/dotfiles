-- IMPORTANT: not lazy-loaded. smart-splits must run at startup so it can set
-- the @pane-is-vim tmux user-option that the tmux side checks via
-- `if -F "#{@pane-is-vim}"` to decide whether to forward C-/A-hjkl to nvim or
-- handle it in tmux. Lazy-loading would mean the variable is unset until the
-- plugin loads, breaking cross-boundary nav/resize on startup.
--
-- In the throwaway nvim launched inside a tmux display-popup (prefix g / prefix d),
-- there is no real pane for smart-splits' tmux backend to attach to, so its
-- on_init warns "tmux init: could not detect pane ID". The popup needs no
-- cross-pane nav, so disable the multiplexer there. smart-splits auto-detects
-- tmux from $TERM_PROGRAM (still "tmux" in a popup), so unsetting $TMUX won't do
-- it; instead use the documented pre-load vim.g hook (config.lua:80), which works
-- because this top-level runs during lazy spec collection, before the plugin loads.
if vim.env.NEOGIT_POPUP or vim.env.DIFFVIEW_POPUP then
  vim.g.smart_splits_multiplexer_integration = false
end

return {
  "mrjones2014/smart-splits.nvim",
  lazy = false,
  opts = {
    resize_mode = {
      silent = true,
    },
    default_amount = 3,
  },
  keys = {
    { "<C-h>", function() require("smart-splits").move_cursor_left() end,  desc = "Move cursor left (smart)" },
    { "<C-j>", function() require("smart-splits").move_cursor_down() end,  desc = "Move cursor down (smart)" },
    { "<C-k>", function() require("smart-splits").move_cursor_up() end,    desc = "Move cursor up (smart)" },
    { "<C-l>", function() require("smart-splits").move_cursor_right() end, desc = "Move cursor right (smart)" },
    { "<A-h>", function() require("smart-splits").resize_left() end,  desc = "Resize left (smart)" },
    { "<A-j>", function() require("smart-splits").resize_down() end,  desc = "Resize down (smart)" },
    { "<A-k>", function() require("smart-splits").resize_up() end,    desc = "Resize up (smart)" },
    { "<A-l>", function() require("smart-splits").resize_right() end, desc = "Resize right (smart)" },
  },
}
