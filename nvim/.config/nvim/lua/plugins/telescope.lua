-- Primary fuzzy finder. Speed comes from telescope-fzf-native (compiled C
-- sorter via `make`). Keys mirror the former mini.pick layout so muscle
-- memory carries over: <leader><space> files / <leader>/ grep / <leader>, buffers.
return {
  "nvim-telescope/telescope.nvim",
  dependencies = {
    "nvim-lua/plenary.nvim",
    { "nvim-telescope/telescope-fzf-native.nvim", build = "make" },
  },
  keys = {
    {
      "<leader><space>",
      function()
        require("telescope.builtin").find_files({
          cwd = require("util.root").get(),
          hidden = true,
        })
      end,
      desc = "Find files",
    },
    {
      "<leader>/",
      function()
        require("telescope.builtin").live_grep({
          cwd = require("util.root").get(),
        })
      end,
      desc = "Live grep",
    },
    {
      "<leader>,",
      function()
        require("telescope.builtin").buffers()
      end,
      desc = "Buffers",
    },
    {
      "<leader>.",
      function()
        require("telescope.builtin").resume()
      end,
      desc = "Resume last picker",
    },
  },
  config = function()
    local telescope = require("telescope")
    local actions = require("telescope.actions")
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
        file_ignore_patterns = {
          "%.git/",
          "node_modules/",
          "%.venv/",
          "__pycache__/",
          "dist/",
          "build/",
        },
        vimgrep_arguments = {
          "rg",
          "--color=never",
          "--no-heading",
          "--with-filename",
          "--line-number",
          "--column",
          "--smart-case",
          "--hidden",
        },
      },
      pickers = {
        find_files = {
          -- fd is faster than the default and respects .gitignore.
          find_command = { "fd", "--type", "f", "--color=never", "--hidden", "--exclude", ".git" },
        },
      },
      extensions = {
        fzf = {
          fuzzy = true,
          override_generic_sorter = true,
          override_file_sorter = true,
          case_mode = "smart_case",
        },
      },
    })

    telescope.load_extension("fzf")
  end,
}
