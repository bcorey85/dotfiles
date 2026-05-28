return {
  {
    "nvim-lualine/lualine.nvim",
    opts = function(_, opts)
      -- Add a bold "unsaved" indicator right after the mode section
      table.insert(opts.sections.lualine_b, 1, {
        function() return "UNSAVED" end,
        cond = function() return vim.bo.modified end,
        color = { fg = "#1a1a2e", bg = "#f85e84", gui = "bold" },
      })
    end,
  },
}
