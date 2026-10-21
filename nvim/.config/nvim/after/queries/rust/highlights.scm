;; extends

; Some, Ok and Err build a value: plain, like any constructor call. None stays a literal.
((identifier) @constructor
  (#any-of? @constructor "Some" "Ok" "Err")
  (#set! priority 101))

; Type names at their definition.
(struct_item
  name: (type_identifier) @declaration.type
  (#set! priority 130))

(enum_item
  name: (type_identifier) @declaration.type
  (#set! priority 130))

(union_item
  name: (type_identifier) @declaration.type
  (#set! priority 130))

(trait_item
  name: (type_identifier) @declaration.type
  (#set! priority 130))

(type_item
  name: (type_identifier) @declaration.type
  (#set! priority 130))

; Constants and statics at their definition.
(const_item
  name: (identifier) @declaration.variable
  (#set! priority 130))

(static_item
  name: (identifier) @declaration.variable
  (#set! priority 130))
