-- nvim-orgmode: a from-scratch Lua reimplementation of Emacs org-mode that reads
-- and writes real .org files (its own treesitter grammar, auto-installed on first
-- setup). Gets ~85-90% of daily org: agenda, capture, TODO cycling, scheduling,
-- clocking, archiving, refile. Gaps vs Emacs: org-babel (code execution) and full
-- export — neither is wired here.
--
-- Org files live in ~/org (created by install/setup or on first capture), kept
-- separate from the markdown vault for full .org fidelity.
--
-- Returns three specs as a list (pack.lua handles list-valued modules). Order
-- matters: orgmode first (registers the org parser + filetype), then the two
-- cosmetic plugins that decorate org buffers.
return {
  {
    src = "nvim-orgmode/orgmode",
    setup = function()
  -- Doom Emacs convention: SPC n = org mode. The <leader>o leaf is the snacks
  -- buffers picker (see plugins/snacks.lua), so no conflict there. `prefix`
  -- rebases the in-buffer org_* maps; the two global entry points have
  -- explicit lhs and are moved alongside it.
      require("orgmode").setup({
        org_agenda_files = "~/org/**/*",
        org_default_notes_file = "~/org/inbox.org",

        -- Richer-than-default workflow states (the bit people rave about).
        -- (t)/(n)/... are fast-access keys when cycling with org_todo.
        org_todo_keywords = { "TODO(t)", "NEXT(n)", "WAITING(w)", "|", "DONE(d)", "CANCELLED(c)" },

        -- org-indent-mode: virtual indentation under headings, no real spaces.
        org_startup_indented = true,

        org_todo_keyword_faces = {
          DONE = ":foreground #98be65 :weight bold",
          CANCELLED = ":foreground #c678dd :slant italic",
          WAITING = ":foreground #ECBE7B",
        },

        org_capture_templates = {
          t = {
            description = "Todo",
            template = "* TODO %?\n  %u",
            target = "~/org/inbox.org",
          },
          n = {
            description = "Note",
            template = "* %?\n  %u",
            target = "~/org/notes.org",
          },
          j = {
            description = "Journal",
            template = "\n*** %<%Y-%m-%d> %<%A>\n**** %U\n\n%?",
            target = "~/org/journal.org",
          },
        },

        mappings = {
          prefix = "<leader>n",
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
    end,
  },

  {
    src = "nvim-orgmode/org-bullets.nvim",
    setup = function()
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
          -- <leader>nv adds [ ] to a plain list item or toggles an existing one
          vim.keymap.set("n", "<leader>nv", function()
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
    src = "lukas-reineke/headlines.nvim",
    setup = function()
      -- Doom-one-tinted heading backgrounds + code-block highlight. headlines'
      -- default config references these group names; link them so they actually
      -- render instead of falling back to nothing.
      vim.api.nvim_set_hl(0, "Headline", { link = "ColorColumn" })
      vim.api.nvim_set_hl(0, "CodeBlock", { link = "CursorLine" })
      vim.api.nvim_set_hl(0, "Dash", { link = "Comment" })
      require("headlines").setup()
    end,
  },
}
