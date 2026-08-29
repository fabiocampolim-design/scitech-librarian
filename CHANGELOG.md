# Changelog

All notable changes to scitech-librarian. Dates are release dates.

## 3.2.3 — 2026-08-29

- Licence: MIT → **Apache License 2.0** (`LICENSE`, `NOTICE`, SPDX headers,
  `CITATION.cff`). Same freedoms for users; adds an explicit patent grant, a
  contributor licence and a fuller limitation of liability. The README's
  Licence section carries the disclaimer and a non-affiliation note for every
  database queried, and the suite guards both.

## 3.2.2 — 2026-08-29 (whole-project review)

- arXiv driver pages as far as `--limit` asks (a hard 3-page cap silently
  truncated `--limit` > 300).
- The "hit the `--limit` cap" suggestion counts filtered venues per
  block/backend pair, not per backend.
- `--init-backends` writes `backends.json` next to `.env`/`queries.json`
  (the project root for a `tools/` drop-in); `wos_manual.py` closes its
  audit log; CI lints `render.py` too.
- `.env.example` rewritten (no stale script name or consortium-specific
  wording; `S2_API_KEY` / `CORE_API_KEY` placeholders); `.gitignore` covers
  `queries*.json` except the example, `.pytest_cache/`,
  `.claude/settings.local.json`.
- Docs: manual lists every CLI flag (`--queries`, `--backends-file`,
  `--timeout`, `--list`, `oa --members`, `import-csv --issn-col/--delimiter`,
  `wos_manual --queries`), sample sizes corrected to the CC0 sample,
  FUTURE_BACKENDS no longer claims the Zotero push is done. A docs-guard
  test now fails when a `--help` flag is missing from the manual or
  AGENTS.md. Samples regenerated under one version.

## 3.2.1 — 2026-08-28 (review follow-up)

- Code-review pass: BibTeX keys survive malformed author names and >26
  collisions; LaTeX specials escaped in `.bib`; CSL type agrees with BibTeX
  for preprints; `merge` keeps the provenance of already-merged records;
  one shared Unpaywall cache helper (failed lookups are retried, stats count
  unique DOIs); inbox ingest leaves no empty directory behind; lazy WoS
  blocks answer `in`/`get()`.

- `render.py` split out of `report.py` (renderers, PRISMA diagrams, PDF chain).
- One deduplication rule everywhere: runs now use `project.merge` (records
  carry `found_by` / `first_seen` from the first run on).
- `project.py oa`: post-hoc Unpaywall pass over runs and manual sources.
- BibTeX (`all_records.bib`) and CSL-JSON (`all_records.csl.json`) outputs;
  RIS/BibTeX/CSL carry the block as a keyword.
- Inbox ingest skips a malformed file instead of stopping; audit-log handles
  closed on exit; `wos_manual.py` loads queries lazily; identical-search
  suggestion in project reports; clearer OpenAlex snapshot note.
- Tests: pytest-collectable, CLI smoke tests, budget-stop, inbox and OA
  cases; pyflakes clean.

## 3.2 — 2026-08-28

- **Research directories** (`project.py`): `project.json` index (labels,
  exclusions, block aliases, defaults), members discovered from `runs/` and
  `manual/`, ingest of RIS / BibTeX / CSV / JSON with provenance and PRISMA
  method, inbox folder, merge with `found_by` / `first_seen`.
- **Project reports** (`report.py --project`): sources table with "new
  here", timeline, PRISMA 2020 flow with both identification columns,
  `screening.json`; filters `--since/--until/--latest/--diff/--year-from/
  --year-to/--backends/--blocks/--sources/--records/--metric/--min-metric/
  --min-citations/--oa-only/--top/--sort` in both modes.
- **Journal metrics** (`journals.py`): OpenAlex 2-year mean citedness,
  Scopus CiteScore / SJR / SNIP (by ISSN or title), SCImago CSV, Journal
  Citation Reports CSV (`import-jcr`), generic CSV; values per year;
  `list --missing`; metric column, venues-by-metric and evolution tables.
- Every script: `--outdir`, `--verbose`, `--quiet`, `--log-dir`,
  `--version`, an audit log per invocation; `wos_manual.py` registers Web
  of Science exports as manual sources.
- OpenAlex daily budget handled (clear error, `OPENALEX_API_KEY` support);
  `issn` field on records; published venue preferred over an arXiv label
  when merging.
- Docs: `AGENTS.md`, `docs/USER_MANUAL.{md,html,pdf}`, `docs/WALKTHROUGH.md`,
  `docs/JCR_IMPORT.md`, design and dev-plan notes; `samples/` rebuilt from
  CC0 sources only; `CITATION.cff`; pyflakes in CI.

## 3.1 — 2026-08-28

- Literature-search reports at three levels (simple / intermediate / full)
  in Markdown, HTML, LaTeX, PDF and plain text, with a PRISMA 2020 flow
  diagram, PRISMA-S checklist and rule-based suggestions; PDF via
  xelatex / lualatex / pdflatex → pandoc → built-in writer.
- Runs write `meta.json`, `blocks.json`, `junk.json`.
- OpenAlex abstracts keep repeated words (inverted-index rebuild fixed).

## 3.0 — 2026-08-26

- First public release: declarative backends (databases as JSON config),
  offline test suite, CI on Linux and Windows, ToS-compliance stance,
  manual Web of Science companion.
