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
            vim.api.nvim_feedkeys(":Obsidian new ", "n", false)
          end,
          desc = "New note",
        },
        {
          "<leader>oN",
          function()
            ensure_editable_win()
            vim.cmd("Obsidian new_from_template")
          end,
          desc = "New from template",
        },
        { "<leader>oo", "<cmd>Obsidian quick_switch<cr>", desc = "Quick switch" },
        { "<leader>ot", "<cmd>Obsidian template<cr>", desc = "Insert template" },
        { "<leader>ob", "<cmd>Obsidian backlinks<cr>", desc = "Backlinks" },
        { "<leader>os", "<cmd>Obsidian search<cr>", desc = "Search vault" },
        { "<leader>of", "<cmd>Obsidian follow_link<cr>", desc = "Follow link" },
        { "<leader>om", desc = "Move note to folder" },
      }
    end)(),
    config = function(_, opts)
      require("obsidian").setup(opts)

      vim.keymap.set("n", "<leader>om", function()
        local client = require("obsidian").get_client()
        local vault_root = tostring(client.dir)

        local dirs = {}
        local function scan(dir)
          local entries = vim.fn.readdir(dir)
          for _, name in ipairs(entries) do
            if name:sub(1, 1) ~= "." and name ~= "Templates" then
              local full = dir .. "/" .. name
              if vim.fn.isdirectory(full) == 1 then
                local rel = full:sub(#vault_root + 2)
                table.insert(dirs, rel)
                scan(full)
              end
            end
          end
        end
        scan(vault_root)
        table.sort(dirs)

        require("fzf-lua").fzf_exec(dirs, {
          prompt = "Move note to> ",
          actions = {
            ["default"] = function(selected)
              if not selected or #selected == 0 then return end
              local choice = selected[1]
              local src = vim.fn.expand("%:p")
              local fname = vim.fn.expand("%:t")
              local dest = vault_root .. "/" .. choice .. "/" .. fname
              local old_buf = vim.api.nvim_get_current_buf()

              vim.cmd("write")
              vim.fn.rename(src, dest)
              vim.cmd("edit " .. vim.fn.fnameescape(dest))
              vim.api.nvim_buf_delete(old_buf, { force = true })
              vim.notify("Moved to " .. choice, vim.log.levels.INFO)
            end,
          },
        })
      end, { desc = "Move note to folder" })
    end,
    opts = {
      legacy_commands = false,
      picker = {
        name = "fzf-lua",
      },
      workspaces = (function()
        local candidates = {
          { name = "general", path = vim.fn.expand("~/vaults/general") },
          { name = "general", path = vim.fn.expand("~/vault") },
        }
        local ws = {}
        for _, w in ipairs(candidates) do
          if vim.fn.isdirectory(w.path) == 1 then
            table.insert(ws, w)
          end
        end
        return ws
      end)(),
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
      ui = { enable = false },
    },
  },
}
