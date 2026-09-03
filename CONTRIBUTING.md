# Contributing to scitech-librarian

Thank you for considering a contribution. This file says what is welcome,
how the project is tested, and the few rules that keep it honest. The design
and its trade-offs are written up in [`docs/DESIGN.md`](docs/DESIGN.md); the
complete machine-oriented description of the tool is [`AGENTS.md`](AGENTS.md).

## What is most welcome

- **A `backends.json` entry for a database we do not ship.** Databases are
  configuration, not code (README, *Adding a database*). Open an issue with
  the entry, the query you ran, the hit count you got and, if you can, the
  same query pasted into the database's own web interface for comparison.
  `docs/FUTURE_BACKENDS.md` has vetted starting points.
- **A count that looks wrong, a backend that misbehaves, a grammar trap.**
  Say which backend, the block from your `queries.json` (or a minimal one),
  the exact query string from `lit/runs/<stamp>/queries.json`, and the
  relevant lines of `run.log`. Never paste an API key; if one ended up in a
  transcript, rotate it.
- **Documentation fixes in any of the five languages.** English is the
  source of truth; see *Translated documentation* below.
- **Sample data only under CC0.** Records from OpenAlex, arXiv and
  INSPIRE-HEP may be redistributed; Scopus, NASA ADS and Semantic Scholar
  data may not (their API terms). Nothing downloaded from a paywall, no
  scraped pages, no full texts.

## Ground rules

1. **Documented APIs only, terms of service respected.** No scraping of any
   web interface, no Google Scholar, no paywall circumvention, no way around
   institutional entitlement. A pull request that adds any of these will be
   closed however good the code is.
2. **Standard library only, Python 3.9+.** No runtime dependency; optional
   tools (pandoc, a TeX engine) may improve output but must never be
   required and their absence must degrade gracefully.
3. **Every behaviour change ships with a test that failed first.** The suite
   is `python tests/test_librarian.py` (offline, no keys, no network; every
   backend runs against canned responses). Write the failing check, watch it
   fail, then make it pass. `pyflakes` must be clean over the whole tree.
4. **Every flag, output key and limitation is documented.** The suite fails
   when a CLI flag is missing from `docs/USER_MANUAL.md` or `AGENTS.md`, when
   the README's check count drifts, and when a translation drifts from the
   English. Run `python docs/build_manual.py` after changing the manual: it
   syncs the check count into every document and rebuilds the HTML and PDF.
5. **Logs stay English.** Console output, `run.log` and the audit logs are
   never translated, whatever the report language, so runs made in different
   languages stay searchable together. Report scaffolding is translated
   through `i18n.py`; records, query strings, block names, file names, JSON
   and flags are reproduced exactly as found.
6. **Nothing personal in the tree.** No absolute paths, no e-mail addresses,
   no keys, no institutional identifiers in code, docs, samples or history.

## Translated documentation

`README.<lang>.md` and `docs/USER_MANUAL.<lang>.md` exist for `pt-BR`, `es`,
`de` and `fr`. When you change `README.md` or `docs/USER_MANUAL.md`, redo the
changed passages in the four translations, keep every fenced code block
verbatim (commands, file names, flags and the comments inside code blocks are
never translated), keep the heading skeleton, section numbers, flags and link
targets identical to English, then run
`python docs/build_manual.py --stamp-translations` followed by
`python docs/build_manual.py`. The suite tells you exactly which guard a
translation fails.

## Pull requests

- One change per pull request, with the `CHANGELOG.md` line you would want to
  read six months later.
- Contributions are accepted under the Apache License 2.0 (its section 5);
  keep the SPDX header on every Python file.
- CI runs `pyflakes` and the suite on Linux, Windows and macOS under
  Python 3.9 and 3.13; all of it must be green.
- Releases are the maintainer's: a `VERSION` bump, a changelog entry, an
  annotated tag and a GitHub Release, followed by an independent code review.

## Where to talk

Open an [issue](https://github.com/fabiocampolim-design/scitech-librarian/issues).
There is no mailing list and no e-mail contact; the maintainer's GitHub
profile is the other door. Please read the [Code of Conduct](CODE_OF_CONDUCT.md)
first.
