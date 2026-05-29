return {
  {
    "folke/noice.nvim",
    event = "VeryLazy",
    dependencies = { "MunifTanjim/nui.nvim" },
    opts = {
      -- Cmdline popup only; let snacks.notifier own notifications.
      cmdline = { enabled = true, view = "cmdline_popup" },
      messages = { enabled = false },
      notify = { enabled = false },
      popupmenu = { enabled = true },
      lsp = {
        progress = { enabled = false },
        hover = { enabled = false },
        signature = { enabled = false },
        message = { enabled = false },
        -- Still upgrade markdown rendering in any noice-owned docs.
        override = {
          ["vim.lsp.util.convert_input_to_markdown_lines"] = true,
          ["vim.lsp.util.stylize_markdown"] = true,
        },
      },
      presets = {
        command_palette = true, -- center the cmdline + popupmenu together
        bottom_search = false,
        long_message_to_split = false,
        inc_rename = false,
        lsp_doc_border = false,
      },
    },
  },
}
