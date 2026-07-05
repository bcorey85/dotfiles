-- nvim-orgmode: a from-scratch Lua reimplementation of Emacs org-mode that reads
-- and writes real .org files (its own treesitter grammar, auto-installed on first
-- setup). Gets ~85-90% of daily org: agenda, capture, TODO cycling, scheduling,
-- clocking, archiving, refile. Gaps vs Emacs: org-babel (code execution) and full
-- export — neither is wired here.
--
-- Org files live in ~/vault/org — the same git repo as the markdown vault, so
-- they share one remote/backup. They're excluded from Obsidian's index (see the
-- vault's .obsidian/app.json) so the org "doing" layer stays out of the vault
-- graph/search. (~/org is a symlink to ~/vault/org for shell muscle memory.)
--
-- Returns three specs as a list (pack.lua handles list-valued modules). Order
-- matters: orgmode first (registers the org parser + filetype), then the two
-- cosmetic plugins that decorate org buffers.
return {
  {
    "nvim-orgmode/orgmode",
    ft = "org",
    config = function()
      -- Doom layout, split across two prefixes (the same split Doom uses):
      --   <leader>n = GLOBAL notes (Doom SPC n): agenda/capture/todos/tags/
      --               clock/search — reachable everywhere, defined as keymaps
      --               below (+ org_agenda/org_capture via mappings.global).
      --   <leader>m = org-buffer localleader (Doom SPC m): todo/schedule/clock/
      --               refile/export — the `mappings.prefix` rebase below.
      -- (<leader>o is the snacks buffers picker, untouched.)
      require("orgmode").setup({
        org_agenda_files = "~/vault/org/**/*",
        org_default_notes_file = "~/vault/org/inbox.org",

        -- Richer-than-default workflow states (the bit people rave about).
        -- (t)/(n)/... are fast-access keys when cycling with org_todo.
        org_todo_keywords = { "TODO(t)", "NEXT(n)", "WAITING(w)", "|", "DONE(d)", "CANCELLED(c)" },

        -- org-indent-mode: virtual indentation under headings, no real spaces.
        org_startup_indented = true,

        org_todo_keyword_faces = {
          DONE = ":foreground #44bc44 :weight bold",
          CANCELLED = ":foreground #feacd0 :slant italic",
          WAITING = ":foreground #d0bc00",
        },

        org_capture_templates = {
          t = {
            description = "Todo",
            template = "* TODO %?\n  %u",
            target = "~/vault/org/inbox.org",
          },
          n = {
            description = "Note",
            template = "* %?\n  %u",
            target = "~/vault/org/notes.org",
          },
          j = {
            description = "Journal",
            template = "\n*** %<%Y-%m-%d> %<%A>\n**** %U\n\n%?",
            target = "~/vault/org/journal.org",
          },
        },

        mappings = {
          prefix = "<leader>m",
          global = {
            org_agenda = "<leader>na",
            org_capture = "<leader>nc",
          },
        },
      })
      -- nvim-orgmode's singleton config (used by all internal modules) does NOT
      -- pick up user's org_return_uses_meta_return. Patch it explicitly so
      -- org_return() routes through meta_return for list continuation.
      require("orgmode.config").mappings.org_return_uses_meta_return = true

      -- Global "notes" entry points (Doom SPC n): reachable from any buffer, not
      -- just inside org files (those use <leader>m above). agenda/capture are
      -- already bound via mappings.global; these add the rest of the SPC n menu.
      local function nmap(lhs, action, desc)
        vim.keymap.set("n", lhs, function()
          require("orgmode").action(action)
        end, { desc = desc })
      end
      nmap("<leader>nt", "agenda.todos", "org: todo list")
      nmap("<leader>nm", "agenda.tags", "org: tags search")
      nmap("<leader>nS", "agenda.search", "org: search agenda headlines")
      nmap("<leader>no", "clock.org_clock_goto", "org: goto active clock")
      nmap("<leader>nC", "clock.org_clock_cancel", "org: cancel clock")
      -- search / browse the org dir via the snacks picker
      vim.keymap.set("n", "<leader>ns", function()
        require("snacks").picker.grep({ cwd = vim.fn.expand("~/vault/org") })
      end, { desc = "org: search notes" })
      vim.keymap.set("n", "<leader>nF", function()
        require("snacks").picker.files({ cwd = vim.fn.expand("~/vault/org") })
      end, { desc = "org: browse notes" })
    end,
  },

  {
    "nvim-orgmode/org-bullets.nvim",
    ft = "org",
    config = function()
      require("org-bullets").setup({
        symbols = {
          checkboxes = false,
        },
      })
      -- Concealment is what turns "** " into a single nested bullet and hides
      -- *bold*/_underline_ markers. orgmode + org-bullets both rely on it.
      vim.api.nvim_create_autocmd("FileType", {
        pattern = "org",
        group = vim.api.nvim_create_augroup("OrgConceal", { clear = true }),
        callback = function()
          vim.opt_local.conceallevel = 1
          vim.opt_local.concealcursor = ""
          -- <CR> in insert mode continues list items via orgmode's meta_return
          -- (listitem nodes only — headlines excluded to avoid spurious * headings).
          vim.keymap.set("i", "<CR>", function()
            local ts_utils = require("orgmode.utils.treesitter")
            local node = ts_utils.get_node_at_cursor()
            local closest = ts_utils.closest_node(node, "listitem")
            if closest then
              return require("orgmode").instance().org_mappings:meta_return()
            end
            vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<CR>", true, false, true), "n", true)
          end, { buffer = true, desc = "org cr (list only)" })
          -- <leader>mv adds [ ] to a plain list item or toggles an existing one
          vim.keymap.set("n", "<leader>mv", function()
            local line = vim.fn.getline(".")
            local prefix, rest = line:match("^(%s*[-+*]%s)(.*)$")
            if not prefix then
              return
            end
            local status, after = rest:match("^%[([Xx -])%]%s?(.*)$")
            if status then
              local new_status = (status == "X" or status == "x") and " " or "X"
              vim.fn.setline(".", prefix .. "[" .. new_status .. "] " .. after)
            else
              vim.fn.setline(".", prefix .. "[ ] " .. rest)
            end
            vim.cmd("redraw")
          end, { buffer = true, desc = "Toggle checkbox" })
        end,
      })
    end,
  },

  {
    "lukas-reineke/headlines.nvim",
    ft = "org",
    config = function()
      -- Doom-one-tinted heading backgrounds + code-block highlight. headlines'
      -- default config references these group names; link them so they actually
      -- render instead of falling back to nothing.
      vim.api.nvim_set_hl(0, "Headline", { link = "ColorColumn" })
      vim.api.nvim_set_hl(0, "CodeBlock", { link = "CursorLine" })
      vim.api.nvim_set_hl(0, "Dash", { link = "Comment" })
      local headlines = require("headlines")
      headlines.setup()

      -- headlines.nvim is unmaintained. Its Syntax-triggered refresh can fire
      -- mid treesitter-highlighter-init, iterating a partially-parsed tree where
      -- a heading match resolves with no marker text — make_reverse_highlight
      -- then concatenates a nil hl_group and throws (E5108) on every affected
      -- markdown buffer. The failure is transient: the next refresh (TextChanged/
      -- WinScrolled, once the tree is fully parsed) renders correctly. Guard the
      -- refresh so the racy pass is a no-op instead of an error.
      local refresh = headlines.refresh
      headlines.refresh = function(...)
        pcall(refresh, ...)
      end
    end,
  },
}
