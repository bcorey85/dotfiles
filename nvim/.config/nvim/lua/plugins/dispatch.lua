-- vim-dispatch — async :Make/:Dispatch, results land in quickfix.
-- Runs builds/tests in a tmux pane (or background job) without blocking Neovim.
-- Default maps (m<CR>, m<Space>, `<CR>, '<CR>, g'<CR> etc.) are kept — they
-- don't conflict with existing config (q→<nop>/Q→macro, C-hjkl→smart-splits).
return {
  src = "tpope/vim-dispatch",
}
