;; extends

; Optional and definite-assignment markers (a?: T, x!: T) are plain punctuation,
; not @punctuation.special (which also marks template ${ }).
([
  (property_signature "?" @punctuation.delimiter)
  (optional_parameter "?" @punctuation.delimiter)
  (method_signature "?" @punctuation.delimiter)
  (abstract_method_signature "?" @punctuation.delimiter)
  (method_definition "?" @punctuation.delimiter)
  (public_field_definition ["?" "!"] @punctuation.delimiter)
]
  (#set! priority 101))
