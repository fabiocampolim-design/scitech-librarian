# scitech-librarian

[![Tests](https://github.com/fabiocampolim-design/scitech-librarian/actions/workflows/tests.yml/badge.svg)](https://github.com/fabiocampolim-design/scitech-librarian/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Dependencies: stdlib only](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)](librarian.py)
[![Plays by the rules](https://img.shields.io/badge/APIs-documented%20%26%20ToS--compliant-blueviolet)](#plays-by-the-rules)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**One query, every scholarly database — and a research directory that
remembers every search, every record you brought in by hand, and writes the
PRISMA report for all of it.**

Write a structured query once; scitech-librarian renders it into the native
syntax of eight bibliographic databases (OpenAlex, NASA ADS, arXiv,
INSPIRE-HEP, Scopus, Semantic Scholar, Crossref, Web of Science), runs them
all, and archives the run — raw records, RIS for Zotero, the exact query
string sent to each backend, hit counts — in a timestamped directory you can
cite. Runs accumulate in a **research directory**: a folder per project that
also takes records obtained outside the tool (Zotero, Mendeley and Web of
Science exports, a colleague's RIS, a reference list) with their
provenance, keeps journal metrics year by year, and produces a
**literature-search report** — search strategy, results, **PRISMA 2020 flow
and PRISMA-S checklist**, timeline, what each search added, venue metrics,
suggestions — for one run or for the whole project, filtered by date,
source, database, year, citations or venue quality, in Markdown, HTML,
LaTeX, PDF or plain text at three levels of detail. A lab runs one
directory per project. Databases are **configuration, not code**.

Standard library only, no install step: five files — `librarian.py`
(search), `project.py` (research directory and ingest), `report.py`
(reports), `journals.py` (venue metrics), `wos_manual.py` (Web of Science
by hand). Full documentation: [**User Manual**](docs/USER_MANUAL.md)
([HTML](docs/USER_MANUAL.html) · [PDF](docs/USER_MANUAL.pdf)); a start-to-PRISMA
[**walkthrough**](docs/WALKTHROUGH.md) of a real project exercises every
feature; [JCR import](docs/JCR_IMPORT.md) covers the licensed Impact Factor. Working with
an AI agent? Hand it [**AGENTS.md**](AGENTS.md) — the complete
machine-oriented instructions — and say *"read AGENTS.md, then run a
novelty check on X"*.

```bash
python librarian.py --selftest                       # ping every backend; report what works
python librarian.py --counts-only                    # fast: hit counts for every query block
python librarian.py --pdfs                           # full run + legal open-access PDF lookup
python project.py ingest export.ris --name zotero --method citation   # records from outside
python report.py --project --since 2026-06-01 --diff # what the searches since June added
python journals.py fetch                             # venue metrics (OpenAlex, no key)
```

> **Feedback is highly appreciated.** If a database misbehaves, a count looks
> wrong, or you've written a `backends.json` entry for a database we don't
> ship, please
> [open an issue](https://github.com/fabiocampolim-design/scitech-librarian/issues) —
> config entries for new databases are especially welcome.

**Why this exists.** A literature search you cannot rerun is a claim you
cannot defend. Systematic reviews and novelty checks ("no one has done X")
depend on exactly which databases you asked, with exactly which query, on
exactly which day — yet that record almost never survives. This tool was built
for a physics PhD's novelty checks and keeps that record by construction:
every run archives its queries, counts and records, so six months later the
search is reproducible and the counts' drift is visible.

## Plays by the rules

This tool is strict about the terms of service of every database it touches —
not as fine print, but as a design principle:

- **Documented public APIs only.** It never scrapes a web interface. Scraping
  Web of Science or Scopus breaches their terms and can get your entire
  institution's access suspended.
- **Web of Science without an API licence is a manual job, so we made the
  manual job small** — `wos_manual.py` prepares every query in WoS's own
  grammar, walks you through pasting them into the official UI, and ingests
  your RIS exports back into the same record schema. Paste, export, done.
- **No Google Scholar.** It has no API, and scraping it violates its terms.
- **Rate limits respected** — per-backend sleeps (arXiv's requested ≥3 s
  between calls included) and a contact email in the User-Agent, which also
  puts you in OpenAlex/Crossref's faster "polite pool".
- **PDFs via Unpaywall only** — legal open-access copies, never paywall
  circumvention.
- **Entitlement is honoured, not worked around** — Scopus results come
  through your institution's subscription (campus network or VPN), and the
  README documents how that access actually works.

## Features

- **One structural query, eight native grammars.** `[[a, b], [c]]` means
  `(a OR b) AND c`; each backend's syntax — `TITLE-ABS-KEY(...)`,
  `TS=(...)`, `abs:"..."`, lowercase `and` — is generated from the same
  definition, so queries never drift out of sync between databases.
- **Databases are data.** Every backend is a JSON entry: query grammar,
  endpoint, auth header, pagination style, and dotted paths into the
  response. `--init-backends` writes the defaults to `backends.json`; edit it
  to add, change or disable databases without touching code. Only engines
  that genuinely need code (arXiv's XML feed) use a small driver.
- **Everything is archived.** Each run writes a timestamped directory with
  raw JSON records, per-block RIS, a deduped combined CSV/RIS/JSON, the exact
  query string sent to each backend, counts as JSON and a paste-ready
  markdown table, run metadata, and a full log. Counts also append to a
  history file so drift over time is visible.
- **A research directory, not a pile of runs.** `project.py` indexes every
  run and every record you bring in from outside (RIS, BibTeX, CSV, JSON —
  Zotero, Mendeley, Web of Science, reference lists; an inbox folder for
  collaborators), keeps provenance (who, when, where from, PRISMA method),
  merges everything with `found_by` / `first_seen` per record, and
  `report.py --project` describes the whole project: what each search
  added, which database found what nobody else did, count drift over time,
  and a PRISMA flow with both identification columns. Filters by date
  window, differential ("new since June"), source kind, database, block,
  publication year, citations, venue metric. One directory per project;
  a lab has several.
- **Journal metrics, year by year.** `journals.py` fetches OpenAlex 2-year
  mean citedness (no key) and Scopus CiteScore/SJR/SNIP (key), imports
  SCImago CSVs and licensed JCR exports, stores values per year so the
  series builds up, and feeds a metric column, a venues-by-metric table, an
  evolution table and `--min-metric` into reports.
- **Logs and audits.** Every script writes an audit log (invocation,
  versions, every warning) under `<outdir>/logs/`; console output is small
  by default, `--verbose` / `--quiet` / `--log-dir` / `--outdir` on all of
  them; `--help` lists every parameter with its default.
- **A literature-search report, PRISMA included.** Every run ends with
  `report.md` (or HTML / LaTeX / PDF / plain text): the search strategy with
  the exact string sent to each database, a results summary, a **PRISMA 2020
  flow diagram** whose automatable stages are filled from the run, a
  **PRISMA-S** search-reporting checklist, the top records per block, and
  rule-based suggestions (tighten this block, rerun that backend, raise the
  cap, read these five hits by hand). Three levels — `simple`,
  `intermediate`, `full` — from a two-page summary to every record with its
  abstract and the complete log. See [Reports and PRISMA](#reports-and-prisma).
- **Crash-proof by checkpointing.** Counts are saved after *every* API call
  and Ctrl-C is safe — a hang late in a long run loses nothing.
- **A junk filter with receipts.** OpenAlex indexes non-curated repositories;
  on a 5,146-record run, 15.3 % of its records came from Zenodo, SSRN,
  Figshare and the like — versus 0 % for ADS, Scopus, Semantic Scholar and
  INSPIRE. On one decisive novelty query that was the whole difference
  between 16 hits and 3. Filtered by default; `--keep-junk` disables.
- **Works with zero affiliation.** Five backends need no key and no
  institution; ADS needs only a free personal token. No VPN, no campus
  network, no subscription — those matter only if you add Scopus or the WoS
  API on top.
- **Physics gets first-class coverage.** NASA ADS and INSPIRE-HEP are
  backends no comparable tool ships; for refereed physics, ADS is essentially
  complete.
- **Novelty checks as a workflow.** Design blocks so a *small* number is the
  informative outcome, run the same blocks over time, watch the counts —
  then read every hit by hand before claiming a gap.
- **Offline-testable.** 157 checks run with no network and no keys (backends
  are exercised against canned API responses; the research directory, ingest
  parsers, journal store and report generator against synthetic
  directories); CI on Linux and Windows, Python 3.9 and 3.13.

## The databases: what each is actually good for

| Database | Key needed | Coverage | Use it for | Watch out for |
|---|---|---|---|---|
| **OpenAlex** | none | ~250M works, incl. preprints | first pass, always works, no institution needed | ~15 % non-curated junk — filtered by default |
| **NASA ADS** | free token | complete refereed physics + astronomy, arXiv merged in | **best single source for physics** | none serious |
| **arXiv** | none | preprints, all fields | brand-new work | chokes on nested booleans — see Pitfalls |
| **INSPIRE-HEP** | none | HEP, lattice QCD, particle theory | literature invisible to general indexes | narrow field scope |
| **Scopus** | free key + institution | ~27–28k curated journals | citation-grade counts for papers | entitlement is IP-based; needs campus network or VPN |
| **Semantic Scholar** | none | broad, good citation graph | cross-checking | ~1 req/s without a key |
| **Crossref** | none | DOI metadata for ~150M items | resolving DOIs | **no boolean support** — counts meaningless, excluded from default runs |
| **Web of Science** | licensed | ~21–22k curated journals | conventional legitimacy | API usually not licensed — use `wos_manual.py` |

**If you only set up two:** OpenAlex (works instantly) and NASA ADS
(30-second free token). Add Scopus if you need citation-grade counts for a
paper. **Coverage reality check:** Scopus indexes ~25–30 % more journals than
WoS and 80–85 % of WoS journals are also in Scopus; for physics ADS is
essentially complete — so Scopus + ADS + arXiv is, in practice, a superset of
WoS.

## Getting the keys

Copy `.env.example` to `.env` and fill it in — the script reads it
automatically, no shell variables to set.

- **NASA ADS** — <https://ui.adsabs.harvard.edu/user/settings/token>. Log in,
  generate, paste. Highest value per minute spent.
- **Scopus / Elsevier** — <https://dev.elsevier.com/apikey/manage>. Free,
  instant. The key authenticates *you*; entitlement comes from your
  institution's subscription, so be on the campus network or VPN (a 401/403
  usually means a network problem, not a bad key). **Elsevier has no revoke
  button** — a leaked key is burned, not disabled. Optionally ask your library
  for an InstToken, which removes the VPN dependency.
- **Semantic Scholar** — optional; works keyless at ~1 req/s.
- **Web of Science** — see the manual companion below; the Starter key's
  restricted grammar makes the API rarely worth it.

**No institution? Most of it still works.** Five of the eight backends
(OpenAlex, arXiv, INSPIRE-HEP, Semantic Scholar, Crossref) need no key and no
institutional access at all, and NASA ADS needs only a free personal token —
so the tool is fully usable from any laptop, with zero affiliation and no
VPN. Institutional entitlement matters only for Scopus (and the licensed WoS
API): there the key authenticates *you*, but results flow through your
institution's subscription, which is typically IP-based — be on the
institutional network, or use whatever VPN, proxy or federated login your
institution provides, before the API will return anything. The test is
always the same: run `--selftest` and see whether Scopus returns a plausible
number.

## Writing queries

Queries live in `queries.json` (copy `queries.example.json` and edit):

```json
{
  "NOV": {
    "title": "my novelty check",
    "note":  "a SMALL number is the good outcome",
    "groups": [
      ["origami", "kirigami"],
      ["acoustic metamaterial", "phononic crystal"],
      ["topological pumping", "edge state"]
    ],
    "arxiv_groups": [0, 2]
  }
}
```

`groups` is a conjunction of disjunctions. `arxiv_groups` optionally names
which (at most two) groups go to arXiv, which degrades on deeply nested
booleans. The most valuable block is usually a deliberate intersection of two
literatures you suspect don't talk to each other — a near-zero result is a
finding, not a failure, *if* you then read every hit by hand.

## Adding a database (no code)

```bash
python librarian.py --init-backends     # writes backends.json for editing
```

A backend entry declares the query grammar, the request, and where the data
lives in the response:

```json
"europepmc": {
  "syntax":  {"term": "always"},
  "request": {"url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
              "params": {"query": "{q}", "format": "json", "pageSize": "{n}",
                         "cursorMark": "{cursor}"},
              "paging": {"style": "cursor", "next": "nextCursorMark", "start": "*"}},
  "parse":   {"total": "hitCount", "items": "resultList.result",
              "fields": {"title": "title", "year": "pubYear", "doi": "doi",
                         "journal": "journalTitle"}}
}
```

Paging styles: `cursor`, `page`, `offset`, `none`. Auth is an env var mapped
to a header. Field paths support `[0]` indexing, `[]` mapping over lists,
`a|b` fallbacks, and named transforms. `docs/FUTURE_BACKENDS.md` has vetted
starting points for Europe PMC, CORE, DOAJ, OpenAIRE, DBLP and PubMed.
Entries in `backends.json` overlay the built-in defaults by name;
`"disabled": true` removes one.

## Web of Science, the honest situation

The full `TS=`/`NEAR` grammar lives in the separately-licensed **Expanded
API**, which national consortium deals typically don't include; the free
**Starter** tier rejects complex booleans. If your library can't get you
Expanded credentials, WoS is a manual job — and `wos_manual.py` makes it a
small one:

```bash
python wos_manual.py prep      # query files + CHECKLIST.md, in WoS grammar
python wos_manual.py walk      # copies each query to your clipboard in turn
python wos_manual.py ingest    # parses your RIS exports into the same schema
python wos_manual.py status    # what you have collected so far
```

The checklist encodes the UI settings that silently break queries (Core
Collection not All Databases; Advanced not Basic; which editions; tagged
`TS=(...)` vs bare form — pasting a tagged query into a dropdown-selected
field gives *"Search Error: Invalid query"*). `ingest` merges manual results
with the automated ones, same schema, same analysis.

## How this compares

[findpapers](https://github.com/jonatasgrosman/findpapers) is the closest
tool: one boolean query across eight databases (IEEE and PubMed included),
with deduplication, refinement, and PDF downloading — a strong choice for
software-engineering-style systematic reviews on Python 3.11+.
[litstudy](https://github.com/NLeSC/litstudy) analyses a collection you
already have (bibliometrics, network graphs, topics) in Jupyter.
[paperscraper](https://github.com/jannisborn/paperscraper) is built for life
sciences (PubMed + preprint servers) with impact-factor and dump tooling.

This tool's niche: **the reproducible search instrument**. Zero-install
single file; the only one with NASA ADS and INSPIRE-HEP (physics); archived,
citable runs with exact query strings and count history; databases as user
config; and a strict documented-APIs-only stance (both findpapers and this
tool use the official WoS Starter API; paperscraper scrapes Google Scholar —
we refuse). If you need IEEE/PubMed today or in-tool PDF collection, use
findpapers; if you need bibliometric graphs, litstudy; for auditable searches
and physics coverage, this one.

## Pitfalls we hit, so you do not have to

(The [User Manual](docs/USER_MANUAL.md) §12 lists every feature and every
known limitation in one place.)

- **arXiv hangs on deeply nested booleans** — not an error, it just never
  returns. At most two groups are sent (`arxiv_groups` chooses which), over
  HTTPS, with a short timeout, because an automatic "most selective" heuristic
  chose wrong.
- **Counts are not comparable across backends.** Proximity operators are
  dropped and stemming differs. Discover here; quote WoS/Scopus in the paper.
- **Windows `cmd.exe` does not treat `#` as a comment** — a pasted trailing
  `# note` becomes an argparse error. Use PowerShell or drop the comment.
- **Unpaywall is one HTTP call per DOI** (~20 min for 3,000). Restrict with
  `--pdf-blocks`; results are cached across runs.

## Output

Every run writes `lit/runs/<timestamp>/`:

```
report.md (html, tex, pdf, txt)  the literature-search report, see below
counts.json / counts.md          hit counts + a paste-ready markdown table
queries.json                     the EXACT query sent to each backend
blocks.json                      the structural query definitions used
meta.json                        run settings, backend endpoints, version, timing
records/<block>_<backend>.json   full records, raw
ris/<block>_<backend>.ris        per-block RIS for Zotero
all_records.{json,csv,ris}       deduped by DOI, sorted by citation count
junk.json                        records removed by the venue filter (with receipts)
prisma.json                      manual PRISMA screening stages -- fill in, re-render
run.log                          everything printed, including errors
```

plus `lit/counts_history.csv`, appended every run, and the research
directory around it:

```
lit/
  project.json                  index: name, labels, exclusions, block aliases, defaults
  runs/<stamp>/                 automated searches (above)
  manual/<name>/                ingested sources: source.json (provenance), records.json, the original file
  inbox/                        drop RIS/BibTeX/CSV/JSON here; `project.py ingest --inbox`
  journals/metrics.json         venue metrics per year (journals.py)
  screening.json                project-wide PRISMA manual stages
  reports/<stamp>-<level>/      project reports (report.py --project)
  logs/                         one audit log per script invocation
```

## The research directory

```bash
python project.py init --name "Topological materials review"
python project.py ingest export.ris --name zotero-aug --block CD --method citation \
       --who "A. Colleague" --origin "Zotero group library"
python project.py ingest --inbox                 # everything dropped in lit/inbox/
python wos_manual.py ingest                      # Web of Science exports become manual sources
python project.py status
python report.py --project                       # everything merged
python report.py --project --since 2026-06-01 --diff --format pdf   # what is new since June
python report.py --project --backends ads scopus --min-metric 3 --metric scopus_citescore
```

Records from outside arrive three ways: the command line (with full
provenance), an inbox folder (drop and ingest), or the Web of Science
routine. They keep the original file, get the common record schema, are
tagged `manual:<name>`, and their `--method` (database, citation, website,
organisation, expert, other) places them in the PRISMA flow. Manual
sources appear in every table like one more database — including "found
only here", which is how you learn what your colleague's reference list
had that six databases did not.

## Reports and PRISMA

A search you cannot report is a search you cannot defend, so every run ends
with a report. `--report-level` picks the detail, `--report-format` the
files; `report.py` re-renders any archived run without touching the network.

| Level | What you get |
|---|---|
| `simple` (default) | run metadata; sources (project); search strategy (structural query + the exact string sent to each backend); results summary; timeline (project); PRISMA 2020 flow + PRISMA-S checklist; top 10 records per block; suggestions |
| `intermediate` | + every unique record; each source's marginal contribution ("found only here"); year / venue / author distributions; journal metrics and their evolution; venues removed by the filter; errors; open-access stats; count drift against earlier runs |
| `full` | + every record with full abstract and author list, and which sources found it; per-source raw lists before deduplication; the filtered records; backend endpoint configuration; project and source provenance files; the complete run log; environment |

Formats: `md`, `html` (self-contained, light/dark, printable), `tex`,
`pdf`, `txt`. The PDF is compiled from the LaTeX with xelatex / lualatex /
pdflatex if one is installed, else with pandoc, else by a built-in
dependency-free writer — the option never fails, only the typesetting
degrades.

**PRISMA.** The report carries a [PRISMA 2020](https://www.prisma-statement.org/)
flow diagram (SVG in HTML, TikZ in LaTeX/PDF, ASCII in Markdown/text). The
stages a tool can know are filled from the data — records identified per
database, records identified via other methods (manual sources by method),
records removed by automation (the venue filter), duplicates removed,
records left to screen — and are honest about the difference between
*identified* (what each database reports) and *retrieved* (what was
downloaded within `--limit`). The stages only a human can know — screened,
excluded, sought, assessed, included, with exclusion reasons, for both
columns — are read from `prisma.json` (one run) or `screening.json`
(research directory); a template is written on the first report, so fill it
in as you screen and re-run `report.py`. A
[PRISMA-S](https://doi.org/10.1186/s13643-020-01542-z) search-reporting
checklist (all 16 items) is auto-completed where the tool has the data —
databases, full strategies, limits, filters, dates, totals, deduplication
method, updates — and marks the rest "to be completed".

```bash
python librarian.py --report-level intermediate --report-format md html
python report.py lit/runs/20260815T095908 --level full --format pdf
python report.py --latest --format txt            # newest run, plain text
python librarian.py --no-report                   # search only
```

Report filters (both modes): `--since/--until DATE`, `--latest`, `--diff`,
`--year-from/--year-to`, `--backends`, `--blocks`, `--sources auto|manual|all`,
`--records FILE…` (extra RIS/BibTeX/CSV/JSON for this report only),
`--metric NAME --min-metric X`, `--min-citations N`, `--oa-only`, `--top N`,
`--sort cited|year|metric`. Filters are printed in the report's metadata and
in PRISMA-S item 9, so a filtered report is never mistaken for the whole
search.

## Journal metrics

```bash
python journals.py fetch                                   # every journal seen in lit/: OpenAlex (+ Scopus with a key)
python journals.py import-scimago scimagojr_2024.csv --year 2024 --all
python journals.py import-csv jcr.csv --provider jcr_if --year 2023 --name-col "Journal name" --value-col JIF
python journals.py show --metric scopus_citescore
```

`lit/journals/metrics.json` keeps one entry per journal (ISSN-keyed) with
values **per year, never overwritten** — refetch next year and the report
shows the series. Providers: OpenAlex 2-year mean citedness and h-index (no
key; snapshot per fetch year), Scopus CiteScore / SJR / SNIP (key; full
history), SCImago SJR / H index / quartile (one CSV download per year, the
route to *all* ~30,000 journals), and the Clarivate Journal Impact Factor —
proprietary, no free API, import-only from a licensed export. The tool will
not scrape it.

### Sample reports

[`samples/`](samples/) holds one real run of the four example blocks in
`queries.example.json` against the three **CC0-licensed** databases
(OpenAlex, arXiv, INSPIRE-HEP; 2026-08-28: 5,705 hits identified, 1,286
records retrieved, 1,226 unique) rendered at every level in every format —
`simple` is 6 pages, `intermediate` 68, `full` 427. Excerpts from the PDFs:

| `simple`, p. 1 — run metadata and search strategy | `simple`, p. 3 — PRISMA 2020 flow |
|---|---|
| [![](samples/img/simple_p1.png)](samples/simple/report.pdf) | [![](samples/img/simple_p3.png)](samples/simple/report.pdf) |

| `simple`, p. 2 — exact query per backend, counts | `full` — records with abstracts |
|---|---|
| [![](samples/img/simple_p2.png)](samples/simple/report.pdf) | [![](samples/img/full_records.png)](samples/full/report.pdf) |

Browse: [simple](samples/simple/report.md) ·
[intermediate](samples/intermediate/report.md) ·
[full](samples/full/report.md) (Markdown, rendered by GitHub), or the
`.html`, `.tex`, `.pdf`, `.txt` next to each.

[`samples/project/`](samples/project/) is the same example as a **research
directory**: two runs (an OpenAlex-only first pass and the full CC0 run)
plus a colleague's reference list ingested as a manual source, with
OpenAlex 2-year mean citedness on file for 103 venues —
`report.md/html/tex/pdf/txt` (simple), `report_intermediate.md`, and
`report_diff.md` (`--since 2026-08-28 --diff`).

| `project`, p. 1 — sources and what each added | `project`, p. 3 — PRISMA with both identification columns |
|---|---|
| [![](samples/img/project_p1.png)](samples/project/report.pdf) | [![](samples/img/project_prisma.png)](samples/project/report.pdf) |

**Why only three databases in the samples.** OpenAlex, arXiv and INSPIRE
publish their metadata under CC0, so their records — abstracts included —
can be redistributed here. Scopus, NASA ADS and Semantic Scholar data come
under their own API terms (Scopus: no redistribution outside your
institution; Semantic Scholar: ODC-BY), so reports built on them are for
your own research directory, not for a public repository. The tool runs
all eight; the samples show three.

## Command reference

```
python librarian.py --selftest              ping every backend; report what works
python librarian.py                         all blocks, all configured backends
python librarian.py --counts-only           fast: hit counts, no record fetch
python librarian.py --blocks A CD           selected blocks
python librarian.py --skip arxiv            exclude a misbehaving backend
python librarian.py --pdfs --pdf-blocks A   legal OA-PDF lookup, restricted
python librarian.py --queries mine.json     use a different query file
python librarian.py --backends-file b.json  use a different backends config
python librarian.py --init-backends         write defaults to backends.json
python librarian.py --list                  blocks + backend readiness
python librarian.py --report-level full     simple | intermediate | full (default simple)
python librarian.py --report-format md pdf  any of md html tex pdf txt (default md)
python librarian.py --no-report             skip the report
python librarian.py --outdir DIR            another research directory (all scripts)
python report.py <run dir> | --latest       re-render an archived run (--level, --format)
python report.py --project [filters]        the whole research directory
python project.py init|status|ingest|exclude|include|label|alias
python journals.py fetch|import-scimago|import-jcr|import-csv|list|show
python wos_manual.py prep|walk|ingest|status
```

Every script: `--help` lists every parameter with its default; `--outdir`,
`--verbose`, `--quiet`, `--log-dir` are common to all.

## A workflow that works

1. Write 5–10 blocks; include at least one deliberate cross-query between
   literatures you suspect are disconnected.
2. `--selftest`, then `--counts-only` to see the shape of each field.
3. Tighten anything returning thousands of hits — a generic word is usually
   the culprit.
4. Full run with `--pdfs`; import the RIS into Zotero. Read `report.md`.
5. **Read every hit of your small blocks by hand** before claiming a gap;
   record what you screened and kept in `prisma.json` and re-render the
   report — the flow diagram is then ready for the paper's supplement.
6. Mine the PDFs' reference lists for works everyone cites and you don't
   have — that catches what keyword search misses, and it caught the two most
   important references in the project this was built for.

Or delegate the loop: state your research question to an AI agent (Claude
Code or similar) and ask it to draft the `queries.json`, run the scans, and
walk the archived results with you. The structured query file, the JSON
config, and the timestamped run directories are deliberately easy for an
agent to write and audit — this tool was built inside exactly that workflow.

## Roadmap

- More databases as config: Europe PMC, CORE, DOAJ, OpenAIRE, DBLP, PubMed
  (`docs/FUTURE_BACKENDS.md` has the vetted API details — contributions of
  working `backends.json` entries are very welcome).
- Legal OA-PDF downloading from the Unpaywall links already collected.
- Zotero Web API push (a run straight into a collection) and RIS keywords
  carrying the block name; BibTeX / CSL-JSON output.
- Snowballing via OpenAlex/Semantic Scholar reference endpoints, and citation
  graphs among a run's results.

## Tests

```bash
python tests/test_librarian.py
```

157 checks, stdlib only, no network and no keys — backends run against
canned API responses; the ingest parsers, research-directory merge, journal
store and report generator against synthetic directories — so the suite
exercises the real parsing, merging and rendering paths offline. CI runs it
on Linux and Windows under Python 3.9 and 3.13.

## How it was built

In Claude Code, for real use: the first version was written in a condensed-matter
physics project's literature-review sessions (mid-August 2026, roughly three
working days to v2.2), hardened by running actual PhD novelty checks —
5,000-record scans, the arXiv hang, the OpenAlex junk discrepancy, WoS UI
query errors — productized on August 26, 2026 (declarative backend
engine, offline test suite, CI) in a single session, and given its PRISMA
report generator, research directory, ingest, journal metrics and manuals on
August 28, 2026. In
[CRediT](https://credit.niso.org/) terms:

| CRediT role | Fabio | Claude |
|---|---|---|
| **Conceptualization** | One query across every database as a reproducible instrument; the counts-as-novelty-check method; the strict ToS stance (manual WoS rather than scraping); the three-level PRISMA report; the research directory as the lab-wide unit, manual sources with provenance, venue metrics tracked over time | The structural query schema; the databases-as-config engine; the report's document model and PDF fallback chain; the directory-as-index design |
| **Methodology** | Query-design discipline ("a small number is the finding — then read every hit"); database selection and institutional-access strategy | Junk-venue quantification; the arXiv group-limiting fix; checkpoint-after-every-call design |
| **Software** | — | All of it |
| **Validation** | Live novelty scans on real research queries; caught the WoS grammar traps, the arXiv hang, the OpenAlex/Scopus count discrepancy | The 157-check offline suite; CI; live selftests |
| **Investigation** | The institutional-access maze (CAPES/CAFe, VPN, key acquisition) | API documentation of 8+ databases; competitor code analysis |
| **Writing** | Review and editing | Original draft |
| **Resources · Supervision · Project administration · Funding acquisition** | All | — |

## Licence

MIT — see `LICENSE`. And respect the terms of service of every database you
query; this tool is built to make that the easy path.
