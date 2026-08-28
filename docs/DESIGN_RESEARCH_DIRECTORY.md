# Design: the research directory (v3.2)

Status: approved 2026-08-28, implemented in v3.2. This document is the spec;
`docs/USER_MANUAL.md` is the user-facing description.

## Problem

Up to v3.1 every run was an island: one `lit/runs/<stamp>/` per search, one
report per run, no way to combine searches made over months, and no way to
bring in records obtained outside the tool (a Zotero library, a colleague's
RIS export, a Web of Science session, a reference list). A research project
— and a lab — accumulates all of these.

## Design principle

**A research directory is a folder, and its index is one JSON file.** No
database, no daemon, no new file formats. Everything the tool wrote before
stays where it was; the project layer is additive and discoverable by
listing directories, so a zip of the folder is the whole project.

## Layout

```
lit/                            one research directory = one project (--outdir)
  project.json                  index: name, description, labels, exclusions,
                                block aliases, defaults
  runs/<stamp>/                 automated searches, unchanged (librarian.py)
  manual/<name>/                sources ingested from outside (project.py ingest)
      source.json               provenance: kind, who, when, origin, method, note
      records.json              records in the common schema, backend "manual:<name>"
      <original file>           the input exactly as received
  inbox/                        drop files here; `project.py ingest --inbox` takes them
  journals/metrics.json         journal metrics store (journals.py)
  screening.json                project-wide PRISMA manual stages
  reports/<stamp>-<level>/      project reports (report.py --project)
  logs/                         one audit log per script invocation
  counts_history.csv            unchanged
```

`project.json`:

```json
{
  "name": "Topological materials review",
  "description": "free text",
  "created": "2026-08-28",
  "exclude": ["20260814T223331"],
  "labels": {"20260828T095041": "August full scan"},
  "block_aliases": {"X": "CD"},
  "defaults": {"level": "simple", "format": ["md"], "metric": "openalex_2yr"}
}
```

Members are **discovered**, not declared: every `runs/<stamp>` and every
`manual/<name>` that exists and is not in `exclude` belongs to the project.
`block_aliases` maps historical block names to canonical ones so a block
renamed between runs still lines up. The file is optional; a directory with
only `runs/` is a valid project with defaults.

## Record provenance

Records keep the v3 schema (`title year doi journal authors url abstract
cited_by block backend`) plus, where a backend provides it, `issn` and
`source_id` (used for journal metrics). Manual records carry
`backend = "manual:<name>"`. When the project merges members, each unique
record (same DOI, else first 90 chars of the lower-cased title) gets
`found_by = ["openalex@20260828T095041", "manual:zotero-aug", ...]` and
`first_seen = <earliest member date>`, which is what the differential and
overlap sections use.

## Ingest

```
python project.py ingest FILE [FILE...] --name NAME [--block B] [--kind auto|ris|bibtex|csv|json]
                          [--who WHO] [--origin TEXT] [--method database|citation|website|organisation|expert|other]
                          [--note TEXT] [--outdir lit]
python project.py ingest --inbox            # every file in lit/inbox/, name = file stem
python project.py status                    # members, counts, last report
python project.py init --name ...           # write project.json
```

Parsers: RIS (moved from `wos_manual.py`, which now imports it), BibTeX (a
small stdlib parser for the common entry types), CSV (flexible header match:
title, year, doi, journal, authors, url, abstract, block, cited), JSON (a
record list, e.g. `all_records.json` from another machine). `--method`
follows PRISMA 2020's "identification via other methods" categories, so
manual sources land in the right box of the flow diagram.
`wos_manual.py ingest` becomes a thin wrapper that ingests into
`manual/wos-<block>/` with `method=database`.

## Journal metrics

`journals.py` maintains `lit/journals/metrics.json`:

```json
{"1367-2630": {"name": "New Journal of Physics", "issn": ["1367-2630"],
               "openalex_id": "S...", "aliases": ["new journal of physics"],
               "metrics": {"openalex_2yr": {"2026": 2.9},
                           "scopus_citescore": {"2022": 5.8, "2023": 6.1},
                           "sjr": {"2023": 1.12}, "jcr_if": {"2023": 2.8}},
               "quartile": {"2023": "Q1"},
               "fetched": {"openalex": "2026-08-28"}}}
```

Providers, in order of availability:

| provider | key | what | history |
|---|---|---|---|
| `openalex` | none | `2yr_mean_citedness` (IF-like), h-index, i10, works/cites by year | snapshot per fetch year (OpenAlex serves only the current value) |
| `scopus` | SCOPUS_API_KEY | CiteScore per year, SJR, SNIP (serial title API) | full history from the API |
| `scimago` | none (manual CSV download) | SJR, H index, quartile for ~30k journals | one CSV per year, imported |
| `jcr` | proprietary | Journal Impact Factor | not fetchable; `import-csv --provider jcr --year` for licensed users |

Keys are ISSN when known, else a normalised name; record → journal matching
uses `issn` first, then the normalised `journal` string. `journals.py fetch`
collects every journal seen in the directory's records (runs + manual) and
fetches the providers available. Values are **appended by year, never
overwritten**, which is the evolution mechanism: refetch yearly and the
report shows the series. Fetching *all* journals is feasible only via the
SCImago CSV (one download) — OpenAlex's ~250k sources would take ~1,250
paged requests for no benefit — so "all journals" = `import-scimago`.

## Reports: project mode and filters

`report.py --project lit/` (or `--outdir lit --project`) merges all members
and renders the same document with these additions:

- Sources section: one row per member (run or manual) with date, method,
  records, unique contribution.
- PRISMA 2020 flow with **both identification columns**: databases (per
  backend, summed over runs) and other methods (per manual source, grouped
  by `--method`), each with its own duplicates-removed and screening path.
- Time: per-block counts over runs; new unique records per run
  ("what August found that June did not"); `first_seen` histogram.
- Journal metrics: a metric column in record tables, top venues by metric,
  and an evolution table for venues with two or more years on file.

Filters (project and single-run mode alike):

| option | meaning |
|---|---|
| `--since DATE --until DATE` | members by search date (run stamp / ingest date) |
| `--latest` | only the most recent member |
| `--diff` | differential: records first seen in members within the window |
| `--year-from Y --year-to Y` | publication year of records |
| `--backends ...` / `--blocks ...` | restrict databases / blocks |
| `--sources auto|manual|all` | which member kinds to include (default all) |
| `--records FILE ...` | extra RIS/BibTeX/CSV/JSON included as a transient manual source |
| `--metric NAME --min-metric X` | journal metric threshold (default metric from project.json) |
| `--min-citations N` | citation threshold |
| `--oa-only` | only records with a legal OA copy (needs `--pdfs` data) |
| `--top N` / `--sort cited|year|metric` | table size and order |
| `--level`, `--format`, `--basename`, `--out DIR` | as before |

## Logging and parameters (all scripts)

Every script accepts `--outdir` (research directory, default `lit`),
`--verbose`, `--quiet`, `--log-dir` (default `<outdir>/logs`) and writes
`<outdir>/logs/<script>_<stamp>_<pid>.log` containing the exact invocation, tool
version, Python version, every warning and error, and a one-line outcome.
Console output stays small by default. `--help` on every script lists every
input and output parameter with its default.

## Documentation

- `README.md` — product page; points humans to `AGENTS.md`.
- `AGENTS.md` — instructions written for an AI agent: commands, file
  schemas, workflows, hard rules (never scrape, never commit real queries).
- `docs/USER_MANUAL.md` → `docs/USER_MANUAL.html`, `docs/USER_MANUAL.pdf`
  (built by `docs/build_manual.py` with pandoc; the Markdown is the source).
  Every feature and every known limitation is listed there.

## Out of scope (v3.2)

Zotero Web API push, PDF downloading, snowballing, citation graphs — see
the roadmap. All remain compatible with this layout (a snowball pass would
simply be another `manual/<name>/` with `method=citation`).
