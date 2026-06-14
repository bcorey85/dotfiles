-- mini.clue — key-clue popup hints (replaced which-key).
--
-- Window-resize submode: <C-w> then +/-/</>  repeat without re-pressing
-- <C-w> (submode_resize = true via gen_clues.windows).
-- Lives in the mini.nvim monorepo — no extra repo required.

return {
  src = "echasnovski/mini.nvim",
  setup = function()
    local miniclue = require("mini.clue")
    miniclue.setup({
      triggers = {
        { mode = { "n", "x" }, keys = "<Leader>" },
        { mode = { "n", "x" }, keys = "g" },
        { mode = { "n", "x" }, keys = "'" },
        { mode = { "n", "x" }, keys = "`" },
        { mode = { "n", "x" }, keys = '"' },
        { mode = { "i", "c" }, keys = "<C-r>" },
        { mode = "n", keys = "<C-w>" },
        { mode = { "n", "x" }, keys = "z" },
        { mode = "n", keys = "[" },
        { mode = "n", keys = "]" },
      },

      clues = {
        miniclue.gen_clues.builtin_completion(),
        miniclue.gen_clues.g(),
        miniclue.gen_clues.marks(),
        miniclue.gen_clues.registers(),
        miniclue.gen_clues.windows({ submode_resize = true }),
        miniclue.gen_clues.z(),

        { mode = { "n", "x" }, keys = "<Leader>b", desc = "+buffer" },
        { mode = { "n", "x" }, keys = "<Leader>c", desc = "+code" },
        { mode = { "n", "x" }, keys = "<Leader>f", desc = "+file/find" },
        { mode = { "n", "x" }, keys = "<Leader>g", desc = "+git" },
        { mode = { "n", "x" }, keys = "<Leader>gh", desc = "+hunks" },
        { mode = { "n", "x" }, keys = "<Leader>l", desc = "+lsp/qf" },
        { mode = { "n", "x" }, keys = "<Leader>n", desc = "+notes (obsidian)" },
        { mode = { "n", "x" }, keys = "<Leader>p", desc = "+plugins" },
        { mode = { "n", "x" }, keys = "<Leader>q", desc = "+quit" },
        { mode = { "n", "x" }, keys = "<Leader>s", desc = "+search" },
        { mode = { "n", "x" }, keys = "<Leader>t", desc = "+tasks" },
        { mode = { "n", "x" }, keys = "<Leader>u", desc = "+ui" },
        { mode = { "n", "x" }, keys = "<Leader>w", desc = "+windows" },
        { mode = { "n", "x" }, keys = "<Leader>y", desc = "+yank" },
        { mode = { "n", "x" }, keys = "<Leader><tab>", desc = "+tabs" },
        { mode = { "n", "x" }, keys = "g", desc = "+goto" },
        { mode = "n", keys = "[", desc = "+prev" },
        { mode = "n", keys = "]", desc = "+next" },
      },

      window = {
        delay = 500,
        config = { width = "auto" },
      },
    })
  end,
}
