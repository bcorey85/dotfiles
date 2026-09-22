;; extends

; Bare values (flex, center) are not strings. Themes without @string.plain
; fall back to @string.
((plain_value) @string.plain
  (#set! priority 101))
