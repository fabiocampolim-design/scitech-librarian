# Pinned: databases and features to add later

The engine is declarative (see the `DEFAULT_BACKENDS` section of the script and
`--init-backends`): each database below can be added as a `backends.json`
entry, no code. API details verified August 2026 — re-check before wiring.

## Databases ready to configure

| Backend | Key | Endpoint | Notes |
|---|---|---|---|
| **Europe PMC** | none | `https://www.ebi.ac.uk/europepmc/webservices/rest/search` | params `query`, `format=json`, `pageSize`, `cursorMark` (cursor paging, start `*`); total `hitCount`, items `resultList.result`; fields: `title`, `pubYear`, `doi`, `journalTitle`, `authorString`. Life sciences + preprints, huge. |
| **CORE v3** | free key | `https://api.core.ac.uk/v3/search/works` | Bearer auth; `q` supports boolean; total `totalHits`, items `results`; OA aggregator, good for full-text links. |
| **DOAJ** | none | `https://doaj.org/api/search/articles/{query}` | query in URL path (needs a small driver or param-in-path support); items `results`, fields under `bibjson.*`. OA journals only. |
| **OpenAIRE** | none (token raises limits) | `https://api.openaire.eu/search/publications` | `format=json`, `keywords`; XML-ish JSON, may need a driver. EU aggregator incl. datasets. |
| **DBLP** | none | `https://dblp.org/search/publ/api` | `q`, `format=json`; total `result.hits.@total`, items `result.hits.hit[].info`. Computer science. |
| **PubMed E-utilities** | optional key | `esearch.fcgi` + `esummary.fcgi` | two-step (search → ids → summaries) — needs a driver. Biomedical. |

Skip (assessed, rejected): BASE (IP whitelist), Lens/Dimensions (commercial),
Google Scholar (no API; scraping breaches ToS — against this tool's stance).

## Done since this list was written

- v3.1 (2026-08-28): literature-search reports in md/html/tex/pdf/txt at
  three levels, PRISMA 2020 flow + PRISMA-S checklist, suggestions.
- v3.2 (2026-08-28): research directories (`project.py`), ingest of
  RIS/BibTeX/CSV/JSON with provenance, project reports with filters and the
  two-column PRISMA flow, journal metrics (`journals.py`: OpenAlex, Scopus,
  SCImago, JCR import), audit logs, AGENTS.md and the user manual.

## Features assessed as feasible (roadmap candidates)

- **Post-hoc open-access lookup** — `--pdfs` runs only inside `librarian.py`;
  a `project.py oa` pass over every member (runs and manual sources) would
  make `report --oa-only` and the OA statistics complete for projects.
- **Zotero Web API push** and RIS keywords carrying the block name; BibTeX
  and CSL-JSON output next to RIS.
- **Post-hoc de-duplication rule for repeated searches** — collapse runs with
  identical query strings in PRISMA "identified" instead of summing them
  (today: `project.py exclude` the reconnaissance run by hand).

- **OA PDF downloading** — the Unpaywall pass already collects `oa_pdf` URLs;
  a `--download-pdfs` flag fetching them (plus arXiv PDFs by id) into
  `lit/runs/<stamp>/pdfs/` is legal and stdlib-doable. Never fetch publisher
  paywalled PDFs.
- **Snowballing** — OpenAlex `referenced_works`/`cited_by` and Semantic
  Scholar `references`/`citations` endpoints are free; a `--snowball <DOI>`
  (with `--depth`) feeding results back through the normal record pipeline.
- **Citation graphs** — with snowball data in hand, emit edges among the
  result set as DOT/GraphML from the same run directory.

## Competitor facts worth keeping

findpapers accesses Web of Science via the **Starter API**
(`api.clarivate.com/apis/wos-starter/v1`, free-trial rate 1 req/s, 50/page) —
the same endpoint this tool's `wos` backend uses. No competitor has ADS or
INSPIRE. paperscraper scrapes Google Scholar (ToS-gray); we don't.
