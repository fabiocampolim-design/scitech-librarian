# Platforms

One row per platform the tool was **actually run on**, dated, with what was
run and what it produced. A platform with no row here has not been tried —
it is not a claim of failure, and it is not a claim of support either.

The tool is standard-library Python 3.9+, so the interesting variation is
not the interpreter but the things around it: console encoding, line
endings, whether a TeX engine and pandoc are installed, and the clipboard
helper `wos_manual.py` shells out to.

## Rows

| Date | Platform | Python | What was run | Result |
|---|---|---|---|---|
| 2026-09-06 | Windows 10 (10.0.19045), native | 3.13.11 (Anaconda) | full offline suite; `--list`, `--version`, `project.py status`, `journals.py list/show`, `report.py --latest`, `wos_manual.py status`; a report rendered to md/html/tex/txt/pdf; manuals rebuilt in five languages | pass — PDF via pandoc + lualatex |
| 2026-09-04 | ubuntu-latest, windows-latest, macos-latest (GitHub Actions) | 3.9 and 3.13 | pyflakes + offline suite, six jobs, commit `41f0d74` | pass |

CI re-runs that matrix on every push, so the second row is the one that goes
stale first; check the Actions tab for the latest commit rather than
trusting the date here.

## Notes per platform

**Windows (native).** The tool's home platform. `project.setup_logging`
reconfigures `stdout`/`stderr` to UTF-8 because journal and author names are
not cp1252, and `librarian.py` flushes every progress line — without that,
Windows buffers and a long backend call looks like a hang. `cmd.exe` does
not treat `#` as a comment, so do not paste a trailing `# explanation` after
a command; use PowerShell or drop the comment. `wos_manual.py` uses the
built-in `clip`.

**Linux.** Covered by CI on every push. `wos_manual.py` needs `xclip` for
the clipboard step; without it the query is printed instead, and nothing
else changes.

**macOS.** Covered by CI on every push. `wos_manual.py` uses `pbcopy`.

**WSL.** Not run. Nothing is known to stand in the way — it is a Linux
Python — but no row means no evidence.

**Docker, mobile.** Out of scope; not pinned for this project.

## PDF rendering

`--format pdf` never fails: it tries a TeX engine, then pandoc, then a
built-in standard-library PDF writer, and reports which one it used. Only
the quality degrades. The committed manual PDFs are built with **lualatex**
and are byte-reproducible under `SOURCE_DATE_EPOCH`; xelatex is not
byte-reproducible (xdvipdfmx draws font subset tags at random), which is why
`ENGINES` in `docs/build_manual.py` lists lualatex first.
