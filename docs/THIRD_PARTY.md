# Third-party inventory

Everything scitech-librarian depends on, calls or reproduces, and the terms
each comes under. The tool itself is Apache-2.0 (see `LICENSE` and `NOTICE`).

The licence column records **what the provider states**, with the link to
where it says it, as checked on 2026-09-06. Terms change; before you
redistribute anything you obtained through this tool, re-read the source's
own page. Where a source's terms forbid redistribution, that is called out.

## Runtime dependencies

**None.** The Python standard library only, on CPython 3.9 or newer. There
is no `requirements.txt`, no lock file, and nothing is vendored except
`tests/conformance.py`, a byte-identical copy of the maintainer's own
publication checker (Apache-2.0, same owner).

## Optional external programs

Called through `subprocess` when present on `PATH`, never bundled, never
required — every path they serve has a standard-library fallback.

| Program | Used for | Licence |
|---|---|---|
| [pandoc](https://pandoc.org) | report and manual HTML/PDF | GPL-2.0-or-later |
| [LuaTeX / XeTeX / pdfTeX](https://tug.org/texlive/) (TeX Live) | typeset PDF | free licences per package (LPPL, GPL, …) |
| `clip` / `pbcopy` / `xclip` | `wos_manual.py` clipboard step | part of the operating system |

Development and CI only: [pyflakes](https://github.com/PyCQA/pyflakes) (MIT),
GitHub Actions `actions/checkout` and `actions/setup-python` (MIT).

## Bibliographic data sources

The nine backends in `librarian.py` and the open-access service. All are
called through their **documented public APIs**; no interface is scraped.

| Backend id | Source | Terms, as the provider states them | Redistribution |
|---|---|---|---|
| `openalex` | [OpenAlex](https://openalex.org) | Data released into the public domain, [CC0](https://docs.openalex.org/additional-help/faq) | Yes |
| `arxiv` | [arXiv](https://arxiv.org/help/api/) | [API Terms of Use](https://info.arxiv.org/help/api/tou.html); arXiv states its metadata is [public domain / CC0](https://info.arxiv.org/help/license/index.html) | Metadata yes; full texts under each author's own licence |
| `inspire` | [INSPIRE-HEP](https://inspirehep.net) | Metadata released under [CC0](https://inspirehep.net/info/general/terms-of-use) | Yes |
| `semanticscholar` | [Semantic Scholar](https://api.semanticscholar.org) | [ODC-BY 1.0](https://api.semanticscholar.org/license/) — attribution required | Yes, with attribution |
| `crossref` | [Crossref](https://api.crossref.org) | Metadata made openly available; see the [REST API terms](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) | Yes |
| `core` | [CORE](https://core.ac.uk) | [CORE terms](https://core.ac.uk/terms); records are aggregated from repositories and stay under **their** licences | Per source record — check individually |
| `ads` | [NASA ADS](https://ui.adsabs.harvard.edu) | [ADS terms of use](https://ui.adsabs.harvard.edu/help/terms/); an API token is personal to you | No bulk redistribution |
| `scopus` | [Scopus](https://dev.elsevier.com) (Elsevier) | [Elsevier API service agreement](https://dev.elsevier.com/api_service_agreement.html); access is entitled through your institution | **No** — not outside your institution |
| `wos` | [Web of Science](https://developer.clarivate.com/apis/wos-starter) (Clarivate) | [Clarivate API terms](https://developer.clarivate.com/); Starter API, restricted grammar | **No** |
| (`--pdfs`) | [Unpaywall](https://unpaywall.org) | Data released as [CC0](https://unpaywall.org/faq) by OurResearch; requires an e-mail address in every call | Yes |

Consequences the tool acts on:

- `samples/` ships one real run against **OpenAlex, arXiv and INSPIRE-HEP
  only**, because those three publish their metadata under CC0 and can
  therefore be redistributed in this repository. Reports built on Scopus,
  ADS, Web of Science or Semantic Scholar are for you, not for a public repo.
- `.gitignore` excludes every research directory (`lit/`, `lit*/`,
  `manual_wos/`) and licensed exports (`JCR_*.csv`, `scimagojr*.csv`,
  `*.ris`, `*.bib`), so a harvest cannot be committed by accident.
- `wos_manual.py` automates *your* clipboard, never Clarivate's website.
  Pointing a scraper at the Web of Science or Scopus web interface breaches
  their terms and can get an institution's access suspended.

## Journal-metric sources

| Source | Terms | Route |
|---|---|---|
| OpenAlex `sources` | CC0, as above | fetched by `journals.py fetch` |
| Scopus Serial Title (CiteScore, SJR, SNIP) | Elsevier agreement, above | fetched with your key |
| [SCImago Journal Rank](https://www.scimagojr.com) | Data page states [CC BY-NC](https://www.scimagojr.com/); download the yearly CSV yourself | `journals.py import-scimago` |
| Clarivate Journal Impact Factor | Proprietary, no free API | import-only from **your** licensed JCR export; the tool will not scrape it |

## Standards and methods reproduced

- **PRISMA 2020** flow and checklist — Page et al., *BMJ* 2021;372:n71,
  [doi:10.1136/bmj.n71](https://doi.org/10.1136/bmj.n71) (CC BY). The flow
  diagram this tool draws is an implementation of the published design.
- **PRISMA-S** search-reporting extension — Rethlefsen et al., *Systematic
  Reviews* 2021;10:39,
  [doi:10.1186/s13643-020-01542-z](https://doi.org/10.1186/s13643-020-01542-z)
  (CC BY). Item numbers and names are quoted in `report.py`.
- **RIS**, **BibTeX** and **CSL-JSON** are open interchange formats,
  implemented from their public specifications.

## Trademarks

Scopus and Web of Science are trademarks of Elsevier B.V. and Clarivate plc
respectively; OpenAlex, CORE, Semantic Scholar, INSPIRE-HEP, arXiv, NASA ADS,
Unpaywall and SCImago are the marks of their owners. They are named here to
say which service the tool talks to. This project is not affiliated with,
endorsed by or sponsored by any of them — see the non-affiliation note in
`README.md` and `NOTICE`.
