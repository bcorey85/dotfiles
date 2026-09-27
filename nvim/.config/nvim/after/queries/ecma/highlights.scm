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
