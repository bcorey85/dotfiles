-- gruvbox-material — the "gruvbox-material" theme family (dark/light via
-- vim.o.background). Switch with `theme-use gruvbox-material [mode]`; scheme
-- mapping, accents, and the comment-floor fixup live in
-- lua/config/theme-sync.lua's FAMILIES table.
-- Measured 2026-07-07 (medium dark): fg #d4be98 L 0.531 (ideal glow band),
-- gap 8.2:1, neutral bg #282828, every accent <= L 0.43 — tighter accent
-- discipline than github dimmed. Comments 4.0:1 stock (fixup raises them).
return {
  "sainnhe/gruvbox-material",
  lazy = true,
  init = function()
    -- Globals read by the vimscript theme when the colorscheme applies.
    vim.g.gruvbox_material_background = "medium"
    vim.g.gruvbox_material_foreground = "material"
    vim.g.gruvbox_material_better_performance = 1
  end,
}
