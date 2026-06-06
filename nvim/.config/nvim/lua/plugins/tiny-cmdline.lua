-- tiny-cmdline: float the cmdline into a centered window on CmdlineEnter.
--
-- Works around neovim/neovim#36846: with cmdheight=0 + laststatus=3, ui2 keeps
-- the statusline drawn during cmdline entry instead of letting the cmdline cover
-- it, so the statusline jumps up a row on every `:`. tiny-cmdline lifts the
-- cmdline into a floating window (centered) on CmdlineEnter so the bottom row
-- is never touched and the statusline stays put. Built on the same
-- vim._core.ui2 system that options.lua already enables.
--
-- Guarded to the ui2 branch via cmdheight==0 so it no-ops on older nvim
-- (0.10/0.11 on WSL/Ubuntu/Arch where options.lua falls back to cmdheight=1).
--
-- Loaded eagerly (lazy=false) because the plugin registers its own
-- UIEnter/CmdlineEnter autocmds at load time. Loading on CmdlineEnter would
-- miss the first `:`, and loading on VeryLazy fires after UIEnter so its init
-- autocmd would never run.
return {
  "rachartier/tiny-cmdline.nvim",
  lazy = false,
  cond = function()
    return vim.o.cmdheight == 0
  end,
  config = function()
    require("tiny-cmdline").setup()
  end,
}
