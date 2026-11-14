-- theme-sync — keep nvim in sync with the shared theme state written by the
-- `theme-mode` script (scripts/.local/bin/theme-mode):
--   ~/.cache/theme-mode    "dark" | "light"
--   ~/.cache/theme-family  family name (FAMILIES below)
-- Both files are fs_poll'ed (~1s), so `theme-mode use one` or a prefix T
-- toggle from herdr flips every running instance with no sockets to manage.
-- <leader>ut shells out to the same script, so a toggle from nvim flips herdr
-- and ghostty too — one source of truth, all ways.
--
-- This module also owns every theme-reactive highlight override (markdown
-- headings, gitsigns word-diff), re-applied on ColorScheme,
-- so a family switch always lands with the right set. Plugin specs stay pure
-- plugin declarations. Keep FAMILIES in sync with theme-mode's registry and
-- the ghostty/herdr theme files.

local M = {}

local MODE_FILE = vim.env.HOME .. "/.cache/theme-mode"
local FAMILY_FILE = vim.env.HOME .. "/.cache/theme-family"
local DEFAULT_FAMILY = "onedarkpro"

-- alpha-blend two hex colours (a = share of c1).
local function blend(c1, c2, a)
  local out = {}
  for i = 2, 6, 2 do
    local v = tonumber(c1:sub(i, i + 1), 16) * a + tonumber(c2:sub(i, i + 1), 16) * (1 - a)
    out[#out + 1] = string.format("%02x", math.floor(v + 0.5))
  end
  return "#" .. table.concat(out)
end

-- Registry shape: the mode axis and the state-file plumbing both key off this table — adding a family is an entry here plus theme-mode's
-- cases and the ghostty/herdr files.
local FAMILIES = {
  ["bamboo"] = {
    -- ribru17/bamboo.nvim: one colorscheme "bamboo" picks its style from
    -- vim.o.background (light palette #fafae0 / vulgaris #252623) and always
    -- sets colors_name to "bamboo", so both are pinned here.
    schemes = { dark = "bamboo", light = "bamboo" },
    colors_name = "bamboo",
    -- bamboo paints markdown headings from its own rainbow blends: H1 =
    -- blend(red, inverse, 0.25), H2 = blend(orange, inverse, 0.25).
    accents = {
      dark = { heading1 = "#ed839d", heading = "#ffb38c" },
      light = { heading1 = "#95202d", heading = "#a7431d" },
    },
  },
  ["gruvbox-material"] = {
    -- sainnhe/gruvbox-material, HARD background, foreground = "mix" —
    -- mix accents (red #f2594b, fg #e2cca9) over hard grounds (#1d2021
    -- dark / #f9f5d7 light) and the plugin's role table (Function green,
    -- Operator orange, Constant aqua, PreProc purple). One colorscheme follows
    -- vim.o.background and sets colors_name "gruvbox-material" in both modes.
    schemes = { dark = "gruvbox-material", light = "gruvbox-material" },
    colors_name = "gruvbox-material",
    -- The variant globals are read at :colorscheme time, hence `pre`.
    pre = function()
      vim.g.gruvbox_material_background = "hard"
      vim.g.gruvbox_material_foreground = "mix"
    end,
    accents = {
      dark = { heading1 = "#f2594b", heading = "#e9b143" }, -- red + yellow
      light = { heading1 = "#af2528", heading = "#b4730e" },
    },
  },
  ["edge"] = {
    schemes = { dark = "edge", light = "edge" },
    colors_name = "edge",
    pre = function()
      vim.g.edge_style = "aura"
    end,
    accents = {
      dark = { heading1 = "#ec7279", heading = "#deb974" },
      light = { heading1 = "#c93f3f", heading = "#9a6604" },
    },
  },
  ["tokyonight"] = {
    -- folke/tokyonight.nvim night #1a1b26 / day #e1e2e7.
    schemes = { dark = "tokyonight-night", light = "tokyonight-day" },
    accents = {
      dark = { heading1 = "#f7768e", heading = "#e0af68" },
      light = { heading1 = "#f52a65", heading = "#8c6c3e" },
    },
  },
  ["onedarkpro"] = {
    schemes = { dark = "onedark", light = "onelight" },
    accents = {
      dark = { heading1 = "#e06c75", heading = "#e5c07b" },
      light = { heading1 = "#e05661", heading = "#eea825" },
    },
  },
  ["dracula"] = {
    schemes = { dark = "dracula", light = "alucard" },
    accents = {
      dark = { heading1 = "#FF79C6", heading = "#BD93F9" },
      light = { heading1 = "#A3144D", heading = "#644AC9" },
    },
  },
  ["nightfox"] = {
    schemes = { dark = "nightfox", light = "dayfox" },
    accents = {
      dark = { heading1 = "#c94f6d", heading = "#dbc074" },
      light = { heading1 = "#a5222f", heading = "#AC5402" },
    },
  },
  ["duskfox"] = {
    schemes = { dark = "duskfox", light = "dawnfox" },
    accents = {
      dark = { heading1 = "#eb6f92", heading = "#f6c177" },
      light = { heading1 = "#b4637a", heading = "#ea9d34" },
    },
  },
  ["dredge"] = {
    -- bcorey85/dredge.nvim: one colorscheme follows vim.o.background.
    schemes = { dark = "dredge", light = "dredge" },
    colors_name = "dredge",
    -- Comments are tuned in APCA and mirrored in hunk; the WCAG floor would
    -- split them from docstrings and from hunk.
    own_comment_contrast = true,
    accents = {
      -- H1 takes the exit magenta; H2-H6 the bind violet.
      dark = { heading1 = "#d6708c", heading = "#8990da", bullet = "#a5a9b0" },
      light = { heading1 = "#a80e62", heading = "#433fa8", bullet = "#4e5158" },
    },
  },
  ["kanagawa"] = {
    -- rebelot/kanagawa.nvim: wave dark / lotus light, both set colors_name "kanagawa".
    schemes = { dark = "kanagawa-wave", light = "kanagawa-lotus" },
    colors_name = "kanagawa",
    accents = {
      dark = { heading1 = "#e46876", heading = "#7e9cd8" },
      light = { heading1 = "#c84053", heading = "#4d699b" },
    },
  },
  ["darcula"] = {
    -- xiantang/darcula-dark.nvim: dark only, in both modes.
    schemes = { dark = "darcula-dark", light = "darcula-dark" },
    colors_name = "darcula-dark",
    dark_only = true,
    accents = {
      dark = { heading1 = "#cc7832", heading = "#b3deef" },
      light = { heading1 = "#cc7832", heading = "#b3deef" },
    },
  },
  ["tairiki"] = {
    -- deparr/tairiki.nvim: dark / light; both set colors_name "tairiki".
    schemes = { dark = "tairiki-dark", light = "tairiki-light" },
    colors_name = "tairiki",
    -- Dark's DiffAdd is a 30% green block; rows take the green/red/grey 15%
    -- into the ground and words the blue 30%, so syntax stays readable.
    pre = function(mode)
      local highlights = nil
      if mode == "dark" then
        local bg = "#151515"
        highlights = function(hl)
          hl.DiffAdd = { bg = blend("#b5bd68", bg, 0.15) }
          hl.DiffDelete = { bg = blend("#cc6666", bg, 0.15) }
          hl.DiffChange = { bg = blend("#696969", bg, 0.12) }
          hl.DiffText = { bg = blend("#81a2be", bg, 0.30) }
        end
      end
      require("tairiki").setup({ highlights = highlights })
    end,
    accents = {
      dark = { heading1 = "#cc6666", heading = "#81a2be" },
      light = { heading1 = "#a31515", heading = "#0070c1" },
    },
  },
  ["everforest"] = {
    -- sainnhe/everforest, hard background: one colorscheme follows vim.o.background.
    schemes = { dark = "everforest", light = "everforest" },
    colors_name = "everforest",
    pre = function()
      vim.g.everforest_background = "hard"
    end,
    accents = {
      dark = { heading1 = "#e67e80", heading = "#e69875" },
      light = { heading1 = "#f85552", heading = "#f57d26" },
    },
  },
  ["gruvbox"] = {
    -- ellisonleao/gruvbox.nvim, medium contrast (the default): one colorscheme
    -- follows vim.o.background and sets colors_name "gruvbox" in both modes.
    schemes = { dark = "gruvbox", light = "gruvbox" },
    colors_name = "gruvbox",
    accents = {
      dark = { heading1 = "#b8bb26", heading = "#fabd2f" }, -- green + yellow
      light = { heading1 = "#79740e", heading = "#b57614" },
    },
  },
  ["papercolor"] = {
    -- NLKNguyen/papercolor-theme: one colorscheme "PaperColor" follows
    -- vim.o.background and sets colors_name "PaperColor" in both modes.
    schemes = { dark = "PaperColor", light = "PaperColor" },
    colors_name = "PaperColor",
    -- Dark diff rows are washes of the sign colours: the plugin's saturated
    -- grounds push the comment floor up to near-text.
    pre = function()
      local diff_washes = {
        diffadd_bg = { "#263218", "22" },
        diffdelete_bg = { "#361728", "52" },
        diffchange_bg = { "#183232", "23" },
        difftext_bg = { "#144848", "30" },
      }
      vim.g.PaperColor_Theme_Options = {
        theme = {
          ["default"] = { allow_bold = 0 },
          ["default.dark"] = { override = diff_washes },
        },
      }
    end,
    -- The plugin predates treesitter and float groups. An empty @variable
    -- drops nvim's default fg so variables take Normal's. Floats take the
    -- ground in place of nvim's default near-black. Every other group that
    -- paints the ground colour as its bg loses it, so it shows no patch on a
    -- float or on the transparent editor.
    post = function()
      local normal = vim.api.nvim_get_hl(0, { name = "Normal", link = false })
      local keeps_bg = { Normal = true, NormalNC = true }
      for name, spec in pairs(vim.api.nvim_get_hl(0, {})) do
        local paints_ground = spec.bg == normal.bg and not spec.reverse
        if paints_ground and not keeps_bg[name] then
          spec.bg = nil
          spec.ctermbg = nil
          vim.api.nvim_set_hl(0, name, spec)
        end
      end
      vim.api.nvim_set_hl(0, "@variable", {})
      vim.api.nvim_set_hl(0, "NormalFloat", { fg = normal.fg, bg = normal.bg })
      local border = vim.api.nvim_get_hl(0, { name = "LineNr", link = false })
      vim.api.nvim_set_hl(0, "FloatBorder", { fg = border.fg, bg = normal.bg })
      vim.api.nvim_set_hl(0, "FloatTitle", { fg = normal.fg, bg = normal.bg })
      vim.api.nvim_set_hl(0, "WinBar", { fg = normal.fg })
      vim.api.nvim_set_hl(0, "WinBarNC", { fg = border.fg })
    end,
    accents = {
      dark = { heading1 = "#ff5faf", heading = "#5fafd7" },
      light = { heading1 = "#d70087", heading = "#005faf" },
    },
  },
  ["vitesse"] = {
    -- bcorey85/vitesse.nvim: one colorscheme "vitesse" follows
    -- vim.o.background and sets colors_name "vitesse" in both modes.
    -- Headings are the theme's own: its primary green at every level.
    schemes = { dark = "vitesse", light = "vitesse" },
    colors_name = "vitesse",
    accents = {
      dark = { heading1 = "#4d9375", heading = "#4d9375" },
      light = { heading1 = "#1c6b48", heading = "#1c6b48" },
    },
  },
  ["hybrid"] = {
    -- HoNamDuong/hybrid.nvim is dark only; light is colors/hybrid-light.lua,
    -- the plugin's highlight table over a light palette.
    schemes = { dark = "hybrid", light = "hybrid-light" },
    -- The plugin draws line numbers in its selection grey, 1.5:1 on the
    -- ground. They take the comment grey at 70% instead. It also paints floats,
    -- menus and the tabline a step darker than the ground; they take the ground,
    -- with a border in the line-number grey.
    post = function(mode)
      local line_number = { dark = "#575d64", light = "#b0b1ae" }
      local ground = { dark = "#1d1f21", light = "#ffffff" }
      vim.api.nvim_set_hl(0, "LineNr", { fg = line_number[mode] })
      local on_ground = { "NormalFloat", "FloatTitle", "Pmenu", "PmenuSbar", "TabLine", "TabLineFill" }
      for _, name in ipairs(on_ground) do
        local spec = vim.api.nvim_get_hl(0, { name = name, link = false })
        spec.bg = ground[mode]
        vim.api.nvim_set_hl(0, name, spec)
      end
      vim.api.nvim_set_hl(0, "FloatBorder", { fg = line_number[mode], bg = ground[mode] })
    end,
    accents = {
      dark = { heading1 = "#e7c547", heading = "#81a2be" },
      light = { heading1 = "#7a5e00", heading = "#4271ae" },
    },
  },
  ["solarized-osaka"] = {
    -- craftzdog/solarized-osaka.nvim: both colorschemes set colors_name "solarized-osaka".
    schemes = { dark = "solarized-osaka", light = "solarized-osaka-light" },
    colors_name = "solarized-osaka",
    accents = {
      dark = { heading1 = "#db302d", heading = "#b28500" },
      light = { heading1 = "#b7221f", heading = "#8f6b00" },
    },
  },
  ["solarized"] = {
    -- maxmx03/solarized.nvim: one colorscheme that follows vim.o.background.
    schemes = { dark = "solarized", light = "solarized" },
    colors_name = "solarized",
    accents = {
      dark = { heading1 = "#dc322f", heading = "#b58900" },
      light = { heading1 = "#dc322f", heading = "#b58900" },
    },
  },
  ["selenized"] = {
    -- calind/selenized.nvim: one colorscheme that follows vim.o.background.
    schemes = { dark = "selenized", light = "selenized" },
    colors_name = "selenized",
    accents = {
      dark = { heading1 = "#fa5750", heading = "#dbb32d" },
      light = { heading1 = "#d2212d", heading = "#ad8900" },
    },
  },
  ["flexoki"] = {
    -- kepano/flexoki-neovim: flexoki-dark / flexoki-light both set colors_name "flexoki".
    schemes = { dark = "flexoki-dark", light = "flexoki-light" },
    colors_name = "flexoki",
    -- Stock diffs are solid accent blocks; rows take the green/red/purple 15%
    -- into the ground and words the blue 30%, so syntax stays readable.
    pre = function(mode)
      local bg = mode == "light" and "#fffcf0" or "#100f0f"
      local hues = mode == "light" and { gr = "#66800b", re = "#af3029", pu = "#5e409d", bl = "#205ea6" }
        or { gr = "#879a39", re = "#d14d41", pu = "#8b7ec8", bl = "#4385be" }
      require("flexoki").setup({
        highlight_groups = {
          DiffAdd = { bg = blend(hues.gr, bg, 0.15) },
          DiffDelete = { bg = blend(hues.re, bg, 0.15) },
          DiffChange = { bg = blend(hues.pu, bg, 0.12) },
          DiffText = { bg = blend(hues.bl, bg, 0.30) },
        },
      })
    end,
    accents = {
      dark = { heading1 = "#ce5d97", heading = "#4385be" },
      light = { heading1 = "#a02f6f", heading = "#205ea6" },
    },
  },
  ["token-flint"] = {
    -- ThorstenRhau/token: one colorscheme "token-flint" follows vim.o.background
    -- (cool grey #272c33 dark / #f5f7f8 light).
    schemes = { dark = "token-flint", light = "token-flint" },
    colors_name = "token-flint",
    accents = {
      dark = { heading1 = "#eb9e83", heading = "#f8d28a" },
      light = { heading1 = "#902a03", heading = "#6b4600" },
    },
  },
  ["token"] = {
    -- ThorstenRhau/token, default variant: one colorscheme "token" follows
    -- vim.o.background (warm graphite #262624 dark / #faf9f5 light).
    schemes = { dark = "token", light = "token" },
    colors_name = "token",
    accents = {
      dark = { heading1 = "#f4906f", heading = "#f7c699" },
      light = { heading1 = "#863716", heading = "#6d4717" },
    },
  },
  ["jellybeans"] = {
    -- WTFox/jellybeans.nvim: one colorscheme "jellybeans" follows vim.o.background
    -- (#151515 dark / sepia #f5e6d3 light).
    schemes = { dark = "jellybeans", light = "jellybeans" },
    colors_name = "jellybeans",
    -- Stock diffs are fg-only, which recolours the code; rows take the
    -- green/red/blue 15% into the ground and words the blue 30%, so syntax
    -- stays readable.
    pre = function(mode)
      local bg = mode == "light" and "#f5e6d3" or "#151515"
      local hues = mode == "light" and { gr = "#386014", re = "#a02020", ch = "#1670af", bl = "#2952a3" }
        or { gr = "#70b950", re = "#d74545", ch = "#5f9ecf", bl = "#8197bf" }
      require("jellybeans").setup({
        on_highlights = function(highlights)
          highlights.DiffAdd = { bg = blend(hues.gr, bg, 0.15) }
          highlights.DiffDelete = { bg = blend(hues.re, bg, 0.15) }
          highlights.DiffChange = { bg = blend(hues.ch, bg, 0.12) }
          highlights.DiffText = { bg = blend(hues.bl, bg, 0.30) }
        end,
      })
    end,
    accents = {
      dark = { heading1 = "#b0d0f0", heading = "#8fbfdc" },
      light = { heading1 = "#234291", heading = "#5f43aa" },
    },
  },
  ["rose-pine"] = {
    -- rose-pine/neovim: main #191724 / dawn #faf4ed, both set colors_name "rose-pine".
    schemes = { dark = "rose-pine-main", light = "rose-pine-dawn" },
    colors_name = "rose-pine",
    accents = {
      dark = { heading1 = "#c4a7e7", heading = "#9ccfd8" },
      light = { heading1 = "#907aa9", heading = "#56949f" },
    },
  },
  ["ef-elea"] = {
    -- oonamo/ef-themes.nvim: #222524 dark / #edf5e2 light. Each scheme sets
    -- colors_name to its own name. Headings are the plugin's markdownH1 / H2.
    schemes = { dark = "ef-elea-dark", light = "ef-elea-light" },
    accents = {
      dark = { heading1 = "#eba8a8", heading = "#a9c99f" },
      light = { heading1 = "#894852", heading = "#306630" },
    },
  },
  ["ef-maris"] = {
    -- oonamo/ef-themes.nvim: #131c2b dark / #edf4f8 light.
    schemes = { dark = "ef-maris-dark", light = "ef-maris-light" },
    accents = {
      dark = { heading1 = "#70a0ff", heading = "#7fce5f" },
      light = { heading1 = "#444fcf", heading = "#3a6f00" },
    },
  },
  ["catppuccin"] = {
    -- catppuccin/nvim: frappé #303446 / latte #eff1f5.
    schemes = { dark = "catppuccin-frappe", light = "catppuccin-latte" },
    accents = {
      dark = { heading1 = "#e78284", heading = "#e5c890" },
      light = { heading1 = "#d20f39", heading = "#df8e1d" },
    },
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

-- Markdown heading + bullet colours. We paint @markup.heading.N.markdown
-- directly (most specific, so it wins over the family scheme);
-- render-markdown's RenderMarkdownH1..H6 link to these. H1 gets the accent,
-- H2–H6 the muted heading colour. Heading backgrounds are the heading colour
-- blended faintly into Normal bg instead of render-markdown's Diff* defaults.
local function set_headings(a)
  local hl = vim.api.nvim_set_hl
  local n = vim.api.nvim_get_hl(0, { name = "Normal", link = false })
  local bg = n.bg and string.format("#%06x", n.bg)
  for i = 1, 6 do
    local fg = i == 1 and a.heading1 or a.heading
    hl(0, "@markup.heading." .. i .. ".markdown", { fg = fg, bold = true })
    if bg then
      hl(0, "RenderMarkdownH" .. i .. "Bg", { bg = blend(fg, bg, 0.12) })
    end
  end
  hl(0, "RenderMarkdownBullet", { fg = a.bullet or a.heading })
end

-- Prose reading calm. Treesitter's markdown_inline/markdown parsers paint each
-- markup kind its own hue (bold/italic pink, code green, quote pink, links
-- lavender, bullets teal), so a single paragraph turns into five competing
-- colours — the "too busy to read prose" complaint. Strip the COLOUR and keep
-- the SIGNAL: bold stays bold, italic stays slanted, links keep an underline,
-- the raw URL and list markers drop to muted. Scoped to the language-specific
-- groups (.markdown_inline / .markdown) so only markdown is calmed — @markup.*
-- in help/other langs keeps its scheme colours. Theme-agnostic (weight/underline
-- + links to Normal/Comment), so it tracks every family/mode switch.
--
-- Inline code follows github.com: body fg on a faint chip, never a hue. Most
-- schemes paint `code` a syntax colour (and @markup.raw ships italic), which
-- makes a sentence with three backticked paths read as three different kinds of
-- thing. The chip is Normal fg blended 12% into Normal bg, so it lands one step
-- off the canvas in either mode without hardcoding a palette.
local function set_prose()
  local hl = vim.api.nvim_set_hl
  local n = vim.api.nvim_get_hl(0, { name = "Normal", link = false })
  local fg = n.fg and string.format("#%06x", n.fg)
  local bg = n.bg and string.format("#%06x", n.bg)
  local rules = {
    ["@markup.strong.markdown_inline"] = { bold = true },
    ["@markup.italic.markdown_inline"] = { italic = true },
    ["@markup.quote.markdown"] = { italic = true },
    ["@markup.link.markdown_inline"] = { underline = true },
    ["@markup.link.label.markdown_inline"] = { underline = true },
    ["@markup.link.url.markdown_inline"] = { link = "Comment" },
    ["@markup.list.markdown"] = { link = "Comment" },
  }
  if fg and bg then
    rules["@markup.raw.markdown_inline"] = { fg = fg, bg = blend(fg, bg, 0.12) }
    rules.RenderMarkdownCodeInline = { link = "@markup.raw.markdown_inline" }
    rules.RenderMarkdownCode = { bg = blend(fg, bg, 0.07) }
  end
  for group, spec in pairs(rules) do
    hl(0, group, spec)
  end
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
  -- A theme that paints changed lines with the added wash gets added-word
  -- treatment for their words too.
  local change_bg = bg_of("GitSignsChangeLn") == bg_of("DiffAdd") and bg_of("DiffAdd") or bg_of("DiffText")
  hl(0, "GitSignsChangeLnInline", { fg = fg, bg = change_bg, bold = true })
  hl(0, "GitSignsAddLnInline", { fg = fg, bg = bg_of("DiffAdd"), bold = true })
  hl(0, "GitSignsDeleteLnInline", { fg = fg, bg = bg_of("DiffDelete"), bold = true })
end

local function luminance(c)
  local l = {}
  for i = 2, 6, 2 do
    local v = tonumber(c:sub(i, i + 1), 16) / 255
    l[#l + 1] = v <= 0.03928 and v / 12.92 or ((v + 0.055) / 1.055) ^ 2.4
  end
  return 0.2126 * l[1] + 0.7152 * l[2] + 0.0722 * l[3]
end

local function contrast(a, b)
  local la, lb = luminance(a), luminance(b)
  return (math.max(la, lb) + 0.05) / (math.min(la, lb) + 0.05)
end

local function set_comment_floor()
  local function get(name, link)
    return vim.api.nvim_get_hl(0, { name = name, link = link })
  end
  local function hex(n)
    return n and string.format("#%06x", n)
  end
  local fg = hex(get("Normal", false).fg)
  local grounds = {}
  for _, name in ipairs({ "Normal", "DiffAdd", "DiffDelete", "DiffChange" }) do
    grounds[#grounds + 1] = hex(get(name, false).bg)
  end
  if not (fg and grounds[1]) then
    return
  end
  local function worst(c)
    local w = math.huge
    for _, g in ipairs(grounds) do
      w = math.min(w, contrast(c, g))
    end
    return w
  end
  local done = {}
  for _, name in ipairs({ "Comment", "@comment", "@comment.documentation", "SpecialComment" }) do
    local spec = get(name, true)
    while spec.link and spec.link:lower():find("comment") do
      name, spec = spec.link, get(spec.link, true)
    end
    local c = hex(spec.fg)
    if c and not spec.link and not done[name] then
      done[name] = true
      local t = 0
      while t < 1 and worst(blend(fg, c, t)) < 4.5 do
        t = t + 0.01
      end
      spec.fg = blend(fg, c, math.min(t, 1))
      vim.api.nvim_set_hl(0, name, spec)
    end
  end
end

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

-- Snacks dashboard shortcuts in the family's purple, their text in plain fg.
-- Path prefixes take the line-number grey (snacks' NonText default vanishes on
-- dark grounds); todo keywords take the warning amber.
local function set_dashboard()
  local links = {
    Key = "Function",
    Icon = "Function",
    Desc = "Normal",
    File = "Normal",
    Dir = "LineNr",
    Todo = "DiagnosticWarn",
  }
  for group, target in pairs(links) do
    vim.api.nvim_set_hl(0, "SnacksDashboard" .. group, { link = target })
  end
end

-- Snacks picker links a path's directory part, hidden and ignored paths and the
-- match count to NonText, which most themes draw near the ground. They take the
-- comment grey, which set_comment_floor keeps readable.
local function set_picker()
  for _, group in ipairs({ "Dir", "PathHidden", "PathIgnored", "Totals" }) do
    vim.api.nvim_set_hl(0, "SnacksPicker" .. group, { link = "Comment" })
  end
end

-- Clear the editor background so the terminal's translucent one shows
-- through. Floats keep theirs to stay readable. Must run last: the passes
-- above read Normal's bg.
local function set_transparent()
  local groups = { "Normal", "NormalNC", "SignColumn", "LineNr", "FoldColumn", "EndOfBuffer" }
  for _, name in ipairs(groups) do
    local spec = vim.api.nvim_get_hl(0, { name = name, link = false })
    spec.bg = nil
    spec.ctermbg = nil
    vim.api.nvim_set_hl(0, name, spec)
  end
end

-- Runs on every ColorScheme. A manual :colorscheme (theme audition) won't
-- match the active family's scheme — skip its accents and apply only
-- the theme-agnostic word-diff glue, so auditions aren't painted over.
local function apply_overrides()
  local family, mode = M.read_state()
  local fam = FAMILIES[family]
  -- colors_name: guard override for a family whose light/dark variants both
  -- register ONE shared colors_name (!= schemes[mode]); set fam.colors_name to
  -- it so this match still fires.
  local own_scheme = vim.g.colors_name == (fam.colors_name or fam.schemes[mode])
  if own_scheme then
    set_headings(fam.accents[mode])
  end
  if own_scheme and fam.post then
    fam.post(mode) -- groups the theme leaves at nvim's defaults
  end
  set_word_diff()
  if not (own_scheme and fam.own_comment_contrast) then
    set_comment_floor()
  end
  set_org_agenda()
  set_dashboard()
  set_picker()
  set_prose()
  -- An audition keeps its own ground: the terminal's belongs to the active family.
  if own_scheme then
    set_transparent()
  end
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
  vim.o.background = fam.dark_only and "dark" or mode
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
