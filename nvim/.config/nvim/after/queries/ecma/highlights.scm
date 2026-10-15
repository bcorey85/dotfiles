;; extends

; Object-literal keys at their definition, apart from member access.
(pair
  key: (property_identifier) @variable.member.key)

(object
  (shorthand_property_identifier) @variable.member.key)

; Keep method-valued keys as methods; the last matching pattern wins.
(pair
  key: (property_identifier) @function.method
  value: [(function_expression) (arrow_function)])

; Function, class and method names at their definition.
(function_declaration
  name: (_) @declaration.function
  (#set! priority 130))

(generator_function_declaration
  name: (_) @declaration.function
  (#set! priority 130))

(method_definition
  name: (_) @declaration.function
  (#set! priority 130))

(class_declaration
  name: (_) @declaration.class
  (#set! priority 130))

; Variable names at their definition; uses stay plain. Priority beats the LSP variable token.
(variable_declarator
  name: (identifier) @declaration.variable
  (#set! priority 130))

(for_in_statement
  left: (identifier) @declaration.variable
  (#set! priority 130))

(array_pattern
  (identifier) @declaration.variable
  (#set! priority 130))

(object_pattern
  (shorthand_property_identifier_pattern) @declaration.variable
  (#set! priority 130))

(pair_pattern
  value: (identifier) @declaration.variable
  (#set! priority 130))

(variable_declarator
  name: (identifier) @declaration.function
  value: [(function_expression) (arrow_function)]
  (#set! priority 130))

; Builtin globals are plain, not named constants.
((identifier) @variable.builtin
  (#any-of? @variable.builtin "JSON" "Intl" "Reflect" "Atomics" "globalThis"))
