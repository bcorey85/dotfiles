local detail = false

CustomOilBar = function()
  local path = vim.fn.expand("%")
  path = path:gsub("oil://", "")
  return "  " .. vim.fn.fnamemodify(path, ":.")
end

return {
  "stevearc/oil.nvim",
  dependencies = { "nvim-mini/mini.icons" },
  keys = {
    { "-", "<cmd>Oil<cr>", desc = "Open parent directory" },
    { "<leader>-", function() require("oil").toggle_float() end, desc = "Oil floating window" },
  },
  opts = {
    win_options = {
      winbar = "%{v:lua.CustomOilBar()}",
    },
    default_file_explorer = true,
    columns = { "icon" },
    delete_to_trash = true,
    skip_confirm_for_simple_edits = true,
    watch_for_changes = true,
    lsp_file_methods = {
      autosave_changes = "unmodified",
    },
    keymaps = {
      ["g?"] = { "actions.show_help", mode = "n" },
      ["<CR>"] = "actions.select",
      ["<C-v>"] = { "actions.select", opts = { vertical = true } },
      ["<C-x>"] = { "actions.select", opts = { horizontal = true } },
      ["<C-t>"] = { "actions.select", opts = { tab = true } },
      ["<C-p>"] = "actions.preview",
      ["q"] = { "actions.close", mode = "n" },
      ["-"] = { "actions.parent", mode = "n" },
      ["_"] = { "actions.open_cwd", mode = "n" },
      ["gs"] = { "actions.change_sort", mode = "n" },
      ["gx"] = "actions.open_external",
      ["g."] = { "actions.toggle_hidden", mode = "n" },
      ["gd"] = {
        desc = "Toggle file detail view",
        callback = function()
          detail = not detail
          if detail then
            require("oil").set_columns({ "icon", "permissions", "size", "mtime" })
          else
            require("oil").set_columns({ "icon" })
          end
        end,
      },
    },
    view_options = {
      show_hidden = true,
    },
  },
}
