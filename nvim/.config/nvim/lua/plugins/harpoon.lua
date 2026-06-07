return {
  "ThePrimeagen/harpoon",
  branch = "harpoon2",
  dependencies = { "nvim-lua/plenary.nvim" },
  keys = {
    { "<leader>a", function() require("harpoon"):list():add() end, desc = "Harpoon: add file" },
    { "<leader>h", function() local h = require("harpoon"); h.ui:toggle_quick_menu(h:list()) end, desc = "Harpoon: menu" },
    { "<leader>1", function() require("harpoon"):list():select(1) end, desc = "Harpoon: slot 1" },
    { "<leader>2", function() require("harpoon"):list():select(2) end, desc = "Harpoon: slot 2" },
    { "<leader>3", function() require("harpoon"):list():select(3) end, desc = "Harpoon: slot 3" },
    { "<leader>4", function() require("harpoon"):list():select(4) end, desc = "Harpoon: slot 4" },
  },
  config = function()
    require("harpoon"):setup({ settings = { save_on_toggle = true } })
  end,
}
