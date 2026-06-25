-- smart-splits must run at startup (it's eager here) so it can set the
-- @pane-is-vim tmux user-option that the tmux side checks via
-- `if -F "#{@pane-is-vim}"` to decide whether to forward C-/A-hjkl to nvim or
-- handle it in tmux.
--
-- In a throwaway nvim launched inside a tmux popup (prefix g = neogit,
-- prefix s = git hunk qf), there is no real pane for smart-splits' tmux backend
-- to attach to, so its on_init warns "tmux init: could not detect pane ID". The
-- popup needs no cross-pane nav, so disable the multiplexer there. smart-splits
-- auto-detects tmux from $TERM_PROGRAM (still "tmux" in a popup), so unsetting
-- $TMUX won't do it; instead set the documented pre-load vim.g hook here. This
-- runs when the module is required (during pack.lua's plugin walk), before the
-- plugin loads.
-- A headless nvim (`nvim --headless ...`: CI, scripted checks, ad-hoc
-- verification) has no UI and no business owning the pane's @pane-is-vim flag.
-- smart-splits' on_init would set it on whatever tmux pane launched the script
-- and not clear it on exit, stranding the flag — so tmux then forwards
-- C-hjkl / prefix-m to that pane (e.g. a Claude/terminal pane) instead of the
-- real nvim. No UI ⇒ list_uis() is empty; disable the integration there too.
if vim.env.NEOGIT_POPUP or vim.env.GIT_QF_POPUP or #vim.api.nvim_list_uis() == 0 then
  vim.g.smart_splits_multiplexer_integration = false
end

return {
  src = "mrjones2014/smart-splits.nvim",
  setup = function()
    require("smart-splits").setup({
      resize_mode = {
        silent = true,
      },
      default_amount = 3,
    })

    local ss = require("smart-splits")
    local map = function(lhs, fn, desc)
      vim.keymap.set("n", lhs, fn, { desc = desc })
    end
    map("<C-h>", ss.move_cursor_left, "Move cursor left (smart)")
    map("<C-j>", ss.move_cursor_down, "Move cursor down (smart)")
    map("<C-k>", ss.move_cursor_up, "Move cursor up (smart)")
    map("<C-l>", ss.move_cursor_right, "Move cursor right (smart)")

    -- Same nav keys in terminal mode so you can move OUT of a terminal split
    -- without first hitting <C-\><C-n>. Tradeoff: <C-l> no longer reaches the
    -- shell as clear-screen inside nvim terminals — type `clear` instead.
    vim.keymap.set("t", "<C-h>", ss.move_cursor_left, { desc = "Move cursor left (smart)" })
    vim.keymap.set("t", "<C-j>", ss.move_cursor_down, { desc = "Move cursor down (smart)" })
    vim.keymap.set("t", "<C-k>", ss.move_cursor_up, { desc = "Move cursor up (smart)" })
    vim.keymap.set("t", "<C-l>", ss.move_cursor_right, { desc = "Move cursor right (smart)" })
    map("<A-h>", ss.resize_left, "Resize left (smart)")
    map("<A-j>", ss.resize_down, "Resize down (smart)")
    map("<A-k>", ss.resize_up, "Resize up (smart)")
    map("<A-l>", ss.resize_right, "Resize right (smart)")
  end,
}
