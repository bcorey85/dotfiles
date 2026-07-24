-- grug-far.nvim — project-wide search & replace over ripgrep, with a live
-- preview of every match before anything is written to disk.
-- Source: github.com/MagicDuck/grug-far.nvim
--
--   <leader>sr   open grug-far (took the key from snacks marks → now <leader>sm)
--   <leader>sr   (visual) prefill the search with the selection
--
-- Inside the grug-far buffer, `g?` shows its local keymap help (replace, sync,
-- qflist, history, etc.).
return {
  "MagicDuck/grug-far.nvim",
  cmd = { "GrugFar", "GrugFarWithin" },
  keys = {
    {
      "<leader>sr",
      function()
        require("grug-far").open()
      end,
      desc = "Search and replace (grug-far)",
    },
    {
      "<leader>sr",
      mode = "x",
      function()
        require("grug-far").with_visual_selection()
      end,
      desc = "Search and replace selection (grug-far)",
    },
  },
  opts = {},
}
