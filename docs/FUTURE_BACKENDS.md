# Pinned: databases and features to add later

The engine is declarative (see the `DEFAULT_BACKENDS` section of `librarian.py`
and `--init-backends`): most databases below can be added as a `backends.json`
entry, no code. **API details re-verified 2026-09-04 against live endpoints —
re-check again before wiring.** The August 2026 edition of this list had four
entries that had gone wrong; see "Corrections" at the end.

## The test a candidate must pass

This tool is a counting instrument, so the question is never "does the API
answer" but "does it answer the query I sent". A backend that turns `A AND B`
into a relevance search returns a number that looks like evidence and is not —
which is why `crossref` ships as `default_exclude`. Every candidate below was
sent the same four queries and passes only if the conjunction falls **below**
both singletons and the disjunction rises **above** both.

| Probe (2026-09-04) | graphene | photosynthesis | A AND B | A OR B | Verdict |
|---|---:|---:|---:|---:|---|
| Europe PMC | 172,093 | 174,455 | 2,730 | 343,818 | boolean |
| PubMed | 103,820 | 70,965 | 193 | 174,592 | boolean |
| CORE | 227,999 | 105,584 | 241 | 333,342 | boolean |
| OpenAIRE | 349,531 | 148,154 | 344 | 497,341 | boolean |
| DOAJ | 28,469 | 20,306 | 38 | 48,737 | boolean |
| Zenodo | 5,006 | 3,335 | 18 | 8,323 | boolean |
| EconBiz | 406 | 233 | 1 | 638 | boolean |
| ERIC | 23 | 476 | 0 | 499 | boolean |
| ClinicalTrials.gov | 16 | 8 | 0 | 24 | boolean |
| GBIF literature | 2 | 249 | 0 | 0 | **phrase only** |
| NASA NTRS | 216 | 663 | 0 | 0 | **phrase only** |
| USGS Publications | 0 | 265 | 0 | 0 | **phrase only** |
| OSF preprints | 73 | 12 | 0 | 0 | **field filter only** |

Run this test on any new candidate before adding it. Counts are that day's
index state and will drift; the *shape* of the four numbers is what matters.

## Databases ready to configure — no key, boolean honoured

| Backend | Endpoint | Notes |
|---|---|---|
| **Europe PMC** | `https://www.ebi.ac.uk/europepmc/webservices/rest/search` | 33 M records: MEDLINE/PubMed, Agricola, preprints (`SRC:"PPR"`), EPO patent abstracts, NICE guidelines. Field tags (`TITLE:`, `ABSTRACT:`, `PUB_YEAR:`), `NOT`, cursor paging on `cursorMark`/`nextCursorMark` starting `*`. Total `hitCount`, items `resultList.result`. **The single biggest coverage gain available.** Full entry below. |
| **OpenAIRE** | `https://api.openaire.eu/graph/v1/researchProducts` | Graph API v1: clean JSON, `search` param, total `header.numFound`, items `results[]` with `mainTitle`, `publicationDate`, `authors`. The European repository layer — EGU, Copernicus, national institutes. |
| **DOAJ** | `https://doaj.org/api/search/articles/{query}` | Query goes in the URL **path**, not a parameter — needs param-in-path support or a two-line driver. Elasticsearch grammar with `bibjson.title:`-style scoping and `.exact`; wildcards, regex, fuzzy and proximity are disabled. Total `total`, items `results[].bibjson.*`. Rate limit 2 req/s. |
| **ERIC** | `https://api.ies.ed.gov/eric/` | Education, ~1.5 M records. Solr grammar with real field scoping (`title:`, `subject:`, `author:`). `format=json`, `rows`; total `response.numFound`, items `response.docs`. |
| **EconBiz** | `https://api.econbiz.de/v1/search` | Economics and business (ZBW): working papers and EconStor grey literature Scopus never sees. Total `hits.total`, items `hits.hits`. |
| **Zenodo** | `https://zenodo.org/api/records` | Deposited datasets, software and preprints with DOIs. Total `hits.total`, items `hits.hits[].metadata`. |
| **ClinicalTrials.gov** | `https://clinicaltrials.gov/api/v2/studies` | Not literature: registered trials. Answers "has anyone tried this in humans", which no bibliographic count can. `countTotal=true` → `totalCount`; items `studies[].protocolSection`. |

### Europe PMC, written out

Verified against the live response shape on 2026-09-04. Paste into
`backends.json` and validate with `--selftest`:

```json
"europepmc": {
  "syntax": {"term": "always", "term_join": " OR ", "group_join": " AND "},
  "request": {
    "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
    "params": {"query": "{q}", "format": "json", "pageSize": "{n}",
               "cursorMark": "{cursor}", "resultType": "core"},
    "paging": {"style": "cursor", "next": "nextCursorMark",
               "start": "*", "size": 100, "sleep": 0.2}
  },
  "parse": {
    "total": "hitCount",
    "items": "resultList.result",
    "fields": {
      "title":    "title",
      "year":     "pubYear",
      "doi":      "doi",
      "journal":  "journalInfo.journal.title",
      "issn":     "journalInfo.journal.issn",
      "authors":  {"path": "authorString", "aslist": true},
      "url":      {"template": "https://europepmc.org/article/{src}/{id}",
                   "vars": {"src": "source", "id": "id"}},
      "abstract": "abstractText",
      "cited":    "citedByCount"
    }
  }
}
```

Note `journalInfo.journal.title` — there is **no** `journalTitle` key in a
`resultType=core` record, whatever an older version of this file said.

## Ready to configure — free key, no institution

| Backend | Key | Endpoint | Notes |
|---|---|---|---|
| **CORE v3** | `CORE_API_KEY`, Bearer | `https://api.core.ac.uk/v3/search/works` | 300 M+ open-access outputs from ~10 k repositories: theses, technical reports, institutional deposits. Field grammar with range operators (`yearPublished>2020`). Total `totalHits`, items `results`. Answered keyless in the 2026-09-04 probe, but CORE documents a key and rate-limits anonymous callers — configure one. |
| **IEEE Xplore** | free metadata key | `https://ieeexploreapi.ieee.org/api/v1/search/articles` | The conference literature in electrical engineering and computing that Scopus indexes thinly and arXiv not at all. Full text needs a subscription; metadata does not. Returned 403 without a key, as expected. |
| **Springer Nature Meta** | free non-commercial key | `https://api.springernature.com/meta/v2/json` | Real boolean grammar, but largely redundant against OpenAlex and Crossref. Low marginal value — add last, if at all. Returned 401 without a key, as expected. |

## Config-only, but `"default_exclude": true`

These answer well and are worth having for a targeted record pull with
`--backends`, but they ignore boolean operators, so their counts must never
reach a novelty claim or a PRISMA number. Same treatment as `crossref`.

| Backend | Endpoint | Why excluded |
|---|---|---|
| **GBIF literature** | `https://api.gbif.org/v1/literature/search` | Papers citing GBIF-mediated occurrence data, with the datasets they used — a genuinely different axis. `q` is a phrase match: two terms return zero. |
| **NASA NTRS** | `https://ntrs.nasa.gov/api/citations/search` | NASA technical reports back to NACA. Phrase-only `q`. Total `stats.total`. |
| **USGS Publications** | `https://pubs.usgs.gov/pubs-services/publication/` | USGS series reports — earth-science grey literature no journal index holds. Phrase-only `q`. Total `recordCount`. |
| **OSF preprints** | `https://api.osf.io/v2/preprints/` | The one door to PsyArXiv (63,498), SocArXiv (24,755), EarthArXiv (1,649), engrXiv (2,033) via `filter[provider]`. But `filter[title]` is a substring filter, not a query language. |
| **DBLP** | `https://dblp.org/search/publ/api` | Computer science, exhaustive and impeccably clean. Implicit AND of prefix tokens, no `OR`, no `NOT`, and it reset the connection under four rapid queries. A records source, not a counts one. |

## Need a small engine change first

| Backend | What is missing | Sketch |
|---|---|---|
| **OSTI** (US DOE) | The total exists **only** in the `X-Total-Count` response header; the body is a bare list. National-laboratory reports, theses and accepted manuscripts with contract numbers. | A `"total": {"header": "X-Total-Count"}` form in the parse spec. Probably lands other backends too. |
| **PubMed E-utilities** | Two-step: `esearch.fcgi` returns ids, `esummary.fcgi` returns records. Worth it for MeSH explosion and the echoed `querytranslation`, not for coverage — Europe PMC already carries MEDLINE. | One reusable id-then-fetch driver, in the shape of the existing arXiv driver. Optional key raises 3 → 10 req/s. |
| **SciELO** | Latin American and Iberian scholarship, heavily social-science, largely invisible to Scopus. The search endpoint refuses programmatic clients (403); ArticleMeta answers but returns identifiers. | The same id-then-fetch driver as PubMed. |
| **J-STAGE** | Japanese society journals, much of it not in Scopus. Returns Atom/PRISM **XML**. | A driver in the shape of the arXiv XML one. |

## Patents

A separate world, and the one place where a missed hit is not an embarrassment
but prior art. None is keyless; all three answered with an auth challenge
rather than a refusal, which is the good outcome.

| Source | Auth | Notes |
|---|---|---|
| **EPO OPS 3.2** | OAuth2 client credentials, free "non-paying" tier | Espacenet's engine: ~130 M documents, worldwide. CQL with real field operators (`ti=`, `ab=`, `pa=`, `ic=`, `pd>=`) and boolean. **The one to build if only one gets built.** Needs a token-refresh step the current auth block cannot express, plus a CQL generator beside the existing per-backend syntax rules. Register at `developers.epo.org`. |
| **USPTO Open Data Portal** | free ODP key | US grants and applications, rich JSON query language. PatentsView's legacy `api.patentsview.org` is **gone** (it serves the ODP's HTML now) and the original endpoints migrated to `data.uspto.gov` in March 2026. |
| **Lens.org** | token on application | Patents *and* scholarly works in one index with the citations between them — the only source here that answers "who patented the thing this paper describes". Free for non-commercial research on application; not self-service. |

Europe PMC already indexes EPO patent **abstracts**, so the keyless backend
above touches patent text before any of this is built.

## Assessed and rejected

| Source | Reason |
|---|---|
| BASE | API requires IP whitelisting per organisation; refused an anonymous call outright. |
| GeoRef | The earth sciences' real abstracting service, licensed by AGI through ProQuest and EBSCO only. |
| Embase, CINAHL, PsycINFO | Licensed per seat by Elsevier and EBSCO; no API a laptop can reach. |
| JSTOR, ProQuest, Sociological Abstracts | No public API at any price an individual can pay. |
| Dimensions | Token-gated; DSL endpoint 404s without one. Commercial. |
| bioRxiv / medRxiv | Their own API answers by DOI and date interval only — no term search. Europe PMC indexes both already. |
| ChemRxiv, PhilPapers | Returned 403 to a plain documented client. |
| PubChem, NASA CMR, PANGAEA | Answer well, but index compounds, satellite collections and datasets — objects, not publications. A `project.py ingest` path at most. |
| Wikidata SPARQL | Works, and holds scholarly-article items, but it is a graph query surface, not a search backend. |
| Google Patents, WIPO PATENTSCOPE | BigQuery-only and no public API respectively. Scraping either breaches the terms this tool's own rules forbid crossing. |
| Google Scholar | No API; scraping breaches ToS — against this tool's stance. |

## What adding them costs

Worth weighing before saying yes to all of it:

- **Counts drift further apart.** Nineteen backends means nineteen stemmers.
  The README's warning that counts are not comparable across databases stops
  being a caveat and becomes the headline.
- **Key sprawl.** Six more environment variables. `--list` and `--selftest`
  carry that weight already; the manual's key table does not.
- **Redistribution terms multiply.** CORE, Springer, IEEE and Lens each attach
  their own reuse conditions, and the licence section currently reasons about
  eight sources by name.
- **The suite grows with each one.** Every backend needs canned responses and a
  parse test — roughly forty new offline checks for the seven drop-ins.

## Corrections to the August 2026 edition of this list

Recorded so the same mistakes are not re-derived:

- **DBLP was listed as ready to configure.** It honours no boolean operators;
  it belongs in the `default_exclude` set, not the default run.
- **Europe PMC's journal was mapped to `journalTitle`.** That key does not
  exist in the response; it is `journalInfo.journal.title`. Wiring it as
  written yields an empty journal on every record.
- **OpenAIRE pointed at the old `search/publications` endpoint** described as
  "XML-ish JSON, may need a driver". The Graph v1 API returns clean JSON and
  needs no driver.
- **Lens was rejected as commercial.** It is free for non-commercial research
  on application.

## Features assessed as feasible (roadmap candidates)

- **Zotero Web API push** (a run straight into a collection) -- still open.
  What 3.2.1 shipped instead: `project.py oa` (post-hoc Unpaywall pass),
  BibTeX / CSL-JSON output, and `block:<name>` keywords so imports arrive
  pre-tagged.
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

## Done since this list was written

- v3.1 (2026-08-28): literature-search reports in md/html/tex/pdf/txt at
  three levels, PRISMA 2020 flow + PRISMA-S checklist, suggestions.
- v3.2 (2026-08-28): research directories (`project.py`), ingest of
  RIS/BibTeX/CSV/JSON with provenance, project reports with filters and the
  two-column PRISMA flow, journal metrics (`journals.py`: OpenAlex, Scopus,
  SCImago, JCR import), audit logs, AGENTS.md and the user manual.
- v3.3 (2026-08-31): report languages (pt-BR, es, de, fr) for the
  non-conversation index, reports and PRISMA.
- v3.4 (2026-09-01/04): README and User Manual in four languages with drift
  guards; community pathways and the design account; keys read from the
  environment with `.env` as one route among several.
