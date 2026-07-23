-- theme-sync — keep nvim in sync with the shared theme state written by the
-- `theme-mode` script (scripts/.local/bin/theme-mode):
--   ~/.cache/theme-mode    "dark" | "light"
--   ~/.cache/theme-family  family name (FAMILIES below)
-- Both files are fs_poll'ed (~1s), so `theme-mode use one` or a prefix T
-- toggle from tmux flips every running instance with no sockets to manage.
-- <leader>ut shells out to the same script, so a toggle from nvim flips tmux
-- and ghostty too — one source of truth, all ways.
--
-- This module also owns every theme-reactive highlight override (markview
-- headings, gitsigns word-diff, per-family fixups), re-applied on ColorScheme,
-- so a family switch always lands with the right set. Plugin specs stay pure
-- plugin declarations. Keep FAMILIES in sync with theme-mode's registry and
-- the ~/.config/tmux/<family>-<mode>.conf files.

local M = {}

local MODE_FILE = vim.env.HOME .. "/.cache/theme-mode"
local FAMILY_FILE = vim.env.HOME .. "/.cache/theme-family"
local DEFAULT_FAMILY = "doom-one"

-- alpha-blend two hex colours (a = share of c1).
local function blend(c1, c2, a)
  local out = {}
  for i = 2, 6, 2 do
    local v = tonumber(c1:sub(i, i + 1), 16) * a + tonumber(c2:sub(i, i + 1), 16) * (1 - a)
    out[#out + 1] = string.format("%02x", math.floor(v + 0.5))
  end
  return "#" .. table.concat(out)
end

-- Rebuild Diff{Add,Delete,Change,Text} as palette-blended background washes.
-- For themes that ship fg-only (or `reverse`) diffs, which starve codediff,
-- native diff mode, and the word-diff glue below. p = { bg, green, red, yellow }.
local function diff_washes(p)
  local hl = vim.api.nvim_set_hl
  hl(0, "DiffAdd", { bg = blend(p.green, p.bg, 0.22) })
  hl(0, "DiffDelete", { bg = blend(p.red, p.bg, 0.22) })
  hl(0, "DiffChange", { bg = blend(p.yellow, p.bg, 0.16) })
  hl(0, "DiffText", { bg = blend(p.yellow, p.bg, 0.38), bold = true })
end

local FAMILIES = {
  ["doom-one"] = {
    -- one scheme for both modes; it picks its palette from vim.o.background
    schemes = { dark = "doom-one", light = "doom-one" },
    accents = {
      dark = { heading1 = "#c678dd", heading = "#51afef" },
      light = { heading1 = "#a626a4", heading = "#4078f2" },
    },
    -- Fix two port defects (NTBBloodbath/doom-one.nvim; see plugins/doom-one.lua):
    -- comments are 2.3:1/2.7:1 unreadable (these are the emacs
    -- doom-one-brighter-comments values), and DiffAdd/Change/Delete are
    -- fg-only — no backgrounds — which starves codediff, native diff mode,
    -- and the word-diff glue below. Rebuild them as palette-blended washes.
    fixup = function(mode)
      local p = mode == "dark"
          and { bg = "#282c34", comment = "#5699af", green = "#98be65", red = "#ff6c6b", yellow = "#ecbe7b" }
        or { bg = "#fafafa", comment = "#3a888e", green = "#50a14f", red = "#e45649", yellow = "#986801" }
      local hl = vim.api.nvim_set_hl
      hl(0, "Comment", { fg = p.comment })
      hl(0, "CommentBold", { fg = p.comment, bold = true })
      hl(0, "DiffAdd", { bg = blend(p.green, p.bg, 0.22) })
      hl(0, "DiffDelete", { bg = blend(p.red, p.bg, 0.22) })
      hl(0, "DiffChange", { bg = blend(p.yellow, p.bg, 0.16) })
      hl(0, "DiffText", { bg = blend(p.yellow, p.bg, 0.38), bold = true })
    end,
  },
  ["gruvbox-material"] = {
    -- one scheme for both modes; it picks its palette from vim.o.background
    schemes = { dark = "gruvbox-material", light = "gruvbox-material" },
    accents = {
      dark = { heading1 = "#d3869b", heading = "#7daea3" },
      light = { heading1 = "#945e80", heading = "#45707a" },
    },
    -- Comment floor: stock #928374 measures 4.0:1 dark / 3.0:1 light. Raise
    -- to palette grey2 (dark) / a floor-clearing dark grey (light): 5.3/5.2:1.
    fixup = function(mode)
      local c = mode == "dark" and "#a89984" or "#665c54"
      vim.api.nvim_set_hl(0, "Comment", { fg = c, italic = true })
    end,
  },
  duskbox = {
    -- ih-hugh/duskbox: an OKLCH-generated equiluminant family. dusk (indigo
    -- night #232336) dark / dawn (warm paper #faf2e8) light. Each variant's
    -- colors/duskbox-<v>.lua sets colors_name "duskbox-<v>", matching
    -- schemes[mode], so no colors_name override is needed. Raw theme — no
    -- fixup: it already ships full treesitter @-captures, Diagnostic* (incl.
    -- virtual-text/underline), @lsp.type semantic tokens, and proper bg-only
    -- diff washes, and its comments clear the floor (body #828ca2 ~4.6:1 dusk /
    -- #6a758a ~4.9:1 dawn). Accents mirror duskbox's own blue heading ramp.
    schemes = { dark = "duskbox-dusk", light = "duskbox-dawn" },
    accents = {
      dark = { heading1 = "#86bafe", heading = "#59c5f5" },
      light = { heading1 = "#2e69b2", heading = "#067398" },
    },
  },
  kanagawa = {
    -- rebelot/kanagawa.nvim: wave (the original — indigo night, saturated) dark,
    -- lotus (yellow paper) light. All variants register colors_name "kanagawa".
    schemes = { dark = "kanagawa-wave", light = "kanagawa-lotus" },
    colors_name = "kanagawa",
    accents = {
      dark = { heading1 = "#957fb8", heading = "#7fb4ca" }, -- oniViolet + springBlue
      light = { heading1 = "#624c83", heading = "#4d699b" },
    },
    -- Wave: comment fujiGray #727169 is 3.33:1 (floor 4.5) — lift toward
    -- fujiWhite, keeping the grey cast. Lotus: body ink #545464 is only 6.2:1
    -- on the yellow paper and comment #8a8980 is 2.9:1 — deepen both (8.1/5.1).
    -- Diff* stay stock: kanagawa ships proper bg-only washes in both modes.
    fixup = function(mode)
      if mode == "dark" then
        vim.api.nvim_set_hl(0, "Comment", { fg = blend("#dcd7ba", "#727169", 0.3), italic = true })
      else
        vim.api.nvim_set_hl(0, "Normal", { fg = "#434350", bg = "#f2ecbc" })
        vim.api.nvim_set_hl(0, "Comment", { fg = "#63625b", italic = true })
      end
    end,
  },
  ["kanagawa-paper"] = {
    -- thesimonho/kanagawa-paper.nvim: ink (dusty indigo-night dark) + canvas
    -- (warm paper light) — a softer, muted cousin of the kanagawa family. Each
    -- variant ships a colors/*.vim shim registering colors_name
    -- "kanagawa-paper-<theme>", matching schemes[mode].
    schemes = { dark = "kanagawa-paper-ink", light = "kanagawa-paper-canvas" },
    accents = {
      dark = { heading1 = "#957fb8", heading = "#7fb4ca" }, -- oniViolet + springBlue
      light = { heading1 = "#624c83", heading = "#3f5f83" },
    },
    -- Ink: comment fujiGray #727169 is 3.33:1 on #1F1F28 — lift toward fujiWhite
    -- keeping the grey cast (5.08:1). Canvas is the hard one: body #73787d is
    -- only 3.40:1 on the #e1e1de paper and comment canvasGray1 #aeaea6 a washed
    -- 1.70:1 — deepen body to #4a4e53 (6.40) and comment to #5a5a52 (5.31).
    -- Diff*: the theme ships real bg washes, but wires DiffText's bg to
    -- change_light (== DiffChange's yellow), so word-diff reads flat. Repoint
    -- DiffText to the theme's own intended blue/teal `text` wash so the changed
    -- word leads its changed line (also feeds set_word_diff's inline groups).
    fixup = function(mode)
      local hl = vim.api.nvim_set_hl
      if mode == "dark" then
        hl(0, "Comment", { fg = blend("#dcd7ba", "#727169", 0.3), italic = true })
        hl(0, "DiffText", { bg = blend("#658594", "#1f1f28", 0.38), bold = true })
      else
        hl(0, "Normal", { fg = "#4a4e53", bg = "#e1e1de" })
        hl(0, "Comment", { fg = "#5a5a52", italic = true })
        hl(0, "DiffText", { bg = blend("#7e8faf", "#e1e1de", 0.38), bold = true })
      end
    end,
  },
  solarized = {
    -- maxmx03/solarized.nvim, palette = "solarized" (Schoonover's original).
    -- Both palettes of this plugin register colors_name = "solarized" and load
    -- via the same :colorscheme, so `pre` selects which one gets built.
    schemes = { dark = "solarized", light = "solarized" },
    colors_name = "solarized",
    pre = function()
      require("solarized").setup({ palette = "solarized" }) -- variant stays "winter" (the canonical accents)
    end,
    accents = {
      dark = { heading1 = "#6c71c4", heading = "#268bd2" }, -- violet + blue
      light = { heading1 = "#6c71c4", heading = "#268bd2" },
    },
    -- Solarized is the hard case for the comment floor: its body fg is itself
    -- only 4.75:1 dark / 4.13:1 light, so a comment that clears 4.5:1 lands ON
    -- TOP of stock body. Fix by shifting one step up the theme's OWN base
    -- ladder (no new colours): body base0→base1 (5.6:1) and comment
    -- base01→base0 (4.8:1) dark. Light needs more room, so body deepens past
    -- base01 to 9.9:1 (the kanagawa-lotus precedent) and comment takes base01
    -- (5.0:1) — separation 4.9 vs 0.4 if body stayed put. Comments keep italic
    -- to carry the distinction the 0.86 dark separation can't alone.
    -- Diff* ship fg-only (DiffDelete/DiffText are `reverse`) — rebuild washes.
    fixup = function(mode)
      local hl = vim.api.nvim_set_hl
      local p = mode == "dark"
          and { bg = "#002b36", fg = "#93a1a1", comment = "#839496" }
        or { bg = "#fdf6e3", fg = "#0f4451", comment = "#586e75" }
      hl(0, "Normal", { fg = p.fg, bg = p.bg })
      hl(0, "Comment", { fg = p.comment, italic = true })
      diff_washes({
        bg = p.bg,
        green = "#859900",
        red = "#dc322f",
        yellow = "#b58900",
      })
    end,
  },
  selenized = {
    -- jan-warchol's Selenized (Solarized's higher-contrast sibling), served by
    -- the SAME plugin as the solarized family (maxmx03/solarized.nvim) via
    -- palette = "selenized" — no separate plugin. pre() flips the palette before
    -- :colorscheme; both palettes register colors_name "solarized" and load via
    -- the same :colorscheme, so the guard keys on that. Raw theme — no fixup:
    -- Selenized's own contrast stands (body 6.1:1 dark / 5.4:1 light), and the
    -- accents below are its own violet/blue, straight from the palette.
    schemes = { dark = "solarized", light = "solarized" },
    colors_name = "solarized",
    pre = function()
      require("solarized").setup({ palette = "selenized" })
    end,
    accents = {
      dark = { heading1 = "#af88eb", heading = "#4695f7" }, -- violet + blue
      light = { heading1 = "#8762c6", heading = "#0072d4" },
    },
  },
  tokyonight = {
    -- folke/tokyonight.nvim: night (the darkest of the three darks — storm and
    -- moon sit on lighter, bluer bases) and day.
    -- Each variant registers its own colors_name, matching schemes[mode].
    schemes = { dark = "tokyonight-night", light = "tokyonight-day" },
    accents = {
      dark = { heading1 = "#bb9af7", heading = "#7aa2f7" }, -- purple + blue
      light = { heading1 = "#9854f1", heading = "#2e7de9" },
    },
    -- Worst comment contrast of any family here: night's #565f89 is 2.76:1 and
    -- day's #848cb5 is 2.54:1 (floor 4.5) — both are barely-there blues. Night
    -- lifts 40% toward body (5.06:1, against body's 10.59). Day is the harder
    -- one: its body fg is a BLUE (#3760bf) that only measures 4.52:1 itself, so
    -- a floor-clearing comment would land on top of body. Deepen body down the
    -- same blue ramp to 8.07:1 (the solarized-light precedent), which buys the
    -- comment room at 4.91:1.
    -- Diff* ship real bg-only washes in both modes and are left stock: night's
    -- add is a genuine BLUE (#243e4a, hue 198) rather than a green, which is
    -- what makes its diffs separate cleanly from the red delete.
    fixup = function(mode)
      local hl = vim.api.nvim_set_hl
      if mode == "dark" then
        hl(0, "Comment", { fg = blend("#c0caf5", "#565f89", 0.4), italic = true })
      else
        hl(0, "Normal", { fg = "#223c7d", bg = "#e1e2e7" })
        hl(0, "Comment", { fg = "#565e80", italic = true })
      end
    end,
  },
  nightfox = {
    -- EdenEast/nightfox.nvim: the namesake nightfox (cool blue-slate night)
    -- dark / dayfox (warm linen paper) light. The family also ships duskfox,
    -- nordfox, terafox, carbonfox darks and a dawnfox light — swap the schemes
    -- below to re-pin. Each variant registers its own colors_name.
    schemes = { dark = "nightfox", light = "dayfox" },
    accents = {
      dark = { heading1 = "#9d79d6", heading = "#719cd6" }, -- magenta + blue
      light = { heading1 = "#6e33ce", heading = "#2848a9" },
    },
    -- Comment floor: stock #738091 is 3.95:1 dark / #837a72 is 3.78:1 light,
    -- both under 4.5. Unlike solarized/tokyonight-day, body has plenty of room
    -- in BOTH modes (10.06 / 11.15), so lift the comment alone — no Normal
    -- deepening needed. Dark blends 30% toward fg1 (5.37:1); light deepens
    -- 30% toward fg1 (5.20:1). Comments stay
    -- upright: nightfox ships styles.comments = "NONE", so italic would be an
    -- invention, not a preservation.
    -- Diff washes: dayfox (light) ships 0.20/0.40 and is left stock, but the
    -- dark namesake blends at just 0.15 toward the *dim* accents — the faintest
    -- in the family, and DiffText (0.20) barely clears DiffChange (0.15), so
    -- word-diff reads as one flat block. Rebuild the DARK washes at family
    -- strength (dayfox's 0.22/0.40), keeping nightfox's own hues (green/red
    -- add/delete, blue change, cyan text) so only contrast lifts, not character.
    -- Checked: DiffText now leads DiffChange 2.52:1 vs 1.35:1 against bg (was
    -- 1.59 vs 1.31, nearly equal); body fg stays >=3.99:1 on every wash.
    fixup = function(mode)
      local hl = vim.api.nvim_set_hl
      local c = mode == "dark" and blend("#cdcecf", "#738091", 0.3) or blend("#3d2b5a", "#837a72", 0.3)
      hl(0, "Comment", { fg = c })
      if mode == "dark" then
        local bg = "#192330"
        hl(0, "DiffAdd", { bg = blend("#81b29a", bg, 0.22) })
        hl(0, "DiffDelete", { bg = blend("#c94f6d", bg, 0.22) })
        hl(0, "DiffChange", { bg = blend("#719cd6", bg, 0.18) })
        hl(0, "DiffText", { bg = blend("#63cdcf", bg, 0.40), bold = true })
      end
    end,
  },
  terafox = {
    -- EdenEast/nightfox.nvim, terafox (teal-and-rust autumn-rain dark) paired
    -- with dawnfox (rosé-dawn light, the rose-pine-dawn palette). A second
    -- nightfox-project family alongside nightfox/dayfox; each variant registers
    -- its own colors_name.
    schemes = { dark = "terafox", light = "dawnfox" },
    accents = {
      dark = { heading1 = "#ad5c7c", heading = "#5a93aa" }, -- rose + teal-blue
      light = { heading1 = "#907aa9", heading = "#286983" }, -- iris + pine
    },
    -- Comment floor: terafox #6d7f8b is 3.81:1 on #152528, dawnfox #9893a5 is
    -- 2.73:1 on #faf4ed (floor 4.5). Body has room in both (13.05 dark / 6.66
    -- light), so lift the comment alone — no Normal deepening. Dark blends 25%
    -- toward fg1 (5.46:1); light needs 60% toward fg1 (4.56:1, still clear of
    -- body's 6.66). Comments stay upright: nightfox ships styles.comments =
    -- "NONE", so italic would be an invention, not a preservation.
    -- Diff* are left stock: both palettes build them as real bg-only blends
    -- (generate_spec's spec.diff).
    fixup = function(mode)
      local c = mode == "dark" and blend("#e6eaea", "#6d7f8b", 0.25) or blend("#575279", "#9893a5", 0.6)
      vim.api.nvim_set_hl(0, "Comment", { fg = c })
    end,
  },
  modus = {
    -- miikanissi/modus-themes.nvim, TINTED variants: vivendi-tinted (night-sky
    -- indigo #0d0e1c) dark / operandi-tinted (warm paper #fbf7f0) light.
    -- WCAG-AAA by design: body sits ~19:1 in both modes — far above the house
    -- 9–13 comfort band, kept stock because maximum contrast IS this theme.
    -- Both styles register colors_name "modus"; the tinted palettes come from
    -- setup(), so pre() re-primes before every :colorscheme.
    schemes = { dark = "modus_vivendi", light = "modus_operandi" },
    colors_name = "modus",
    pre = function()
      require("modus-themes").setup({
        variants = { modus_operandi = "tinted", modus_vivendi = "tinted" },
      })
    end,
    accents = {
      dark = { heading1 = "#b6a0ff", heading = "#79a8ff" }, -- violet + blue
      light = { heading1 = "#531ab6", heading = "#0031a9" },
    },
    -- The port takes big liberties with prot's syntax mapping (tan functions,
    -- plain-fg constants, violet statements, invented italics — none exist in
    -- emacs, where bold/italic constructs are opt-in and off). Re-anchor every
    -- deviating group to the emacs *-tinted palette slots (modus-themes.el
    -- defconst blocks): fnname/fnname-call, keyword (also drives Statement*),
    -- constant, type, variable/property, preprocessor, comment, docstring;
    -- numbers and plain variable uses are body-fg in emacs. Also: DiffText
    -- ships IDENTICAL to DiffChange (same bg), which blinds the word-diff
    -- glue — lift it a shade past the line wash.
    fixup = function(mode)
      local hl = vim.api.nvim_set_hl
      local p = mode == "dark"
          and {
            comment = "#ef8386", string = "#2fafff", docstring = "#9ac8e0",
            fnname = "#f78fe7", fncall = "#d09dc0", keyword = "#79a8ff",
            constant = "#b6a0ff", type = "#11c777", variable = "#4ae2f0",
            preproc = "#ff7f86", fg = "#ffffff",
          }
          or {
            comment = "#7f0000", string = "#00598b", docstring = "#304463",
            fnname = "#602938", fncall = "#7b435c", keyword = "#0031a9",
            constant = "#531ab6", type = "#306010", variable = "#00603f",
            preproc = "#894000", fg = "#000000",
          }
      hl(0, "Comment", { fg = p.comment })
      hl(0, "String", { fg = p.string })
      hl(0, "Character", { fg = p.string })
      hl(0, "Function", { fg = p.fnname })
      hl(0, "Keyword", { fg = p.keyword })
      for _, g in ipairs({ "Statement", "Conditional", "Repeat", "Exception", "StorageClass", "Structure" }) do
        hl(0, g, { fg = p.keyword })
      end
      hl(0, "Type", { fg = p.type })
      hl(0, "Constant", { fg = p.constant })
      hl(0, "Boolean", { fg = p.constant })
      hl(0, "Number", { fg = p.fg })
      hl(0, "Identifier", { fg = p.variable })
      for _, g in ipairs({ "PreProc", "Include", "Define", "Macro" }) do
        hl(0, g, { fg = p.preproc })
      end
      hl(0, "@variable", { fg = p.fg })
      hl(0, "@variable.parameter", { fg = p.variable })
      hl(0, "@property", { fg = p.variable })
      hl(0, "@function.call", { fg = p.fncall })
      hl(0, "@function.method.call", { fg = p.fncall })
      hl(0, "@constructor", { fg = p.fncall })
      hl(0, "@keyword.function", { link = "Keyword" })
      hl(0, "@constant.builtin", { fg = p.constant })
      hl(0, "@string.documentation", { fg = p.docstring })
      if mode == "dark" then
        hl(0, "DiffText", { fg = "#efef80", bg = "#514b12", bold = true })
      else
        hl(0, "DiffText", { fg = "#553d00", bg = "#f5c96c", bold = true })
      end
    end,
  },
  one = {
    -- olimorris/onedarkpro.nvim: Atom's One, ONEDARK / ONELIGHT pair. Cooler
    -- and sharper than the doom-one family. Each variant compiles its own
    -- colors_name ("onedark"/"onelight"), matching schemes[mode].
    schemes = { dark = "onedark", light = "onelight" },
    accents = {
      dark = { heading1 = "#c678dd", heading = "#61afef" }, -- purple + blue
      -- light headings match the recolored onelight palette (plugins/onedarkpro.lua):
      -- stock #9a77cf/#118dc3 were 2.95:1/3.10:1 on the #eaeaea bg — too faint.
      light = { heading1 = "#7942cc", heading = "#056995" }, -- 5.04:1 each
    },
    -- Comment floor. Dark (onedark, #282c34 bg): One ships #7f848e (3.73:1) —
    -- lift to #939aa3 (4.93:1). Light (onelight, toned to #eaeaea): stock
    -- #9b9fa6 is 2.21:1 — lift to #656971 (4.58:1). onelight's syntax palette
    -- is darkened wholesale in plugins/onedarkpro.lua; this only covers Comment
    -- (it also carries the italic that the palette override can't set).
    fixup = function(mode)
      local c = mode == "dark" and "#939aa3" or "#656971"
      vim.api.nvim_set_hl(0, "Comment", { fg = c, italic = true })
    end,
  },
}

local applied ---@type string|nil  last family+mode we set, to skip redundant reloads

-- Read a state file's first line, trimmed; nil if missing.
local function read_state(path)
  local f = io.open(path, "r")
  if not f then
    return nil
  end
  local raw = f:read("l") or ""
  f:close()
  return (raw:gsub("%s+", ""))
end

local function normalize_mode(mode)
  return mode == "light" and "light" or "dark"
end

local function normalize_family(family)
  return FAMILIES[family] and family or DEFAULT_FAMILY
end

function M.read_state()
  return normalize_family(read_state(FAMILY_FILE)), normalize_mode(read_state(MODE_FILE))
end

-- markview heading colours (referenced by markview.lua's headings config).
local function set_headings(a)
  local hl = vim.api.nvim_set_hl
  hl(0, "MdHeading1", { fg = a.heading1, bold = true })
  for i = 2, 6 do
    hl(0, "MdHeading" .. i, { fg = a.heading, bold = true })
  end
  hl(0, "MdBullet", { fg = a.heading })
end

-- gitsigns word-diff readability (the `=` whole-file inline overlay, keymaps.lua).
-- gitsigns' inline word-diff groups (GitSigns{Change,Add,Delete}LnInline)
-- default to `reverse = true`, which paints dim token fgs (comments worst)
-- as unreadable blocks. Replace reverse with the theme's own diff
-- backgrounds + a forced bright Normal fg, so the emphasised word reads on
-- ANY underlying token. Reads the resolved palette at ColorScheme time, so
-- it is theme-agnostic and tracks every family/mode switch.
local function set_word_diff()
  local hl = vim.api.nvim_set_hl
  local function bg_of(name)
    return vim.api.nvim_get_hl(0, { name = name, link = false }).bg
  end
  local fg = vim.api.nvim_get_hl(0, { name = "Normal", link = false }).fg
  -- DiffText (word-emphasis) sits a shade lighter than DiffChange (the
  -- line bg), so the changed word still pops out of its own changed line.
  hl(0, "GitSignsChangeLnInline", { fg = fg, bg = bg_of("DiffText"), bold = true })
  hl(0, "GitSignsAddLnInline", { fg = fg, bg = bg_of("DiffAdd"), bold = true })
  hl(0, "GitSignsDeleteLnInline", { fg = fg, bg = bg_of("DiffDelete"), bold = true })
end

-- Runs on every ColorScheme. A manual :colorscheme (theme audition) won't
-- match the active family's scheme — skip its fixup/accents and apply only
-- the theme-agnostic word-diff glue, so auditions aren't painted over.
-- nvim-orgmode agenda readability (prefix n a / n t popups). The plugin
-- samples its @org.agenda.* colors from whatever the active theme defines,
-- which under minimal, low-colour families lands scheduled-item text
-- near-invisible. Pin them to semantic groups every family paints; the
-- plugin's own versions are `hi default`, so these explicit links win
-- regardless of load order.
local function set_org_agenda()
  local links = {
    ["@org.agenda.scheduled"] = "Normal",
    ["@org.agenda.scheduled_past"] = "WarningMsg",
    ["@org.agenda.deadline.upcoming"] = "WarningMsg",
    ["@org.agenda.deadline"] = "ErrorMsg",
  }
  for group, target in pairs(links) do
    vim.api.nvim_set_hl(0, group, { link = target })
  end
end

local function apply_overrides()
  local family, mode = M.read_state()
  local fam = FAMILIES[family]
  -- colors_name: guard override for themes whose variant colorschemes all
  -- register one shared name (e.g. kanagawa-lotus sets colors_name = "kanagawa")
  if vim.g.colors_name == (fam.colors_name or fam.schemes[mode]) then
    if fam.fixup then
      fam.fixup(mode) -- before word-diff: it reads the Diff* bgs set here
    end
    set_headings(fam.accents[mode])
  end
  set_word_diff()
  set_org_agenda()
end

-- Apply family+mode by setting background and re-running :colorscheme. Skips
-- the reload if already active (a reload clears user highlights and re-runs
-- the theme build), unless `force` is set (used for the initial apply).
function M.apply(family, mode, force)
  family, mode = normalize_family(family), normalize_mode(mode)
  local key = family .. "/" .. mode
  if not force and key == applied then
    return
  end
  applied = key
  local fam = FAMILIES[family]
  if fam.pre then
    fam.pre(mode) -- variant globals the theme reads at :colorscheme time
  end
  vim.o.background = mode
  vim.cmd.colorscheme(fam.schemes[mode])
end

function M.apply_from_file(force)
  local family, mode = M.read_state()
  M.apply(family, mode, force)
end

local polls = {} -- libuv fs_poll handles, created lazily in start()

-- Apply the current state now and start watching both state files.
function M.start()
  -- Ensure the state files exist so fs_poll has targets.
  local defaults = { [MODE_FILE] = "dark", [FAMILY_FILE] = DEFAULT_FAMILY }
  for path, value in pairs(defaults) do
    if not vim.uv.fs_stat(path) then
      local f = io.open(path, "w")
      if f then
        f:write(value .. "\n")
        f:close()
      end
    end
  end

  vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("ThemeOverrides", { clear = true }),
    callback = apply_overrides,
  })

  M.apply_from_file(true)

  if next(polls) then
    return
  end
  for _, path in ipairs({ MODE_FILE, FAMILY_FILE }) do
    local poll = vim.uv.new_fs_poll()
    if poll then
      -- 1s cadence: imperceptible for a manual toggle, negligible overhead.
      poll:start(
        path,
        1000,
        vim.schedule_wrap(function()
          M.apply_from_file(false)
        end)
      )
      polls[#polls + 1] = poll
    end
  end
end

return M
