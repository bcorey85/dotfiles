# single-caller-census: dead-weight census for the smell pass

Source: ~/agent-evals/queue/review-gets-a-census-of-added-single-caller-pass.md

### Context
On one branch, simplify passes kept finding the same dead-weight classes the review loop let through: a function called once that only forwarded to one step, a load/save pair wrapping one generic JSON read and write, an interface field nothing read, and a whole helper module made redundant when a later commit in the same branch widened another helper. The reviewer's dead-weight rule asks for a reference search only on exports, so private single-caller forwarders and unread fields never get counted, and nothing re-checks earlier branch code after a later commit changes what it duplicates. Each was cheap to find mechanically (reference counts over the branch's added symbols) and cost a user-prompted pass to find by hand.

### Done when
A script run on a branch diff lists each added function with exactly one call site whose body is a single call or a single return, each added interface or record field with zero reads, and each added function whose callers all also call a newer helper with the same output; the review loop and refactor branch-prep hand the list to smell-reviewer. A fixture diff with one of each produces three entries; before the change, none.
