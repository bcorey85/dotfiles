return {
  "ThePrimeagen/harpoon",
  branch = "harpoon2",
  keys = {
    { "<leader>a", desc = "Harpoon: add file" },
    { "<leader><tab>", desc = "Harpoon: menu" },
    { "<leader>1", desc = "Harpoon: slot 1" },
    { "<leader>2", desc = "Harpoon: slot 2" },
    { "<leader>3", desc = "Harpoon: slot 3" },
    { "<leader>4", desc = "Harpoon: slot 4" },
  },
  dependencies = { "nvim-lua/plenary.nvim" },
  config = function()
    local harpoon = require("harpoon")
    harpoon:setup({ settings = { save_on_toggle = true } })

    vim.keymap.set("n", "<leader>a", function()
      harpoon:list():add()
    end, { desc = "Harpoon: add file" })
    vim.keymap.set("n", "<leader><tab>", function()
      harpoon.ui:toggle_quick_menu(harpoon:list())
    end, { desc = "Harpoon: menu" })
    for i = 1, 4 do
      vim.keymap.set("n", "<leader>" .. i, function()
        harpoon:list():select(i)
      end, { desc = "Harpoon: slot " .. i })
    end
  end,
}
