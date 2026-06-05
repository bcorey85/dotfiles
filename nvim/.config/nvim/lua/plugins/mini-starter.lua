return {
  {
    "echasnovski/mini.nvim",
    event = "VimEnter",
    config = function()
      local starter = require("mini.starter")
      starter.setup({
        header = "Neovim",
        footer = "",
        items = {
          {
            name = "Session restore",
            action = function()
              require("persistence").load()
            end,
            section = "Actions",
          },
          {
            name = "Config files",
            action = function()
              require("mini.pick").builtin.files({}, { source = { cwd = vim.fn.stdpath("config") } })
            end,
            section = "Actions",
          },
          { name = "Lazy", action = "Lazy", section = "Actions" },
          { name = "Lazy update", action = "Lazy update", section = "Actions" },
          { name = "Quit", action = "qa", section = "Actions" },
          starter.sections.recent_files(8, false),
        },
        content_hooks = {
          starter.gen_hook.adding_bullet(),
          starter.gen_hook.aligning("center", "center"),
        },
      })

      -- j/k navigate items. mini.starter treats typed characters as a filter
      -- query by default, so bare j/k would filter (and "no active items") rather
      -- than move. These buffer-local maps override that on the dashboard only.
      vim.api.nvim_create_autocmd("FileType", {
        pattern = "ministarter",
        callback = function(args)
          vim.keymap.set("n", "j", function()
            starter.update_current_item("next")
          end, { buffer = args.buf })
          vim.keymap.set("n", "k", function()
            starter.update_current_item("prev")
          end, { buffer = args.buf })
        end,
      })
    end,
  },
}
