return {
  {
    "zbirenbaum/copilot.lua",
    opts = {
      filetypes = {
        markdown = false,
      },
    },
  },
  {
    "obsidian-nvim/obsidian.nvim",
    version = "*",
    lazy = true,
    ft = "markdown",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "ibhagwan/fzf-lua",
    },
    keys = (function()
      local function ensure_editable_win()
        if not vim.bo.modifiable then
          for _, win in ipairs(vim.api.nvim_list_wins()) do
            local buf = vim.api.nvim_win_get_buf(win)
            if vim.bo[buf].modifiable and vim.bo[buf].buflisted then
              vim.api.nvim_set_current_win(win)
              return
            end
          end
          vim.cmd("vnew")
        end
      end

      return {
        {
          "<leader>on",
          function()
            ensure_editable_win()
            vim.cmd("enew")
            vim.api.nvim_feedkeys(":ObsidianNew ", "n", false)
          end,
          desc = "New note",
        },
        {
          "<leader>oN",
          function()
            ensure_editable_win()
            vim.cmd("ObsidianNewFromTemplate")
          end,
          desc = "New from template",
        },
        { "<leader>oo", "<cmd>ObsidianQuickSwitch<cr>", desc = "Quick switch" },
        { "<leader>ot", "<cmd>ObsidianTemplate<cr>", desc = "Insert template" },
        { "<leader>ob", "<cmd>ObsidianBacklinks<cr>", desc = "Backlinks" },
        { "<leader>os", "<cmd>ObsidianSearch<cr>", desc = "Search vault" },
        { "<leader>of", "<cmd>ObsidianFollowLink<cr>", desc = "Follow link" },
        { "<leader>om", desc = "Move note to folder" },
      }
    end)(),
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
          path = vim.fn.expand("~/vault"),
        },
      },
      templates = {
        folder = "Templates",
        date_format = "%m/%d/%Y %I:%M %p",
      },
      completion = {
        min_chars = 3,
      },
      note = {
        template = "Inbox.md",
      },
      notes_subdir = "00. Inbox",
      note_id_func = function(title)
        if title then
          return title
        end
        return tostring(os.time())
      end,
      wiki_link_func = function(opts)
        return string.format("[[%s]]", opts.label)
      end,
    },
  },
}
