;; extends

; Bare values (flex, center) are not strings. Themes without @string.plain
; fall back to @string.
((plain_value) @string.plain
  (#set! priority 101))

; @include calls a mixin: plain, like any call. Mixin and function names stay
; coloured at their definition.
((include_statement
  (identifier) @function.call)
  (#set! priority 101))

; Media query operators (and, not, only) are keywords.
((keyword_query) @keyword
  (#set! priority 101))
