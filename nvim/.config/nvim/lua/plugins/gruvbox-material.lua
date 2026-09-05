-- gruvbox-material (sainnhe/gruvbox-material) — theme-mode family, run with
-- `foreground = "original"` so its accents are the ORIGINAL gruvbox hexes
-- (red #fb4934, fg #ebdbb2), not the softer material set (#f2594b / #e2cca9).
-- Kept alongside the `gruvbox` family (ellisonleao/gruvbox.nvim) for A/B: same
-- palette, different chrome (bg1 #32302f vs #3c3836) and different role
-- assignment (Function green, Operator orange, Constant aqua, PreProc purple).
--
-- Loads eagerly (lazy = false, priority = 1000) so it's on the rtp before
-- config.lazy.lua's theme-sync.start(). The variant globals are set by
-- theme-sync's `pre` hook, which runs before :colorscheme.
return {
  "sainnhe/gruvbox-material",
  name = "gruvbox-material",
  lazy = false,
  priority = 1000,
}
