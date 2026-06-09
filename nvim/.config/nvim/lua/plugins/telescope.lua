-- Primary fuzzy finder. Speed comes from telescope-fzf-native (compiled C
-- sorter via `make` — wired as a vim.pack build hook below). Keys mirror the
-- former mini.pick layout so muscle memory carries over: <leader><space> files
-- / <leader>/ grep / <leader>o buffers.
return {
  src = "nvim-telescope/telescope.nvim",
  deps = {
    "nvim-lua/plenary.nvim",
    {
      src = "nvim-telescope/telescope-fzf-native.nvim",
      build = function(d)
        vim.system({ "make" }, { cwd = d.path }):wait()
      end,
    },
    "nvim-telescope/telescope-ui-select.nvim",
  },
  setup = function()
    local telescope = require("telescope")
    local actions = require("telescope.actions")
    local builtin = require("telescope.builtin")

    -- Shared blacklist: dirs that are always junk and must be excluded from
    -- every search surface (rg globs, fd --exclude, and the Lua post-filter).
    -- Keep this list in one place so the three consumers below never diverge.
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

    -- Build rg glob exclusion flags: each dir becomes "--glob=!**/<dir>/**"
    -- Added alongside --no-ignore-vcs so that gitignored dotfiles (.env,
    -- .env.local, .docker.local, etc.) are visible, while junk dirs are still
    -- skipped via explicit globs rather than .gitignore delegation.
    local rg_args = {
      "rg",
      "--color=never",
      "--no-heading",
      "--with-filename",
      "--line-number",
      "--column",
      "--smart-case",
      "--hidden",
      "--no-ignore-vcs", -- surface gitignored files like .env, .env.local
    }
    for _, dir in ipairs(excluded_dirs) do
      table.insert(rg_args, "--glob=!" .. "**/" .. dir .. "/**")
    end

    -- Build fd exclusion flags: each dir becomes a "--exclude <dir>" pair.
    -- --no-ignore-vcs mirrors the rg flag above for the same reason: fd
    -- respects .gitignore by default, which would hide .env-style files.
    local fd_args = { "fd", "--type", "f", "--color=never", "--hidden", "--no-ignore-vcs" }
    for _, dir in ipairs(excluded_dirs) do
      table.insert(fd_args, "--exclude")
      table.insert(fd_args, dir)
    end

    -- Build Lua post-filter patterns for pickers that don't use rg/fd
    -- (buffers, oldfiles, etc.).  Lua patterns need "." escaped to "%.",
    -- and we match on the trailing "/" so only directories are filtered.
    local file_ignore_patterns = {}
    for _, dir in ipairs(excluded_dirs) do
      -- Escape Lua magic chars (only "." is common in these dir names)
      local escaped = dir:gsub("%.", "%%.")
      table.insert(file_ignore_patterns, escaped .. "/")
    end

    telescope.setup({
      defaults = {
        -- fzf algorithm for matching; fast even on large repos.
        path_display = { "truncate" },
        -- Prompt on top with results reading downward (snacks/fzf-lua style).
        -- sorting_strategy must be "ascending" or the best match lands at the
        -- bottom, away from the top prompt.
        sorting_strategy = "ascending",
        layout_config = {
          prompt_position = "top",
        },
        mappings = {
          -- <C-j>/<C-k> for next/prev selection (mini.pick muscle memory).
          -- Telescope's default <C-n>/<C-p> and arrow keys still work too.
          i = {
            ["<C-j>"] = actions.move_selection_next,
            ["<C-k>"] = actions.move_selection_previous,
          },
          -- `q` closes the picker (press <Esc> first to leave the prompt's
          -- insert mode, then `q`). <C-c> still closes from insert mode.
          n = {
            ["q"] = actions.close,
            ["<C-j>"] = actions.move_selection_next,
            ["<C-k>"] = actions.move_selection_previous,
          },
        },
        file_ignore_patterns = file_ignore_patterns,
        vimgrep_arguments = rg_args,
      },
      pickers = {
        find_files = {
          -- fd is faster than the default; --no-ignore-vcs ensures gitignored
          -- dotfiles (.env, .env.local) are included alongside hidden files.
          find_command = fd_args,
        },
      },
      extensions = {
        fzf = {
          fuzzy = true,
          override_generic_sorter = true,
          override_file_sorter = true,
          case_mode = "smart_case",
        },
        ["ui-select"] = {
          require("telescope.themes").get_dropdown({}),
        },
      },
    })

    telescope.load_extension("fzf")
    telescope.load_extension("ui-select")

    local map = function(lhs, fn, desc)
      vim.keymap.set("n", lhs, fn, { desc = desc })
    end

    map("<leader><space>", function()
      builtin.find_files({ cwd = vim.uv.cwd(), hidden = true })
    end, "Find files")
    map("<leader>/", function()
      builtin.live_grep({ cwd = vim.uv.cwd() })
    end, "Live grep")
    map("<leader>o", function()
      builtin.buffers()
    end, "Buffers")
    map("<leader>.", function()
      builtin.resume()
    end, "Resume last picker")
    map("<leader>sw", function()
      builtin.grep_string()
    end, "Grep word under cursor")
    map("<leader>ss", function()
      builtin.lsp_document_symbols()
    end, "Symbols (document)")
    map("<leader>sS", function()
      builtin.lsp_dynamic_workspace_symbols()
    end, "Symbols (workspace)")
    map("<leader>sk", function()
      builtin.keymaps()
    end, "Keymaps")
    map("<leader>sb", function()
      builtin.current_buffer_fuzzy_find()
    end, "Search in buffer")
    map("<leader>sh", function()
      builtin.help_tags()
    end, "Help tags")
    map("<leader>fr", function()
      builtin.oldfiles()
    end, "Recent files")
  end,
}
