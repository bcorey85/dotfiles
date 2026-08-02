-- Audition colorscheme families (non-default). Each is lazy: lazy.nvim scans a
-- plugin's colors/ dir at install and auto-loads the owning plugin when
-- theme-sync :colorscheme's one of its schemes (nightfox.lua is the eager
-- bootstrap that drives that). Per-family scheme/accent/fixup mapping lives in
-- theme-sync's FAMILIES registry; the ghostty + tmux sides live in theme-mode.
return {
  { "catppuccin/nvim", name = "catppuccin", lazy = true }, -- catppuccin-macchiato / -latte
  { "ellisonleao/gruvbox.nvim", lazy = true }, -- gruvbox (background-driven)
  { "projekt0n/github-nvim-theme", lazy = true }, -- github_dark_dimmed / _light_default
  { "sainnhe/everforest", lazy = true }, -- everforest (g:everforest_background-driven)
}
