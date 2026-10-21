;; extends

; Type names at their definition.
([
  (class_declaration name: (identifier) @declaration.class)
  (interface_declaration name: (identifier) @declaration.type)
  (record_declaration name: (identifier) @declaration.type)
  (struct_declaration name: (identifier) @declaration.type)
  (enum_declaration name: (identifier) @declaration.type)
  (delegate_declaration name: (identifier) @declaration.type)
]
  (#set! priority 130))

; Constructors at their definition, like methods.
([
  (constructor_declaration name: (identifier) @declaration.function)
  (destructor_declaration name: (identifier) @declaration.function)
]
  (#set! priority 130))
