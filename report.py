#!/usr/bin/env python3
"""
report.py -- literature-search reports for one run or a whole research
directory, with a PRISMA 2020 flow.

    python report.py lit/runs/20260815T095908                 # one run: simple, markdown
    python report.py --latest --level full --format html pdf  # newest run
    python report.py --project                                # everything in lit/, merged
    python report.py --project --since 2026-06-01 --diff      # what the searches since June added
    python report.py --project --backends ads scopus --min-metric 3 --metric openalex_2yr
    python report.py --project --records colleague.ris --sources all --format pdf

librarian.py calls this automatically at the end of every run
(--report-level / --report-format / --no-report); run it by hand to re-render
any archived run, or the merged project, without re-querying.

Levels
------
simple        metadata, sources, search strategy (structural + exact per-backend
              query strings), results summary, timeline (project), PRISMA 2020
              flow + PRISMA-S checklist, top records per block, suggestions
intermediate  + every unique record, backend overlap, year / venue / author
              distributions, journal metrics, filtered venues, errors,
              open-access stats, count drift against previous runs
full          + every record with full abstract and author list and which
              sources found it, per-source raw lists before deduplication,
              filtered records, backend endpoint configuration, the complete
              run log (single run), environment

Formats: md (Markdown), html, tex (LaTeX), pdf, txt (plain text).
PDF is compiled from the LaTeX with xelatex / lualatex / pdflatex when one is
installed, else with pandoc, else with a built-in stdlib writer (plain text
layout) -- the option never fails, the quality just degrades.

Filters (both modes; member filters apply to --project only)
------------------------------------------------------------
  --since DATE --until DATE   members (runs / manual sources) by search date
  --latest                    only the most recent member (project) / newest run
  --diff                      only records first seen inside the window
  --year-from Y --year-to Y   publication year
  --backends ... --blocks ... restrict databases / blocks
  --sources auto|manual|all   which member kinds (default all)
  --records FILE ...          extra RIS/BibTeX/CSV/JSON as a transient manual source
  --metric NAME --min-metric X   journal metric threshold (journals.py)
  --min-citations N  --oa-only  --top N  --sort cited|year|metric

PRISMA
------
Automatable stages are filled from the data: records identified per database
(and per manual source that is a database export), identified via other
methods (manual sources by --method), removed by automation (the venue
filter), duplicates removed, records to screen. The manual stages come from
prisma.json in the run directory, or screening.json in the research
directory for --project; a template is written on the first report.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import platform
import re
import shutil
import subprocess
import sys
import textwrap
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    import project as _project
    import journals as _journals
except ImportError:                     # report.py copied alone: single-run mode only
    _project = _journals = None
try:
    from librarian import VERSION          # single source of the version number
except ImportError:
    try:
        from litscan import VERSION        # type: ignore
    except ImportError:
        VERSION = "unknown"
LEVELS = ("simple", "intermediate", "full")
FORMATS = ("md", "html", "tex", "pdf", "txt")

# PRISMA-S (Rethlefsen et al. 2021, doi:10.1186/s13643-020-01542-z) items.
PRISMA_S_ITEMS = [
    ("1", "Database name", "auto"),
    ("2", "Multi-database searching", "auto"),
    ("3", "Study registries", "na"),
    ("4", "Online resources and browsing", "auto"),
    ("5", "Citation searching", "auto"),
    ("6", "Contacts", "auto"),
    ("7", "Other methods", "auto"),
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
                "excluded_reasons maps a reason to a count. The other_* keys are "
                "the right-hand column (records identified via other methods).",
    "records_screened": None,
    "records_excluded": None,
    "reports_sought": None,
    "reports_not_retrieved": None,
    "reports_assessed": None,
    "excluded_reasons": {},
    "other_sought": None,
    "other_not_retrieved": None,
    "other_assessed": None,
    "other_excluded_reasons": {},
    "studies_included": None,
    "reports_included": None,
    "citation_searching": "",
    "other_methods": "",
    "prior_work": "",
    "peer_review": "",
}


# ---------------------------------------------------------------------------
# Loading: one run, or a research directory
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


def _history(outdir: Path) -> list:
    hfile = Path(outdir) / "counts_history.csv"
    if hfile.exists():
        with hfile.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    return []


def load_run(run: Path) -> dict:
    """Everything the report needs, read from one archived run directory.
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
    outdir = run.parent.parent
    if "started" not in meta:
        m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", run.name)
        meta["started"] = "{}-{}-{} {}:{}:{}".format(*m.groups()) if m else run.name
    block_names = meta.get("blocks") or list(counts)
    backends = meta.get("backends") or sorted({b for c in counts.values() for b in c})
    for r in uniq:
        r.setdefault("found_by", [r.get("backend", "?")])
    return {"run": run, "stamp": meta.get("stamp") or run.name, "meta": meta,
            "counts": counts, "queries": queries, "blocks": blocks,
            "block_names": block_names, "backends": backends,
            "unique": uniq, "raw": raw, "junk": junk, "prisma": prisma,
            "log": log, "history": _history(outdir), "project": None, "members": [],
            "journals": _journals.load_store(outdir) if _journals else {},
            "prisma_file": run / "prisma.json", "outdir": outdir, "filters": {}}


def load_project(outdir: Path, since: str = "", until: str = "", latest: bool = False,
                 sources: str = "all", extra_records: list | None = None) -> dict:
    """Merge every member of a research directory into the same shape
    load_run() returns, plus project/members provenance."""
    if not _project:
        raise RuntimeError("project.py is needed for --project")
    outdir = Path(outdir)
    p = _project.load_project(outdir)
    ms = _project.members(outdir, p)
    if sources != "all":
        ms = [m for m in ms if m["kind"] == ("run" if sources == "auto" else "manual")]
    if since:
        ms = [m for m in ms if m["date"][:10] >= since]
    if until:
        ms = [m for m in ms if m["date"][:10] <= until]
    if latest and ms:
        ms = ms[-1:]
    for f in extra_records or []:
        f = Path(f)
        recs = _project.parse_records(f)
        for r in recs:
            r["block"] = r.get("block") or "MANUAL"
            r["backend"] = f"manual:{f.stem}"
        ms.append({"id": f.stem, "kind": "manual", "path": f, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "label": "given on the command line (not stored)", "method": "other",
                   "source": {"origin": str(f), "method": "other"}, "_records": recs})
    aliases = p["block_aliases"]
    raw, junk, counts, queries, blocks = {}, [], defaultdict(dict), {}, {}
    all_recs, backends, cfg = [], [], {}
    limit, keep_junk, pdfs = 0, False, False
    for m in ms:
        recs = m.get("_records") or _project.member_records(m, aliases)
        m["n_records"] = len(recs)
        all_recs.extend(recs)
        for r in recs:
            raw.setdefault(f"{m['id']}/{r.get('block', '')}_{r.get('backend', '')}", []).append(r)
        if m["kind"] == "run":
            meta = m.get("meta", {})
            limit = max(limit, meta.get("limit") or 0)
            keep_junk = keep_junk or bool(meta.get("keep_junk"))
            pdfs = pdfs or bool(meta.get("pdfs"))
            cfg.update(meta.get("backend_config", {}))
            run_counts = _json(m["path"] / "counts.json", {})
            declared = meta.get("backends") or sorted({b for c in run_counts.values() for b in c})
            for b in declared:                 # pre-3.1 runs have no meta.json: infer from counts
                if b not in backends:
                    backends.append(b)
            for n, c in run_counts.items():
                n = aliases.get(n, n)
                for b, v in c.items():
                    if _int(v) is not None:       # an earlier "ERR" is superseded by a number
                        counts[n][b] = (_int(counts[n].get(b)) or 0) + _int(v)
                    elif b not in counts[n]:
                        counts[n][b] = v
            for n, q in _json(m["path"] / "queries.json", {}).items():
                queries[aliases.get(n, n)] = q          # latest run wins (members are sorted)
            for n, b in _json(m["path"] / "blocks.json", {}).items():
                blocks[aliases.get(n, n)] = b
            for r in _json(m["path"] / "junk.json", []):
                r["member"] = m["id"]
                junk.append(r)
        else:
            b = f"manual:{m['id']}"
            if b not in backends:
                backends.append(b)
            for r in recs:
                counts[r.get("block", "MANUAL")][b] = counts[r.get("block", "MANUAL")].get(b, 0) + 1
            blocks.setdefault(r.get("block", "MANUAL") if recs else "MANUAL",
                              {"title": "records from manual sources", "note": "", "groups": []})
    uniq = _project.merge(all_recs)
    block_names = list(blocks) + [n for n in counts if n not in blocks]
    dates = [m["date"][:10] for m in ms]
    meta = {"version": VERSION, "stamp": "project", "blocks": block_names, "backends": backends,
            "started": (f"{min(dates)} to {max(dates)}" if dates else "n/a"),
            "limit": limit, "counts_only": False, "keep_junk": keep_junk, "pdfs": pdfs,
            "interrupted": False, "backend_config": cfg, "query_file": "per run",
            "environment": {"python": platform.python_version(), "platform": sys.platform}}
    return {"run": outdir, "stamp": f"{p['name']}", "meta": meta, "counts": dict(counts),
            "queries": queries, "blocks": blocks, "block_names": block_names,
            "backends": backends, "unique": uniq, "raw": raw, "junk": junk,
            "prisma": _json(outdir / "screening.json", {}), "log": "",
            "history": _history(outdir), "project": p, "members": ms,
            "journals": _journals.load_store(outdir) if _journals else {},
            "prisma_file": outdir / "screening.json", "outdir": outdir,
            "filters": {k: v for k, v in (("since", since), ("until", until),
                                          ("latest", latest), ("sources", sources)) if v}}


# ---------------------------------------------------------------------------
# Filters on records (both modes)
# ---------------------------------------------------------------------------

def _metric_of(d: dict, r: dict, metric: str):
    if not d.get("journals") or not _journals:
        return None, None
    idx = d.setdefault("_jidx", _journals.alias_index(d["journals"]))
    return _journals.metric_value(_journals.lookup(d["journals"], r, idx), metric)


def apply_filters(d: dict, backends=None, blocks=None, year_from=None, year_to=None,
                  min_citations=None, oa_only=False, metric=None, min_metric=None,
                  diff=False, since="", until="") -> dict:
    """Restrict d['unique'] and d['raw'] in place; records the filters used."""
    f = d["filters"]

    def keep(r):
        if backends and r.get("backend") not in backends and not (
                r.get("found_by") and any(x.split("@")[0] in backends for x in r["found_by"])):
            return False
        if blocks and r.get("block") not in blocks and not set(r.get("blocks", [])) & set(blocks):
            return False
        y = _int(r.get("year"))
        if year_from and (y is None or y < year_from):
            return False
        if year_to and (y is None or y > year_to):
            return False
        if min_citations and (r.get("cited_by") or 0) < min_citations:
            return False
        if oa_only and not r.get("is_oa"):
            return False
        if min_metric is not None:
            v, _ = _metric_of(d, r, metric or "openalex_2yr")
            if v is None or v < min_metric:
                return False
        if diff:
            fs = (r.get("first_seen") or "")[:10]
            if since and fs < since:
                return False
            if until and fs > until:
                return False
        return True

    d["unique"] = [r for r in d["unique"] if keep(r)]
    d["raw"] = {k: [r for r in v if keep(r)] for k, v in d["raw"].items()}
    d["raw"] = {k: v for k, v in d["raw"].items() if v}
    if backends:
        d["backends"] = [b for b in d["backends"] if b in backends]
        f["backends"] = " ".join(backends)
    if blocks:
        d["block_names"] = [b for b in d["block_names"] if b in blocks]
        f["blocks"] = " ".join(blocks)
    for k, v in (("year_from", year_from), ("year_to", year_to), ("min_citations", min_citations),
                 ("oa_only", oa_only), ("min_metric", min_metric), ("diff", diff)):
        if v:
            f[k] = v
    if min_metric is not None:
        f["metric"] = metric or "openalex_2yr"
    return d


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
    if limit and not d.get("project"):
        for stem, recs in d["raw"].items():
            n, b = stem.rsplit("_", 1)
            tot = _int(counts.get(n, {}).get(b))
            if tot and tot > limit and len(recs) + junk_by.get(b, 0) >= limit:
                capped.append((n, b, tot))
    # identification via other methods: manual members whose method is not "database"
    other_by = Counter()
    for m in d.get("members") or []:
        if m["kind"] == "manual" and m.get("method") != "database":
            other_by[m.get("method", "other")] += m.get("n_records", 0)
    db_backends = [b for b in backends if not (b.startswith("manual:") and other_by and any(
        m["id"] == b[7:] and m.get("method") != "database" for m in d.get("members") or []))]
    return {"identified": identified, "n_identified": sum(identified[b] for b in db_backends),
            "db_backends": db_backends, "other_by": other_by, "n_other": sum(other_by.values()),
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
        "identified_by": {b: s["identified"][b] for b in s["db_backends"]},
        "identified": s["n_identified"],
        "other_by": dict(s["other_by"]), "other": s["n_other"],
        "retrieved": s["n_fetched"] + s["n_junk"],
        "automation_removed": s["n_junk"], "duplicates_removed": s["n_dupes"],
        "to_screen": s["n_unique"],
        "screened": g("records_screened") if g("records_screened") is not None else s["n_unique"],
        "screened_manual": g("records_screened") is not None,
        "excluded": g("records_excluded"), "sought": g("reports_sought"),
        "not_retrieved": g("reports_not_retrieved"), "assessed": g("reports_assessed"),
        "excluded_reasons": {k: _int(v) for k, v in (p.get("excluded_reasons") or {}).items()},
        "other_sought": g("other_sought"), "other_not_retrieved": g("other_not_retrieved"),
        "other_assessed": g("other_assessed"),
        "other_excluded_reasons": {k: _int(v) for k, v in (p.get("other_excluded_reasons") or {}).items()},
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
        vals = {b: _int(v) for b, v in counts.get(n, {}).items()
                if _int(v) is not None and not b.startswith("manual:")}
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
    if not citation_grade & set(backends) and not any(b.startswith("manual:wos") for b in backends):
        out.append("No citation-grade backend (Scopus, Web of Science, NASA ADS) was in "
                   "this search; add ADS (free token) or Scopus before quoting counts.")
    if d["unique"] and not s["oa_checked"]:
        out.append("Open-access status was not looked up; rerun with `--pdfs` (optionally "
                   "`--pdf-blocks`) to collect legal OA PDF links via Unpaywall.")
    if d["unique"] and d["prisma"].get("records_screened") is None:
        out.append(f"The PRISMA flow's manual stages are empty: fill in "
                   f"{Path(d['prisma_file']).name} (screened / excluded / assessed / included) "
                   f"and rerun report.py to complete the diagram.")
    if d["unique"] and not d.get("journals"):
        out.append("No journal metrics on file; run `python journals.py fetch` (OpenAlex, no "
                   "key) to add impact-factor-like figures and enable `--min-metric`.")
    if d.get("project") and not any(m["kind"] == "manual" for m in d["members"]):
        out.append("Every source is an automated run. Records you obtained by hand -- a "
                   "Zotero export, a reference list, a Web of Science session -- go in with "
                   "`python project.py ingest FILE --method citation|database|...` and then "
                   "appear in the PRISMA flow's other-methods column.")
    for n, prev, now, when in _drift(d):
        out.append(f"Block {n}: total hits changed from {prev:,} (run {when}) to {now:,}; "
                   f"count drift is expected as indexes grow, but a large jump usually "
                   f"means the query changed -- diff queries.json between the runs.")
    if not out:
        out.append("Nothing flagged: counts are in a sensible range on every backend and "
                   "every call succeeded. Next step is reading the small blocks by hand.")
    return out


def _drift(d: dict) -> list[tuple]:
    out = []
    hist = d["history"]
    if not hist or d.get("project"):
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


REC_HDR = ["Title", "Authors", "Year", "Venue", "Cited", "DOI"]


def _rec_rows(d, recs, full=False, metric=None):
    rows = []
    for r in recs:
        au = r.get("authors") or []
        au_s = "; ".join(au) if full else "; ".join(au[:3]) + (" et al." if len(au) > 3 else "")
        row = [r.get("title", ""), au_s, r.get("year", ""), r.get("journal", ""),
               str(r.get("cited_by", 0)), _doi_cell(r)]
        if metric:
            v, y = _metric_of(d, r, metric)
            row.append(f"{v:g} ({y})" if v is not None else "")
        rows.append(row)
    return rows


def _sorted(recs, sort, d, metric):
    if sort == "year":
        return sorted(recs, key=lambda r: -(_int(r.get("year")) or 0))
    if sort == "metric":
        return sorted(recs, key=lambda r: -(_metric_of(d, r, metric)[0] or 0))
    return recs   # already by citations


def build(d: dict, level: str = "simple", top: int | None = None, sort: str = "cited",
          metric: str | None = None) -> tuple[str, list]:
    """-> (title, nodes)"""
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    lvl = LEVELS.index(level)
    s = stats(d)
    meta, blocks, backends = d["meta"], d["block_names"], d["backends"]
    proj = d.get("project")
    metric = metric or (proj or {}).get("defaults", {}).get("metric") or "openalex_2yr"
    have_metrics = bool(d.get("journals"))
    rec_hdr = REC_HDR + ([_journals.METRICS.get(metric, metric)] if have_metrics and _journals else [])
    title = (f"Literature search report -- {proj['name']}" if proj
             else f"Literature search report -- run {d['stamp']}")
    N = []

    # --- 1. metadata --------------------------------------------------------
    N.append(("h", 1, title))
    N.append(("p", f"Generated by scitech-librarian {meta.get('version', VERSION)} "
                   f"(report level: {level}). Every number below is reproducible from "
                   f"the archived {'research directory' if proj else 'run directory'} "
                   f"`{Path(d['run']).name}`."))
    mode = "counts only (no records fetched)" if meta.get("counts_only") \
        else f"full fetch, up to {meta.get('limit') or 'n/a'} records per block and backend"
    rows = [["Search dates" if proj else "Run started", meta.get("started", d["stamp"])]]
    if proj:
        rows += [["Project", proj["name"]], ["Description", proj.get("description") or "-"],
                 ["Sources", f"{sum(1 for m in d['members'] if m['kind'] == 'run')} automated run(s), "
                             f"{sum(1 for m in d['members'] if m['kind'] == 'manual')} manual source(s)"]]
    else:
        rows += [["Duration", f"{meta.get('duration_s', 0):.0f} s" if meta.get("duration_s") else "n/a"],
                 ["Query file", meta.get("query_file", "queries.json")]]
    rows += [["Blocks", ", ".join(blocks)],
             ["Backends / sources", ", ".join(backends)],
             ["Mode", mode],
             ["Non-curated venue filter", "off (--keep-junk)" if meta.get("keep_junk") else "on"],
             ["Open-access lookup", "Unpaywall" if meta.get("pdfs") else "not run"],
             ["Journal metrics", f"on file for {len(d['journals'])} journals" if have_metrics else "none (journals.py fetch)"],
             ["Filters", ", ".join(f"{k}={v}" for k, v in d["filters"].items()) or "none"]]
    if not proj:
        rows.append(["Interrupted", "yes -- partial run" if meta.get("interrupted") else "no"])
    N.append(("table", ["Item", "Value"], rows))

    # --- 2. sources (project) -------------------------------------------------
    if proj:
        N.append(("h", 2, "Sources"))
        N.append(("p", "Every search that feeds this report, oldest first. 'New here' counts "
                       "unique records that no earlier source had found -- what each search added."))
        first = Counter()
        for r in d["unique"]:
            fb = [x.split("@", 1)[1] for x in r.get("found_by", []) if "@" in x]
            dates = {m["id"]: m["date"] for m in d["members"]}
            if fb:
                first[min(fb, key=lambda i: dates.get(i, ""))] += 1
        rows = []
        for m in d["members"]:
            desc = (m.get("meta", {}).get("query_file", "") if m["kind"] == "run"
                    else m.get("source", {}).get("origin", ""))
            rows.append([m["id"], m["kind"], m["date"][:16], m.get("method", ""),
                         str(m.get("n_records", 0)), str(first.get(m["id"], 0)),
                         m.get("label") or desc])
        N.append(("table", ["Source", "Kind", "Date", "Method", "Records", "New here", "Label / origin"], rows))

    # --- 3. search strategy ---------------------------------------------------
    N.append(("h", 2, "Search strategy"))
    N.append(("p", "Each block is one structural query -- a conjunction of synonym groups, "
                   "(a OR b) AND (c OR d) -- rendered into every backend's native grammar. "
                   "The strings below are exactly what was sent (PRISMA-S item 8)"
                   + (", from the most recent run of each block." if proj else ".")))
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
        qrows = [[bk, d["queries"].get(n, {}).get(bk, "")] for bk in backends
                 if not bk.startswith("manual:")]
        if qrows:
            N.append(("table", ["Backend", "Query string sent"], qrows))

    # --- 4. results summary ---------------------------------------------------
    N.append(("h", 2, "Results summary"))
    hdr = ["Block"] + backends + ["Identified", "Retrieved", "Unique"]
    rows = []
    uniq_block = Counter()
    for r in d["unique"]:
        for bn in (r.get("blocks") or [r.get("block")]):
            uniq_block[bn] += 1
    for n in blocks:
        c = d["counts"].get(n, {})
        ident = sum(_int(v) or 0 for v in c.values())
        rows.append([n] + [str(c.get(bk, "-")) for bk in backends]
                    + [f"{ident:,}", str(s["retrieved_block"].get(n, 0)), str(uniq_block.get(n, 0))])
    rows.append(["Total"] + [f"{s['identified'][bk]:,}" for bk in backends]
                + [f"{s['n_identified'] + s['n_other']:,}", str(s["n_fetched"]), str(s["n_unique"])])
    N.append(("table", hdr, rows))
    N.append(("p", "Identified = database hit counts (not comparable across backends: "
                   "proximity operators are dropped and stemming differs)"
                   + ("; summed over runs, and for manual sources the number of records ingested"
                      if proj else "")
                   + ". Retrieved = records actually downloaded after the venue filter, capped "
                     "by `--limit`. Unique = after DOI/title deduplication across all sources."))
    if s["errors"]:
        N.append(("p", "Failed calls: " + ", ".join(f"{n}/{b}" for n, b in s["errors"]) + "."))

    # --- 5. timeline (project) ------------------------------------------------
    if proj:
        runs = [m for m in d["members"] if m["kind"] == "run"]
        if len(runs) >= 1:
            N.append(("h", 2, "Timeline"))
            N.append(("p", "Per-block hit totals in each automated run (sum over backends), "
                           "oldest first; drift shows how the indexes -- or the queries -- changed."))
            hdr = ["Block"] + [m["id"] for m in runs]
            rows = []
            for n in blocks:
                row = [n]
                for m in runs:
                    c = _json(m["path"] / "counts.json", {})
                    al = proj["block_aliases"]
                    vals = [v for k, v in c.items() if al.get(k, k) == n]
                    row.append(f"{sum(_int(x) or 0 for c_ in vals for x in c_.values()):,}" if vals else "-")
                rows.append(row)
            N.append(("table", hdr, rows))
        fs = Counter((r.get("first_seen") or "")[:7] for r in d["unique"] if r.get("first_seen"))
        if fs:
            N.append(("h", 3, "When records entered the project"))
            N.append(("table", ["Month", "Records first seen"],
                      [[k, str(v)] for k, v in sorted(fs.items())]))

    # --- 6. PRISMA -----------------------------------------------------------
    N.append(("h", 2, "PRISMA 2020 flow"))
    pn = prisma_numbers(d, s)
    N.append(("prisma", pn))
    man = lambda v: "--" if v is None else f"{v:,}"  # noqa: E731
    frows = [["Records identified from databases", f"{pn['identified']:,}"]]
    frows += [[f"  {bk}", f"{v:,}"] for bk, v in pn["identified_by"].items()]
    if pn["other_by"]:
        frows.append(["Records identified via other methods", f"{pn['other']:,}"])
        frows += [[f"  {k}", f"{v:,}"] for k, v in pn["other_by"].items()]
    frows += [["Records retrieved (downloaded / ingested)", f"{pn['retrieved']:,}"],
              ["Removed before screening: automation (non-curated venues)",
               f"{pn['automation_removed']:,}"],
              ["Removed before screening: duplicates", f"{pn['duplicates_removed']:,}"],
              ["Records to screen (unique)", f"{pn['to_screen']:,}"],
              ["Records screened", man(pn["screened"]) + ("" if pn["screened_manual"] else " (assumed = unique)")],
              ["Records excluded at screening", man(pn["excluded"])],
              ["Reports sought for retrieval", man(pn["sought"])],
              ["Reports not retrieved", man(pn["not_retrieved"])],
              ["Reports assessed for eligibility", man(pn["assessed"])]]
    for reason, k in pn["excluded_reasons"].items():
        frows.append([f"  excluded: {reason}", man(k)])
    if pn["other_by"]:
        frows += [["Other methods: reports sought", man(pn["other_sought"])],
                  ["Other methods: reports not retrieved", man(pn["other_not_retrieved"])],
                  ["Other methods: reports assessed", man(pn["other_assessed"])]]
        for reason, k in pn["other_excluded_reasons"].items():
            frows.append([f"  other methods, excluded: {reason}", man(k)])
    frows += [["Studies included", man(pn["studies_included"])],
              ["Reports of included studies", man(pn["reports_included"])]]
    N.append(("table", ["Stage", "n"], frows))
    N.append(("p", f"Automation stages are computed from the data; '--' marks manual stages "
                   f"not yet recorded in {Path(d['prisma_file']).name}. Note that 'identified' "
                   f"counts hits reported by each database while 'retrieved' is what was "
                   f"downloaded within `--limit`, so the two differ on large blocks."))

    N.append(("h", 3, "PRISMA-S search-reporting checklist"))
    N.append(("table", ["Item", "Requirement", "This search"], _prisma_s_rows(d, s)))

    # --- 7. records ----------------------------------------------------------
    if d["unique"]:
        top_n = top if top is not None else (10 if lvl == 0 else None)
        N.append(("h", 2, "Records" if not top_n else f"Top {top_n} records per block"))
        N.append(("p", f"Deduplicated across sources, sorted by {sort}."
                       + ("" if not top_n else " The complete set is in all_records.csv / .ris"
                          + (" of each run." if proj else "."))))
        for n in blocks:
            recs = [r for r in d["unique"] if n in (r.get("blocks") or [r.get("block")])]
            if not recs:
                continue
            recs = _sorted(recs, sort, d, metric)
            N.append(("h", 3, f"Block {n} ({len(recs)} unique)"))
            sel = recs[:top_n] if top_n else recs
            if lvl == 2:
                for r in sel:
                    N.append(("h", 4, r.get("title", "")))
                    au = "; ".join(r.get("authors") or []) or "(no authors)"
                    line = f"{au}. {r.get('journal', '')} ({r.get('year', '')}). " \
                           f"Cited by {r.get('cited_by', 0)}."
                    found = r.get("found_by") or sorted(s["found_by"].get(_key(r), {r.get('backend', '?')}))
                    line += f" Found by: {', '.join(found)}."
                    if have_metrics:
                        v, y = _metric_of(d, r, metric)
                        if v is not None:
                            line += f" {metric}: {v:g} ({y})."
                    if r.get("doi"):
                        line += f" DOI: {r['doi']}"
                    elif r.get("url"):
                        line += f" URL: {r['url']}"
                    if "is_oa" in r:
                        line += f" OA: {'yes' if r.get('is_oa') else 'no'}" \
                                + (f" ({r['oa_pdf']})" if r.get("oa_pdf") else "")
                    N.append(("p", line))
                    if r.get("abstract"):
                        N.append(("p", "Abstract: " + r["abstract"]))
            else:
                N.append(("table", rec_hdr, _rec_rows(d, sel, metric=metric if have_metrics else None)))

    # --- 8. intermediate analyses ---------------------------------------------
    if lvl >= 1 and d["unique"]:
        N.append(("h", 2, "Source overlap"))
        rows = [[bk, str(s["retrieved"].get(bk, 0)), str(s["exclusive"].get(bk, 0)),
                 str(s["junk_by"].get(bk, 0))] for bk in backends]
        N.append(("table", ["Source", "Retrieved", "Found only here", "Filtered venues"], rows))
        N.append(("p", "'Found only here' counts unique records no other source returned "
                       "-- a measure of each database's marginal contribution."))

        N.append(("h", 2, "Distributions"))
        ys = sorted(s["years"].items())
        if ys:
            N.append(("h", 3, "Publication year"))
            N.append(("table", ["Year", "Records"], [[y, str(k)] for y, k in ys]))
        if s["journals"]:
            N.append(("h", 3, "Top venues"))
            rows = []
            for j, k in s["journals"].most_common(15):
                row = [j, str(k)]
                if have_metrics:
                    v, y = _metric_of(d, {"journal": j}, metric)
                    row.append(f"{v:g} ({y})" if v is not None else "")
                rows.append(row)
            N.append(("table", ["Venue", "Records"] + ([_journals.METRICS.get(metric, metric)]
                                                       if have_metrics else []), rows))
        if s["authors"]:
            N.append(("h", 3, "Most frequent authors"))
            N.append(("table", ["Author", "Records"],
                      [[a, str(k)] for a, k in s["authors"].most_common(15)]))
        if s["oa_checked"]:
            N.append(("h", 3, "Open access"))
            N.append(("p", f"{s['n_oa']} of {s['oa_checked']} records with a DOI have a legal "
                           f"open-access copy per Unpaywall "
                           f"({100 * s['n_oa'] / s['oa_checked']:.0f}%)."))
        if have_metrics:
            N.extend(_metrics_section(d, s, metric))
        if d["junk"]:
            N.append(("h", 2, "Filtered non-curated venues"))
            vc = Counter((r.get("journal") or "?").split("(")[0].strip() for r in d["junk"])
            N.append(("table", ["Venue", "Records removed"],
                      [[v, str(k)] for v, k in vc.most_common(20)]))
        if d["history"] and not proj:
            N.append(("h", 2, "Count history"))
            N.append(("p", "Per-block totals across archived runs (counts_history.csv); "
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

    # --- 9. full dumps --------------------------------------------------------
    if lvl == 2:
        if d["raw"]:
            N.append(("h", 2, "Per-source raw results (before deduplication)"))
            for stem, recs in d["raw"].items():
                if not recs:
                    continue
                N.append(("h", 3, f"{stem} ({len(recs)} records)"))
                N.append(("table", REC_HDR, _rec_rows(d, recs, full=True)))
        if d["junk"]:
            N.append(("h", 2, "Filtered records"))
            N.append(("table", REC_HDR + ["Source"],
                      [row + [r.get("backend", "")] for row, r in
                       zip(_rec_rows(d, d["junk"], full=True), d["junk"])]))
        if meta.get("backend_config"):
            N.append(("h", 2, "Backend configuration"))
            rows = [[b, c.get("url", "(driver)"), c.get("auth", "none"),
                     c.get("paging", "-")] for b, c in meta["backend_config"].items()]
            N.append(("table", ["Backend", "Endpoint", "Auth", "Paging"], rows))
        if proj:
            N.append(("h", 2, "project.json"))
            N.append(("code", json.dumps(proj, indent=2)))
            for m in d["members"]:
                if m["kind"] == "manual" and m.get("source"):
                    N.append(("h", 3, f"manual/{m['id']}/source.json"))
                    N.append(("code", json.dumps(m["source"], indent=2)))
        if d["prisma"]:
            N.append(("h", 2, Path(d["prisma_file"]).name))
            N.append(("code", json.dumps(d["prisma"], indent=2)))
        if d["log"]:
            N.append(("h", 2, "Run log"))
            N.append(("code", d["log"]))
        N.append(("h", 2, "Environment"))
        env = meta.get("environment", {})
        rows = [["Python", env.get("python", platform.python_version())],
                ["Platform", env.get("platform", platform.platform())],
                ["Tool version", meta.get("version", VERSION)],
                ["Report generated", time.strftime("%Y-%m-%d %H:%M")]]
        N.append(("table", ["Item", "Value"], rows))

    # --- 10. suggestions ------------------------------------------------------
    N.append(("h", 2, "Suggestions"))
    N.append(("ul", suggest(d, s)))
    return title, N


def _metrics_section(d, s, metric) -> list:
    """Top venues by the chosen metric among venues in the record set, and the
    evolution table for venues with two or more years on file."""
    N = [("h", 2, "Journal metrics")]
    label = _journals.METRICS.get(metric, metric)
    N.append(("p", f"Metric: {label} ({metric}), from {Path(d['outdir']).name}/journals/metrics.json "
                   f"(journals.py). Values are kept per year; the evolution table shows every "
                   f"year on file for venues that appear in this record set."))
    idx = d.setdefault("_jidx", _journals.alias_index(d["journals"]))
    seen, rows, evo = set(), [], []
    for j, k in s["journals"].most_common():
        e = _journals.lookup(d["journals"], {"journal": j}, idx)
        if not e or id(e) in seen:
            continue
        seen.add(id(e))
        v, y = _journals.metric_value(e, metric)
        if v is not None:
            q = e.get("quartile", {}).get(y, "")
            rows.append((v, [e["name"], str(k), f"{v:g}", y, q]))
        series = e.get("metrics", {}).get(metric) or {}
        if len(series) >= 2:
            evo.append([e["name"]] + [f"{series[yy]:g}" for yy in sorted(series)] +
                       [", ".join(sorted(series))])
    rows.sort(key=lambda x: -x[0])
    if rows:
        N.append(("h", 3, f"Venues in this set by {label}"))
        N.append(("table", ["Venue", "Records", label, "Year", "Q"], [r for _, r in rows[:25]]))
    if evo:
        N.append(("h", 3, f"{label}: evolution"))
        width = max(len(r) for r in evo)
        N.append(("table", ["Venue"] + [f"y{i}" for i in range(1, width - 1)] + ["Years"],
                  [r[:-1] + [""] * (width - len(r)) + [r[-1]] for r in evo]))
    return N


def _prisma_s_rows(d, s) -> list:
    meta, backends = d["meta"], d["backends"]
    started = meta.get("started", d["stamp"])
    limit = meta.get("limit")
    filt = "off" if meta.get("keep_junk") else "on: records from non-curated repositories " \
                                              "(Zenodo, Figshare, SSRN...) removed"
    prev = sorted({r["timestamp"] for r in d["history"] if r["timestamp"] != d["stamp"]})
    p = d["prisma"]
    manual = [m for m in d.get("members") or [] if m["kind"] == "manual"]
    by_method = defaultdict(list)
    for m in manual:
        by_method[m.get("method", "other")].append(m["id"])
    dbs = [b for b in backends if not b.startswith("manual:")]
    auto = {
        "1": ", ".join(dbs) + " (documented public APIs)"
             + (f"; manual database exports: {', '.join(by_method['database'])}" if by_method["database"] else ""),
        "2": f"{len(dbs)} database{'s' if len(dbs) != 1 else ''}, one structural query per block "
             f"rendered into each native grammar; see Search strategy",
        "4": ", ".join(by_method["website"]) if by_method["website"] else "none recorded",
        "5": ", ".join(by_method["citation"]) or p.get("citation_searching") or "not performed",
        "6": ", ".join(by_method["expert"]) if by_method["expert"] else "none recorded",
        "7": ", ".join(by_method["organisation"] + by_method["other"]) or p.get("other_methods") or "none",
        "8": "reported verbatim per backend under Search strategy; archived in queries.json"
             + (" of each run" if d.get("project") else ""),
        "9": ("counts only, no records" if meta.get("counts_only") else
              f"record download capped at {limit or 'n/a'} per block and backend, most-cited "
              f"first") + "; no date, language or document-type limits applied"
             + (f"; report filters: {', '.join(f'{k}={v}' for k, v in d['filters'].items())}"
                if d["filters"] else ""),
        "10": f"venue filter {filt}",
        "11": p.get("prior_work") or "none",
        "12": (f"{len(prev)} earlier run(s) archived; counts tracked in counts_history.csv"
               if prev and not d.get("project") else
               f"{sum(1 for m in d.get('members') or [] if m['kind'] == 'run')} run(s) combined; see Timeline"
               if d.get("project") else "first run of these blocks"),
        "13": f"searched on {started}",
        "14": p.get("peer_review") or "none",
        "15": f"{s['n_identified']:,} identified from databases"
              + (f", {s['n_other']:,} via other methods" if s["n_other"] else "")
              + f"; {s['n_fetched'] + s['n_junk']:,} retrieved; {s['n_unique']:,} unique",
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
    """(key, lines) for the ASCII / TikZ / SVG renderers. The 'other' boxes
    exist only when records came in via other methods."""
    m = lambda v: "--" if v is None else f"{v:,}"  # noqa: E731
    ident = [f"{b}: {k:,}" for b, k in pn["identified_by"].items()]
    boxes = [
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
    if pn.get("other_by"):
        boxes += [
            ("ot-id", ["Records identified via other methods", f"(n = {pn['other']:,})"]
                      + [f"{k}: {v:,}" for k, v in pn["other_by"].items()]),
            ("ot-sought", [f"Reports sought for retrieval (n = {m(pn['other_sought'])})",
                           f"not retrieved (n = {m(pn['other_not_retrieved'])})"]),
            ("ot-assessed", [f"Reports assessed for eligibility (n = {m(pn['other_assessed'])})"]
                            + [f"excluded: {r} (n = {m(k)})" for r, k in pn["other_excluded_reasons"].items()]),
        ]
    return boxes


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

    arrow = [" " * (W // 2) + "|", " " * (W // 2) + "v"]
    lines = ["IDENTIFICATION"]
    lines += pair(boxes["id-left"], boxes["id-right"])
    if "ot-id" in boxes:
        lines += ["", "IDENTIFICATION VIA OTHER METHODS"]
        lines += pair(boxes["ot-id"], boxes["ot-sought"])
        lines += pair(boxes["ot-assessed"], None, arrow=False)
    lines += arrow + ["SCREENING"]
    lines += pair(boxes["sc-left"], boxes["sc-right"])
    lines += arrow
    lines += pair(boxes["sc-left2"], boxes["sc-right2"])
    lines += arrow
    lines += pair(boxes["sc-left3"], boxes["sc-right3"])
    lines += arrow + ["INCLUDED"]
    lines += pair(boxes["in-left"], None, arrow=False)
    return "\n".join(ln.rstrip() for ln in lines)


def _svg_flow(pn: dict) -> str:
    boxes = dict(_flow_boxes(pn))
    bw, lh, pad, gap = 300, 15, 10, 60
    x_left, x_right = 110, 110 + bw + gap
    y = 20
    els, positions = [], {}
    order = [("id-left", "id-right")]
    if "ot-id" in boxes:
        order += [("ot-id", "ot-sought"), ("ot-assessed", None)]
    order += [("sc-left", "sc-right"), ("sc-left2", "sc-right2"),
              ("sc-left3", "sc-right3"), ("in-left", None)]
    labels = {"id-left": "Identification", "ot-id": "Other methods",
              "sc-left": "Screening", "in-left": "Included"}

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

    out = [
        "\\begin{center}\\begin{tikzpicture}[node distance=9mm and 12mm,",
        "  box/.style={draw, rounded corners=2pt, text width=62mm, align=left, font=\\scriptsize},",
        "  lab/.style={rotate=90, font=\\scriptsize\\bfseries}]",
        f"\\node[box] (id) {{{node('id-left')}}};",
        f"\\node[box, right=of id] (idr) {{{node('id-right')}}};",
    ]
    prev = "id"
    if "ot-id" in boxes:
        out += [f"\\node[box, below=of id] (ot) {{{node('ot-id')}}};",
                f"\\node[box, right=of ot] (otr) {{{node('ot-sought')}}};",
                f"\\node[box, below=of ot] (ota) {{{node('ot-assessed')}}};",
                "\\node[lab, left=3mm of ot] {Other methods};",
                "\\draw[->] (ot) -- (otr); \\draw[->] (ot) -- (ota); \\draw[->] (id) -- (ot);"]
        prev = "ota"
    out += [
        f"\\node[box, below=of {prev}] (sc) {{{node('sc-left')}}};",
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
        f"\\draw[->] ({prev}) -- (sc); \\draw[->] (sc) -- (sc2); \\draw[->] (sc2) -- (sc3);",
        "\\draw[->] (sc3) -- (inc);",
        "\\end{tikzpicture}\\end{center}",
    ]
    return "\n".join(out)


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
            "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\^{}",
            # a cell starting with [ right after \\ would be read as an optional
            # argument (real data: "[WITHDRAWN] ..." titles)
            "[": "{[}", "]": "{]}"}


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
        "\\setlength{\\parskip}{4pt}\\setlength{\\parindent}{0pt}\\setlength{\\tabcolsep}{3pt}",
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
    # usable width: \linewidth minus 2*\tabcolsep (3pt) per column, so a
    # ten-column counts table does not run off the page
    usable = 0.98 - 0.0125 * n
    widths = [max(0.045, usable * ln / total) for ln in lens]
    scale = usable / sum(widths)
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

    objs = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    page_ids = []
    kids_placeholder = add(b"")
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


def _run(cmd: list, cwd: Path, timeout: int = 1800) -> bool:
    # 30 min per pass: a full-level report on a few thousand records is >1000
    # pages and takes xelatex several minutes.
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

def write_reports(run: Path | None = None, level: str = "simple", formats=("md",),
                  basename: str = "report", quiet: bool = False, d: dict | None = None,
                  out_dir: Path | None = None, **build_kw) -> dict:
    """Render one run (or a prepared data dict) at one level into every
    requested format. -> {format: path}. Writes the PRISMA template if absent."""
    formats = list(dict.fromkeys(formats))
    for f in formats:
        if f not in FORMATS:
            raise ValueError(f"unknown format {f!r}; choose from {FORMATS}")
    if d is None:
        d = load_run(Path(run))
    pj = Path(d["prisma_file"])
    if not pj.exists():
        pj.parent.mkdir(parents=True, exist_ok=True)
        pj.write_text(json.dumps(PRISMA_TEMPLATE, indent=2), encoding="utf-8")
    out_dir = Path(out_dir) if out_dir else Path(d["run"])
    out_dir.mkdir(parents=True, exist_ok=True)
    title, nodes = build(d, level, **build_kw)
    written = {}
    need = set(formats)
    if "pdf" in need:
        need |= {"tex", "md", "txt"}
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
            p = out_dir / f"{basename}.{f}"
            p.write_text(text, encoding="utf-8")
            if f in formats:
                written[f] = p
    if "pdf" in formats:
        tex_p = out_dir / f"{basename}.tex"
        md_p = out_dir / f"{basename}.md"
        tmp_md = None
        if "md" not in formats:
            md_p.write_text(rendered["md"], encoding="utf-8")
            tmp_md = md_p
        pdf_p = out_dir / f"{basename}.pdf"
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
    ap.add_argument("--version", action="version", version=f"scitech-librarian {VERSION}")
    ap.add_argument("--project", action="store_true",
                    help="merge every run and manual source in the research directory")
    ap.add_argument("--latest", action="store_true",
                    help="newest run (single mode) / most recent member only (--project)")
    ap.add_argument("--level", choices=LEVELS, default=None,
                    help="simple | intermediate | full (default: project.json default, else simple)")
    ap.add_argument("--format", nargs="+", choices=FORMATS, default=None,
                    help="md html tex pdf txt (default: project.json default, else md)")
    ap.add_argument("--basename", default="report", help="output file stem (default: report)")
    ap.add_argument("--out", default=None,
                    help="output directory (default: the run dir, or <outdir>/reports/<stamp>-<level>)")
    g = ap.add_argument_group("filters")
    g.add_argument("--since", default="", metavar="YYYY-MM-DD", help="members searched on/after")
    g.add_argument("--until", default="", metavar="YYYY-MM-DD", help="members searched on/before")
    g.add_argument("--diff", action="store_true",
                   help="only records first seen inside the --since/--until window")
    g.add_argument("--year-from", type=int, default=None, help="publication year >=")
    g.add_argument("--year-to", type=int, default=None, help="publication year <=")
    g.add_argument("--backends", nargs="+", default=None, help="databases / sources to include")
    g.add_argument("--blocks", nargs="+", default=None, help="blocks to include")
    g.add_argument("--sources", choices=("auto", "manual", "all"), default="all",
                   help="member kinds (project): automated runs, manual sources, or both")
    g.add_argument("--records", nargs="+", default=None, metavar="FILE",
                   help="extra RIS/BibTeX/CSV/JSON files included as a transient manual source")
    g.add_argument("--metric", default=None,
                   help="journal metric name for tables, sorting and --min-metric "
                        "(default openalex_2yr; see journals.py)")
    g.add_argument("--min-metric", type=float, default=None, help="keep records whose venue metric >=")
    g.add_argument("--min-citations", type=int, default=None)
    g.add_argument("--oa-only", action="store_true", help="only records with a legal OA copy (needs --pdfs data)")
    g.add_argument("--top", type=int, default=None, help="records per block in tables (default 10 / all)")
    g.add_argument("--sort", choices=("cited", "year", "metric"), default="cited")
    if _project:
        _project.add_common_args(ap)
    else:
        ap.add_argument("--outdir", default=None)
        ap.add_argument("--quiet", "-q", action="store_true")
        ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    outdir = _project.resolve_outdir(args.outdir) if _project else Path(args.outdir or "lit")
    log = _project.setup_logging("report", args, outdir) if _project else None
    if args.project:
        d = load_project(outdir, args.since, args.until, args.latest, args.sources, args.records)
        stamp = time.strftime("%Y%m%dT%H%M%S")
        level = args.level or d["project"]["defaults"].get("level", "simple")
        formats = args.format or d["project"]["defaults"].get("format", ["md"])
        out_dir = Path(args.out) if args.out else outdir / "reports" / f"{stamp}-{level}"
    else:
        if args.latest:
            runs = sorted((outdir / "runs").glob("*"))
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
        d = load_run(run)
        if args.records and _project:
            for f in args.records:
                recs = _project.parse_records(Path(f))
                for r in recs:
                    r["block"], r["backend"] = r.get("block") or "MANUAL", f"manual:{Path(f).stem}"
                d["raw"][f"MANUAL_manual:{Path(f).stem}"] = recs
                d["backends"].append(f"manual:{Path(f).stem}")
            d["unique"] = _project.merge([r for v in d["raw"].values() for r in v])
        level = args.level or "simple"
        formats = args.format or ["md"]
        out_dir = Path(args.out) if args.out else run
    apply_filters(d, args.backends, args.blocks, args.year_from, args.year_to, args.min_citations,
                  args.oa_only, args.metric, args.min_metric, args.diff, args.since, args.until)
    written = write_reports(None, level, formats, args.basename, quiet=args.quiet, d=d,
                            out_dir=out_dir, top=args.top, sort=args.sort, metric=args.metric)
    if log:
        for f, p in written.items():
            log.debug("wrote %s", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
