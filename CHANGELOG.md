# Changelog

All notable changes to scitech-librarian. Dates are release dates.

## 3.2.9 — 2026-08-31

- Check-count sync hygiene (the 3.2.8 review's three notes): the sync writes
  docs back LF (`newline="
"`), so a contributor with `core.autocrlf=false`
  no longer gets a whole-file CRLF diff; a count phrase inside double quotes
  is treated as a quotation of a historical figure — never rewritten and not
  held to the current count (`count_mentions`/`rewrite_count`, shared by
  `build_manual.py` and the suite's guard); the built manual HTML is read
  once per suite run. All suite-guarded.

## 3.2.8 — 2026-08-31

- Check-count guard hardened end to end: `build_manual.py` refuses to sync
  the count from a suite run that crashed before its summary (a red but
  *complete* run still syncs); the count phrase pattern lives once, in
  `build_manual.CHECK_COUNT_RE`, and the suite imports it; the guard runs in
  the summary block (no "keep this last" fragility), holds each doc
  separately to the real count — README, manual, `AGENTS.md` (which now
  quotes the count) and the built `USER_MANUAL.html` — and a doc with no
  count sentence at all now fails instead of passing silently.
- The no-pandoc HTML fallback keeps the manual's front-matter title,
  subtitle and date, so the "HTML carries the version" guard holds on
  machines without pandoc too; guarded by the suite.

## 3.2.7 — 2026-08-31

- The v3.2.6 README quoted "189 checks" while the manual and the suite said
  190 (the count was re-synced by `build_manual.py` but not committed). The
  suite now guards that README, manual and `AGENTS.md` quote the real count,
  and `build_manual.py` syncs the count even when the suite is red (it counts
  PASS+FAIL lines), so the guard cannot block its own fix.
- LF-pin guard: git output is decoded as UTF-8 with replacement, so a
  localized git message can no longer abort the suite.
- Platform guard: "Linux and Windows" is rejected anywhere in the docs again
  (no legitimate use exists); the built `USER_MANUAL.html` must carry
  `VERSION` (catches a forgotten `build_manual.py` run).

## 3.2.6 — 2026-08-31

- The LF-pin guard added in 3.2.4 crashed the whole suite with
  `FileNotFoundError` on a machine without git, and false-failed for a
  `tools/` drop-in living inside another repository. It now judges only this
  repo's own checkout (a `.git` here): no `.git` → nothing to pin; in our own
  checkout a git error fails loudly instead of masking a missing pin.
- Platform guard: README must say "Linux, Windows and macOS" twice, any
  hard-wrap accepted; the negative match is anchored to the CI sentence.
- New guard: the manual's `subtitle: "version …"` must equal `VERSION`
  (CITATION.cff already was).

## 3.2.5 — 2026-08-31

- Post-release code-review fixes (same day): the manual and `AGENTS.md` still
  described CI as "Linux and Windows"; corrected, and the platform guard now
  covers README, manual and `AGENTS.md`. The LF-pin guard reads the effective
  attribute (`git check-attr eol`) instead of matching `.gitattributes` text,
  and passes outside a git checkout.

## 3.2.4 — 2026-08-31

- CI now runs the suite on macOS as well as Linux and Windows (Python 3.9
  and 3.13) — the only check a Windows-developed tool gets on that platform.
  The README's description of the CI platforms is updated to match, and the
  suite guards both (the matrix and the README wording).
- `.gitattributes` pins the vendored conformance checker and its wiring test
  to LF, so a Windows checkout with `core.autocrlf=true` keeps them
  byte-identical to the canonical copy; guarded by the suite.

## 3.2.3 — 2026-08-29

- Post-release code-review fixes (same day): `CITATION.cff` at 3.2.3; the
  non-affiliation note names Crossref; SPDX headers on the test suite and
  `docs/build_manual.py`; the suite now guards CITATION↔VERSION, the
  backend list in the note, the headers, and the operative liability clause.

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
