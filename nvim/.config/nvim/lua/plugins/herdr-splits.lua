-- herdr counterpart of smart-splits.lua — C/M-hjkl nav+resize across the
-- herdr<->nvim boundary. Pairs with the herdr-side plugin
-- (`herdr plugin install lmilojevicc/herdr-splits.nvim`) and the
-- plugin_action keybinds in herdr/.config/herdr/config.toml.
-- Loads only inside herdr; smart-splits.lua covers tmux (mutually exclusive
-- via HERDR_ENV).
return {
  "lmilojevicc/herdr-splits.nvim",
  cond = vim.env.HERDR_ENV == "1",
  event = "VeryLazy",
  config = function()
    require("herdr-splits").setup({
      neovim_amount = 3,
      at_edge = "wrap",
      unzoom_on_nav = true,
      nav_at_edge = "wrap",
    })
  end,
  keys = {
    { "<C-h>", function() require("herdr-splits").move_cursor_left() end, desc = "Move cursor left (herdr)" },
    { "<C-j>", function() require("herdr-splits").move_cursor_down() end, desc = "Move cursor down (herdr)" },
    { "<C-k>", function() require("herdr-splits").move_cursor_up() end, desc = "Move cursor up (herdr)" },
    { "<C-l>", function() require("herdr-splits").move_cursor_right() end, desc = "Move cursor right (herdr)" },
    { "<C-h>", function() require("herdr-splits").move_cursor_left() end, mode = "t", desc = "Move cursor left (herdr)" },
    { "<C-j>", function() require("herdr-splits").move_cursor_down() end, mode = "t", desc = "Move cursor down (herdr)" },
    { "<C-k>", function() require("herdr-splits").move_cursor_up() end, mode = "t", desc = "Move cursor up (herdr)" },
    { "<C-l>", function() require("herdr-splits").move_cursor_right() end, mode = "t", desc = "Move cursor right (herdr)" },
    { "<M-h>", function() require("herdr-splits").resize_left() end, desc = "Resize left (herdr)" },
    { "<M-j>", function() require("herdr-splits").resize_down() end, desc = "Resize down (herdr)" },
    { "<M-k>", function() require("herdr-splits").resize_up() end, desc = "Resize up (herdr)" },
    { "<M-l>", function() require("herdr-splits").resize_right() end, desc = "Resize right (herdr)" },
  },
}
