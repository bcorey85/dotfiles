-- flash.nvim — label-jump motion. `s` + 1-2 chars, then the label key jumps.
-- Also decorates `f`/`t`/`F`/`T` (repeat with `;`/`,`, no plugin key needed) and
-- `/` search with the same labels, so the ordinary motions get the jump for free.
--
-- `s` is free here: mini.surround is remapped to the `gs*` prefix (mini.lua).
-- The cmdline `<c-s>` toggle LazyVim ships is deliberately not mapped — `<C-s>`
-- is Save File in keymaps.lua.
return {
  "folke/flash.nvim",
  event = "VeryLazy",
  opts = {},
  keys = {
    { "s", mode = { "n", "x", "o" }, function() require("flash").jump() end, desc = "Flash" },
    { "S", mode = { "n", "x", "o" }, function() require("flash").treesitter() end, desc = "Flash Treesitter" },
    { "r", mode = "o", function() require("flash").remote() end, desc = "Remote Flash" },
    { "R", mode = { "o", "x" }, function() require("flash").treesitter_search() end, desc = "Treesitter Search" },
  },
}
