# Content Model

All content lives in `content/` as JSON. Git is the database. The site build reads these files; the MCP server and hook write them.

## Directory layout

```
content/
├── feed/                  # one file per entry: YYYY-MM-DD-slug.json
├── projects/              # one file per project
├── now.json               # what's happening this week
├── cv.json                # experience, skills, education, certifications
└── profile.json           # name, headline, links, avatar
```

## Feed entry

```json
{
  "id": "2026-07-08-dual-claude-accounts",
  "date": "2026-07-08",
  "type": "decision | problem-solved | shipped | learning",
  "tags": ["claude-code", "devx", "direnv"],
  "title": {
    "en": "Optional one-sentence headline that states the insight (~60 chars).",
    "pt": "Manchete opcional de uma frase que diz o achado."
  },
  "narrative": {
    "en": "Plain-language story: the problem, the decision, why it matters. 2-4 sentences a non-technical reader understands.",
    "pt": "A mesma história em português."
  },
  "technical": {
    "en": "Expandable detail: stack, approach, trade-offs. Markdown allowed.",
    "pt": "Detalhe técnico em português."
  },
  "outcome": {
    "en": "One line, measurable when possible. Optional.",
    "pt": "Uma linha, mensurável quando possível. Opcional."
  },
  "project": "living-portfolio",
  "status": "draft | published"
}
```

Notes:
- `title` is optional; without it the site falls back to the narrative's first sentence.
- `type` maps 1:1 to the four rubric criteria — it doubles as a visual badge on the site.
- `project` is optional: the id of a `content/projects/<id>.json` the entry belongs to. Besides linking, it drives the **zero window**: ids listed in `config/zero_window.json` (personal and open-source work) skip the 48h veto and merge on the Action's next run.
- `status`: `draft` while the entry sits on the `staging` branch; the drain writes it as `published` when it moves the entry into a `drafts/<date>` or `retidas/<date>` PR branch. The site only builds `main` and only renders `published`, so nothing shows before the merge — the merge is the publish, and the Action needs no commit step.
- Entries are immutable after publish; corrections are new commits (git history is part of the credibility).

## Project

```json
{
  "id": "living-portfolio",
  "featured": true,
  "title": { "en": "...", "pt": "..." },
  "summary": { "en": "...", "pt": "..." },
  "case_study": { "en": "markdown", "pt": "markdown" },
  "story": {
    "problem": { "en": "...", "pt": "..." },
    "decision": { "en": "...", "pt": "..." },
    "evidence": { "en": "...", "pt": "..." }
  },
  "metric": { "value": "−88%", "label": { "en": "execution time", "pt": "no tempo de execução" } },
  "stack": ["astro", "python", "mcp", "claude-code"],
  "links": { "repo": "https://...", "live": "https://..." },
  "period": { "start": "2026-07", "end": null }
}
```

`story` (problem → decision → evidence) and `metric` are optional; featured projects with a `story` render as the large two-column cards on the home page, the rest as compact rows.

## Now

```json
{
  "updated": "2026-07-08",
  "items": [
    { "en": "Migrating a BI stack between platforms for an enterprise client", "pt": "..." },
    { "en": "Studying for a BI platform certification", "pt": "..." }
  ]
}
```

Week-level granularity by design — it stays honest even during quiet stretches. The `updated` date renders on the site; the `update_now` MCP tool refreshes it.

## CV

`cv.json` mirrors the classic résumé sections (experience, skills, education, certifications, languages, awards), each field bilingual. It is the single source of truth: the site renders it, and a future `export_cv` tool can generate a PDF from it so the résumé and the site never drift apart.

## i18n rule

Every human-readable string is an `{ "en": ..., "pt": ... }` object. Both languages are written at commit time by the LLM — never left as a TODO. A missing translation fails the build, deliberately.
