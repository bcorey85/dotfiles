# Skimmable Writing Directive

Shared by `/eng-arch` and `/adr` — the single source of truth for the skimmability rules. Engineers in problem-solving mode scan headings (NN/g layer-cake pattern); they don't read. Write to be skimmed: trigger layer-cake scanning, then earn commitment reading with trust signals.

- **Headings = answers, not topics.** `Token interceptor` not `Implementation details`. `401 handling` not `Error section`. A layer-cake scanner must extract value without dropping into the body.
- **BLUF at every level.** Start each section with the claim, not the setup. Inverted pyramid all the way down.
- **Bullets > paragraphs. Tables > bullets** for structured comparisons (endpoints, phases, options, before/after).
- **Code refs over descriptions.** `file:line` beats "the file that handles X". Cite the path; let the reader click.
- **Bold the load-bearing word** in any multi-line bullet. Triggers spotted-pattern scanning back to the key term.
- **One idea per bullet.** No em-dash chains. Split.
- **Cut connective tissue.** "Importantly", "It's worth noting", "Going forward" — delete on sight.
- **One Diátaxis mode per document.** Reference (_how_ it currently works) / explanation (_why_ we decided) / how-to / tutorial. Don't mix modes; cross-link instead. The invoking skill states which mode applies.
- **If a section is one paragraph, it's probably wrong.** Split into bullets or cut.
