-- vitesse (local checkout ~/dev/vitesse.nvim, a pure-Lua port of antfu's Vitesse) —
-- audition only, not a theme-mode family: :colorscheme vitesse follows
-- vim.o.background. lazy = true: lazy.nvim loads it on the :colorscheme call.
-- cond: the checkout exists on one machine only.
local checkout = vim.fn.expand("~/dev/vitesse.nvim")

return {
  dir = checkout,
  name = "vitesse",
  lazy = true,
  cond = vim.fn.isdirectory(checkout) == 1,
}
