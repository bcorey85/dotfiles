-- version ^1.0.0 tracks the latest 1.x release tag, whose assets include the
-- prebuilt rust fuzzy matcher — so `implementation = "rust"` works without a
-- local cargo build (no build hook needed).
return {
  src = "saghen/blink.cmp",
  version = vim.version.range("^1.0.0"),
  deps = { "rafamadriz/friendly-snippets" },
  setup = function()
    require("blink.cmp").setup({
      keymap = { preset = "super-tab" },
      appearance = {
        nerd_font_variant = "mono",
      },
      completion = {
        documentation = {
          auto_show = true,
          auto_show_delay_ms = 200,
        },
        ghost_text = { enabled = false },
        list = {
          selection = {
            preselect = true,
            auto_insert = false,
          },
        },
      },
      sources = {
        default = { "lazydev", "lsp", "path", "snippets", "buffer" },
        providers = {
          lazydev = {
            name = "LazyDev",
            module = "lazydev.integrations.blink",
            score_offset = 100, -- show lazydev suggestions above LSP
          },
        },
      },
      signature = {
        enabled = true,
      },
      fuzzy = {
        implementation = "rust",
      },
    })
  end,
}
