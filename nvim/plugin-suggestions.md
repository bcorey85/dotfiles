# Neovim Plugin Suggestions — Manifest

A running ledger of plugins evaluated for this config. The goal is to **stop
re-litigating the same recommendations**. If something is in the "Declined"
table, it has already been considered and rejected — don't pitch it again unless
the reasoning here has materially changed.

## Guiding principles (the filter every candidate must pass)

1. **tpope-style** — extends a key or command you already know (`.`, `%`, `:Cmd`),
   `.`-repeatable, native-feeling. No new modal UI.
2. **oil.nvim-style (buffer-native)** — you operate on things through a normal
   editable buffer using the motions you already have. No special keymaps to learn.
3. **No new keybinds to memorize.** Reuse or extend existing ones.
4. **No visual sugar, no auto-magic, no paradigms that need a week to evaluate.**
5. Must not conflict with the hand-rolled `[`/`]` bracket scheme or the mini.ai
   `a`/`i` namespace.

Legend: ✅ installed · 🤔 offered, undecided · ❌ declined · ⛔ **do not re-suggest**

---

## ⛔ DO NOT SUGGEST AGAIN

| Plugin               | Repo                                               | Why it keeps coming up                                                                               | Why it's a hard no                                                           |
| -------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **vim-dadbod / -ui** | `tpope/vim-dadbod`, `kristijanhusak/vim-dadbod-ui` | It's the textbook tpope + buffer-native fit, so it surfaces every time those principles are applied. | **Recommended ~30 times. The answer is no. Stop.** Not part of the workflow. |

---

## ✅ Installed this session

| Plugin                      | Repo                                     | What it does                                                                    | Notes                                                    |
| --------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------- |
| aerial.nvim                 | `stevearc/aerial.nvim`                   | Code outline / symbol sidebar (left). `{x`/`}x` symbol hop.                     | `lazy_load=false` so hops work before opening the panel. |
| tiny-inline-diagnostic.nvim | `rachartier/tiny-inline-diagnostic.nvim` | Cursor-line inline diagnostics (native `virtual_text` off in `config/lsp.lua`). | **Loved it.**                                            |
| vim-matchup                 | `andymass/vim-matchup`                   | `%` matches keyword/tag pairs (`<div></div>`, `function`/`end`).                | Native engine; TS module path skipped (gone on `main`).  |
| vim-abolish                 | `tpope/vim-abolish`                      | Case coercion (`crs`/`crc`/`cru`/`cr-`) + case-preserving `:S`.                 | **"Bad ass."** The taste-defining win.                   |
| vim-repeat                  | `tpope/vim-repeat`                       | Makes `.` repeat plugin maps (e.g. abolish coercions).                          | Amplifies abolish. Changes no default.                   |

---

## 🤔 Offered, undecided

| Plugin         | Repo                      | What it does                                                                                    | Principle hit                                                                                   | Verdict                                                                                                                                   |
| -------------- | ------------------------- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| vim-easy-align | `junegunn/vim-easy-align` | `ga` operator: align blocks on a delimiter (`gaip=`).                                           | tpope-style operator, no default touched (`ga` was unused).                                     | **Top remaining pick.** Discrete bulk-text op like abolish.                                                                               |
| vim-eunuch     | `tpope/vim-eunuch`        | `:Rename` `:Move` `:Chmod +x` `:SudoWrite` `:Mkdir` `:Wall`.                                    | Pure tpope command-extension.                                                                   | Grab if `:Chmod +x` / `:SudoWrite` resonate; oil covers rename/move/delete.                                                               |
| vim-tbone      | `tpope/vim-tbone`         | `:Twrite {pane}` send buffer/selection to a tmux pane; `:Tyank`/`:Tput`.                        | tpope, command-only, fits tmux-heavy setup.                                                     | Niche but dead-on for REPL-in-a-pane.                                                                                                     |
| vim-exchange   | `tommcdo/vim-exchange`    | `cx{motion}` to mark, `cx` again to swap the two regions; `cxx` line, `X` visual, `cxc` cancel. | `.`-repeatable operator on unused `cx`/`X`; abolish/easy-align "discrete bulk-text op" lineage. | **Maybe — feels like a stretch.** Swaps non-adjacent text (args, list items) without the yank/paste dance, but unsure it earns its place. |

---

## ❌ Declined (considered, rejected — reasons recorded)

| Plugin                  | Repo                                                                 | Reason rejected                                                                                                                                                                                                            |
| ----------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| dial.nvim               | `monaqa/dial.nvim`                                                   | "Bloat." Enhanced `C-a`/`C-x` for bools/dates/etc. — not wanted.                                                                                                                                                           |
| nvim-spider             | `chrisgrieser/nvim-spider`                                           | Overrides `w`/`e`/`b` — strays too far from defaults.                                                                                                                                                                      |
| vim-unimpaired          | `tpope/vim-unimpaired`                                               | Collides with hand-rolled `]f`/`]a`/`]q` bracket scheme; toggles duplicate `<leader>u*`.                                                                                                                                   |
| targets.vim             | `wellle/targets.vim`                                                 | Fights mini.ai for `a`/`i`. mini.ai already does seeking/next-last/counts; only real delta (separator objects) is a 3-line mini.ai custom textobject instead.                                                              |
| nvim-ts-autotag         | `windwp/nvim-ts-autotag`                                             | mini.pairs already handles HTML tag close.                                                                                                                                                                                 |
| rainbow-delimiters.nvim | `HiPhish/rainbow-delimiters.nvim`                                    | Visual sugar.                                                                                                                                                                                                              |
| color previewer         | `brenoprata10/nvim-highlight-colors` / `catgoose/nvim-colorizer.lua` | Visual sugar.                                                                                                                                                                                                              |
| inc-rename.nvim         | `smjonas/inc-rename.nvim`                                            | Passed (live rename preview — not pursued).                                                                                                                                                                                |
| todo-comments.nvim      | `folke/todo-comments.nvim`                                           | Not useful to the workflow.                                                                                                                                                                                                |
| nvim-ufo                | `kevinhwang91/nvim-ufo`                                              | Doesn't use folds; aerial covers the "outline a big file" case.                                                                                                                                                            |
| diffview.nvim           | `sindrets/diffview.nvim`                                             | **Tried before and removed** — kept only the review-comment piece (`config/review.lua`).                                                                                                                                   |
| neotest                 | `nvim-neotest/neotest`                                               | Tests run in tmux.                                                                                                                                                                                                         |
| persistence.nvim        | `folke/persistence.nvim`                                             | tmux-sessionizer covers project restore.                                                                                                                                                                                   |
| yanky.nvim              | `gbprod/yanky.nvim`                                                  | Yank-ring paradigm — not wanted.                                                                                                                                                                                           |
| refactoring.nvim        | `ThePrimeagen/refactoring.nvim`                                      | Paradigm to explore — not wanted.                                                                                                                                                                                          |
| trouble.nvim            | `folke/trouble.nvim`                                                 | snacks picker + quicker already cover diagnostics/refs/qf.                                                                                                                                                                 |
| nvim-bqf                | `kevinhwang91/nvim-bqf`                                              | quicker (editable qf) + snacks preview cover it.                                                                                                                                                                           |
| glance.nvim             | `dnlhc/glance.nvim`                                                  | snacks LSP references cover it.                                                                                                                                                                                            |
| outline.nvim            | `hedyhli/outline.nvim`                                               | aerial chosen instead.                                                                                                                                                                                                     |
| nvim-navbuddy / namu    | `SmiteshP/nvim-navbuddy`, `bassamsdata/namu.nvim`                    | Overlap aerial / snacks symbol picker.                                                                                                                                                                                     |
| overseer.nvim           | `stevearc/overseer.nvim`                                             | Task running lives in tmux.                                                                                                                                                                                                |
| lsp_lines / endhints    | —                                                                    | tiny-inline-diagnostic chosen instead.                                                                                                                                                                                     |
| octo.nvim               | `pwntester/octo.nvim`                                                | Mentioned early; not pursued.                                                                                                                                                                                              |
| ssr.nvim                | `cshuaimin/ssr.nvim`                                                 | Mentioned early; not pursued.                                                                                                                                                                                              |
| **mini.\* batch**       | `echasnovski/mini.nvim`                                              | `mini.move`, `mini.operators`, `mini.splitjoin`, `mini.align`, `mini.bracketed`, `mini.hipatterns` — declined as paradigm shifts needing a week to evaluate. (Already run: mini.ai/surround/pairs/indentscope/clue/icons.) |
| vim-fetch               | `kopischke/vim-fetch`                                                | Super edge case. `gf`/CLI honoring `file:line:col`; snacks picker + LSP already land on exact lines for searched results, leaving only pasted-path / `nvim file:line` cases.                                               |
| vim-apathy              | `tpope/vim-apathy`                                                   | Super edge case. Per-filetype `path`/`include` so `gf` resolves imports + `[I` search; LSP `gd` already opens imports, shrinking payoff to non-LSP filetypes.                                                              |

---

## Config tweaks (not plugins) — alternatives noted, skipped

| Tweak                                        | Where                                           | Status                                                 |
| -------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------ |
| treesitter-textobjects `swap` (reorder args) | `plugins/treesitter.lua` (plugin already owned) | Skipped.                                               |
| mini.ai separator textobject (`ci,` / `da,`) | `plugins/mini-ai.lua` `custom_textobjects`      | Offered as the targets.vim alternative; not yet added. |
| `inccommand = "nosplit"` (live `:s` preview) | `config/options.lua:44`                         | **Already set** — no action.                           |
