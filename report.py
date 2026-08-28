#!/usr/bin/env python3
"""
report.py -- literature-search report generator for scitech-librarian runs.

    python report.py lit/runs/20260815T095908                 # simple, markdown
    python report.py --latest --level full --format html pdf
    python report.py lit/runs/<stamp> --level intermediate --format md html tex txt pdf

librarian.py calls this automatically at the end of every run
(--report-level / --report-format / --no-report); run it by hand to re-render
an archived run at another level or in another format without re-querying.

Levels
------
simple        metadata, search strategy (structural + exact per-backend query
              strings), results summary, PRISMA 2020 flow + PRISMA-S checklist,
              top records per block, suggestions
intermediate  + every unique record, backend overlap, year / journal / author
              distributions, filtered venues, errors, open-access stats, count
              drift against previous runs of the same blocks
full          + every record with full abstract and author list, per-backend
              raw lists before deduplication, filtered records, backend
              endpoint configuration, the complete run log, environment

Formats: md (Markdown), html, tex (LaTeX), pdf, txt (plain text).
PDF is compiled from the LaTeX with xelatex / lualatex / pdflatex when one is
installed, else with pandoc, else with a built-in stdlib writer (plain text
layout) -- the option never fails, the quality just degrades.

PRISMA
------
The PRISMA 2020 flow diagram's automatable stages (records identified per
database, removed by automation tools = the junk-venue filter, duplicates
removed, records to screen) are filled from the run. The manual stages
(screened / excluded / sought / assessed / included) are read from an optional
prisma.json in the run directory; a template with null values is written on
the first report so you can fill it in and re-render.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "3.1"
LEVELS = ("simple", "intermediate", "full")
FORMATS = ("md", "html", "tex", "pdf", "txt")

# PRISMA-S (Rethlefsen et al. 2021, doi:10.1186/s13643-020-01542-z) items.
PRISMA_S_ITEMS = [
    ("1", "Database name", "auto"),
    ("2", "Multi-database searching", "auto"),
    ("3", "Study registries", "na"),
    ("4", "Online resources and browsing", "na"),
    ("5", "Citation searching", "manual"),
    ("6", "Contacts", "na"),
    ("7", "Other methods", "manual"),
    ("8", "Full search strategies", "auto"),
    ("9", "Limits and restrictions", "auto"),
    ("10", "Search filters", "auto"),
    ("11", "Prior work", "manual"),
    ("12", "Updates", "auto"),
    ("13", "Dates of searches", "auto"),
    ("14", "Peer review", "manual"),
    ("15", "Total records", "auto"),
    ("16", "Deduplication", "auto"),
]

PRISMA_TEMPLATE = {
    "_comment": "Manual screening stages of the PRISMA 2020 flow. Fill in the "
                "integers and re-run report.py; null = not yet done. "
                "excluded_reasons maps a reason to a count.",
    "records_screened": None,
    "records_excluded": None,
    "reports_sought": None,
    "reports_not_retrieved": None,
    "reports_assessed": None,
    "excluded_reasons": {},
    "studies_included": None,
    "reports_included": None,
    "citation_searching": "",
    "other_methods": "",
    "prior_work": "",
    "peer_review": "",
}


# ---------------------------------------------------------------------------
# Loading a run directory
# ---------------------------------------------------------------------------

def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, ValueError):
        return default


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load_run(run: Path) -> dict:
    """Everything the report needs, read from the archived run directory.
    Runs made before meta.json existed still load; missing pieces degrade."""
    run = Path(run)
    meta = _json(run / "meta.json", {})
    counts = _json(run / "counts.json", {})
    queries = _json(run / "queries.json", {})
    blocks = _json(run / "blocks.json", {})
    uniq = _json(run / "all_records.json", [])
    junk = _json(run / "junk.json", [])
    prisma = _json(run / "prisma.json", {})
    raw = {}
    for f in sorted((run / "records").glob("*.json")) if (run / "records").exists() else []:
        raw[f.stem] = _json(f, [])
    log = (run / "run.log").read_text(encoding="utf-8", errors="replace") \
        if (run / "run.log").exists() else ""
    hist = []
    hfile = run.parent.parent / "counts_history.csv"
    if hfile.exists():
        with hfile.open(encoding="utf-8", newline="") as f:
            hist = list(csv.DictReader(f))
    if "started" not in meta:
        m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", run.name)
        meta["started"] = "{}-{}-{} {}:{}:{}".format(*m.groups()) if m else run.name
    block_names = meta.get("blocks") or list(counts)
    backends = meta.get("backends") or sorted({b for c in counts.values() for b in c})
    return {"run": run, "stamp": meta.get("stamp") or run.name, "meta": meta,
            "counts": counts, "queries": queries, "blocks": blocks,
            "block_names": block_names, "backends": backends,
            "unique": uniq, "raw": raw, "junk": junk, "prisma": prisma,
            "log": log, "history": hist}


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def _key(r: dict) -> str:
    return (r.get("doi") or "").lower() or (r.get("title") or "").lower()[:90]


def stats(d: dict) -> dict:
    """Numbers every section and the PRISMA flow draw from."""
    counts, backends, blocks = d["counts"], d["backends"], d["block_names"]
    identified = {b: 0 for b in backends}
    errors = []
    for n in blocks:
        for b in backends:
            v = counts.get(n, {}).get(b)
            if v == "ERR":
                errors.append((n, b))
            elif _int(v) is not None:
                identified[b] += _int(v)
    retrieved = {b: 0 for b in backends}
    retrieved_block = defaultdict(int)
    for stem, recs in d["raw"].items():
        for r in recs:
            b = r.get("backend") or stem.rsplit("_", 1)[-1]
            retrieved[b] = retrieved.get(b, 0) + 1
            retrieved_block[r.get("block") or stem.rsplit("_", 1)[0]] += 1
    junk_by = Counter(r.get("backend", "?") for r in d["junk"])
    n_fetched = sum(retrieved.values())
    uniq = d["unique"]
    n_unique = len(uniq)
    # Which backends found each unique record (by dedup key), for overlap.
    found_by = defaultdict(set)
    for recs in d["raw"].values():
        for r in recs:
            found_by[_key(r)].add(r.get("backend", "?"))
    exclusive = Counter()
    for k, bs in found_by.items():
        if len(bs) == 1:
            exclusive[next(iter(bs))] += 1
    years = Counter(r.get("year") for r in uniq if r.get("year"))
    journals = Counter(r.get("journal") for r in uniq if r.get("journal"))
    authors = Counter(a for r in uniq for a in (r.get("authors") or []))
    oa = [r for r in uniq if "is_oa" in r]
    n_oa = sum(1 for r in oa if r.get("is_oa"))
    limit = d["meta"].get("limit")
    capped = []
    if limit:
        for stem, recs in d["raw"].items():
            n, b = stem.rsplit("_", 1)
            tot = _int(counts.get(n, {}).get(b))
            if tot and tot > limit and len(recs) + junk_by.get(b, 0) >= limit:
                capped.append((n, b, tot))
    return {"identified": identified, "n_identified": sum(identified.values()),
            "retrieved": retrieved, "retrieved_block": dict(retrieved_block),
            "n_fetched": n_fetched, "junk_by": junk_by, "n_junk": len(d["junk"]),
            "n_unique": n_unique, "n_dupes": max(n_fetched - n_unique, 0),
            "errors": errors, "found_by": found_by, "exclusive": exclusive,
            "years": years, "journals": journals, "authors": authors,
            "oa_checked": len(oa), "n_oa": n_oa, "capped": capped}


def prisma_numbers(d: dict, s: dict) -> dict:
    p = d["prisma"]
    g = lambda k: _int(p.get(k))  # noqa: E731
    return {
        "identified_by": s["identified"], "identified": s["n_identified"],
        "retrieved": s["n_fetched"] + s["n_junk"],
        "automation_removed": s["n_junk"], "duplicates_removed": s["n_dupes"],
        "to_screen": s["n_unique"],
        "screened": g("records_screened") if g("records_screened") is not None else s["n_unique"],
        "screened_manual": g("records_screened") is not None,
        "excluded": g("records_excluded"), "sought": g("reports_sought"),
        "not_retrieved": g("reports_not_retrieved"), "assessed": g("reports_assessed"),
        "excluded_reasons": {k: _int(v) for k, v in (p.get("excluded_reasons") or {}).items()},
        "studies_included": g("studies_included"), "reports_included": g("reports_included"),
    }


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

def suggest(d: dict, s: dict) -> list[str]:
    out = []
    counts, blocks, backends, meta = d["counts"], d["block_names"], d["backends"], d["meta"]
    if s["errors"]:
        bad = sorted({b for _, b in s["errors"]})
        out.append(f"{len(s['errors'])} backend call(s) failed ({', '.join(bad)}); "
                   f"rerun those with `--backends {' '.join(bad)}` or exclude them "
                   f"with `--skip` so the counts table is complete.")
    for n in blocks:
        vals = {b: _int(v) for b, v in counts.get(n, {}).items() if _int(v) is not None}
        if not vals:
            continue
        tot = sum(vals.values())
        big = [b for b, v in vals.items() if v > 2000]
        if big:
            out.append(f"Block {n}: {', '.join(f'{b} {vals[b]:,}' for b in big)} hits -- "
                       f"a generic term is probably driving this; tighten a group or add "
                       f"a more specific one before reading.")
        if tot == 0:
            out.append(f"Block {n}: zero hits on every backend. Either the intersection "
                       f"is genuinely empty (a finding -- check the synonyms first) or one "
                       f"group is too narrow; try dropping one group and rerunning.")
        elif tot <= 10:
            out.append(f"Block {n}: only {tot} hit(s) in total -- novelty-check territory. "
                       f"Read every record by hand before claiming a gap, and quote the "
                       f"Scopus / Web of Science count in the paper.")
        nz = [v for v in vals.values() if v > 0]
        if len(nz) >= 2 and max(nz) / max(min(nz), 1) > 20:
            out.append(f"Block {n}: counts differ >20x across backends "
                       f"({min(nz):,} to {max(nz):,}); grammar and coverage diverge, so "
                       f"do not compare these numbers -- discover here, quote one source.")
    if meta.get("counts_only"):
        out.append("This was a counts-only run: no records were fetched, so the record "
                   "sections and the deduplicated set are empty. Rerun without "
                   "`--counts-only` for records, RIS and PRISMA numbers.")
    if s["capped"]:
        worst = max(t for _, _, t in s["capped"])
        out.append(f"{len(s['capped'])} block/backend pair(s) hit the `--limit` cap "
                   f"({meta.get('limit')}); raise it (largest total {worst:,}) if you need "
                   f"the complete record set rather than the most-cited slice.")
    for b, k in s["junk_by"].items():
        r = s["retrieved"].get(b, 0)
        if r + k and k / (r + k) > 0.10:
            out.append(f"{b}: {k} of {r + k} records ({100 * k / (r + k):.0f}%) came from "
                       f"non-curated venues and were filtered; its raw count overstates "
                       f"the curated literature by about that much.")
    citation_grade = {"scopus", "wos", "ads"}
    if not citation_grade & set(backends):
        out.append("No citation-grade backend (Scopus, Web of Science, NASA ADS) was in "
                   "this run; add ADS (free token) or Scopus before quoting counts.")
    if d["unique"] and not s["oa_checked"]:
        out.append("Open-access status was not looked up; rerun with `--pdfs` (optionally "
                   "`--pdf-blocks`) to collect legal OA PDF links via Unpaywall.")
    if d["unique"] and d["prisma"].get("records_screened") is None:
        out.append("The PRISMA flow's manual stages are empty: fill in prisma.json in the "
                   "run directory (screened / excluded / assessed / included) and rerun "
                   "report.py to complete the diagram.")
    drift = _drift(d)
    for n, prev, now, when in drift:
        out.append(f"Block {n}: total hits changed from {prev:,} (run {when}) to {now:,}; "
                   f"count drift is expected as indexes grow, but a large jump usually "
                   f"means the query changed -- diff queries.json between the runs.")
    if not out:
        out.append("Nothing flagged: counts are in a sensible range on every backend and "
                   "every call succeeded. Next step is reading the small blocks by hand.")
    return out


def _drift(d: dict) -> list[tuple]:
    """Compare this run's per-block totals with the previous run of the same
    block in counts_history.csv."""
    out = []
    hist = d["history"]
    if not hist:
        return out
    for n in d["block_names"]:
        rows = [r for r in hist if r.get("block") == n and r.get("timestamp") != d["stamp"]]
        if not rows:
            continue
        last = max(r["timestamp"] for r in rows)
        prev = sum(_int(r["count"]) or 0 for r in rows if r["timestamp"] == last)
        now = sum(_int(v) or 0 for v in d["counts"].get(n, {}).values())
        if prev and now and (max(prev, now) / max(min(prev, now), 1)) > 1.5:
            out.append((n, prev, now, last))
    return out


# ---------------------------------------------------------------------------
# Document model: a list of nodes
#   ("h", level, text)   ("p", text)   ("ul", [items])   ("code", text)
#   ("table", headers, rows)   ("prisma", numbers)   ("hr",)
# Table cells are strings or ("link", text, url).
# ---------------------------------------------------------------------------

def _link(text, url):
    return ("link", str(text), url) if url else str(text)


def _doi_cell(r):
    doi = r.get("doi") or ""
    return _link(doi, f"https://doi.org/{doi}") if doi else _link("(link)", r.get("url")) \
        if r.get("url") else ""


def _groups_text(groups) -> str:
    return " AND ".join("(" + " OR ".join(g) + ")" for g in groups)


def _rec_rows(recs, full=False):
    rows = []
    for r in recs:
        au = r.get("authors") or []
        au_s = "; ".join(au) if full else "; ".join(au[:3]) + (" et al." if len(au) > 3 else "")
        rows.append([r.get("title", ""), au_s, r.get("year", ""), r.get("journal", ""),
                     str(r.get("cited_by", 0)), _doi_cell(r)])
    return rows


REC_HDR = ["Title", "Authors", "Year", "Venue", "Cited", "DOI"]


def build(d: dict, level: str = "simple") -> tuple[str, list]:
    """-> (title, nodes)"""
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    lvl = LEVELS.index(level)
    s = stats(d)
    meta, blocks, backends = d["meta"], d["block_names"], d["backends"]
    title = f"Literature search report -- run {d['stamp']}"
    N = []

    # --- 1. run metadata ------------------------------------------------
    N.append(("h", 1, title))
    N.append(("p", f"Generated by scitech-librarian {meta.get('version', VERSION)} "
                   f"(report level: {level}). Every number below is reproducible from "
                   f"the archived run directory `{d['run'].name}`."))
    mode = "counts only (no records fetched)" if meta.get("counts_only") \
        else f"full fetch, up to {meta.get('limit') or 'n/a'} records per block and backend"
    rows = [["Run started", meta.get("started", d["stamp"])],
            ["Duration", f"{meta.get('duration_s', 0):.0f} s" if meta.get("duration_s") else "n/a"],
            ["Query file", meta.get("query_file", "queries.json")],
            ["Blocks", ", ".join(blocks)],
            ["Backends", ", ".join(backends)],
            ["Mode", mode],
            ["Non-curated venue filter", "off (--keep-junk)" if meta.get("keep_junk") else "on"],
            ["Open-access lookup", "Unpaywall" if meta.get("pdfs") else "not run"],
            ["Interrupted", "yes -- partial run" if meta.get("interrupted") else "no"]]
    N.append(("table", ["Item", "Value"], rows))

    # --- 2. search strategy ---------------------------------------------
    N.append(("h", 2, "Search strategy"))
    N.append(("p", "Each block is one structural query -- a conjunction of synonym groups, "
                   "(a OR b) AND (c OR d) -- rendered into every backend's native grammar. "
                   "The strings below are exactly what was sent (PRISMA-S item 8)."))
    for n in blocks:
        b = d["blocks"].get(n, {})
        N.append(("h", 3, f"Block {n}: {b.get('title', n)}"))
        if b.get("note"):
            N.append(("p", f"Purpose: {b['note']}"))
        if b.get("groups"):
            N.append(("code", _groups_text(b["groups"])))
            if b.get("arxiv_groups"):
                N.append(("p", f"arXiv receives groups {b['arxiv_groups']} only "
                               f"(nested-boolean limitation)."))
        qrows = [[bk, d["queries"].get(n, {}).get(bk, "")] for bk in backends]
        N.append(("table", ["Backend", "Query string sent"], qrows))

    # --- 3. results summary ---------------------------------------------
    N.append(("h", 2, "Results summary"))
    hdr = ["Block"] + backends + ["Identified", "Retrieved", "Unique"]
    rows = []
    uniq_block = Counter(r.get("block") for r in d["unique"])
    for n in blocks:
        c = d["counts"].get(n, {})
        ident = sum(_int(v) or 0 for v in c.values())
        rows.append([n] + [str(c.get(bk, "-")) for bk in backends]
                    + [f"{ident:,}", str(s["retrieved_block"].get(n, 0)), str(uniq_block.get(n, 0))])
    rows.append(["Total"] + [f"{s['identified'][bk]:,}" for bk in backends]
                + [f"{s['n_identified']:,}", str(s["n_fetched"]), str(s["n_unique"])])
    N.append(("table", hdr, rows))
    N.append(("p", "Identified = database hit counts (not comparable across backends: "
                   "proximity operators are dropped and stemming differs). Retrieved = "
                   "records actually downloaded after the venue filter, capped by `--limit`. "
                   "Unique = after DOI/title deduplication across all backends."))
    if s["errors"]:
        N.append(("p", "Failed calls: " + ", ".join(f"{n}/{b}" for n, b in s["errors"]) + "."))

    # --- 4. PRISMA -------------------------------------------------------
    N.append(("h", 2, "PRISMA 2020 flow"))
    pn = prisma_numbers(d, s)
    N.append(("prisma", pn))
    frows = [["Records identified from databases", f"{pn['identified']:,}"]]
    frows += [[f"  {bk}", f"{pn['identified_by'].get(bk, 0):,}"] for bk in backends]
    frows += [["Records retrieved (downloaded)", f"{pn['retrieved']:,}"],
              ["Removed before screening: automation (non-curated venues)",
               f"{pn['automation_removed']:,}"],
              ["Removed before screening: duplicates", f"{pn['duplicates_removed']:,}"],
              ["Records to screen (unique)", f"{pn['to_screen']:,}"]]
    man = lambda v: "--" if v is None else f"{v:,}"  # noqa: E731
    frows += [["Records screened", man(pn["screened"]) + ("" if pn["screened_manual"] else " (assumed = unique)")],
              ["Records excluded at screening", man(pn["excluded"])],
              ["Reports sought for retrieval", man(pn["sought"])],
              ["Reports not retrieved", man(pn["not_retrieved"])],
              ["Reports assessed for eligibility", man(pn["assessed"])]]
    for reason, k in pn["excluded_reasons"].items():
        frows.append([f"  excluded: {reason}", man(k)])
    frows += [["Studies included", man(pn["studies_included"])],
              ["Reports of included studies", man(pn["reports_included"])]]
    N.append(("table", ["Stage", "n"], frows))
    N.append(("p", "Automation stages are computed from the run; '--' marks manual stages "
                   "not yet recorded in prisma.json. Note that 'identified' counts hits "
                   "reported by each database while 'retrieved' is what was downloaded "
                   "within `--limit`, so the two differ on large blocks."))

    N.append(("h", 3, "PRISMA-S search-reporting checklist"))
    N.append(("table", ["Item", "Requirement", "This search"], _prisma_s_rows(d, s)))

    # --- 5. records -----------------------------------------------------
    if d["unique"]:
        top = 10 if lvl == 0 else None
        N.append(("h", 2, "Records" if top is None else f"Top {top} records per block"))
        N.append(("p", "Deduplicated across backends, sorted by citation count."
                       + ("" if top is None else " The complete set is in all_records.csv / .ris.")))
        for n in blocks:
            recs = [r for r in d["unique"] if r.get("block") == n]
            if not recs:
                continue
            N.append(("h", 3, f"Block {n} ({len(recs)} unique)"))
            sel = recs[:top] if top else recs
            if lvl == 2:
                for r in sel:
                    N.append(("h", 4, r.get("title", "")))
                    au = "; ".join(r.get("authors") or []) or "(no authors)"
                    meta_line = f"{au}. {r.get('journal', '')} ({r.get('year', '')}). " \
                                f"Cited by {r.get('cited_by', 0)}."
                    found = sorted(s["found_by"].get(_key(r), {r.get('backend', '?')}))
                    meta_line += f" Found by: {', '.join(found)}."
                    if r.get("doi"):
                        meta_line += f" DOI: {r['doi']}"
                    elif r.get("url"):
                        meta_line += f" URL: {r['url']}"
                    if "is_oa" in r:
                        meta_line += f" OA: {'yes' if r.get('is_oa') else 'no'}" \
                                     + (f" ({r['oa_pdf']})" if r.get("oa_pdf") else "")
                    N.append(("p", meta_line))
                    if r.get("abstract"):
                        N.append(("p", "Abstract: " + r["abstract"]))
            else:
                N.append(("table", REC_HDR, _rec_rows(sel)))

    # --- 6. intermediate analyses ----------------------------------------
    if lvl >= 1 and d["unique"]:
        N.append(("h", 2, "Backend overlap"))
        rows = [[bk, str(s["retrieved"].get(bk, 0)), str(s["exclusive"].get(bk, 0)),
                 str(s["junk_by"].get(bk, 0))] for bk in backends]
        N.append(("table", ["Backend", "Retrieved", "Found only here", "Filtered venues"], rows))
        N.append(("p", "'Found only here' counts unique records no other backend in this "
                       "run returned -- a measure of each database's marginal contribution."))

        N.append(("h", 2, "Distributions"))
        ys = sorted(s["years"].items())
        if ys:
            N.append(("h", 3, "Publication year"))
            N.append(("table", ["Year", "Records"], [[y, str(k)] for y, k in ys]))
        if s["journals"]:
            N.append(("h", 3, "Top venues"))
            N.append(("table", ["Venue", "Records"],
                      [[j, str(k)] for j, k in s["journals"].most_common(15)]))
        if s["authors"]:
            N.append(("h", 3, "Most frequent authors"))
            N.append(("table", ["Author", "Records"],
                      [[a, str(k)] for a, k in s["authors"].most_common(15)]))
        if s["oa_checked"]:
            N.append(("h", 3, "Open access"))
            N.append(("p", f"{s['n_oa']} of {s['oa_checked']} records with a DOI have a legal "
                           f"open-access copy per Unpaywall "
                           f"({100 * s['n_oa'] / s['oa_checked']:.0f}%)."))
        if d["junk"]:
            N.append(("h", 2, "Filtered non-curated venues"))
            vc = Counter((r.get("journal") or "?").split("(")[0].strip() for r in d["junk"])
            N.append(("table", ["Venue", "Records removed"],
                      [[v, str(k)] for v, k in vc.most_common(20)]))
        if d["history"]:
            N.append(("h", 2, "Count history"))
            N.append(("p", "Per-block totals across archived runs (lit/counts_history.csv); "
                           "drift shows how the indexes -- or your queries -- changed."))
            rows = []
            stamps = sorted({r["timestamp"] for r in d["history"]})[-6:]
            for n in blocks:
                row = [n]
                for st in stamps:
                    tot = [_int(r["count"]) for r in d["history"]
                           if r["timestamp"] == st and r["block"] == n]
                    row.append(f"{sum(t for t in tot if t is not None):,}" if tot else "-")
                rows.append(row)
            N.append(("table", ["Block"] + stamps, rows))
        errs = [ln for ln in d["log"].splitlines() if "ERROR" in ln]
        if errs:
            N.append(("h", 2, "Errors"))
            N.append(("code", "\n".join(errs)))

    # --- 7. full dumps ---------------------------------------------------
    if lvl == 2:
        if d["raw"]:
            N.append(("h", 2, "Per-backend raw results (before deduplication)"))
            for stem, recs in d["raw"].items():
                if not recs:
                    continue
                N.append(("h", 3, f"{stem} ({len(recs)} records)"))
                N.append(("table", REC_HDR, _rec_rows(recs, full=True)))
        if d["junk"]:
            N.append(("h", 2, "Filtered records"))
            N.append(("table", REC_HDR + ["Backend"],
                      [row + [r.get("backend", "")] for row, r in
                       zip(_rec_rows(d["junk"], full=True), d["junk"])]))
        if meta.get("backend_config"):
            N.append(("h", 2, "Backend configuration"))
            rows = [[b, c.get("url", "(driver)"), c.get("auth", "none"),
                     c.get("paging", "-")] for b, c in meta["backend_config"].items()]
            N.append(("table", ["Backend", "Endpoint", "Auth", "Paging"], rows))
        if d["prisma"]:
            N.append(("h", 2, "prisma.json"))
            N.append(("code", json.dumps(d["prisma"], indent=2)))
        if d["log"]:
            N.append(("h", 2, "Run log"))
            N.append(("code", d["log"]))
        N.append(("h", 2, "Environment"))
        env = meta.get("environment", {})
        rows = [["Python", env.get("python", platform.python_version())],
                ["Platform", env.get("platform", platform.platform())],
                ["Tool version", meta.get("version", VERSION)],
                ["Report generated on", env.get("report_host", platform.node())]]
        N.append(("table", ["Item", "Value"], rows))

    # --- 8. suggestions --------------------------------------------------
    N.append(("h", 2, "Suggestions"))
    N.append(("ul", suggest(d, s)))
    return title, N


def _prisma_s_rows(d, s) -> list:
    meta, backends = d["meta"], d["backends"]
    started = meta.get("started", d["stamp"])
    limit = meta.get("limit")
    filt = "off" if meta.get("keep_junk") else "on: records from non-curated repositories " \
                                              "(Zenodo, Figshare, SSRN...) removed"
    prev = sorted({r["timestamp"] for r in d["history"] if r["timestamp"] != d["stamp"]})
    p = d["prisma"]
    auto = {
        "1": ", ".join(backends) + " (queried through their documented public APIs)",
        "2": f"{len(backends)} database{'s' if len(backends) != 1 else ''}, one structural query per block rendered into "
             f"each native grammar; see Search strategy",
        "5": p.get("citation_searching") or "not performed by the tool (manual, if any)",
        "7": p.get("other_methods") or "none",
        "8": "reported verbatim per backend under Search strategy; archived in queries.json",
        "9": ("counts only, no records" if meta.get("counts_only") else
              f"record download capped at {limit or 'n/a'} per block and backend, most-cited "
              f"first") + "; no date, language or document-type limits applied",
        "10": f"venue filter {filt}",
        "11": p.get("prior_work") or "none",
        "12": (f"{len(prev)} earlier run(s) archived; counts tracked in counts_history.csv"
               if prev else "first run of these blocks"),
        "13": f"all databases searched on {started}",
        "14": p.get("peer_review") or "none",
        "15": f"{s['n_identified']:,} identified; {s['n_fetched'] + s['n_junk']:,} retrieved; "
              f"{s['n_unique']:,} unique",
        "16": f"exact DOI match, else first 90 characters of the lower-cased title; "
              f"{s['n_dupes']:,} duplicates removed",
    }
    rows = []
    for num, name, kind in PRISMA_S_ITEMS:
        val = auto.get(num, "not applicable" if kind == "na" else "to be completed")
        rows.append([num, name, val])
    return rows


# ---------------------------------------------------------------------------
# PRISMA flow diagram helpers
# ---------------------------------------------------------------------------

def _flow_boxes(pn: dict) -> list[tuple[str, list[str]]]:
    """(column, lines) in reading order for the ASCII / TikZ / SVG renderers."""
    m = lambda v: "--" if v is None else f"{v:,}"  # noqa: E731
    ident = [f"{b}: {k:,}" for b, k in pn["identified_by"].items()]
    return [
        ("id-left", ["Records identified from databases", f"(n = {pn['identified']:,})"] + ident),
        ("id-right", ["Records removed before screening:",
                      f"automation tools (venue filter) (n = {pn['automation_removed']:,})",
                      f"duplicates removed (n = {pn['duplicates_removed']:,})"]),
        ("sc-left", [f"Records screened (n = {m(pn['screened'])})"]),
        ("sc-right", [f"Records excluded (n = {m(pn['excluded'])})"]),
        ("sc-left2", [f"Reports sought for retrieval (n = {m(pn['sought'])})"]),
        ("sc-right2", [f"Reports not retrieved (n = {m(pn['not_retrieved'])})"]),
        ("sc-left3", [f"Reports assessed for eligibility (n = {m(pn['assessed'])})"]),
        ("sc-right3", ["Reports excluded:"] + (
            [f"{r} (n = {m(k)})" for r, k in pn["excluded_reasons"].items()] or ["(n = --)"])),
        ("in-left", [f"Studies included in review (n = {m(pn['studies_included'])})",
                     f"Reports of included studies (n = {m(pn['reports_included'])})"]),
    ]


def _ascii_flow(pn: dict) -> str:
    boxes = dict(_flow_boxes(pn))
    W = 44

    def box(lines):
        wrapped = [w for ln in lines for w in (textwrap.wrap(ln, W - 4) or [""])]
        top = "+" + "-" * (W - 2) + "+"
        return [top] + [f"| {w:<{W - 4}} |" for w in wrapped] + [top]

    def pair(left, right, arrow=True):
        L, R = box(left), box(right) if right else []
        h = max(len(L), len(R))
        L += [" " * W] * (h - len(L))
        R += [" " * W] * (h - len(R))
        mid = h // 2
        out = []
        for i in range(h):
            conn = " --> " if (arrow and right and i == mid) else "     "
            out.append(L[i] + conn + R[i])
        return out

    lines = ["IDENTIFICATION"]
    lines += pair(boxes["id-left"], boxes["id-right"])
    lines += [" " * (W // 2) + "|", " " * (W // 2) + "v", "SCREENING"]
    lines += pair(boxes["sc-left"], boxes["sc-right"])
    lines += [" " * (W // 2) + "|", " " * (W // 2) + "v"]
    lines += pair(boxes["sc-left2"], boxes["sc-right2"])
    lines += [" " * (W // 2) + "|", " " * (W // 2) + "v"]
    lines += pair(boxes["sc-left3"], boxes["sc-right3"])
    lines += [" " * (W // 2) + "|", " " * (W // 2) + "v", "INCLUDED"]
    lines += pair(boxes["in-left"], None, arrow=False)
    return "\n".join(ln.rstrip() for ln in lines)


def _svg_flow(pn: dict) -> str:
    boxes = dict(_flow_boxes(pn))
    bw, lh, pad, gap = 300, 15, 10, 60
    x_left, x_right = 110, 110 + bw + gap
    y = 20
    els, positions = [], {}
    order = [("id-left", "id-right"), ("sc-left", "sc-right"), ("sc-left2", "sc-right2"),
             ("sc-left3", "sc-right3"), ("in-left", None)]
    labels = {"id-left": "Identification", "sc-left": "Screening", "in-left": "Included"}

    def draw(key, x, y0):
        lines = [w for ln in boxes[key] for w in textwrap.wrap(ln, 42) or [""]]
        h = len(lines) * lh + 2 * pad
        els.append(f'<rect x="{x}" y="{y0}" width="{bw}" height="{h}" rx="4" '
                   f'fill="var(--box)" stroke="var(--line)"/>')
        for i, ln in enumerate(lines):
            els.append(f'<text x="{x + pad}" y="{y0 + pad + lh * (i + 1) - 4}" '
                       f'font-size="11" fill="var(--fg)">{html.escape(ln)}</text>')
        positions[key] = (x, y0, h)
        return h

    for left, right in order:
        if left in labels:
            els.append(f'<text x="10" y="{y + 14}" font-size="11" font-weight="bold" '
                       f'fill="var(--fg)" transform="rotate(-90 10,{y + 14})" '
                       f'text-anchor="end">{labels[left]}</text>')
        h = draw(left, x_left, y)
        if right:
            hr = draw(right, x_right, y)
            els.append(f'<line x1="{x_left + bw}" y1="{y + h // 2}" x2="{x_right}" '
                       f'y2="{y + h // 2}" stroke="var(--line)" marker-end="url(#arr)"/>')
            h = max(h, hr)
        y += h + 30
    # vertical arrows between left boxes
    lefts = [k for k, _ in order]
    for a, b in zip(lefts, lefts[1:]):
        xa, ya, ha = positions[a]
        xb, yb, _ = positions[b]
        els.append(f'<line x1="{xa + bw // 2}" y1="{ya + ha}" x2="{xb + bw // 2}" y2="{yb}" '
                   f'stroke="var(--line)" marker-end="url(#arr)"/>')
    width = x_right + bw + 20
    return (f'<svg class="prisma" viewBox="0 0 {width} {y}" width="100%" '
            f'style="max-width:{width}px" xmlns="http://www.w3.org/2000/svg">'
            f'<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" '
            f'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="var(--line)"/></marker></defs>'
            + "".join(els) + "</svg>")


def _tikz_flow(pn: dict) -> str:
    boxes = dict(_flow_boxes(pn))

    def node(key):
        return " \\\\ ".join(_tex(w) for ln in boxes[key] for w in textwrap.wrap(ln, 40))

    return "\n".join([
        "\\begin{center}\\begin{tikzpicture}[node distance=9mm and 12mm,",
        "  box/.style={draw, rounded corners=2pt, text width=62mm, align=left, font=\\scriptsize},",
        "  lab/.style={rotate=90, font=\\scriptsize\\bfseries}]",
        f"\\node[box] (id) {{{node('id-left')}}};",
        f"\\node[box, right=of id] (idr) {{{node('id-right')}}};",
        f"\\node[box, below=of id] (sc) {{{node('sc-left')}}};",
        f"\\node[box, right=of sc] (scr) {{{node('sc-right')}}};",
        f"\\node[box, below=of sc] (sc2) {{{node('sc-left2')}}};",
        f"\\node[box, right=of sc2] (sc2r) {{{node('sc-right2')}}};",
        f"\\node[box, below=of sc2] (sc3) {{{node('sc-left3')}}};",
        f"\\node[box, right=of sc3] (sc3r) {{{node('sc-right3')}}};",
        f"\\node[box, below=of sc3] (inc) {{{node('in-left')}}};",
        "\\node[lab, left=3mm of id] {Identification};",
        "\\node[lab, left=3mm of sc2] {Screening};",
        "\\node[lab, left=3mm of inc] {Included};",
        "\\draw[->] (id) -- (idr); \\draw[->] (sc) -- (scr); \\draw[->] (sc2) -- (sc2r);",
        "\\draw[->] (sc3) -- (sc3r);",
        "\\draw[->] (id) -- (sc); \\draw[->] (sc) -- (sc2); \\draw[->] (sc2) -- (sc3);",
        "\\draw[->] (sc3) -- (inc);",
        "\\end{tikzpicture}\\end{center}",
    ])


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _cell_text(c) -> str:
    return c[1] if isinstance(c, tuple) else str(c)


def render_md(title: str, nodes: list) -> str:
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "h":
            out.append("#" * nd[1] + " " + nd[2] + "\n")
        elif k == "p":
            out.append(nd[1] + "\n")
        elif k == "ul":
            out.append("\n".join(f"- {it}" for it in nd[1]) + "\n")
        elif k == "code":
            out.append("```\n" + nd[1] + "\n```\n")
        elif k == "table":
            esc = lambda c: (f"[{c[1]}]({c[2]})" if isinstance(c, tuple)  # noqa: E731
                             else str(c).replace("|", "\\|").replace("\n", " "))
            out.append("| " + " | ".join(nd[1]) + " |")
            out.append("|" + "---|" * len(nd[1]))
            for row in nd[2]:
                out.append("| " + " | ".join(esc(c) for c in row) + " |")
            out.append("")
        elif k == "prisma":
            out.append("```\n" + _ascii_flow(nd[1]) + "\n```\n")
        elif k == "hr":
            out.append("---\n")
    return "\n".join(out)


def render_txt(title: str, nodes: list, width: int = 88) -> str:
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "h":
            t = nd[2]
            out.append("")
            out.append(t.upper() if nd[1] == 1 else t)
            out.append(("=" if nd[1] == 1 else "-" if nd[1] == 2 else "~")[0] * min(len(t), width))
        elif k == "p":
            out.append(textwrap.fill(nd[1], width))
            out.append("")
        elif k == "ul":
            for it in nd[1]:
                out.append(textwrap.fill(it, width, initial_indent="  * ", subsequent_indent="    "))
            out.append("")
        elif k == "code":
            out.extend("    " + ln for ln in nd[1].splitlines())
            out.append("")
        elif k == "table":
            out.append(_txt_table(nd[1], nd[2], width))
        elif k == "prisma":
            out.append(_ascii_flow(nd[1]))
            out.append("")
    return "\n".join(out).strip() + "\n"


def _txt_table(headers, rows, width) -> str:
    cells = [[_cell_text(c) for c in r] for r in rows]
    ncol = len(headers)
    widths = [max([len(headers[i])] + [len(r[i]) for r in cells if i < len(r)]) for i in range(ncol)]
    # squeeze the widest columns so the table fits
    while sum(widths) + 3 * (ncol - 1) > width and max(widths) > 12:
        widths[widths.index(max(widths))] -= 1
    lines = []

    def fmt(r):
        wrapped = [textwrap.wrap(r[i] if i < len(r) else "", widths[i]) or [""] for i in range(ncol)]
        h = max(len(w) for w in wrapped)
        return ["   ".join((w[j] if j < len(w) else "").ljust(widths[i])
                           for i, w in enumerate(wrapped)).rstrip() for j in range(h)]

    lines += fmt(headers)
    lines.append("   ".join("-" * w for w in widths))
    for r in cells:
        lines += fmt(r)
    return "\n".join(lines) + "\n"


_CSS = """
:root{--fg:#1b1b1b;--bg:#fff;--muted:#666;--line:#999;--box:#f6f6f6;--acc:#2a5db0}
@media(prefers-color-scheme:dark){:root{--fg:#e6e6e6;--bg:#151515;--muted:#aaa;--line:#888;--box:#222;--acc:#7aa7ff}}
body{font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg);max-width:1100px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.6rem}h2{border-bottom:1px solid var(--line);padding-bottom:.2rem;margin-top:2rem}
h4{margin:1.2rem 0 .2rem}table{border-collapse:collapse;width:100%;font-size:.88rem;margin:.6rem 0 1rem}
th,td{border:1px solid var(--line);padding:.3rem .5rem;text-align:left;vertical-align:top}
th{background:var(--box)}
pre{background:var(--box);padding:.6rem;overflow-x:auto;font-size:.82rem;white-space:pre-wrap}
a{color:var(--acc)}.wrap{overflow-x:auto}.meta{color:var(--muted)}
@media print{body{max-width:none;font-size:11pt}h2{page-break-after:avoid}}
"""


def render_html(title: str, nodes: list) -> str:
    e = html.escape
    out = [f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           f"<title>{e(title)}</title><style>{_CSS}</style></head><body>"]
    for nd in nodes:
        k = nd[0]
        if k == "h":
            out.append(f"<h{nd[1]}>{e(nd[2])}</h{nd[1]}>")
        elif k == "p":
            out.append(f"<p>{_html_inline(nd[1])}</p>")
        elif k == "ul":
            out.append("<ul>" + "".join(f"<li>{_html_inline(i)}</li>" for i in nd[1]) + "</ul>")
        elif k == "code":
            out.append(f"<pre>{e(nd[1])}</pre>")
        elif k == "table":
            cell = lambda c: (f'<a href="{e(c[2])}">{e(c[1])}</a>' if isinstance(c, tuple)  # noqa: E731
                              else e(str(c)))
            out.append('<div class="wrap"><table><thead><tr>'
                       + "".join(f"<th>{e(h)}</th>" for h in nd[1]) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{cell(c)}</td>" for c in r) + "</tr>"
                                 for r in nd[2]) + "</tbody></table></div>")
        elif k == "prisma":
            out.append(_svg_flow(nd[1]))
        elif k == "hr":
            out.append("<hr>")
    out.append("</body></html>")
    return "\n".join(out)


def _html_inline(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"(https?://[^\s)]+)", r'<a href="\1">\1</a>', t)
    return t


_TEX_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
            "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\^{}"}


def _tex(s: str) -> str:
    return "".join(_TEX_ESC.get(ch, ch) for ch in str(s))


def _tex_inline(s: str) -> str:
    parts = re.split(r"(`[^`]+`)", s)
    return "".join(f"\\texttt{{{_tex(p[1:-1])}}}" if p.startswith("`") and p.endswith("`") and len(p) > 1
                   else _tex(p) for p in parts)


def render_tex(title: str, nodes: list) -> str:
    out = [
        "\\documentclass[10pt,a4paper]{article}",
        "\\usepackage{iftex}",
        "\\ifPDFTeX\\usepackage[utf8]{inputenc}\\usepackage[T1]{fontenc}\\usepackage{lmodern}",
        "\\else\\usepackage{fontspec}\\fi",
        "\\usepackage[margin=2cm]{geometry}\\usepackage{longtable}\\usepackage{array}",
        "\\usepackage{tikz}\\usetikzlibrary{positioning,arrows.meta}",
        "\\usepackage{xurl}\\usepackage[hidelinks]{hyperref}\\usepackage{fancyvrb}",
        "\\setlength{\\parskip}{4pt}\\setlength{\\parindent}{0pt}",
        "\\tikzset{>={Latex}}",
        f"\\title{{{_tex(title)}}}\\author{{scitech-librarian {VERSION}}}\\date{{\\today}}",
        "\\begin{document}\\maketitle",
    ]
    sec = {1: None, 2: "section", 3: "subsection", 4: "subsubsection"}
    for nd in nodes:
        k = nd[0]
        if k == "h":
            if sec.get(nd[1]):
                out.append(f"\\{sec[nd[1]]}*{{{_tex(nd[2])}}}")
        elif k == "p":
            out.append(_tex_inline(nd[1]) + "\n")
        elif k == "ul":
            out.append("\\begin{itemize}" + "".join(f"\\item {_tex_inline(i)}" for i in nd[1])
                       + "\\end{itemize}")
        elif k == "code":
            wrapped = "\n".join(w for ln in nd[1].splitlines()
                                for w in (textwrap.wrap(ln, 105, replace_whitespace=False,
                                                        drop_whitespace=False) or [""]))
            out.append("\\begin{Verbatim}[fontsize=\\scriptsize]\n" + wrapped
                       + "\n\\end{Verbatim}")
        elif k == "table":
            out.append(_tex_table(nd[1], nd[2]))
        elif k == "prisma":
            out.append(_tikz_flow(nd[1]))
        elif k == "hr":
            out.append("\\hrule")
    out.append("\\end{document}")
    return "\n".join(out)


def _tex_table(headers, rows) -> str:
    """Column widths proportional to content length (capped), so a table
    whose long text sits in the last column still reads."""
    n = len(headers)
    lens = []
    for i in range(n):
        vals = [len(_cell_text(r[i])) for r in rows if i < len(r)] + [len(headers[i])]
        lens.append(min(max(vals), 60) + 4)
    total = sum(lens)
    widths = [max(0.06, 0.94 * ln / total) for ln in lens]
    scale = 0.94 / sum(widths)
    spec = "".join(f"p{{{w * scale:.3f}\\linewidth}}" for w in widths)
    cell = lambda c: (f"\\href{{{c[2]}}}{{{_tex(c[1])}}}" if isinstance(c, tuple)  # noqa: E731
                      else _tex(c))
    lines = ["{\\scriptsize\\begin{longtable}{" + spec + "}", "\\hline",
             " & ".join(f"\\textbf{{{_tex(h)}}}" for h in headers) + " \\\\ \\hline",
             "\\endhead"]
    for r in rows:
        r = list(r) + [""] * (n - len(r))
        lines.append(" & ".join(cell(c) for c in r[:n]) + " \\\\")
    lines += ["\\hline", "\\end{longtable}}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PDF: LaTeX -> pandoc -> built-in text writer
# ---------------------------------------------------------------------------

def _pdf_builtin(text: str, path: Path) -> None:
    """Minimal stdlib PDF: Courier 8pt, wrapped monospaced text, page breaks.
    Ugly but dependency-free -- the guarantee that --format pdf never fails."""
    lines = [w for ln in text.splitlines() for w in (textwrap.wrap(ln, 100,
             replace_whitespace=False, drop_whitespace=False) or [""])]
    per_page = 70
    pages = [lines[i:i + per_page] for i in range(0, max(len(lines), 1), per_page)]

    def esc(s):
        s = s.encode("latin-1", "replace").decode("latin-1")
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objs = []  # index+1 = object number

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    page_ids = []
    kids_placeholder = add(b"")  # pages object, filled later
    for pg in pages:
        stream = "BT /F1 8 Tf 10 TL 36 806 Td " + " ".join(f"({esc(ln)}) Tj T*" for ln in pg) + " ET"
        sb = stream.encode("latin-1")
        cid = add(b"<< /Length " + str(len(sb)).encode() + b" >>\nstream\n" + sb + b"\nendstream")
        pid = add(f"<< /Type /Page /Parent {kids_placeholder} 0 R /MediaBox [0 0 595 842] "
                  f"/Resources << /Font << /F1 {font} 0 R >> >> /Contents {cid} 0 R >>".encode())
        page_ids.append(pid)
    objs[kids_placeholder - 1] = (f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] "
                                  f"/Count {len(page_ids)} >>").encode()
    catalog = add(f"<< /Type /Catalog /Pages {kids_placeholder} 0 R >>".encode())
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n"
            ).encode()
    path.write_bytes(bytes(out))


def _run(cmd: list, cwd: Path, timeout: int = 180) -> bool:
    try:
        r = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def make_pdf(tex_path: Path, md_path: Path, txt: str, pdf_path: Path) -> str:
    """Try LaTeX engines, then pandoc, then the built-in writer. Returns the
    name of the method that produced the file."""
    cwd = pdf_path.parent
    stem = tex_path.stem
    for eng in ("xelatex", "lualatex", "pdflatex"):
        if shutil.which(eng):
            ok = all(_run([eng, "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd)
                     for _ in range(2))
            produced = cwd / f"{stem}.pdf"
            for ext in (".aux", ".log", ".out", ".toc"):
                try:
                    (cwd / f"{stem}{ext}").unlink()
                except OSError:
                    pass
            if ok and produced.exists():
                if produced != pdf_path:
                    produced.replace(pdf_path)
                return eng
    if shutil.which("pandoc") and md_path.exists():
        if _run(["pandoc", md_path.name, "-o", pdf_path.name], cwd) and pdf_path.exists():
            return "pandoc"
    _pdf_builtin(txt, pdf_path)
    return "builtin"


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def write_reports(run: Path, level: str = "simple", formats=("md",),
                  basename: str = "report", quiet: bool = False) -> dict:
    """Render one run at one level into every requested format.
    -> {format: path}. Writes prisma.json template if absent."""
    run = Path(run)
    formats = list(dict.fromkeys(formats))
    for f in formats:
        if f not in FORMATS:
            raise ValueError(f"unknown format {f!r}; choose from {FORMATS}")
    pj = run / "prisma.json"
    if not pj.exists():
        pj.write_text(json.dumps(PRISMA_TEMPLATE, indent=2), encoding="utf-8")
    d = load_run(run)
    title, nodes = build(d, level)
    written = {}
    need = set(formats)
    if "pdf" in need:
        need |= {"tex", "md", "txt"}       # candidates for the PDF chain
    rendered = {}
    if "md" in need:
        rendered["md"] = render_md(title, nodes)
    if "html" in need:
        rendered["html"] = render_html(title, nodes)
    if "tex" in need:
        rendered["tex"] = render_tex(title, nodes)
    if "txt" in need:
        rendered["txt"] = render_txt(title, nodes)
    for f, text in rendered.items():
        if f in formats or (f == "tex" and "pdf" in formats):
            p = run / f"{basename}.{f}"
            p.write_text(text, encoding="utf-8")
            if f in formats:
                written[f] = p
    if "pdf" in formats:
        tex_p = run / f"{basename}.tex"
        md_p = run / f"{basename}.md"
        tmp_md = None
        if "md" not in formats:
            md_p.write_text(rendered["md"], encoding="utf-8")
            tmp_md = md_p
        pdf_p = run / f"{basename}.pdf"
        how = make_pdf(tex_p, md_p, rendered["txt"], pdf_p)
        if tmp_md:
            tmp_md.unlink()
        if "tex" not in formats:
            tex_p.unlink()
        written["pdf"] = pdf_p
        if not quiet:
            print(f"    pdf via {how}" + ("  (install TeX Live or pandoc for a typeset PDF)"
                                          if how == "builtin" else ""))
    if not quiet:
        for f, p in written.items():
            print(f"    report ({level}): {p}")
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?", help="run directory (lit/runs/<stamp>)")
    ap.add_argument("--latest", action="store_true", help="use the newest run under lit/runs")
    ap.add_argument("--level", choices=LEVELS, default="simple")
    ap.add_argument("--format", nargs="+", choices=FORMATS, default=["md"])
    ap.add_argument("--basename", default="report", help="output file stem (default: report)")
    args = ap.parse_args()
    if args.latest:
        here = Path(__file__).resolve().parent
        root = here.parent if here.name == "tools" else here
        runs = sorted((root / "lit" / "runs").glob("*"))
        if not runs:
            print("no runs found", file=sys.stderr)
            return 2
        run = runs[-1]
    elif args.run:
        run = Path(args.run)
    else:
        ap.print_help()
        return 2
    if not (run / "counts.json").exists():
        print(f"{run} is not a run directory (no counts.json)", file=sys.stderr)
        return 2
    write_reports(run, args.level, args.format, args.basename)
    return 0


if __name__ == "__main__":
    sys.exit(main())
