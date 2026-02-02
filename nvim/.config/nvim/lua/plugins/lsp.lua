return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        vue_ls = {
          -- Increase timeout for Vue language server
          flags = {
            debounce_text_changes = 500,
          },
          init_options = {
            typescript = {
              tsdk = vim.fn.stdpath("data") .. "/mason/packages/typescript-language-server/node_modules/typescript/lib",
            },
          },
        },
        ts_ls = {
          -- TypeScript language server
          init_options = {
            plugins = {
              {
                name = "@vue/typescript-plugin",
                location = vim.fn.stdpath("data") .. "/mason/packages/vue-language-server/node_modules/@vue/language-server",
                languages = { "vue" },
              },
            },
          },
          filetypes = { "typescript", "javascript", "javascriptreact", "typescriptreact", "vue" },
        },
      },
    },
  },
}
