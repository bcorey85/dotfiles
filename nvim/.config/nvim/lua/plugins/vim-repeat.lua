-- vim-repeat (tpope) — teaches the `.` command to repeat PLUGIN maps, not just
-- built-in edits. Vanilla `.` only repeats native changes; after a plugin
-- mapping it either no-ops or repeats the wrong thing. Plugins that call
-- repeat#set() (vim-abolish's coercions, vim-surround, etc.) become dot-
-- repeatable once this is on the runtimepath. Zero config; changes no default
-- key, only extends `.` into places it currently does nothing.
--
-- Concretely: `crs` (abolish snake_case coercion) then `.` `.` coerces the next
-- words too, instead of `.` doing nothing.
return {
  "tpope/vim-repeat",
  event = "VeryLazy",
}
