# Walkthrough: a new research project, start to PRISMA

A usage test that exercises every feature on a real topic, in the order a
project actually goes. Commands are exactly what was run on 2026-08-28;
numbers are from that day (they will drift — that is the point of the
count history). Everything lives in one research directory,
`lit_demo/`, chosen with `--outdir`.

**Topic.** Machine-learned interatomic potentials (MLPs) for heat transport
in amorphous solids — and the novelty question: *has anyone combined an MLP
with an Allen–Feldman / diffuson decomposition of thermal conductivity in
a glass?*

## 1. Write the blocks — `queries_demo.json`

Four blocks, funnel-shaped: a grounding block (the field), a sub-field, the
intersection we work in, and the novelty cross-query.

```json
{
  "GROUND":  {"title": "Machine-learned interatomic potentials (grounding)",
              "note":  "thousands expected; checks every backend answers",
              "groups": [["machine learning potential", "machine-learned interatomic potential",
                          "neural network potential", "Gaussian approximation potential"]]},
  "AMORPH":  {"title": "MLPs applied to amorphous / glassy solids", "note": "hundreds expected",
              "arxiv_groups": [0, 1],
              "groups": [["machine learning potential", "machine-learned interatomic potential",
                          "neural network potential", "Gaussian approximation potential"],
                         ["amorphous", "glass", "glassy", "disordered solid"]]},
  "THERMAL": {"title": "MLPs for thermal transport in amorphous solids",
              "note":  "the intersection our project targets -- tens; read every hit",
              "arxiv_groups": [0, 2],
              "groups": [["machine learning potential", "..."], ["amorphous", "glass", "glassy", "disordered solid"],
                         ["thermal conductivity", "phonon transport", "heat transport", "thermal transport"]]},
  "NOV":     {"title": "NOVELTY CHECK: anharmonic / diffuson-level analysis with MLPs in glasses",
              "note":  "a SMALL number is the good outcome",
              "arxiv_groups": [0, 3],
              "groups": [["machine learning potential", "..."], ["amorphous", "glass", "glassy"],
                         ["thermal conductivity", "heat transport", "phonon transport"],
                         ["Allen-Feldman", "diffuson", "propagon", "locon", "anharmonic"]]}
}
```

`arxiv_groups` names the two groups arXiv receives (it hangs on deeper
booleans); for NOV that is the MLP group and the diffuson group — the most
selective pair.

## 2. See what will run, and open the research directory

```
python librarian.py --queries queries_demo.json --outdir lit_demo --list
python project.py init --outdir lit_demo --name "MLP thermal transport in glasses" \
       --description "machine-learned potentials for heat transport in amorphous solids"
```

`--list` shows the four blocks and which backends are ready (six here:
OpenAlex, arXiv, INSPIRE, Semantic Scholar, ADS, Scopus; Crossref is
excluded by default — no boolean support). `init` writes
`lit_demo/project.json` and the `runs/ manual/ inbox/ logs/` folders.

## 3. Counts only — the shape of each block (seconds)

```
python librarian.py --queries queries_demo.json --outdir lit_demo --counts-only --no-report
```

| Block | openalex | arxiv | inspire | semanticscholar | ads | scopus |
|---|---|---|---|---|---|---|
| GROUND | 9,580 | 1,733 | 17 | 3,381 | 4,908 | 3,219 |
| AMORPH | 463 | 151 | 0 | 214 | 367 | 243 |
| THERMAL | 65 | 138 | 0 | 28 | 50 | 38 |
| NOV | 17 | 82 | 0 | 7 | 23 | 9 |

Thousands → hundreds → tens → single digits: the funnel works. (arXiv's
82 on NOV is larger because it only sees two of the four groups.) INSPIRE's
zeros are expected — it indexes high-energy physics.

## 4. The full run — records, RIS, open-access links, report

```
python librarian.py --queries queries_demo.json --outdir lit_demo --limit 150 \
       --pdfs --pdf-blocks THERMAL NOV --report-level intermediate --report-format md html
```

1,964 records fetched, 1,298 unique. Unpaywall found a legal open-access
copy for 97 of the 127 DOIs in the two small blocks (76 %). The run
directory holds `all_records.ris` for Zotero and the report; its
**Suggestions** said, correctly: GROUND is driven by a generic term and its
counts differ >20× across backends (do not compare them); ten block/backend
pairs hit the `--limit 150` cap; PRISMA manual stages are empty; no journal
metrics yet.

## 5. Read the novelty block

`report.md` → "Block NOV": the exact strings sent to each database, then
the records. With 17/7/23/9 hits this is the block to read by hand,
every record, before saying anything about a gap.

## 6. A colleague's reference list arrives — the inbox

Drop `colleague-reflist.ris` (exported from Zotero) into `lit_demo/inbox/`:

```
python project.py ingest --inbox --outdir lit_demo --method citation --block THERMAL \
       --who "a colleague" --origin "reference list of a 2023 review"
```

Seven records become `manual/colleague-reflist/` with `source.json`
provenance. Two of them no database had returned (Allen & Feldman 1993;
Allen, Feldman, Fabian & Wooten 1999 — the diffuson papers): the report's
Sources table shows "New here: 2".

## 7. Web of Science, by hand

```
python wos_manual.py prep --outdir lit_demo --queries queries_demo.json
```

writes `manual_wos/CHECKLIST.md` with the UI settings that silently break
queries and every block in WoS grammar, tagged and bare, e.g. for NOV:

```
TS=(("machine learning potential" OR "machine-learned interatomic potential" OR
     "neural network potential" OR "Gaussian approximation potential") AND
    (amorphous OR glass OR glassy) AND ("thermal conductivity" OR "heat transport" OR
    "phonon transport") AND ("Allen-Feldman" OR diffuson OR propagon OR locon OR anharmonic))
```

Paste, export RIS into `manual_wos/ris/NOV.ris`, then
`python wos_manual.py ingest --outdir lit_demo` registers it as a manual
source with `method=database` (it joins the databases column of PRISMA).

## 8. Venue metrics

```
python journals.py fetch --outdir lit_demo
python journals.py show --outdir lit_demo --metric openalex_2yr
python journals.py list --outdir lit_demo --missing jcr_if
```

344 journals seen; OpenAlex answered for 79 before its daily free budget
ran out (the tool stops asking and says so — `OPENALEX_API_KEY` raises the
budget; rerun tomorrow), Scopus covered the rest by ISSN or title. `list
--missing jcr_if` is the look-up list for a licensed JCR import
(`docs/JCR_IMPORT.md`).

## 9. Label the members, then the project report

```
python project.py label 20260828T123648 "counts-only reconnaissance" --outdir lit_demo
python project.py label 20260828T123821 "full run, six databases, OA lookup" --outdir lit_demo
python project.py status --outdir lit_demo
python report.py --project --outdir lit_demo --level simple --format md html pdf
```

| Source | Kind | Date | Method | Records | New here | Label / origin |
|---|---|---|---|---|---|---|
| 20260828T123648 | run | 2026-08-28 12:36 | database | 0 | 0 | counts-only reconnaissance |
| 20260828T123821 | run | 2026-08-28 12:38 | database | 1964 | 1298 | full run, six databases, OA lookup |
| colleague-reflist | manual | 2026-08-28 12:41 | citation | 7 | 2 | reference list of a 2023 review |

The counts-only run adds no records but its hit counts are summed into
"identified"; since it was a reconnaissance of the same query, exclude it
so PRISMA does not count the same hits twice:

```
python project.py exclude 20260828T123648 --outdir lit_demo
```

## 10. Filtered views

```
python report.py --project --outdir lit_demo --sources manual                       # only the colleague's list
python report.py --project --outdir lit_demo --blocks THERMAL NOV \
       --metric openalex_2yr --min-metric 5 --top 5 --sort metric                   # high-metric venues only
python report.py --project --outdir lit_demo --backends ads scopus --year-from 2023  # citation-grade, recent
python report.py --project --outdir lit_demo --since 2026-09-01 --diff              # next month: what is new
```

Every filter is printed in the report's metadata table and in PRISMA-S
item 9. The `--diff` view is empty today and is the command to run after
the next monthly rerun.

## 11. Screening — the human stages

Read, decide, and record the numbers in `lit_demo/screening.json` (the
template was written by the first report):

```json
{"records_screened": 1300, "records_excluded": 1252,
 "reports_sought": 48, "reports_not_retrieved": 2, "reports_assessed": 46,
 "excluded_reasons": {"no amorphous system": 17, "no thermal-transport quantity": 9,
                      "empirical potential only": 6},
 "other_sought": 7, "other_not_retrieved": 0, "other_assessed": 7,
 "other_excluded_reasons": {"already found by databases": 5},
 "studies_included": 16, "reports_included": 18,
 "citation_searching": "reference list of a 2023 review (colleague-reflist)",
 "prior_work": "none", "peer_review": "search strings reviewed by the group's librarian"}
```

Then `python report.py --project --outdir lit_demo --format pdf`: the PRISMA
2020 diagram is complete — databases column (24,729 identified over six
databases, 671 duplicates, 1,300 screened … 16 studies included) and the
other-methods column (7 identified by citation searching, 5 excluded as
already found) — ready for a supplement.

## 12. What the directory holds

```
lit_demo/
  project.json  screening.json  counts_history.csv  unpaywall_cache.json
  runs/20260828T123648  runs/20260828T123821
  manual/colleague-reflist/{source.json, records.json, colleague-reflist.ris}
  manual_wos/{CHECKLIST.md, queries/, ris/}
  journals/metrics.json
  reports/{step9-simple, step10a, step10b, step10c, step11-final, step13-diff}
  logs/  (13 audit logs: librarian ×2, project ×3, report ×4, journals ×3, wos_manual ×1)
```

A zip of this folder is the whole project: reproducible, citable, and
ready for the next search.

## What the test found (fixed in v3.2)

Running the walkthrough on real data surfaced: a merged record keeping
"arXiv preprint" as its venue when another database knew the published
journal; Scopus title look-ups reporting 404 as a warning instead of "no
match"; and the OpenAlex daily budget, now handled with a clear stop.
