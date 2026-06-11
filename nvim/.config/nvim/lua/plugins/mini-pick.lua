-- Fuzzy finder via mini.pick + mini.extra + mini.visits.
-- Replaces telescope.nvim (+ fzf-native / ui-select).
-- Keymaps mirror the former telescope layout so muscle memory carries over.
--
-- Mark items with <C-x>; <M-CR> (choose_marked) sends them to quickfix when
-- the items are files or buffers (MiniPick.default_choose_marked behaviour).
return {
  -- ── mini.pick ──────────────────────────────────────────────────────────────
  {
    src = "echasnovski/mini.pick",
    setup = function()
      local pick = require("mini.pick")

      -- Shared blacklist: dirs that are always junk and must be excluded from
      -- every search surface. Keep this list in one place so all consumers
      -- below never diverge.
      local excluded_dirs = {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
        "target",
        "coverage",
        ".cache",
      }

      -- Build rg exclusion flags: each dir becomes "--glob=!**/<dir>/**".
      -- --no-ignore-vcs surfaces gitignored dotfiles (.env, .env.local, etc.)
      -- while junk dirs are still excluded via explicit globs rather than
      -- delegating to .gitignore.
      local rg_base = {
        "rg",
        "--color=never",
        "--no-heading",
        "--line-number",
        "--column",
        "--smart-case",
        "--hidden",
        "--no-ignore-vcs",
      }
      for _, dir in ipairs(excluded_dirs) do
        table.insert(rg_base, "--glob=!" .. "**/" .. dir .. "/**")
      end

      -- Build fd flags for file finding: --no-ignore-vcs mirrors rg above —
      -- fd also respects .gitignore by default, which would hide .env-style
      -- files without this flag.
      local fd_cmd = { "fd", "--type", "f", "--color=never", "--hidden", "--no-ignore-vcs" }
      for _, dir in ipairs(excluded_dirs) do
        table.insert(fd_cmd, "--exclude")
        table.insert(fd_cmd, dir)
      end

      -- Live grep modeled on MiniPick.builtin.grep_live (pick.lua ~line 1416).
      -- We replicate the match-respawn pattern using only public API so that
      -- rg_base (--hidden, --no-ignore-vcs, exclusion globs) is always applied.
      -- Deviation from upstream: H.querytick is private; we call
      -- MiniPick.get_querytick() in its place — semantically identical because
      -- get_querytick just returns H.querytick.
      local live_grep = function()
        -- Matches upstream grep_live item format: file\x00line\x00col\x00text.
        -- --field-match-separator '\x00' is what makes default_show parse items
        -- correctly (H.item_to_string splits on \x00 → '│' for display).
        local function build_command(query)
          local cmd = vim.list_extend({}, rg_base)
          vim.list_extend(cmd, { "--field-match-separator", "\\x00", "--no-fixed-strings", "--", query })
          return cmd
        end

        local cwd = vim.fn.getcwd()
        local set_items_opts = { do_match = false, querytick = MiniPick.get_querytick() }
        local spawn_opts = { cwd = cwd }
        local sys = { kill = function() end }

        local match = function(_, _, query)
          sys:kill()
          if MiniPick.get_querytick() == set_items_opts.querytick then
            return
          end
          if #query == 0 then
            sys = { kill = function() end }
            return MiniPick.set_picker_items({}, set_items_opts)
          end
          set_items_opts.querytick = MiniPick.get_querytick()
          local command = build_command(table.concat(query))
          sys =
            MiniPick.set_picker_items_from_cli(command, { set_items_opts = set_items_opts, spawn_opts = spawn_opts })
        end

        local show_icons = function(buf_id, items, query)
          MiniPick.default_show(buf_id, items, query, { show_icons = true })
        end

        return MiniPick.start({
          source = {
            name = "Grep live (rg)",
            items = {},
            match = match,
            show = show_icons,
          },
        })
      end

      pick.setup({
        mappings = {
          -- <C-j>/<C-k>: next/prev item — muscle memory from telescope config.
          -- mini.pick's defaults are <C-n>/<C-p>; we remap to j/k variants.
          move_down = "<C-j>",
          move_up = "<C-k>",
          -- <C-d>/<C-u>: scroll — scrolls the preview when it's open (<Tab>),
          -- otherwise pages the match list. <C-u> is delete_left's default, so
          -- that action moves to <M-u> to avoid the collision.
          scroll_down = "<C-d>",
          scroll_up = "<C-u>",
          delete_left = "<M-u>",
        },
      })

      -- :grep / :copen quickfix searches get the same visibility as the pickers
      -- (hidden files, gitignored dotfiles). Exclusion globs live here — single
      -- source of truth alongside rg_base — not in options.lua.
      local grepprg_globs = {}
      for _, dir in ipairs(excluded_dirs) do
        table.insert(grepprg_globs, "--glob=!" .. "**/" .. dir .. "/**")
      end
      vim.o.grepprg = "rg --vimgrep --smart-case --hidden --no-ignore-vcs " .. table.concat(grepprg_globs, " ")
      vim.o.grepformat = "%f:%l:%c:%m"

      -- vim.ui.select → MiniPick.ui_select so all code-action / rename / etc.
      -- prompts render in the mini.pick floating window.
      vim.ui.select = pick.ui_select

      local map = function(lhs, fn, desc)
        vim.keymap.set("n", lhs, fn, { desc = desc })
      end

      local show_icons = function(buf_id, items, query)
        MiniPick.default_show(buf_id, items, query, { show_icons = true })
      end

      -- <leader><space>: file finder via fd with full exclusion list.
      -- builtin.files only accepts a tool *name*; use builtin.cli for custom
      -- flags (--no-ignore-vcs, per-dir --exclude). source.show wires devicons
      -- (builtin.files does this internally; builtin.cli does not).
      map("<leader><space>", function()
        pick.builtin.cli({
          command = fd_cmd,
        }, { source = { name = "Files", show = show_icons } })
      end, "Find files")

      -- <leader>/: live grep via rg with full rg_base flags (hidden files,
      -- gitignored dotfiles, exclusion globs). Respawns rg on every keystroke
      -- via the match-respawn pattern lifted from builtin.grep_live.
      map("<leader>/", live_grep, "Live grep")

      map("<leader>o", function()
        pick.builtin.buffers()
      end, "Buffers")

      map("<leader>.", function()
        pick.builtin.resume()
      end, "Resume last picker")

      -- <leader>sw: one-shot grep for word under cursor via builtin.cli so
      -- rg_base flags (--hidden, --no-ignore-vcs, exclusion globs) apply.
      -- builtin.grep routes through H.grep_get_command which never sets those.
      map("<leader>sw", function()
        local cword = vim.fn.expand("<cword>")
        local cmd = vim.list_extend({}, rg_base)
        vim.list_extend(cmd, { "--field-match-separator", "\\x00", "--no-fixed-strings", "--", cword })
        pick.builtin.cli({
          command = cmd,
        }, {
          source = {
            name = "Grep word: " .. cword,
            show = show_icons,
          },
        })
      end, "Grep word under cursor")

      map("<leader>ss", function()
        require("mini.extra").pickers.lsp({ scope = "document_symbol" })
      end, "Symbols (document)")

      map("<leader>sS", function()
        require("mini.extra").pickers.lsp({ scope = "workspace_symbol" })
      end, "Symbols (workspace)")

      map("<leader>sk", function()
        require("mini.extra").pickers.keymaps()
      end, "Keymaps")

      map("<leader>sb", function()
        require("mini.extra").pickers.buf_lines({ scope = "current" })
      end, "Search in buffer")

      map("<leader>sh", function()
        pick.builtin.help()
      end, "Help tags")

      map("<leader>fr", function()
        require("mini.extra").pickers.oldfiles()
      end, "Recent files")
    end,
  },

  -- ── mini.extra ─────────────────────────────────────────────────────────────
  {
    src = "echasnovski/mini.extra",
    setup = function()
      require("mini.extra").setup({})
    end,
  },

  -- ── mini.visits ────────────────────────────────────────────────────────────
  -- Frecency = frequency + recency. Registers file visits automatically via
  -- BufEnter (1 s debounce); persists to disk on exit. Trial — cut this spec
  -- and the <leader>fv keymap if unused after a few weeks.
  {
    src = "echasnovski/mini.visits",
    setup = function()
      require("mini.visits").setup({})

      -- <leader>fv: frecency-sorted file picker (most-visited + most-recent).
      -- MiniExtra.pickers.visit_paths defaults to recency_weight=0.5 (balanced
      -- frecency) with no extra configuration needed.
      vim.keymap.set("n", "<leader>fv", function()
        require("mini.extra").pickers.visit_paths()
      end, { desc = "Frecent files" })
    end,
  },
}
