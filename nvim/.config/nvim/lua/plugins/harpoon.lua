return {
  src = "ThePrimeagen/harpoon",
  version = "harpoon2",
  deps = { "nvim-lua/plenary.nvim" },
  setup = function()
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
