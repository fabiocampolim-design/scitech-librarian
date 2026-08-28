# Dev plan v3.2 — research directory, ingest, journal metrics, docs

Spec: `docs/DESIGN_RESEARCH_DIRECTORY.md`. Each step ends with the offline
suite green (`python tests/test_librarian.py`). Steps are ordered so that
every intermediate state is shippable.

1. **Common plumbing** — `--outdir`, `--verbose/--quiet`, `--log-dir`, audit
   log writer shared by all scripts (small helper duplicated per file to keep
   each script standalone). `librarian.py` records `outdir` in `meta.json`.
   Tests: log file written with invocation line; `--outdir` respected.
2. **`project.py`** — `init`, `status`, `ingest` (RIS/BibTeX/CSV/JSON,
   `--inbox`), `load_project()` / `members()` / `merged_records()` API used
   by the report. RIS parser moves here; `wos_manual.py` imports it and its
   `ingest` writes `manual/wos-<block>/`. Tests: each parser on a fixture;
   provenance fields; alias mapping; dedup + `found_by`/`first_seen`.
3. **`report.py --project`** — sources section, two-column PRISMA, time
   sections, filters table from the spec. Single-run mode keeps working and
   gains the same filters. Tests: filters on a synthetic project with two
   runs and one manual source; `--diff` picks only new records; PRISMA
   other-methods column populated.
4. **`journals.py`** — store, OpenAlex fetch (canned in tests), Scopus serial
   fetch (canned), SCImago CSV import, generic CSV import, `show`; records
   gain `issn`/`source_id` where backends provide them (OpenAlex, Scopus,
   Crossref field paths). Report: metric column, top venues by metric,
   evolution table, `--min-metric`. Tests: store append-not-overwrite; ISSN
   and name matching; report threshold.
5. **Docs** — `AGENTS.md`, `docs/USER_MANUAL.md` (+ built HTML/PDF via
   `docs/build_manual.py`), README rewrite (research- and lab-wide intro,
   pointer to AGENTS.md, features/limitations), `docs/FUTURE_BACKENDS.md`
   roadmap refresh.
6. **Samples + release** — rebuild `samples/` (single-run) and add
   `samples/project/` (a two-run + manual-source project report), version
   3.2, commit, push, CI green, sync the working copies.
