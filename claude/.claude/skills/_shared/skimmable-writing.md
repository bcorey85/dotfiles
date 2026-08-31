# Skimmable Writing Directive

Shared by `/eng-arch` and `/adr` — the single source of truth for the skimmability rules. Engineers in problem-solving mode scan headings (NN/g layer-cake pattern); they don't read. Write to be skimmed: trigger layer-cake scanning, then earn commitment reading with trust signals.

- **Headings = answers, not topics.** A layer-cake scanner must extract value without dropping into the body.

  | Topic (weak)           | Answer (strong)   |
  | ---------------------- | ----------------- |
  | Implementation details | Token interceptor |
  | Error section          | 401 handling      |

- **BLUF at every level.** Start each section with the claim, not the setup. Inverted pyramid all the way down.
- **Bullets for independent items, paragraphs for reasoning.** A causal chain — this, therefore that, which is why the alternative failed — belongs in prose. Bulleting it severs the logic and leaves a list of assertions with the argument deleted. Tables beat both for structured comparisons (endpoints, phases, options, before/after).
- **Code refs over descriptions.** `file:line` beats "the file that handles X". Cite the path; let the reader click.
- **Bold the load-bearing word** in a multi-line bullet: at most one per bullet, none at all in a one-line bullet. Past that density it stops cueing anything and turns into wallpaper.
- **One idea per bullet.** No em-dash chains. Split.
- **Cut filler, keep connectives.** Delete throat-clearing — "Importantly", "It's worth noting", "Going forward". Keep the words that carry logic: "because", "so", "which is why", "unless", "even though". Prose with every connective stripped stops sounding like an engineer explaining something and starts sounding like a machine listing assertions.
- **No rhetorical tics.** A sentence pattern used three or more times in one document is a tic rather than a style — the X-not-Y antithesis, the colon-then-punchline, the rule of three. Count them before finalizing and rewrite the repeats as plain sentences.
- **Uncertainty survives compression.** Cutting words never promotes a measured-once number, an unverified claim, or an assumption into a fact. Where the evidence is thin the sentence says so, at whatever length that takes.
- **One Diátaxis mode per document.** Reference (_how_ it currently works) / explanation (_why_ we decided) / how-to / tutorial. Don't mix modes; cross-link instead. The invoking skill states which mode applies.
