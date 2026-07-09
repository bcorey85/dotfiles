-- github-theme — the "github" theme family (github_dark_default / github_light).
-- Switch to it with `theme-mode use github`; scheme mapping and accents live
-- in lua/config/theme-sync.lua's FAMILIES table. lazy.nvim auto-loads
-- colorschemes from lazy specs when :colorscheme requests them, so this costs
-- nothing at startup while benched.
return {
  "projekt0n/github-nvim-theme",
  name = "github-theme",
  lazy = true,
}
