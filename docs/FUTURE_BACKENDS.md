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

## Features assessed as feasible (roadmap candidates)

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
