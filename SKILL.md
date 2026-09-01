---
name: literature-search
description: Search and fetch academic/scientific literature across multiple bibliographic databases at once (OpenAlex, NASA ADS, arXiv, INSPIRE-HEP, Scopus, Semantic Scholar, CORE, Crossref, Unpaywall, and Web of Science via a manual fallback) with scitech-librarian — the maintained, published, stdlib-only tool; never with an ad-hoc script or a copied "litscan". Use this whenever the user wants a literature review, asks to search or query scientific/academic databases, wants to check "what's been published on X", check novelty of an idea against the literature, build or update a project's research directory, produce a PRISMA search report, look up journal metrics, or mentions any of Web of Science, Scopus, OpenAlex, ADS, INSPIRE-HEP, Semantic Scholar, CORE, arXiv or Unpaywall by name — even if they only name one database, since the others are usually worth checking too. Also use it as the first step before deep-diving into a new research topic or before claiming something is or isn't novel.
---

# Literature search — run scitech-librarian, never a local copy

The tool is **scitech-librarian** (github.com/fabiocampolim-design/scitech-librarian,
Apache-2.0, Python 3.9+ stdlib only), maintained in exactly one place: the
user's clone of that repository. **No project carries a copy of it** — its
scripts are run from the clone with `--outdir` pointing into the current
project. Find the clone like this:

1. `SCITECH_LIBRARIAN_HOME`, if that environment variable is set.
2. Otherwise the directory that holds `librarian.py` next to `AGENTS.md` and
   `CITATION.cff` (search the user's projects for `**/scitech-librarian/librarian.py`).
3. If there is none, clone it (`git clone https://github.com/fabiocampolim-design/scitech-librarian`)
   and tell the user where you put it.

Read its `AGENTS.md` first when you need the full CLI, file schemas and hard
rules — it is written for you. This file ships in the repository as `SKILL.md`;
install it by copying it to `~/.claude/skills/literature-search/SKILL.md`, and
keep that copy byte-identical (the repository's test suite checks it).

## The six scripts

| Script | Does | Typical call |
|---|---|---|
| `librarian.py` | one query file → the same search on every reachable backend; raw records, RIS, CSV, `counts.md`, a PRISMA 2020 report; `--report-lang en|pt-BR|es|de|fr` (3.3.0+) | `python librarian.py --queries <proj>/lit/queries.json --outdir <proj>/lit` |
| `project.py` | a research directory: `project.json` index, ingested manual sources with provenance, inbox, `merge` (found_by / first_seen), `oa` Unpaywall pass | `python project.py --outdir <proj>/lit init|merge|ingest|oa` |
| `report.py` | single-run or `--project` reports; levels simple / intermediate / full; formats md html tex pdf txt; PRISMA + PRISMA-S; `--since/--until/--diff/--top/…` filters; `--lang en|pt-BR|es|de|fr` (or `"defaults": {"lang": …}` in `project.json`) | `python report.py --project <proj>/lit --report-level full --report-format md pdf` |
| `journals.py` | venue metrics per year (OpenAlex 2-yr, Scopus CiteScore/SJR/SNIP, SCImago CSV, JCR import) | `python journals.py fetch --outdir <proj>/lit` |
| `wos_manual.py` | Web of Science manual round-trip: `prep` query files + checklist, `walk` (clipboard), `ingest` exported RIS into the same schema | `python wos_manual.py prep --outdir <proj>/lit` |
| `render.py` | renderer library used by `report.py` (not called directly) | — |

Every script: `--help` lists every flag with its default, `--verbose/--quiet`,
an audit log per invocation under `<outdir>/logs/`, `--version`.

**Report languages (since 3.3.0).** Offer them when the user or the project is
Portuguese/Spanish/German/French-speaking. Only the report's *scaffolding* is
translated (headings, PRISMA stage names, checklist, explanations); records,
query strings, block titles/notes, backend names, flags, file names, JSON and
every log stay English — a project rule, guarded by the suite. Sample:
`samples/pt-BR/report.md` in the repository.

## Workflow

1. **Keys**: `.env` lives next to the scripts (gitignored; Scopus, ADS, CORE,
   WoS Starter, `OPENALEX_API_KEY`, contact email; template `.env.example` in
   the repository). Never copy it into a project, never commit it, and
   **rotate any key that ends up in a chat transcript** — Scopus keys have no
   revoke button. `librarian.py --selftest` says which backends are reachable.
2. **Queries**: copy the repository's `queries.example.json` to
   `<project>/lit/queries.json`. A block is a conjunction of disjunctions:
   `[[a, b], [c]]` = `(a OR b) AND c`; give each block a `title` and a `note`
   saying what a good hit looks like. The most valuable block is usually the
   deliberate intersection of two literatures you suspect never cite each
   other — a near-zero count there is a finding once every hit has been read
   by hand.
3. `--selftest`, then `--counts-only` (shape the blocks; tighten anything in
   the thousands — prefer narrowing over raising `--limit`, default 300 per
   backend, if the goal is a defensible completeness claim), then the full
   run; `--pdfs` (optionally `--pdf-blocks`) for the resumable Unpaywall pass.
4. Results: `<outdir>/runs/<timestamp>/` (records, `all_records.ris` for
   Zotero, `counts.md`, the REPORT, `run.log`); `<outdir>/counts_history.csv`
   accumulates across runs so drift is visible.
5. For a living review, `project.py init` once, then `merge` each run in and
   `ingest` manual sources (WoS exports, hand-found PDFs' metadata) so one
   `project.json` holds everything with provenance.

## Facts that save time (learned 2026-08)

- Windows `cmd.exe` does not treat `#` as a comment — a trailing
  `# explanation` breaks argparse; use PowerShell or drop it.
- OpenAlex has a **daily free request budget** ("Insufficient budget", HTTP 429,
  resets midnight UTC); the tools stop cleanly on it; `OPENALEX_API_KEY`
  raises it. Big `journals.py` fetches exhaust it fast.
- A free Semantic Scholar key does **not** raise its ~1 req/s ceiling.
- Crossref relevance search is meaningless for novelty checks; arXiv hangs on
  deeply nested booleans; ~15% of OpenAlex hits are non-curated junk (filtered
  unless `--keep-junk`).
- **CORE** is slow (40 s+ per request) and sometimes fails server-side
  ("Idle timeout reached"): best-effort, don't retry-loop; its value is
  repository/thesis content without DOIs.
- **WoS**: the full grammar is rarely licensed (the Expanded API is not in most
  institutional deals) — manual `wos_manual.py` round-trip. For narrow blocks
  Scopus + ADS + arXiv is in practice a superset; for broad sweeps WoS-only
  records ran 46–63% in a real test, mostly a fetch-limit artefact.
- **Dead ends checked 2026-08-16 against an institutional catalogue — do not
  re-investigate without new information:** Dimensions Analytics API, ProQuest
  Dissertations API, INSPEC, Reaxys (no API access); SciFinder/ChemSpider/
  PubChem are compound tools, not literature search.
- **Licence of results**: abstracts and counts carry each database's terms
  (CC0 for OpenAlex/arXiv/INSPIRE, ODC-BY for Semantic Scholar, no
  redistribution for Scopus/ADS/S2 data). Nothing downloaded goes into a
  public repository; cite and link instead.

## After the scan

- `all_records.ris` imports straight into Zotero (a Zotero MCP server can
  then search the library by meaning).
- Mine the reference lists of the downloaded PDFs (a PDF-extraction skill,
  if one is installed) — citation-graph gaps and vocabulary gaps are
  different failure modes, and this step has caught the most important
  references in past reviews.

## No stray copies

Anything that looks like `litscan.py` or a scitech-librarian module inside
another project is a stale copy — it drifts silently from the maintained
tool. Delete it and point the project at the clone (`--outdir` does the rest).
