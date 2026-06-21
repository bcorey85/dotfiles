-- vim-matchup — supercharges the `%` motion. Native `%` only jumps between
-- bracket pairs; matchup extends it to KEYWORD and TAG pairs via its built-in
-- matchit-style engine: HTML/JSX `<div>`↔`</div>`, Lua `function`/`if`/`do`↔`end`,
-- `if`/`then`/`elseif`/`else`/`end`, etc. Replaces Neovim's native matchparen.
--
-- The motions it adds (all work as text-object targets with d/c/y too):
--   %    jump to the matching open/close word
--   g%   jump BACKWARD to the matching word
--   [%   jump to the PREVIOUS unmatched open word (out of the enclosing block)
--   ]%   jump to the NEXT unmatched close word
--   z%   jump INTO the next pair (e.g. into a tag/block from outside)
--
-- NOTE: matchup's optional treesitter integration goes through the OLD
-- nvim-treesitter module system (require'nvim-treesitter.configs'), which the
-- `main` branch this config uses has removed. The native engine handles tags and
-- keyword pairs without it, so we deliberately don't wire that path. Placed after
-- treesitter in plugin_order purely for tidy ordering.
return {
  src = "andymass/vim-matchup",
  setup = function()
    -- When the matching word is scrolled off-screen, show it in a small popup
    -- (the everyday "where's the opening tag for this </div>" answer) instead of
    -- the default statusline echo.
    vim.g.matchup_matchparen_offscreen = { method = "popup" }
    -- Defer the match highlight so it doesn't recompute on every cursor tick —
    -- recommended for large files.
    vim.g.matchup_matchparen_deferred = 1
  end,
}
