-- mini.surround — add/delete/replace surrounding pairs. From the mini.nvim
-- monorepo (shared clone).
return {
  src = "echasnovski/mini.nvim",
  setup = function()
    require("mini.surround").setup({
      mappings = {
        add = "gsa",
        delete = "gsd",
        find = "gsf",
        find_left = "gsF",
        highlight = "gsh",
        replace = "gsr",
        update_n_lines = "gsn",
      },
    })
  end,
}
