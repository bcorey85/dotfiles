return {
  src = "obsidian-nvim/obsidian.nvim",
  version = vim.version.range("^3.0.0"),
  -- Gate to the vault: obsidian pulls in a require chain (obsidian.actions /
  -- .note / .api / .yaml) that cost a few ms on EVERY startup, but the plugin is
  -- only useful inside ~/vault. cond is evaluated in config.pack — when false the
  -- spec (and its setup, keymaps, completion wiring) is skipped entirely. Tradeoff:
  -- the <leader>N* note commands only exist when nvim is launched from the vault.
  cond = function()
    return vim.startswith(vim.fs.normalize(vim.fn.getcwd()), vim.fs.normalize(vim.fn.expand("~/vault")))
  end,
  deps = {
    "nvim-lua/plenary.nvim",
    "folke/snacks.nvim",
  },
  setup = function()
    require("obsidian").setup({
      legacy_commands = false,
      picker = {
        name = "snacks.pick",
      },
      workspaces = (function()
        local candidates = {
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
      link = { style = "wiki" },
      ui = { enable = false },
    })

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

    vim.keymap.set("n", "<leader>Nn", function()
      ensure_editable_win()
      vim.cmd("enew")
      vim.api.nvim_feedkeys(":Obsidian new ", "n", false)
    end, { desc = "New note" })
    vim.keymap.set("n", "<leader>NN", function()
      ensure_editable_win()
      vim.cmd("Obsidian new_from_template")
    end, { desc = "New from template" })
    vim.keymap.set("n", "<leader>No", "<cmd>Obsidian quick_switch<cr>", { desc = "Quick switch" })
    vim.keymap.set("n", "<leader>Nt", "<cmd>Obsidian template<cr>", { desc = "Insert template" })
    vim.keymap.set("n", "<leader>Nb", "<cmd>Obsidian backlinks<cr>", { desc = "Backlinks" })
    vim.keymap.set("n", "<leader>Ns", "<cmd>Obsidian search<cr>", { desc = "Search vault" })
    vim.keymap.set("n", "<leader>Nf", "<cmd>Obsidian follow_link<cr>", { desc = "Follow link" })

    vim.keymap.set("n", "<leader>Nm", function()
      local vault_root = tostring(Obsidian.dir)

      local src_buf = vim.api.nvim_get_current_buf()
      local src = vim.api.nvim_buf_get_name(src_buf)
      local fname = vim.fn.fnamemodify(src, ":t")

      if vim.bo[src_buf].modified then
        vim.api.nvim_buf_call(src_buf, function()
          vim.cmd("write")
        end)
      end

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

      -- vim.ui.select is routed through snacks.picker (picker.ui_select, set in
      -- plugins/snacks.lua) so this renders as a snacks floating picker.
      vim.ui.select(dirs, { prompt = "Move note to" }, function(choice)
        if not choice then
          return
        end
        local dest = vault_root .. "/" .. choice .. "/" .. fname

        vim.fn.rename(src, dest)
        vim.cmd("edit " .. vim.fn.fnameescape(dest))
        vim.api.nvim_buf_delete(src_buf, { force = true })
        vim.notify("Moved to " .. choice, vim.log.levels.INFO)
      end)
    end, { desc = "Move note to folder" })
  end,
}
