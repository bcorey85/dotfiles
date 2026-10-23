;; extends

; Bare values (flex, center) are not strings. Themes without @string.plain
; fall back to their default.
((plain_value) @string.plain
  (#set! priority 101))

; Function calls (rgb, var, calc) are uses: plain.
((function_name) @function.call
  (#set! priority 101))
