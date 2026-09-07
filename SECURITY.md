# Security policy

## Reporting a vulnerability

Report privately through GitHub's **[Report a vulnerability][advisory]** form
on this repository (Security → Advisories). That opens a private advisory
visible only to the maintainer.

Please do not open a public issue for a vulnerability, and do not include a
working exploit in the first message — a description of the class of problem
and the conditions that trigger it is enough to start.

[advisory]: https://github.com/fabiocampolim-design/scitech-librarian/security/advisories/new

**What to expect.** This is a one-maintainer project, worked on in
research time: an acknowledgement within about a week, and a fix or a clear
"won't fix, here is why" once the report is understood. Only the latest
release is supported; fixes ship in a new release rather than as patches to
older tags.

## Scope

In scope: anything in this repository — `librarian.py`, `project.py`,
`report.py`, `render.py`, `i18n.py`, `journals.py`, `wos_manual.py`,
`docs/build_manual.py`, the test suite and the CI workflow.

Out of scope: the bibliographic APIs themselves (report those to OpenAlex,
Elsevier, Clarivate, NASA ADS, CORE, Semantic Scholar, Crossref, arXiv,
INSPIRE-HEP or Unpaywall), and anything you install to render PDFs (pandoc,
TeX Live).

## What this tool touches

Useful context for judging impact — the design notes in
[`docs/DESIGN.md`](docs/DESIGN.md) carry the full threat note.

- **Credentials.** API keys are read from the process environment; a `.env`
  next to the scripts fills in only what the environment does not already
  set. `.env` is gitignored and its values are never written to a run
  directory, a log or a report. Keys travel to the database that owns them,
  over HTTPS, in a header or a query parameter as that API specifies.
- **Network.** Outbound HTTPS to the documented public API of each configured
  backend, plus Unpaywall when `--pdfs` is used. Nothing listens on a port.
  No telemetry: the tool never reports to the author.
- **Processes.** `render.py` and `docs/build_manual.py` invoke `xelatex`,
  `lualatex`, `pdflatex` or `pandoc` when they are on `PATH`, with a file
  path argument; `wos_manual.py` invokes the platform clipboard helper
  (`clip`, `pbcopy`, `xclip`). No shell is used and no argument is built from
  network data.
- **Files.** Everything is written under the research directory (`lit/` by
  default, `--outdir`): records, logs, reports, the Unpaywall cache.
- **Untrusted input.** Records fetched from an API, and files you ingest
  (RIS, BibTeX, CSV, JSON), are data. They reach LaTeX and HTML through the
  escapers in `render.py`; a title or an abstract that breaks out of either
  is a vulnerability worth reporting.

## Repository hardening

Dependabot alerts and security updates, secret scanning with push
protection, and private vulnerability reporting are enabled on this
repository. The tool itself has no runtime dependencies — the standard
library only — so `.github/dependabot.yml` watches the GitHub Actions used
by CI.
