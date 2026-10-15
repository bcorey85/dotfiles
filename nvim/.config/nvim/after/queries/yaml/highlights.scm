;; extends

; Keys are definitions; unquoted values are plain. Quoted values stay strings.
(block_mapping_pair
  key: (flow_node
    (plain_scalar
      (string_scalar) @variable.member.key)))

(block_mapping_pair
  value: (flow_node
    (plain_scalar
      (string_scalar) @variable
      (#not-any-of? @variable "TRUE" "FALSE" "True" "False"))))

(block_sequence_item
  (flow_node
    (plain_scalar
      (string_scalar) @variable
      (#not-any-of? @variable "TRUE" "FALSE" "True" "False"))))
