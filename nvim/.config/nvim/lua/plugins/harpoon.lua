return {
  "ThePrimeagen/harpoon",
  branch = "harpoon2",
  dependencies = { "nvim-lua/plenary.nvim" },
  config = function()
    local harpoon = require("harpoon")
    harpoon:setup()
  end,
  keys = {
    {
      "<leader>ha",
      function() require("harpoon"):list():add() end,
      desc = "Harpoon: add file",
    },
    {
      "<leader>hh",
      function()
        local harpoon = require("harpoon")
        harpoon.ui:toggle_quick_menu(harpoon:list())
      end,
      desc = "Harpoon: toggle menu",
    },
    {
      "<leader>h1",
      function() require("harpoon"):list():select(1) end,
      desc = "Harpoon: file 1",
    },
    {
      "<leader>h2",
      function() require("harpoon"):list():select(2) end,
      desc = "Harpoon: file 2",
    },
    {
      "<leader>h3",
      function() require("harpoon"):list():select(3) end,
      desc = "Harpoon: file 3",
    },
    {
      "<leader>h4",
      function() require("harpoon"):list():select(4) end,
      desc = "Harpoon: file 4",
    },
    {
      "<leader>hp",
      function() require("harpoon"):list():prev() end,
      desc = "Harpoon: prev file",
    },
    {
      "<leader>hn",
      function() require("harpoon"):list():next() end,
      desc = "Harpoon: next file",
    },
  },
}
