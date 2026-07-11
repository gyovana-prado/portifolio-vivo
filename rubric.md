# Relevance Rubric

This is the heart of the system: the criteria the LLM uses at session end to decide whether work is portfolio-worthy, and the rules for sanitizing it. It is versioned in the repo on purpose — if you fork this project, adapting the rubric to your own bar is expected.

## The question being answered

Not "what did I do today?" but: **does this session contain evidence that this person knows how to do hard things — evidence worth showing to anyone, right now?**

A living portfolio is not a diary. Most sessions should produce **nothing**, and that is the system working correctly. Logging everything is the fastest way to bury the signal.

## Log the session if it contains at least one of:

1. **A non-obvious technical decision with a real trade-off.**
   "Chose X over Y because Z" where a competent peer might reasonably have chosen Y. The decision and its reasoning are the content — this is where judgment shows.

2. **A hard problem solved, with a measurable or observable result.**
   Performance improvements, migrations completed, incidents resolved. Numbers when they exist ("88% faster"), concrete before/after when they don't.

3. **Something that exists now and didn't this morning.**
   A shipped skill, an MCP server, a pipeline, a data model, a tool. Creation is inherently demonstrable.

4. **A learning applied in practice for the first time.**
   Not "read about X" — "used X to solve a real problem." First real-world application of a technique or tool.

## Never log:

- Routine configuration, environment setup, dependency wrangling
- Ordinary debugging with no insight worth transferring
- Meetings, planning, status updates
- Repetition of work already logged (the tenth dbt model like the first nine)
- Anything whose only content is effort ("worked 6 hours on...") — effort is not evidence

## The final test

Before committing, the evaluator must pass the entry through this filter:

> Would a senior engineer reading this think *"interesting — how did she do that?"* — or scroll past?

If scroll: discard. No exceptions for slow weeks. A quiet feed is honest; a padded feed is noise wearing a portfolio costume.

## Sanitization rules

Confidentiality is enforced by **information category**, not by name substitution. Removing a client's name while keeping "BI migration for a São Paulo real-estate marketplace" still identifies the client.

**Never include:**
- Client or employer-client names, product names, brand names
- Industry + geography + scale combinations that narrow to an identifiable company
- Business metrics, revenue figures, user counts, contract terms
- Internal system names, repository names, colleague names
- Timelines that could map to a known client engagement

**Always allowed (this is the actual portfolio content):**
- The technical problem class ("migrating 40 dbt models between warehouses")
- Technologies, patterns, and architectures used
- The reasoning behind decisions
- Quantified technical outcomes ("query time reduced 88%") without business context
- Generic role of the counterpart ("a BI consultancy client", "an enterprise client")

**When in doubt, generalize up one level.** "A client in retail fitness" → "an enterprise client". The technical story loses nothing; the confidentiality risk drops to zero.

**Contract awareness.** Before enabling the pipeline, the owner must verify their service contracts allow disclosing *that the work exists*, not just its details. Some agreements restrict acknowledging the engagement itself. This system cannot check that for you.

## Entry format produced by the evaluator

Every logged entry is written in **two layers × two languages** at commit time:

- **Narrative layer** (plain language, EN + PT): the problem, the decision, why it matters — readable by a non-technical person, conveying *why this was hard*.
- **Technical layer** (expandable, EN + PT): stack, approach, trade-offs — enough for a technical reader to verify depth.

See [content-model.md](content-model.md) for the schema.
