-- vim-abolish (tpope) — three things, all zero-config (vimscript plugin, active
-- on load; no setup() required):
--
--   1. Case coercion of the word under the cursor (cr = "coerce"):
--        crs  snake_case        crc  camelCase      crm  MixedCase
--        cru  UPPER_CASE        cr-  kebab-case     cr.  dot.case
--        crt  Title Case        cr<space> space case
--      `cr` is not a native normal-mode command, so these don't shadow anything.
--
--   2. :S (:Subvert) — case-PRESERVING substitute. `:%S/foo/bar/g` rewrites
--      foo→bar, Foo→Bar, FOO→BAR in one pass. Slots into the :s / :cdo workflow.
--      Also expands brace alternation: :%S/{old,new}/{new,old}/ swaps the two.
--
--   3. :Abolish — define correcting abbreviations (e.g. common typos). Unused by
--      default; available if wanted.
return {
  "tpope/vim-abolish",
  event = "VeryLazy",
  cmd = { "Abolish", "Subvert", "S" },
}
