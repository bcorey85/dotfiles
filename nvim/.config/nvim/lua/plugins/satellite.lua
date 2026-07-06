-- satellite.nvim — decorated scrollbar (VS Code overview-ruler equivalent),
-- by the gitsigns author. Positional marks on the right edge of every
-- window: git hunks (via gitsigns), diagnostics, search matches, marks,
-- quickfix entries, cursor. Stock config — handlers all default-on.
-- :SatelliteDisable / :SatelliteEnable / :SatelliteRefresh if it misbehaves.
return {
  "lewis6991/satellite.nvim",
  event = "VeryLazy",
  opts = {
    handlers = {
      -- The cursor mark rides beside the thumb while scrolling (cursor stays
      -- in view) — reads as a glitchy dash, adds nothing. VS Code semantics:
      -- mark CONTENT positions (hunks/diagnostics/search), not the cursor.
      cursor = { enable = false },
    },
  },
}
