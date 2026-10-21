;; extends

; Type names at their definition.
(type_spec
  name: (type_identifier) @declaration.type
  (#set! priority 130))

(type_alias
  name: (type_identifier) @declaration.type
  (#set! priority 130))

; Package-level constants and variables at their definition; locals stay plain.
(source_file
  (const_declaration
    (const_spec
      name: (identifier) @declaration.variable
      (#set! priority 130))))

(source_file
  (var_declaration
    (var_spec
      name: (identifier) @declaration.variable
      (#set! priority 130))))

(source_file
  (var_declaration
    (var_spec_list
      (var_spec
        name: (identifier) @declaration.variable
        (#set! priority 130)))))
