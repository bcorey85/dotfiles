return {
  "epwalsh/obsidian.nvim",
  version = "*",
  lazy = true,
  ft = "markdown",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "ibhagwan/fzf-lua",
  },
  keys = {
    { "<leader>on", "<cmd>enew<cr>:ObsidianNew ", desc = "New note" },
    { "<leader>oN", "<cmd>ObsidianNewFromTemplate<cr>", desc = "New from template" },
    { "<leader>oo", "<cmd>ObsidianQuickSwitch<cr>", desc = "Quick switch" },
    { "<leader>ot", "<cmd>ObsidianTemplate<cr>", desc = "Insert template" },
    { "<leader>ob", "<cmd>ObsidianBacklinks<cr>", desc = "Backlinks" },
    { "<leader>os", "<cmd>ObsidianSearch<cr>", desc = "Search vault" },
    { "<leader>om", desc = "Move note to folder" },
  },
  config = function(_, opts)
    require("obsidian").setup(opts)

    vim.keymap.set("n", "<leader>om", function()
      local vault = vim.fn.finddir(".obsidian", vim.fn.expand("%:p:h") .. ";")
      if vault == "" then
        vim.notify("Not in an Obsidian vault", vim.log.levels.WARN)
        return
      end
      local vault_root = vim.fn.fnamemodify(vault, ":h")

      vim.ui.select({
        "00. Inbox",
        "01. Literature",
        "02. Permanent",
        "90. Projects",
        "91. Areas",
        "92. Resources",
        "93. Archives",
        "Files",
      }, { prompt = "Move note to:" }, function(choice)
        if choice then
          local src = vim.fn.expand("%:p")
          local fname = vim.fn.expand("%:t")
          local dest = vault_root .. "/" .. choice .. "/" .. fname
          local old_buf = vim.api.nvim_get_current_buf()

          vim.cmd("write")
          vim.fn.rename(src, dest)
          vim.cmd("edit " .. vim.fn.fnameescape(dest))
          vim.api.nvim_buf_delete(old_buf, { force = true })
          vim.notify("Moved to " .. choice, vim.log.levels.INFO)
        end
      end)
    end, { desc = "Move note to folder" })
  end,
  opts = {
    picker = {
      name = "fzf-lua",
    },
    workspaces = {
      {
        name = "general",
        path = "/mnt/c/vault/general/",
      },
    },
    templates = {
      folder = "Templates",
    },
    notes_subdir = "00. Inbox",
    note_id_func = function(title)
      if title then
        return title
      end
      return tostring(os.time())
    end,
  },
}
