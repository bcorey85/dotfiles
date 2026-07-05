return {
  "nvim-treesitter/nvim-treesitter",
  branch = "main",
  build = ":TSUpdate",
  event = { "BufReadPost", "BufNewFile" },
  cmd = { "TSInstall", "TSUpdate", "TSUpdateSync", "TSInstallSync" },
  dependencies = {
    { "nvim-treesitter/nvim-treesitter-textobjects", branch = "main" },
  },
  config = function()
    local langs = {
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
    }
    require("nvim-treesitter").install(langs)

    -- Derive the FileType pattern from the install list so the two can never
    -- drift. vim.treesitter.language.get_filetypes() maps parser → real ft names
    -- (e.g. tsx → typescriptreact, bash → sh, vimdoc → help).
    local fts = {}
    for _, lang in ipairs(langs) do
      vim.list_extend(fts, vim.treesitter.language.get_filetypes(lang))
    end

    vim.api.nvim_create_autocmd("FileType", {
      pattern = fts,
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
    end, { desc = "Next function" })
    vim.keymap.set("n", "[f", function()
      move.goto_previous_start("@function.outer", "textobjects")
    end, { desc = "Previous function" })
    vim.keymap.set("n", "]C", function()
      move.goto_next_start("@class.outer", "textobjects")
    end, { desc = "Next class" })
    vim.keymap.set("n", "[C", function()
      move.goto_previous_start("@class.outer", "textobjects")
    end, { desc = "Previous class" })
    vim.keymap.set("n", "]a", function()
      move.goto_next_start("@parameter.inner", "textobjects")
    end, { desc = "Next argument" })
    vim.keymap.set("n", "[a", function()
      move.goto_previous_start("@parameter.inner", "textobjects")
    end, { desc = "Previous argument" })
  end,
}
