# AGENTS.md — instructions for AI agents using scitech-librarian

You are operating scitech-librarian on behalf of a researcher. This file is
the complete, machine-oriented description of the tool: what it does, the
commands, the files it reads and writes, and the rules you must not break.
Humans: hand this file to your agent ("read AGENTS.md, then …") — it is
written so that a coding agent can drive the tool correctly without the
README. The human-oriented manual is `docs/USER_MANUAL.md`.

## What the tool is

A reproducible literature-search instrument for science and engineering:

1. `librarian.py` runs one structured query against up to eight
   bibliographic databases through their documented APIs and archives every
   run (records, exact query strings, counts, log, PRISMA report).
2. `project.py` turns a directory of runs into a **research directory**: it
   indexes runs, ingests records obtained outside the tool (RIS, BibTeX,
   CSV, JSON — Zotero, Mendeley, Web of Science exports, reference lists),
   and keeps provenance for every record.
3. `report.py` renders a literature-search report — search strategy, results
   summary, PRISMA 2020 flow, PRISMA-S checklist, records, suggestions — for
   one run or for the whole research directory merged, in md/html/tex/pdf/txt
   at three levels, with date/source/venue/citation filters.
4. `journals.py` keeps journal metrics (OpenAlex 2-year mean citedness,
   Scopus CiteScore/SJR/SNIP, SCImago SJR/quartile, imported JCR IF) per
   year, so reports can show and filter by venue quality and its evolution.
5. `wos_manual.py` handles Web of Science, which has no usable free API, as
   a paste-and-export routine, and registers the exports as manual sources.

Standard library only. Python 3.9+. No install step: copy the six `.py`
files (five scripts plus `render.py`, which `report.py` imports) or clone,
and run.

## Hard rules

- **Never scrape a web interface.** The tool queries documented APIs only.
  Do not write code that fetches Web of Science, Scopus, Google Scholar or
  any publisher page as HTML. Web of Science is a manual job via
  `wos_manual.py`. This is a legal and ethical constraint, not a preference.
- **Never commit `queries.json`, `.env`, or `lit/`** (or any research
  directory) to a public repository. They contain the researcher's actual
  research direction, credentials, and downloaded records. `.gitignore`
  already excludes them; do not undo that.
- **Never claim a gap in the literature from counts alone.** A small count
  is a lead; the researcher must read every hit. Say so in any summary you
  write.
- **Do not fetch PDFs from publishers.** `--pdfs` looks up legal open-access
  copies via Unpaywall only.
- **Respect rate limits.** The backends sleep between calls on purpose; do
  not remove the sleeps or parallelise calls to one provider.
- **Report counts honestly.** Counts are not comparable across databases
  (different grammars, stemming, no proximity operators). Never present one
  database's count as "the" number.

## Setup checklist

1. `cp .env.example .env` and fill what the researcher has: `CONTACT_EMAIL`
   (always; it puts requests in the polite pool), `ADS_TOKEN` (free),
   `SCOPUS_API_KEY` (free key; results need the institution's network/VPN),
   optional `S2_API_KEY`, `CORE_API_KEY`, `WOS_STARTER_KEY`.
2. `cp queries.example.json queries.json` and write the blocks (below).
3. `python librarian.py --selftest` — reports which backends work.
4. `python project.py init --name "<project name>"` — optional but
   recommended; writes `lit/project.json`.

## Writing queries (`queries.json`)

```json
{
  "NOV": {
    "title": "short description",
    "note": "why this block exists; what a good result looks like",
    "groups": [["origami", "kirigami"], ["acoustic metamaterial", "phononic crystal"], ["topological pumping", "edge state"]],
    "arxiv_groups": [0, 2]
  }
}
```

- `groups` is a conjunction of disjunctions: `[[a, b], [c]]` = `(a OR b) AND c`.
- Quote nothing; the tool quotes per backend. Avoid a lone generic word
  (`"model"`, `"structure"`): it drives counts into the thousands.
- `arxiv_groups` names at most two groups for arXiv, which hangs on deeply
  nested booleans. If omitted, the first two are sent.
- A good project has 5–10 blocks: grounding blocks (expect thousands),
  narrower blocks (hundreds), and deliberate cross-queries between two
  literatures (the novelty checks, where a small number is the finding).

## Commands (every script accepts `--outdir DIR --verbose --quiet --log-dir DIR`)

### librarian.py — search

```
python librarian.py                               all blocks, all configured backends
python librarian.py --counts-only                 hit counts only, fast
python librarian.py --blocks A CD --backends openalex ads
python librarian.py --skip arxiv                  exclude a misbehaving backend
python librarian.py --limit 500                   max records per block AND backend (default 300, most-cited first)
python librarian.py --pdfs [--pdf-blocks A]       legal OA-PDF lookup via Unpaywall (one call per DOI; cache kept)
python librarian.py --keep-junk                   do not filter non-curated venues (Zenodo, SSRN, Figshare…)
python librarian.py --queries other.json --backends-file b.json --timeout 60
python librarian.py --report-level simple|intermediate|full --report-format md html tex pdf txt
python librarian.py --no-report
python librarian.py --list | --selftest | --init-backends
```

Output: `lit/runs/<stamp>/` with `counts.json|md`, `queries.json` (exact
strings sent), `blocks.json`, `meta.json`, `records/<block>_<backend>.json`,
`ris/`, `all_records.{json,csv,ris,bib,csl.json}` (deduplicated), `junk.json`,
`prisma.json` (template), `run.log`, `report.*`; and `lit/counts_history.csv`,
`lit/logs/librarian_<stamp>_<pid>.log`.

### project.py — research directory

```
python project.py init --name NAME [--description TEXT]
python project.py status
python project.py ingest FILE... --name NAME [--block B] [--kind ris|bibtex|csv|json]
                  [--method database|citation|website|organisation|expert|other]
                  [--who WHO] [--origin TEXT] [--note TEXT]
python project.py ingest --inbox                  every file dropped in lit/inbox/
python project.py oa [--members ID...]           Unpaywall pass over members lacking OA data (legal copies only)
python project.py exclude <member> | include <member>
python project.py label <member> "text"
python project.py alias OLDBLOCK NEWBLOCK         a block renamed between runs
```

`--method` places the source in the PRISMA flow: `database` (a database
export, e.g. Web of Science UI) joins the databases column; anything else
goes to "identification via other methods".

### report.py — reports

```
python report.py lit/runs/<stamp> [--level L] [--format F...]      one run
python report.py --latest                                            newest run
python report.py --project [--outdir lit]                            everything merged
filters:  --since YYYY-MM-DD --until YYYY-MM-DD --latest --diff
          --year-from Y --year-to Y --backends ... --blocks ...
          --sources auto|manual|all --records FILE...
          --metric NAME --min-metric X --min-citations N --oa-only
          --top N --sort cited|year|metric
output:   --basename NAME --out DIR
```

Project reports go to `lit/reports/<stamp>-<level>/`. `--diff` with
`--since` answers "what did the searches since DATE add".

### journals.py — venue metrics

```
python journals.py fetch [--providers openalex scopus] [--refresh]
python journals.py import-scimago FILE.csv --year 2024 [--all]
python journals.py import-jcr FILE... [--year Y]      Journal Citation Reports downloads (see docs/JCR_IMPORT.md)
python journals.py import-csv FILE --provider NAME --year Y --name-col C --value-col C [--issn-col C]
python journals.py list [--missing METRIC]            journals seen in the directory; --missing = manual look-up list
python journals.py show [--metric openalex_2yr] [--limit 50]
```

JCR cannot be fetched; coordinate with the researcher: run `list --missing
jcr_if`, ask them to download the JCR category CSVs (600-row cap per
download, slice by category then quartile), then `import-jcr`.

Store: `lit/journals/metrics.json`, values per year, never overwritten.
Metric names: `openalex_2yr openalex_h scopus_citescore sjr snip scimago_h
jcr_if` (+ any imported provider). JCR Impact Factor cannot be fetched (it
is proprietary); only imported from a licensed export.

### wos_manual.py — Web of Science by hand

```
python wos_manual.py prep      query files + CHECKLIST.md in WoS grammar
python wos_manual.py walk      copies each query to the clipboard in turn
python wos_manual.py ingest    parses lit/manual_wos/ris/<BLOCK>.ris and registers manual sources
python wos_manual.py status
```

## Record schema (every JSON record everywhere)

```
title year doi journal authors[] url abstract cited_by issn block backend
```
Merged project records add `found_by` (`["openalex@<run>", "manual:<name>@<name>", …]`),
`first_seen` (date of the earliest source), `blocks[]`. Manual records have
`backend = "manual:<name>"`. Deduplication key: DOI, else the first 90
characters of the lower-cased title.

## Workflows to run for the researcher

**Novelty check.** Write 1–3 cross-query blocks → `--counts-only` → tighten
anything in the thousands → full run → read `report.md` Suggestions → the
researcher reads every hit of the small blocks → record screening numbers in
`prisma.json` → `report.py` again.

**Systematic search over time.** `project.py init` once. Rerun
`librarian.py` monthly (same `queries.json`). Ingest colleagues' RIS and the
Web of Science exports. `report.py --project` for the full picture;
`--project --since <last report date> --diff` for "what is new";
`journals.py fetch` once a year for the metric series. Fill `screening.json`
as screening progresses; the PRISMA diagram completes itself.

**Lab-wide.** One research directory per project (`--outdir`). A lab
overview is `report.py --project --outdir <each>`; there is no cross-project
merge (by design: different questions, different blocks).

## Interpreting the report for the researcher

- *Identified* = database hit counts (sum over runs in project mode);
  *retrieved* = records actually downloaded within `--limit`; *unique* =
  after deduplication. Say which one you quote.
- "Found only here" is a database's marginal contribution; a backend with
  zero exclusive records can be dropped from the next run.
- Count drift between runs is normal (indexes grow); a jump >1.5× usually
  means the query changed — diff `queries.json` of the two runs.
- PRISMA manual stages show `--` until `prisma.json` / `screening.json` is
  filled; do not invent those numbers.

## Limitations you must state when relevant

- Counts differ across databases and are not comparable; proximity
  operators are dropped.
- Scopus needs institutional entitlement (campus network/VPN); a 401/403
  is a network problem before it is a key problem.
- Web of Science API is rarely licensed; the manual path is the norm.
- arXiv receives at most two groups per block.
- `--limit` caps records per block and backend; large blocks are the
  most-cited slice, not the complete set.
- OpenAlex indexes non-curated repositories; ~15 % of its records are
  filtered by default (`junk.json` keeps them).
- Journal metrics: OpenAlex values are snapshots (one per fetch year);
  JCR IF is not available without a licence.
- No PDF download, no snowballing, no citation graph, no Zotero API push
  (roadmap). BibTeX/CSL-JSON are outputs; Zotero libraries come in as RIS
  exports through `project.py ingest`.

## Tests

`python tests/test_librarian.py` — offline, stdlib only, no keys; must pass
before any change is proposed. CI runs it on Linux and Windows, Python 3.9
and 3.13.
