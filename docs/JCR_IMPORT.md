# Journal Citation Reports: the manual import procedure

Clarivate's Journal Impact Factor (JIF) has no free API and its terms
forbid scraping, so JCR data enters a research directory only through
files you download yourself from the JCR web interface, under your
institution's licence. This page is the coordination protocol between you
(who can log in) and the tool (which imports, stores per year, and tells
you what is still missing).

## What the tool needs

The **"Download"** button on JCR's *Browse journals* page produces a CSV
(`JCR_JournalResults_<date>.csv`) with a few preamble lines, then a table
whose columns include `Journal name`, `ISSN`, `eISSN`, `Category`,
`<year> JIF`, `JIF Quartile`. That file is imported as is:

```
python journals.py import-jcr ~/Downloads/JCR_JournalResults_*.csv
python journals.py import-jcr file1.csv file2.csv --year 2024     # year forced
python journals.py list --missing jcr_if                           # what is still uncovered
```

Columns are detected automatically; the JIF year is read from the
`<year> JIF` column name. Values go into `lit/journals/metrics.json` as
`jcr_if` under that year, quartile alongside; importing next year's file
adds a second point — the evolution table in reports shows the series.

## The 600-row limit: how to slice a 3,000-journal set

JCR exports at most 600 rows per download. Filters on the *Browse
journals* page are the "query"; use them so that every download is under
600 rows and the downloads together cover the journals you care about.

**Step 0 — know what you need.** Run

```
python journals.py list --missing jcr_if
```

That prints every journal seen in the research directory without a JIF on
file (names and ISSNs). You are covering *those*, not all of JCR.

**Step 1 — partition by category.** In JCR: *Browse journals* → Filter →
*Categories*. Tick one category at a time (or a few small ones that
together stay under 600), keep *JCR Year* at the latest edition, *Edition*
SCIE (+ SSCI/ESCI if your field spills over), then **Download** (CSV).
Typical sizes, so you can plan: PHYSICS, CONDENSED MATTER ≈ 70; PHYSICS,
APPLIED ≈ 180; PHYSICS, MULTIDISCIPLINARY ≈ 90; NANOSCIENCE &
NANOTECHNOLOGY ≈ 110; OPTICS ≈ 100; CHEMISTRY, PHYSICAL ≈ 180; MATERIALS
SCIENCE, MULTIDISCIPLINARY ≈ 450; ENGINEERING, ELECTRICAL & ELECTRONIC ≈
350; COMPUTER SCIENCE, ARTIFICIAL INTELLIGENCE ≈ 200; MULTIDISCIPLINARY
SCIENCES ≈ 130. Ten downloads cover a physics / materials / photonics
lab's ~3,000 journals.

**Step 2 — a category over 600.** Add the *JIF Quartile* filter and
download Q1, Q2, Q3, Q4 separately (each is a quarter of the category),
or the *JIF range* filter with cut points you choose. Name the files by
category and slice, e.g. `JCR_2024_MATSCI-MULTI_Q1.csv`.

**Step 3 — import and check.**

```
python journals.py import-jcr JCR_2024_*.csv
python journals.py list --missing jcr_if        # should now be short
```

Journals still listed are either outside the categories you chose (search
them by name in JCR and download that single-journal result) or not in
JCR at all (conference series, preprint servers, discontinued titles).

**Step 4 — yearly.** JCR releases each June. Repeat with the new edition;
the tool appends the new year and the report's evolution table gains a
column. Nothing is overwritten.

## Keeping it legal and tidy

- Downloads are for your own use under your institution's licence; keep
  the CSVs inside the research directory (they are gitignored with `lit/`)
  and never commit them to a public repository.
- The report cites the metric as "JCR Impact Factor (imported <date>)"
  through `fetched.jcr` in the store; the year comes from the file.
- If you prefer a metric that needs no licence: `journals.py fetch` (OpenAlex
  2-year mean citedness, Scopus CiteScore with a key) or the SCImago CSV
  (`import-scimago`, ~30,000 journals in one free download).
