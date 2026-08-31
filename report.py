#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Fabio Campolim
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
import json
import platform
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import i18n as _i18n
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
            m["queries"] = _json(m["path"] / "queries.json", {})
            for n, q in m["queries"].items():
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
                blk = r.get("block") or "MANUAL"
                counts[blk][b] = counts[blk].get(b, 0) + 1
                blocks.setdefault(blk, {"title": "records from manual sources", "note": "", "groups": []})
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
    junk_pair = Counter((r.get("block", "?"), r.get("backend", "?")) for r in d["junk"])
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
            if tot and tot > limit and len(recs) + junk_pair.get((n, b), 0) >= limit:
                capped.append((n, b, tot))
    # identification via other methods: manual members whose method is not "database"
    other_by = Counter()
    for m in d.get("members") or []:
        if m["kind"] == "manual" and m.get("method") != "database":
            other_by[m.get("method", "other")] += m.get("n_records", 0)
    other_sources = {f"manual:{m['id']}" for m in d.get("members") or []
                     if m["kind"] == "manual" and m.get("method") != "database"}
    db_backends = [b for b in backends if b not in other_sources]
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

def suggest(d: dict, s: dict, lang: str = "en") -> list[str]:
    _ = _i18n.translator(lang)
    out = []
    counts, blocks, backends, meta = d["counts"], d["block_names"], d["backends"], d["meta"]
    if s["errors"]:
        bad = sorted({b for _, b in s["errors"]})
        out.append(_("{n} backend call(s) failed ({bad}); rerun those with `--backends {flags}` "
                     "or exclude them with `--skip` so the counts table is complete.",
                     n=len(s["errors"]), bad=", ".join(bad), flags=" ".join(bad)))
    for n in blocks:
        vals = {b: _int(v) for b, v in counts.get(n, {}).items()
                if _int(v) is not None and not b.startswith("manual:")}
        if not vals:
            continue
        tot = sum(vals.values())
        big = [b for b, v in vals.items() if v > 2000]
        if big:
            out.append(_("Block {n}: {big} hits -- a generic term is probably driving this; "
                         "tighten a group or add a more specific one before reading.",
                         n=n, big=", ".join(f"{b} {_.num(vals[b])}" for b in big)))
        if tot == 0:
            out.append(_("Block {n}: zero hits on every backend. Either the intersection is "
                         "genuinely empty (a finding -- check the synonyms first) or one group "
                         "is too narrow; try dropping one group and rerunning.", n=n))
        elif tot <= 10:
            out.append(_("Block {n}: only {tot} hit(s) in total -- novelty-check territory. Read "
                         "every record by hand before claiming a gap, and quote the Scopus / Web "
                         "of Science count in the paper.", n=n, tot=tot))
        nz = [v for v in vals.values() if v > 0]
        if len(nz) >= 2 and max(nz) / max(min(nz), 1) > 20:
            out.append(_("Block {n}: counts differ >20x across backends ({lo} to {hi}); grammar "
                         "and coverage diverge, so do not compare these numbers -- discover "
                         "here, quote one source.", n=n, lo=_.num(min(nz)), hi=_.num(max(nz))))
    if meta.get("counts_only"):
        out.append(_("This was a counts-only run: no records were fetched, so the record "
                     "sections and the deduplicated set are empty. Rerun without "
                     "`--counts-only` for records, RIS and PRISMA numbers."))
    if s["capped"]:
        worst = max(t for _x, _y, t in s["capped"])
        out.append(_("{n} block/backend pair(s) hit the `--limit` cap ({limit}); raise it "
                     "(largest total {worst}) if you need the complete record set rather than "
                     "the most-cited slice.", n=len(s["capped"]), limit=meta.get("limit"),
                     worst=_.num(worst)))
    for b, k in s["junk_by"].items():
        r = s["retrieved"].get(b, 0)
        if r + k and k / (r + k) > 0.10:
            out.append(_("{b}: {k} of {tot} records ({pct}%) came from non-curated venues and "
                         "were filtered; its raw count overstates the curated literature by "
                         "about that much.", b=b, k=k, tot=r + k, pct=f"{100 * k / (r + k):.0f}"))
    citation_grade = {"scopus", "wos", "ads"}
    if not citation_grade & set(backends) and not any(b.startswith("manual:wos") for b in backends):
        out.append(_("No citation-grade backend (Scopus, Web of Science, NASA ADS) was in this "
                     "search; add ADS (free token) or Scopus before quoting counts."))
    if d["unique"] and not s["oa_checked"]:
        out.append(_("Open-access status was not looked up; rerun with `--pdfs` (optionally "
                     "`--pdf-blocks`) to collect legal OA PDF links via Unpaywall."))
    if d["unique"] and d["prisma"].get("records_screened") is None:
        out.append(_("The PRISMA flow's manual stages are empty: fill in {file} (screened / "
                     "excluded / assessed / included) and rerun report.py to complete the "
                     "diagram.", file=Path(d["prisma_file"]).name))
    if d["unique"] and not d.get("journals"):
        out.append(_("No journal metrics on file; run `python journals.py fetch` (OpenAlex, no "
                     "key) to add impact-factor-like figures and enable `--min-metric`."))
    runs = [m for m in d.get("members") or [] if m["kind"] == "run" and m.get("queries")]
    dup = []
    for i, a in enumerate(runs):
        for b in runs[i + 1:]:
            same = [n for n in a["queries"] if n in b["queries"] and a["queries"][n] == b["queries"][n]]
            if same and len(same) == len(a["queries"]):
                dup.append((a["id"], b["id"]))
    for a, b in dup[:3]:
        out.append(_("Runs {a} and {b} sent identical query strings; PRISMA 'identified' sums "
                     "both. If one was a reconnaissance of the same search, hide it with "
                     "`python project.py exclude {a}` so hits are not counted twice.", a=a, b=b))
    if d.get("project") and not any(m["kind"] == "manual" for m in d["members"]):
        out.append(_("Every source is an automated run. Records you obtained by hand -- a "
                     "Zotero export, a reference list, a Web of Science session -- go in with "
                     "`python project.py ingest FILE --method citation|database|...` and then "
                     "appear in the PRISMA flow's other-methods column."))
    for n, prev, now, when in _drift(d):
        out.append(_("Block {n}: total hits changed from {prev} (run {when}) to {now}; count "
                     "drift is expected as indexes grow, but a large jump usually means the "
                     "query changed -- diff queries.json between the runs.",
                     n=n, prev=_.num(prev), when=when, now=_.num(now)))
    if not out:
        out.append(_("Nothing flagged: counts are in a sensible range on every backend and "
                     "every call succeeded. Next step is reading the small blocks by hand."))
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
          metric: str | None = None, lang: str = "en") -> tuple[str, list]:
    """-> (title, nodes). `lang` translates the scaffolding only (i18n.py):
    data, query strings, backend names, flags, file names and the run log
    are reproduced as they are."""
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    lvl = LEVELS.index(level)
    _ = _i18n.translator(lang)
    lang = _.lang
    s = stats(d)
    meta, blocks, backends = d["meta"], d["block_names"], d["backends"]
    proj = d.get("project")
    metric = metric or (proj or {}).get("defaults", {}).get("metric") or "openalex_2yr"
    have_metrics = bool(d.get("journals"))
    rec_hdr = [_(h) for h in REC_HDR] + ([_journals.METRICS.get(metric, metric)]
                                         if have_metrics and _journals else [])
    title = (_("Literature search report -- {name}", name=proj["name"]) if proj
             else _("Literature search report -- run {stamp}", stamp=d["stamp"]))
    N = []

    # --- 1. metadata --------------------------------------------------------
    N.append(("h", 1, title))
    N.append(("p", _("Generated by scitech-librarian {version} (report level: {level}). Every "
                     "number below is reproducible from the archived {what} `{dir}`.",
                     version=meta.get("version", VERSION), level=level,
                     what=_("research directory") if proj else _("run directory"),
                     dir=Path(d["run"]).name)))
    mode = _("counts only (no records fetched)") if meta.get("counts_only") \
        else _("full fetch, up to {limit} records per block and backend",
               limit=meta.get("limit") or _("n/a"))
    rows = [[_("Search dates") if proj else _("Run started"), meta.get("started", d["stamp"])]]
    if proj:
        rows += [[_("Project"), proj["name"]], [_("Description"), proj.get("description") or "-"],
                 [_("Sources"), _("{runs} automated run(s), {manual} manual source(s)",
                                  runs=sum(1 for m in d["members"] if m["kind"] == "run"),
                                  manual=sum(1 for m in d["members"] if m["kind"] == "manual"))]]
    else:
        rows += [[_("Duration"), f"{meta.get('duration_s', 0):.0f} s" if meta.get("duration_s") else _("n/a")],
                 [_("Query file"), meta.get("query_file", "queries.json")]]
    rows += [[_("Blocks"), ", ".join(blocks)],
             [_("Backends / sources"), ", ".join(backends)],
             [_("Mode"), mode],
             [_("Non-curated venue filter"), _("off (--keep-junk)") if meta.get("keep_junk") else _("on")],
             [_("Open-access lookup"), "Unpaywall" if meta.get("pdfs") else _("not run")],
             [_("Journal metrics"), _("on file for {n} journals", n=len(d["journals"])) if have_metrics
              else _("none (journals.py fetch)")],
             [_("Filters"), ", ".join(f"{k}={v}" for k, v in d["filters"].items()) or _("none")]]
    if not proj:
        rows.append([_("Interrupted"), _("yes -- partial run") if meta.get("interrupted") else _("no")])
    N.append(("table", [_("Item"), _("Value")], rows))

    # --- 2. sources (project) -------------------------------------------------
    if proj:
        N.append(("h", 2, _("Sources")))
        N.append(("p", _("Every search that feeds this report, oldest first. 'New here' counts "
                         "unique records that no earlier source had found -- what each search added.")))
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
        N.append(("table", [_("Source"), _("Kind"), _("Date"), _("Method"), _("Records"),
                            _("New here"), _("Label / origin")], rows))

    # --- 3. search strategy ---------------------------------------------------
    N.append(("h", 2, _("Search strategy")))
    N.append(("p", _("Each block is one structural query -- a conjunction of synonym groups, "
                     "(a OR b) AND (c OR d) -- rendered into every backend's native grammar. "
                     "The strings below are exactly what was sent (PRISMA-S item 8){tail}",
                     tail=_(", from the most recent run of each block.") if proj else ".")))
    for n in blocks:
        b = d["blocks"].get(n, {})
        N.append(("h", 3, _("Block {n}: {title}", n=n, title=b.get("title", n))))
        if b.get("note"):
            N.append(("p", _("Purpose: {note}", note=b["note"])))
        if b.get("groups"):
            N.append(("code", _groups_text(b["groups"])))
            if b.get("arxiv_groups"):
                N.append(("p", _("arXiv receives groups {groups} only (nested-boolean limitation).",
                                 groups=b["arxiv_groups"])))
        qrows = [[bk, d["queries"].get(n, {}).get(bk, "")] for bk in backends
                 if not bk.startswith("manual:")]
        if qrows:
            N.append(("table", [_("Backend"), _("Query string sent")], qrows))

    # --- 4. results summary ---------------------------------------------------
    N.append(("h", 2, _("Results summary")))
    hdr = [_("Block")] + backends + [_("Identified"), _("Retrieved"), _("Unique")]
    rows = []
    uniq_block = Counter()
    for r in d["unique"]:
        for bn in (r.get("blocks") or [r.get("block")]):
            uniq_block[bn] += 1
    for n in blocks:
        c = d["counts"].get(n, {})
        ident = sum(_int(v) or 0 for v in c.values())
        rows.append([n] + [str(c.get(bk, "-")) for bk in backends]
                    + [_.num(ident), str(s["retrieved_block"].get(n, 0)), str(uniq_block.get(n, 0))])
    rows.append([_("Total")] + [_.num(s["identified"][bk]) for bk in backends]
                + [_.num(s["n_identified"] + s["n_other"]), str(s["n_fetched"]), str(s["n_unique"])])
    N.append(("table", hdr, rows))
    N.append(("p", _("Identified = database hit counts (not comparable across backends: "
                     "proximity operators are dropped and stemming differs){proj}. Retrieved = "
                     "records actually downloaded after the venue filter, capped by `--limit`. "
                     "Unique = after DOI/title deduplication across all sources.",
                     proj=_("; summed over runs, and for manual sources the number of records "
                            "ingested") if proj else "")))
    if s["errors"]:
        N.append(("p", _("Failed calls: {calls}.",
                         calls=", ".join(f"{n}/{b}" for n, b in s["errors"]))))

    # --- 5. timeline (project) ------------------------------------------------
    if proj:
        runs = [m for m in d["members"] if m["kind"] == "run"]
        if len(runs) >= 1:
            N.append(("h", 2, _("Timeline")))
            N.append(("p", _("Per-block hit totals in each automated run (sum over backends), "
                             "oldest first; drift shows how the indexes -- or the queries -- changed.")))
            hdr = [_("Block")] + [m["id"] for m in runs]
            rows = []
            for n in blocks:
                row = [n]
                for m in runs:
                    c = _json(m["path"] / "counts.json", {})
                    al = proj["block_aliases"]
                    vals = [v for k, v in c.items() if al.get(k, k) == n]
                    row.append(_.num(sum(_int(x) or 0 for c_ in vals for x in c_.values())) if vals else "-")
                rows.append(row)
            N.append(("table", hdr, rows))
        fs = Counter((r.get("first_seen") or "")[:7] for r in d["unique"] if r.get("first_seen"))
        if fs:
            N.append(("h", 3, _("When records entered the project")))
            N.append(("table", [_("Month"), _("Records first seen")],
                      [[k, str(v)] for k, v in sorted(fs.items())]))

    # --- 6. PRISMA -----------------------------------------------------------
    N.append(("h", 2, _("PRISMA 2020 flow")))
    pn = prisma_numbers(d, s)
    pn["lang"] = lang                     # render.py draws the flow in the same language
    N.append(("prisma", pn))
    man = _.num                           # None -> '--'
    frows = [[_("Records identified from databases"), man(pn["identified"])]]
    frows += [[f"  {bk}", man(v)] for bk, v in pn["identified_by"].items()]
    if pn["other_by"]:
        frows.append([_("Records identified via other methods"), man(pn["other"])])
        frows += [[f"  {k}", man(v)] for k, v in pn["other_by"].items()]
    frows += [[_("Records retrieved (downloaded / ingested)"), man(pn["retrieved"])],
              [_("Removed before screening: automation (non-curated venues)"),
               man(pn["automation_removed"])],
              [_("Removed before screening: duplicates"), man(pn["duplicates_removed"])],
              [_("Records to screen (unique)"), man(pn["to_screen"])],
              [_("Records screened"), man(pn["screened"]) + ("" if pn["screened_manual"] else _(" (assumed = unique)"))],
              [_("Records excluded at screening"), man(pn["excluded"])],
              [_("Reports sought for retrieval"), man(pn["sought"])],
              [_("Reports not retrieved"), man(pn["not_retrieved"])],
              [_("Reports assessed for eligibility"), man(pn["assessed"])]]
    for reason, k in pn["excluded_reasons"].items():
        frows.append([_("  excluded: {reason}", reason=reason), man(k)])
    if pn["other_by"]:
        frows += [[_("Other methods: reports sought"), man(pn["other_sought"])],
                  [_("Other methods: reports not retrieved"), man(pn["other_not_retrieved"])],
                  [_("Other methods: reports assessed"), man(pn["other_assessed"])]]
        for reason, k in pn["other_excluded_reasons"].items():
            frows.append([_("  other methods, excluded: {reason}", reason=reason), man(k)])
    frows += [[_("Studies included"), man(pn["studies_included"])],
              [_("Reports of included studies"), man(pn["reports_included"])]]
    N.append(("table", [_("Stage"), "n"], frows))
    N.append(("p", _("Automation stages are computed from the data; '--' marks manual stages not "
                     "yet recorded in {file}. Note that 'identified' counts hits reported by each "
                     "database while 'retrieved' is what was downloaded within `--limit`, so the "
                     "two differ on large blocks.", file=Path(d["prisma_file"]).name)))

    N.append(("h", 3, _("PRISMA-S search-reporting checklist")))
    N.append(("table", [_("Item"), _("Requirement"), _("This search")], _prisma_s_rows(d, s, lang)))

    # --- 7. records ----------------------------------------------------------
    if d["unique"]:
        top_n = top if top is not None else (10 if lvl == 0 else None)
        N.append(("h", 2, _("Records") if not top_n else _("Top {n} records per block", n=top_n)))
        N.append(("p", _("Deduplicated across sources, sorted by {sort}.{tail}", sort=sort,
                         tail="" if not top_n else
                         (_(" The complete set is in all_records.csv / .ris of each run.") if proj
                          else _(" The complete set is in all_records.csv / .ris.")))))
        for n in blocks:
            recs = [r for r in d["unique"] if n in (r.get("blocks") or [r.get("block")])]
            if not recs:
                continue
            recs = _sorted(recs, sort, d, metric)
            N.append(("h", 3, _("Block {n} ({k} unique)", n=n, k=len(recs))))
            sel = recs[:top_n] if top_n else recs
            if lvl == 2:
                for r in sel:
                    N.append(("h", 4, r.get("title", "")))
                    au = "; ".join(r.get("authors") or []) or _("(no authors)")
                    line = f"{au}. {r.get('journal', '')} ({r.get('year', '')}). " \
                           + _("Cited by {k}.", k=r.get("cited_by", 0))
                    found = r.get("found_by") or sorted(s["found_by"].get(_key(r), {r.get('backend', '?')}))
                    line += _(" Found by: {who}.", who=", ".join(found))
                    if have_metrics:
                        v, y = _metric_of(d, r, metric)
                        if v is not None:
                            line += f" {metric}: {v:g} ({y})."
                    if r.get("doi"):
                        line += f" DOI: {r['doi']}"
                    elif r.get("url"):
                        line += f" URL: {r['url']}"
                    if "is_oa" in r:
                        line += _(" OA: {yn}", yn=_("yes") if r.get("is_oa") else _("no")) \
                                + (f" ({r['oa_pdf']})" if r.get("oa_pdf") else "")
                    N.append(("p", line))
                    if r.get("abstract"):
                        N.append(("p", _("Abstract: ") + r["abstract"]))
            else:
                N.append(("table", rec_hdr, _rec_rows(d, sel, metric=metric if have_metrics else None)))

    # --- 8. intermediate analyses ---------------------------------------------
    if lvl >= 1 and d["unique"]:
        N.append(("h", 2, _("Source overlap")))
        rows = [[bk, str(s["retrieved"].get(bk, 0)), str(s["exclusive"].get(bk, 0)),
                 str(s["junk_by"].get(bk, 0))] for bk in backends]
        N.append(("table", [_("Source"), _("Retrieved"), _("Found only here"), _("Filtered venues")], rows))
        N.append(("p", _("'Found only here' counts unique records no other source returned "
                         "-- a measure of each database's marginal contribution.")))

        N.append(("h", 2, _("Distributions")))
        ys = sorted(s["years"].items())
        if ys:
            N.append(("h", 3, _("Publication year")))
            N.append(("table", [_("Year"), _("Records")], [[y, str(k)] for y, k in ys]))
        if s["journals"]:
            N.append(("h", 3, _("Top venues")))
            rows = []
            for j, k in s["journals"].most_common(15):
                row = [j, str(k)]
                if have_metrics:
                    v, y = _metric_of(d, {"journal": j}, metric)
                    row.append(f"{v:g} ({y})" if v is not None else "")
                rows.append(row)
            N.append(("table", [_("Venue"), _("Records")] + ([_journals.METRICS.get(metric, metric)]
                                                             if have_metrics else []), rows))
        if s["authors"]:
            N.append(("h", 3, _("Most frequent authors")))
            N.append(("table", [_("Author"), _("Records")],
                      [[a, str(k)] for a, k in s["authors"].most_common(15)]))
        if s["oa_checked"]:
            N.append(("h", 3, _("Open access")))
            N.append(("p", _("{oa} of {n} records with a DOI have a legal open-access copy per "
                             "Unpaywall ({pct}%).", oa=s["n_oa"], n=s["oa_checked"],
                             pct=f"{100 * s['n_oa'] / s['oa_checked']:.0f}")))
        if have_metrics:
            N.extend(_metrics_section(d, s, metric, lang))
        if d["junk"]:
            N.append(("h", 2, _("Filtered non-curated venues")))
            vc = Counter((r.get("journal") or "?").split("(")[0].strip() for r in d["junk"])
            N.append(("table", [_("Venue"), _("Records removed")],
                      [[v, str(k)] for v, k in vc.most_common(20)]))
        if d["history"] and not proj:
            N.append(("h", 2, _("Count history")))
            N.append(("p", _("Per-block totals across archived runs (counts_history.csv); "
                             "drift shows how the indexes -- or your queries -- changed.")))
            rows = []
            stamps = sorted({r["timestamp"] for r in d["history"]})[-6:]
            for n in blocks:
                row = [n]
                for st in stamps:
                    tot = [_int(r["count"]) for r in d["history"]
                           if r["timestamp"] == st and r["block"] == n]
                    row.append(_.num(sum(t for t in tot if t is not None)) if tot else "-")
                rows.append(row)
            N.append(("table", [_("Block")] + stamps, rows))
        errs = [ln for ln in d["log"].splitlines() if "ERROR" in ln]
        if errs:
            N.append(("h", 2, _("Errors")))
            N.append(("code", "\n".join(errs)))

    # --- 9. full dumps --------------------------------------------------------
    if lvl == 2:
        raw_hdr = [_(h) for h in REC_HDR]
        if d["raw"]:
            N.append(("h", 2, _("Per-source raw results (before deduplication)")))
            for stem, recs in d["raw"].items():
                if not recs:
                    continue
                N.append(("h", 3, _("{stem} ({n} records)", stem=stem, n=len(recs))))
                N.append(("table", raw_hdr, _rec_rows(d, recs, full=True)))
        if d["junk"]:
            N.append(("h", 2, _("Filtered records")))
            N.append(("table", raw_hdr + [_("Source")],
                      [row + [r.get("backend", "")] for row, r in
                       zip(_rec_rows(d, d["junk"], full=True), d["junk"])]))
        if meta.get("backend_config"):
            N.append(("h", 2, _("Backend configuration")))
            rows = [[b, c.get("url", "(driver)"), c.get("auth", "none"),
                     c.get("paging", "-")] for b, c in meta["backend_config"].items()]
            N.append(("table", [_("Backend"), _("Endpoint"), _("Auth"), _("Paging")], rows))
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
            N.append(("h", 2, _("Run log")))
            N.append(("code", d["log"]))
        N.append(("h", 2, _("Environment")))
        env = meta.get("environment", {})
        rows = [[_("Python"), env.get("python", platform.python_version())],
                [_("Platform"), env.get("platform", platform.platform())],
                [_("Tool version"), meta.get("version", VERSION)],
                [_("Report generated"), time.strftime("%Y-%m-%d %H:%M")]]
        N.append(("table", [_("Item"), _("Value")], rows))

    # --- 10. suggestions ------------------------------------------------------
    N.append(("h", 2, _("Suggestions")))
    N.append(("ul", suggest(d, s, lang)))
    return title, N


def _metrics_section(d, s, metric, lang: str = "en") -> list:
    """Top venues by the chosen metric among venues in the record set, and the
    evolution table for venues with two or more years on file."""
    _ = _i18n.translator(lang)
    N = [("h", 2, _("Journal metrics"))]
    label = _journals.METRICS.get(metric, metric)
    N.append(("p", _("Metric: {label} ({metric}), from {dir}/journals/metrics.json (journals.py). "
                     "Values are kept per year; OpenAlex figures are snapshots taken in the fetch "
                     "year (the API serves only current values); the evolution table shows every "
                     "year on file for venues that appear in this record set.",
                     label=label, metric=metric, dir=Path(d["outdir"]).name)))
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
        N.append(("h", 3, _("Venues in this set by {label}", label=label)))
        N.append(("table", [_("Venue"), _("Records"), label, _("Year"), _("Q")], [r for _r, r in rows[:25]]))
    if evo:
        N.append(("h", 3, _("{label}: evolution", label=label)))
        width = max(len(r) for r in evo)
        N.append(("table", [_("Venue")] + [f"y{i}" for i in range(1, width - 1)] + [_("Years")],
                  [r[:-1] + [""] * (width - len(r)) + [r[-1]] for r in evo]))
    return N


def _prisma_s_rows(d, s, lang: str = "en") -> list:
    _ = _i18n.translator(lang)
    meta, backends = d["meta"], d["backends"]
    started = meta.get("started", d["stamp"])
    limit = meta.get("limit")
    filt = _("off") if meta.get("keep_junk") else \
        _("on: records from non-curated repositories (Zenodo, Figshare, SSRN...) removed")
    prev = sorted({r["timestamp"] for r in d["history"] if r["timestamp"] != d["stamp"]})
    p = d["prisma"]
    manual = [m for m in d.get("members") or [] if m["kind"] == "manual"]
    by_method = defaultdict(list)
    for m in manual:
        by_method[m.get("method", "other")].append(m["id"])
    dbs = [b for b in backends if not b.startswith("manual:")]
    n_runs = sum(1 for m in d.get("members") or [] if m["kind"] == "run")
    auto = {
        "1": _("{dbs} (documented public APIs)", dbs=", ".join(dbs))
             + (_("; manual database exports: {names}", names=", ".join(by_method["database"]))
                if by_method["database"] else ""),
        "2": (_("1 database, one structural query per block rendered into each native grammar; "
                "see Search strategy") if len(dbs) == 1 else
              _("{n} databases, one structural query per block rendered into each native "
                "grammar; see Search strategy", n=len(dbs))),
        "4": ", ".join(by_method["website"]) if by_method["website"] else _("none recorded"),
        "5": ", ".join(by_method["citation"]) or p.get("citation_searching") or _("not performed"),
        "6": ", ".join(by_method["expert"]) if by_method["expert"] else _("none recorded"),
        "7": ", ".join(by_method["organisation"] + by_method["other"]) or p.get("other_methods") or _("none"),
        "8": _("reported verbatim per backend under Search strategy; archived in queries.json{tail}",
               tail=_(" of each run") if d.get("project") else ""),
        "9": (_("counts only, no records") if meta.get("counts_only") else
              _("record download capped at {limit} per block and backend, most-cited first",
                limit=limit or _("n/a"))) + _("; no date, language or document-type limits applied")
             + (_("; report filters: {filters}",
                  filters=", ".join(f"{k}={v}" for k, v in d["filters"].items())) if d["filters"] else ""),
        "10": _("venue filter {filt}", filt=filt),
        "11": p.get("prior_work") or _("none"),
        "12": (_("{n} earlier run(s) archived; counts tracked in counts_history.csv", n=len(prev))
               if prev and not d.get("project") else
               _("{n} run(s) combined; see Timeline", n=n_runs)
               if d.get("project") else _("first run of these blocks")),
        "13": _("searched on {date}", date=started),
        "14": p.get("peer_review") or _("none"),
        "15": _("{n} identified from databases", n=_.num(s["n_identified"]))
              + (_(", {n} via other methods", n=_.num(s["n_other"])) if s["n_other"] else "")
              + _("; {r} retrieved; {u} unique", r=_.num(s["n_fetched"] + s["n_junk"]), u=_.num(s["n_unique"])),
        "16": _("exact DOI match, else first 90 characters of the lower-cased title; {n} duplicates "
                "removed", n=_.num(s["n_dupes"])),
    }
    rows = []
    for num, name, kind in PRISMA_S_ITEMS:
        val = auto.get(num, _("not applicable") if kind == "na" else _("to be completed"))
        rows.append([num, _(name), val])
    return rows


# ---------------------------------------------------------------------------
# Rendering lives in render.py; the names are re-exported so importers and
# the test suite keep working (report.render_md, report._tex, ...).
# ---------------------------------------------------------------------------

from render import (_ascii_flow, _cell_text, _flow_boxes, _pdf_builtin, _run,  # noqa: E402
                    _svg_flow, _tex, _tex_inline, _tex_table, _tikz_flow, _txt_table,
                    make_pdf, render_html, render_md, render_tex, render_txt)

_REEXPORTED = (_ascii_flow, _cell_text, _flow_boxes, _pdf_builtin, _run, _svg_flow, _tex,
               _tex_inline, _tex_table, _tikz_flow, _txt_table)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def default_lang(d: dict) -> str:
    """The research directory's `defaults.lang` (project.json), else 'en'.
    project.json is data, not a flag: an unknown value warns and degrades to
    English rather than losing the report."""
    proj = d.get("project")
    if proj is None and _project is not None and d.get("outdir"):
        proj = _project.load_project(Path(d["outdir"]))
    want = ((proj or {}).get("defaults") or {}).get("lang")
    try:
        return _i18n.normalize(want)
    except ValueError as e:
        print(f"warning: project.json defaults.lang ignored -- {e}; writing English", file=sys.stderr)
        return "en"


def write_reports(run: Path | None = None, level: str = "simple", formats=("md",),
                  basename: str = "report", quiet: bool = False, d: dict | None = None,
                  out_dir: Path | None = None, lang: str | None = None, **build_kw) -> dict:
    """Render one run (or a prepared data dict) at one level into every
    requested format. -> {format: path}. Writes the PRISMA template if absent.
    `lang` (en, pt-BR, es, de, fr) translates the report scaffolding; None
    means the research directory's default, else English. Console output and
    logs stay English regardless."""
    formats = list(dict.fromkeys(formats))
    for f in formats:
        if f not in FORMATS:
            raise ValueError(f"unknown format {f!r}; choose from {FORMATS}")
    if d is None:
        d = load_run(Path(run))
    lang = _i18n.normalize(lang) if lang else default_lang(d)
    pj = Path(d["prisma_file"])
    if not pj.exists():
        pj.parent.mkdir(parents=True, exist_ok=True)
        pj.write_text(json.dumps(PRISMA_TEMPLATE, indent=2), encoding="utf-8")
    out_dir = Path(out_dir) if out_dir else Path(d["run"])
    out_dir.mkdir(parents=True, exist_ok=True)
    title, nodes = build(d, level, lang=lang, **build_kw)
    written = {}
    need = set(formats)
    if "pdf" in need:
        need |= {"tex", "md", "txt"}
    rendered = {}
    if "md" in need:
        rendered["md"] = render_md(title, nodes)
    if "html" in need:
        rendered["html"] = render_html(title, nodes, lang)
    if "tex" in need:
        rendered["tex"] = render_tex(title, nodes, VERSION, lang)
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
    ap.add_argument("--lang", default=None, metavar="LANG",
                    help="report language: en, pt-BR, es, de, fr (default: project.json "
                         "defaults.lang, else en). Only the report's own wording is translated; "
                         "records, query strings, file names and logs are never touched")
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
                for r in recs:
                    r["member"], r["member_date"] = Path(f).stem, time.strftime("%Y-%m-%d %H:%M:%S")
            for r in d["unique"]:
                r.setdefault("member", d["stamp"])
                r.setdefault("member_date", d["meta"].get("started", ""))
            d["unique"] = _project.merge(d["unique"] + [r for k, v in d["raw"].items()
                                                        if k.startswith("MANUAL_manual:") for r in v])
        level = args.level or "simple"
        formats = args.format or ["md"]
        out_dir = Path(args.out) if args.out else run
    apply_filters(d, args.backends, args.blocks, args.year_from, args.year_to, args.min_citations,
                  args.oa_only, args.metric, args.min_metric, args.diff, args.since, args.until)
    try:
        lang = _i18n.normalize(args.lang) if args.lang else None
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    written = write_reports(None, level, formats, args.basename, quiet=args.quiet, d=d,
                            out_dir=out_dir, lang=lang, top=args.top, sort=args.sort,
                            metric=args.metric)
    if log:
        for f, p in written.items():
            log.debug("wrote %s", p)
        _project.close_logging(log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
