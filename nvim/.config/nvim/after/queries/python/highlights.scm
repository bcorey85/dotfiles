;; extends

; None in a type position, apart from the value.
((none) @constant.builtin.type
  (#has-ancestor? @constant.builtin.type type)
  (#set! priority 110))
