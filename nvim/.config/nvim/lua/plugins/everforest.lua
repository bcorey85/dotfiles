-- everforest — the "everforest" theme family (dark/light via
-- vim.o.background). Switch with `theme-use everforest [mode]`; scheme
-- mapping, accents, and the comment-floor fixup live in
-- lua/config/theme-sync.lua's FAMILIES table.
-- Measured 2026-07-07 (medium dark): fg #d3c6aa L 0.571 at only 19% sat,
-- gap 7.4:1, lifted bg #2d353b (L 0.034), accents <= L 0.53 / 49% sat.
-- Comments 3.8:1 stock (fixup raises them). Eye-ranked ~= github dimmed in
-- the original 30-theme audition.
return {
  "sainnhe/everforest",
  lazy = true,
  init = function()
    -- Globals read by the vimscript theme when the colorscheme applies.
    vim.g.everforest_background = "medium"
    vim.g.everforest_better_performance = 1
  end,
}
