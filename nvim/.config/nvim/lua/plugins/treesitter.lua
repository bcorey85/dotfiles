return {
  {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    branch = "main",
    lazy = false,
    dependencies = {
      { "nvim-treesitter/nvim-treesitter-textobjects", branch = "main" },
    },
    config = function()
      require("nvim-treesitter").install({
        "bash",
        "c",
        "css",
        "diff",
        "html",
        "javascript",
        "jsdoc",
        "json",
        "lua",
        "luadoc",
        "markdown",
        "markdown_inline",
        "python",
        "query",
        "regex",
        "scss",
        "toml",
        "tsx",
        "typescript",
        "vim",
        "vimdoc",
        "vue",
        "xml",
        "yaml",
      })

      vim.api.nvim_create_autocmd("FileType", {
        pattern = {
          "bash",
          "c",
          "css",
          "diff",
          "help",
          "html",
          "javascript",
          "jsdoc",
          "json",
          "jsonc",
          "lua",
          "luadoc",
          "markdown",
          "python",
          "query",
          "regex",
          "scss",
          "toml",
          "tsx",
          "typescript",
          "vim",
          "vue",
          "xml",
          "yaml",
        },
        callback = function(args)
          pcall(vim.treesitter.start, args.buf)
          vim.bo[args.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
        end,
      })

      -- select module is no longer used directly (mini.ai owns a/i).
      -- move module is still used for ]f/[f/]C/[C below.
      require("nvim-treesitter-textobjects").setup({
        move = { set_jumps = true },
      })

      -- SELECT textobjects (af/if/ac/ic/aa/ia) are now handled by mini.ai via
      -- gen_spec.treesitter — see lua/plugins/mini-ai.lua. Registering them here
      -- too would reintroduce the a/i timeout-ambiguity mini.ai solves.
      local move = require("nvim-treesitter-textobjects.move")

      vim.keymap.set("n", "]f", function()
        move.goto_next_start("@function.outer", "textobjects")
      end)
      vim.keymap.set("n", "[f", function()
        move.goto_previous_start("@function.outer", "textobjects")
      end)
      vim.keymap.set("n", "]C", function()
        move.goto_next_start("@class.outer", "textobjects")
      end)
      vim.keymap.set("n", "[C", function()
        move.goto_previous_start("@class.outer", "textobjects")
      end)
    end,
  },
}
