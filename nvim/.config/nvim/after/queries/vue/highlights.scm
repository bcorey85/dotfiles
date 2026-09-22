;; extends

; Directive names (:key, @click, #slot, .prop, .prevent) are attribute names,
; the same colour as v-for and class. Their sigils are plain punctuation.
((directive_attribute
  [
    (directive_value)
    (directive_modifier)
  ] @tag.attribute)
  (#set! priority 101))

((directive_attribute
  [
    ":"
    "@"
    "#"
    "."
  ] @punctuation.delimiter)
  (#set! priority 101))
