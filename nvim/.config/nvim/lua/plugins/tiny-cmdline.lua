-- tiny-cmdline: float the cmdline into a centered window on CmdlineEnter.
--
-- Works around neovim/neovim#36846: with cmdheight=0 + laststatus=3, ui2 keeps
-- the statusline drawn during cmdline entry instead of letting the cmdline cover
-- it, so the statusline jumps up a row on every `:`. tiny-cmdline lifts the
-- cmdline into a floating window (centered) on CmdlineEnter so the bottom row
-- is never touched and the statusline stays put.
--
-- cond gates this to the ui2 branch (cmdheight==0) so it no-ops on older nvim
-- (0.10/0.11 on WSL/Ubuntu/Arch where options.lua falls back to cmdheight=1).
-- The plugin registers its own UIEnter/CmdlineEnter autocmds on setup, so it
-- must load at startup (it does — pack.lua loads everything eagerly).
return {
  src = "rachartier/tiny-cmdline.nvim",
  cond = function()
    return vim.o.cmdheight == 0
  end,
  setup = function()
    require("tiny-cmdline").setup()
  end,
}
