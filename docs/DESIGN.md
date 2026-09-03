# scitech-librarian — design account

The decisions behind the tool, the trade-offs each one carries, what was
rejected, and who decided what. The README's *How it was built* table gives
the CRediT summary; this file is the reasoning behind it. "Fabio" is the
author and maintainer; "Claude" is the AI assistant (Claude Code) that wrote
the software under his direction. Every design decision below was made or
ratified by Fabio; the assistant proposed mechanisms and implemented them.

## 1. The problem

A literature search you cannot rerun is a claim you cannot defend. Systematic
reviews and novelty checks ("nobody has done X") rest on exactly which
databases were asked, with exactly which query, on exactly which day — and
that record almost never survives the session it was made in. The tool was
built during the novelty checks of a condensed-matter physics PhD, where the
question was not "find me papers" but "show me, reproducibly, that this
intersection of two literatures is empty, and let me show that again in six
months". Two consequences shaped everything:

- **The archive is the product.** Records, counts and reports are outputs;
  the timestamped run directory with the exact query string sent to each
  backend is what the researcher will cite.
- **A small number is the informative outcome.** The workflow, the report's
  suggestions and the junk filter are all tuned for deliberate intersections
  where a near-zero count is a finding — provided every hit is then read.

*Framed by Fabio; the archive-first consequence was his requirement from the
first session.*

## 2. Decisions and trade-offs

### 2.1 One structural query, rendered into native grammars

A block is a conjunction of disjunctions (`[[a, b], [c]]` = `(a OR b) AND c`).
Each backend's syntax — `TITLE-ABS-KEY(...)`, `TS=(...)`, `abs:"..."`,
lowercase `and` — is generated from that one definition.

- *Gain:* queries never drift between databases; the exact rendered string
  is archived per backend.
- *Cost:* proximity operators (`NEAR/n`, `W/n`) and field-specific tricks
  are not expressible. Counts are therefore **not comparable across
  backends**, and the documentation says so rather than pretending.
- *Rejected:* a free-text boolean string per database (what findpapers
  takes). It puts the drift back in the researcher's hands.

*Schema proposed by Claude; the "no proximity operators, say so" trade-off
accepted by Fabio.*

### 2.2 Databases are configuration, not code

Every backend is a JSON entry: grammar, endpoint, auth header, paging style,
dotted paths into the response. `--init-backends` writes the defaults;
`backends.json` overlays them by name. Only engines that genuinely need code
(arXiv's XML feed) have a small driver.

- *Gain:* a user adds Europe PMC or DOAJ without touching Python; the
  declarative engine is testable against canned responses.
- *Cost:* a backend that needs stateful pagination or non-JSON responses
  needs a driver; the path language (`[0]`, `[]`, `a|b`, named transforms)
  is a small DSL to learn.
- *Rejected:* a client library per database. Eight dependencies, eight
  release cycles, and the stdlib-only promise gone.

*Engine design by Claude; the "config, not code" requirement by Fabio, who
had watched database-specific scripts rot.*

### 2.3 Standard library only, nothing to install

Five scripts and two shared modules, Python 3.9+, no dependency. pandoc and
a TeX engine improve the PDF when present; a built-in writer covers their
absence so the `pdf` option never fails, only degrades.

- *Gain:* runs from any laptop, drops into another project's `tools/`
  folder, survives years of dependency churn.
- *Cost:* hand-written RIS/BibTeX/CSV parsers, a minimal PDF writer, a
  Markdown-to-HTML converter for the manual — all maintained here.
- *Rejected:* `requests`, `pandas`, `bibtexparser`, `reportlab`. Each would
  have been simpler to write against and worse to depend on.

*Fabio's constraint from day one.*

### 2.4 Documented APIs only; Web of Science by hand

No scraping of any web interface, no Google Scholar, PDFs only through
Unpaywall, Scopus entitlement honoured rather than worked around. Web of
Science, whose usable grammar sits in a rarely licensed API, is a manual
round-trip made small: `wos_manual.py` prepares the queries in WoS grammar,
walks the user through pasting them, and ingests the RIS exports into the
same schema.

- *Gain:* the tool cannot get an institution's access suspended; results
  carry their licence terms honestly (CC0 samples only in the repository).
- *Cost:* WoS is slower than the automated backends; Google Scholar's
  breadth is unavailable.
- *Rejected:* scraping (paperscraper's approach to Google Scholar), and
  "just for counts" scraping of the WoS UI, which violates its terms the
  same way.

*Fabio's decision, non-negotiable; the manual round-trip mechanism by Claude.*

### 2.5 Everything is archived, and counts are checkpointed

Every run writes a timestamped directory: raw records per block and
backend, deduplicated combined sets in five formats, the exact query per
backend, counts as JSON and as a paste-ready table, metadata, a full log.
Counts append to a history file. Counts are saved after every API call and
Ctrl-C is safe.

- *Gain:* six months later the search is reproducible and the drift of the
  counts is visible; a hang late in a long run loses nothing.
- *Cost:* disk (a 5,000-record run is tens of megabytes); a run is never
  "just a number on screen".
- *Rejected:* an in-memory run with an optional `--save`. The default must
  be the defensible one.

*Archive-everything by Fabio; checkpoint-after-every-call by Claude after
the arXiv hang cost a full run.*

### 2.6 A junk filter with receipts

OpenAlex indexes non-curated repositories. On a 5,146-record run, 15.3 % of
its records came from Zenodo, SSRN, Figshare and the like — 0 % for ADS,
Scopus, Semantic Scholar and INSPIRE — and on one decisive novelty query
that was the difference between 16 hits and 3. The filter is on by default,
`--keep-junk` disables it, and every removed record is kept in `junk.json`
with the venue that removed it.

- *Gain:* novelty counts mean what they seem to mean.
- *Cost:* a legitimate preprint-only result can be filtered; hence the
  receipts and the switch.
- *Rejected:* silent filtering, and no filtering. Both hide the problem.

*Quantified and implemented by Claude; the "receipts, never silent"
condition by Fabio.*

### 2.7 arXiv gets at most two groups

arXiv hangs — never returns — on deeply nested booleans. At most two groups
are sent (`arxiv_groups` chooses which), over HTTPS with a short timeout.

- *Rejected:* an automatic "most selective groups" heuristic. It was
  implemented, chose wrong on a real query, and was replaced by an explicit
  per-block choice with a sane default (the first two groups).

*Fix by Claude after Fabio's run exposed the wrong heuristic.*

### 2.8 The report ends every run, with PRISMA

A search you cannot report is a search you cannot defend, so every run
writes a report: strategy with the exact strings, results, a PRISMA 2020
flow whose automatable stages are filled from the data, a PRISMA-S
checklist, top records per block, rule-based suggestions. Three levels,
five formats. The stages only a human can know are read from a JSON file
the user fills in as screening proceeds.

- *Gain:* the flow diagram for the paper's supplement is a by-product of
  running the tool; *identified* versus *retrieved* is made explicit rather
  than conflated.
- *Cost:* a document model, three renderers and a PDF chain to maintain.
- *Rejected:* a report generated only on demand. It would never be written.

*Three-level PRISMA report by Fabio; document model, renderers and the PDF
fallback chain by Claude.*

### 2.9 The research directory, not a pile of runs

`project.py` indexes every run and every record brought in from outside
(RIS, BibTeX, CSV, JSON; an inbox folder for collaborators; the WoS
round-trip), keeps provenance (who, when, where from, PRISMA method), and
merges everything with `found_by` / `first_seen` per record. The project
report describes what each search added, which source found what nobody
else did, drift over time, and a PRISMA flow with both identification
columns. One directory per project; a lab has several; there is
deliberately no cross-project merge.

- *Gain:* the colleague's reference list and the six databases sit in one
  table, and "found only here" answers the question that matters.
- *Cost:* an index that must tolerate hand-edited and half-written
  directories (every consumer repairs a malformed `defaults`, for example).
- *Rejected:* a database (SQLite) as the store. Files in folders are what a
  researcher can inspect, back up and cite.

*Directory-as-lab-unit and manual sources with provenance by Fabio;
directory-as-index design by Claude.*

### 2.10 Journal metrics, per year, never overwritten

`journals.py` stores OpenAlex, Scopus, SCImago and licensed JCR values per
journal and per year, so a refetch next year builds a series instead of
replacing a number. The Journal Impact Factor is import-only from a licensed
export; the tool will not scrape it.

*Fabio's requirement (a metric is a time series); implementation by Claude.*

### 2.11 Report languages translate scaffolding only

`--lang pt-BR|es|de|fr` translates the report's own wording — headings,
PRISMA stages and diagram, checklist, explanations, suggestions, thousands
separators. Records, query strings, block names and notes, backend names,
flags, file names, JSON dumps, the embedded run log, `run.log`, the audit
logs and the console are never translated. The catalogue is keyed by the
English text, so the English output is byte-identical to before the feature
existed, and the suite guards every one of these boundaries.

- *Gain:* a report in Portuguese is still a faithful record of the search,
  and runs made in different languages stay searchable together.
- *Rejected:* translating block titles or log lines. It would turn a record
  into a paraphrase.

*Boundary set by Fabio; catalogue design and guards by Claude.*

### 2.12 Documentation in five languages, guarded, not synchronised

The README and the User Manual exist in Brazilian Portuguese, Spanish,
German and French beside the English originals. English is the source of
truth. Instead of machine-synchronising, the suite holds every translation
to the English heading skeleton and numbering, every fenced code block
verbatim, every flag and link target, the live check count, the same
version and date, and a recorded digest of the English text it was made
from — so any English edit fails the suite until the translation is redone.

- *Gain:* a translation can never silently describe an older tool; a
  translator gets an exact list of what drifted.
- *Cost:* every English edit is four more edits; the count sync must know
  the count word of each language.
- *Rejected:* translating comments inside code blocks (the verbatim rule is
  what makes the guard strong), and a "stale" warning instead of a failure.

*Fabio pinned the request and chose fail-on-stale; guards by Claude.*

### 2.13 The suite guards the docs, and the docs quote the suite

Offline, stdlib-only checks run every backend against canned responses and
the directory, ingest, journal and report code against synthetic trees. The
suite also fails when a CLI flag is missing from the manual or `AGENTS.md`,
when the README's check count drifts, when the built HTML is stale, when a
release's version is inconsistent across `librarian.py`, `CITATION.cff` and
the manual, and when the vendored publication checker differs from its
canonical copy. `docs/build_manual.py` syncs the check count into every
document and builds the manuals.

- *Rejected:* documentation as a separate, unchecked artefact.

*Fabio's rule ("the suite guards the docs"); mechanisms by Claude.*

### 2.14 Reproducible builds of the manual

The manual PDF is byte-reproducible: the build hands pandoc and the TeX
engine `SOURCE_DATE_EPOCH` derived from the manual's front-matter date, and
prefers lualatex, because xdvipdfmx draws font subset tags at random on every
run so a xelatex PDF can never be identical. A rebuild of an unchanged manual
leaves the tree clean.

*Found during an audit; fix by Claude, engine choice measured.*

### 2.15 The AI-agent skill ships with the tool

`SKILL.md` teaches a coding agent to run the tool from the user's clone —
which script does what, the key and query workflow, each database's traps —
without a hard-coded path (the clone is found through an environment
variable or by searching for the entry script). An installed copy must be
byte-identical to the shipped file, checked by the suite, because a skill
kept only in the agent's configuration once lagged a release by a whole
feature.

*Pattern by Fabio's portfolio rules; implementation by Claude.*

## 3. What the tool is not

Not a downloader (Unpaywall links only), not a bibliometrics package (see
litstudy), not a snowballing or citation-graph tool (roadmap), not a
Zotero client (RIS/BibTeX/CSL-JSON out, RIS in). Counts are not comparable
across databases and are documented as such. Google Scholar is not and will
not be a backend.

## 4. How it was built

In Claude Code, for real use: the first version in a physics project's
literature-review sessions (mid-August 2026), hardened by actual PhD novelty
checks, productised on 26 August 2026 (declarative engine, offline suite,
CI), given the PRISMA report, research directory, ingest, journal metrics
and manuals on 28 August 2026, report languages on 31 August, and the
shipped skill, reproducible PDF and translated documentation on
1 September 2026. Each release is followed by an independent code review
whose findings become failing tests first. The CRediT table in the README
summarises the division of work; the account above is its evidence.
