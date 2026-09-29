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

; Type names at their definition.
(interface_declaration
  name: (_) @declaration)

(type_alias_declaration
  name: (_) @declaration)

(enum_declaration
  name: (_) @declaration)

(abstract_class_declaration
  name: (_) @declaration)

; Keys of object types and interfaces, like object-literal keys.
(property_signature
  name: (property_identifier) @variable.member.key)

; Keep function-typed keys as methods; the last matching pattern wins.
(property_signature
  name: (property_identifier) @function.method
  type: (type_annotation
    [
      (union_type
        (parenthesized_type
          (function_type)))
      (function_type)
    ]))
