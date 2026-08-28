#!/usr/bin/env python3
"""
journals.py -- journal metrics for a research directory (impact-factor-like
figures, kept by year so their evolution is visible).

    python journals.py fetch                      # every journal seen in lit/, all providers available
    python journals.py fetch --providers openalex --refresh
    python journals.py import-scimago scimagojr_2024.csv --year 2024 [--all]
    python journals.py import-jcr JCR_JournalResults_*.csv       # Journal Citation Reports downloads
    python journals.py list --missing jcr_if                      # what to look up by hand
    python journals.py import-csv jcr.csv --provider jcr_if --year 2023 --name-col "Journal name" --value-col "JIF"
    python journals.py show [--metric openalex_2yr]

Store: <outdir>/journals/metrics.json, one entry per journal keyed by ISSN
(else normalised name), values appended per year and never overwritten --
refetch next year and the report shows the series.

Providers
---------
openalex   no key. 2yr_mean_citedness (an impact-factor-like 2-year mean
           citations per work), h-index, i10, works and citations by year.
           OpenAlex serves only the current value, so it is stored under the
           fetch year: a snapshot series builds up over time.
scopus     SCOPUS_API_KEY. Serial Title API: CiteScore per year, SJR, SNIP --
           full history in one call.
scimago    no key, no API: download the year's CSV from scimagojr.com
           (Journal Rankings -> Download data) and import it. SJR, H index,
           quartile for ~30,000 journals -- this is the "all journals" path.
jcr        Clarivate's Journal Impact Factor is proprietary and has no free
           API; licensed users export a CSV from JCR and import it with
           import-csv --provider jcr_if.

Metric names used everywhere (reports, --min-metric):
  openalex_2yr  openalex_h  scopus_citescore  sjr  snip  scimago_h  jcr_if
  plus any --provider name you import.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

try:
    import librarian
except ImportError:                       # drop-in installs may keep the old name
    import litscan as librarian           # type: ignore
_extract = librarian._extract
VERSION = librarian.VERSION
from project import (add_common_args, close_logging, load_project, member_records, members,
                     resolve_outdir, setup_logging)

METRICS = {"openalex_2yr": "OpenAlex 2-yr mean citedness", "openalex_h": "OpenAlex h-index",
           "scopus_citescore": "Scopus CiteScore", "sjr": "SCImago Journal Rank",
           "snip": "Scopus SNIP", "scimago_h": "SCImago H index", "jcr_if": "JCR Impact Factor"}
PROVIDERS = ("openalex", "scopus")


def norm_name(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", (s or "").lower())
    s = re.sub(r"^(the|die|le|la|il)\s+", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_issn(s: str) -> str:
    s = re.sub(r"[^0-9Xx]", "", s or "").upper()
    return f"{s[:4]}-{s[4:]}" if len(s) == 8 else ""


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def store_path(outdir: Path) -> Path:
    return Path(outdir) / "journals" / "metrics.json"


def load_store(outdir: Path) -> dict:
    p = store_path(outdir)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        return {}


def save_store(outdir: Path, store: dict) -> None:
    p = store_path(outdir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(store, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _entry(store: dict, name: str, issns: list) -> dict:
    """Find or create the entry for a journal; ISSN key wins, name key else."""
    issns = [i for i in (norm_issn(x) for x in issns) if i]
    for i in issns:
        if i in store:
            e = store[i]
            break
    else:
        nk = "name:" + norm_name(name)
        known = alias_index(store).get(norm_name(name))
        if issns and nk in store:               # upgrade a name-keyed entry to ISSN
            e = store.pop(nk)
            store[issns[0]] = e
        elif known is not None:                 # same journal already on file under another key
            e = known
        elif issns:
            e = store.setdefault(issns[0], {})
        else:
            e = store.setdefault(nk, {})
    e.setdefault("name", name)
    e.setdefault("issn", [])
    for i in issns:
        if i not in e["issn"]:
            e["issn"].append(i)
    e.setdefault("aliases", [])
    for a in (norm_name(name), norm_name(e["name"])):
        if a and a not in e["aliases"]:
            e["aliases"].append(a)
    e.setdefault("metrics", {})
    e.setdefault("quartile", {})
    e.setdefault("fetched", {})
    return e


def put(e: dict, metric: str, year, value) -> None:
    if value is None or value == "":
        return
    try:
        value = float(str(value).replace(",", "."))
    except ValueError:
        return
    e["metrics"].setdefault(metric, {})[str(year)] = round(value, 3)


def lookup(store: dict, rec: dict, _index: dict | None = None) -> dict | None:
    """Entry for a record, by ISSN then by normalised journal name."""
    i = norm_issn(rec.get("issn") or "")
    if i and i in store:
        return store[i]
    idx = _index if _index is not None else alias_index(store)
    return idx.get(norm_name(rec.get("journal") or ""))


def alias_index(store: dict) -> dict:
    idx = {}
    for e in store.values():
        for a in e.get("aliases", []):
            idx.setdefault(a, e)
    return idx


def metric_value(e: dict | None, metric: str):
    """(value, year) of the most recent year on file, or (None, None)."""
    if not e:
        return None, None
    series = e.get("metrics", {}).get(metric) or {}
    if not series:
        return None, None
    y = max(series)
    return series[y], y


def collect(outdir: Path) -> dict:
    """{name: [issns]} for every journal seen in the directory's records."""
    seen = {}
    for m in members(outdir, load_project(outdir)):
        for r in member_records(m):
            j = (r.get("journal") or "").strip()
            if not j or librarian.is_junk(r) or j.lower().startswith("arxiv"):
                continue
            seen.setdefault(j, set())
            if r.get("issn"):
                seen[j].add(norm_issn(r["issn"]))
    return {k: sorted(v - {""}) for k, v in seen.items()}


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def fetch_openalex(name: str, issns: list) -> dict | None:
    base = "https://api.openalex.org/sources"
    mail = f"&mailto={librarian.CONTACT}" if librarian.CONTACT else ""
    if os.environ.get("OPENALEX_API_KEY"):
        mail += f"&api_key={os.environ['OPENALEX_API_KEY']}"
    for i in issns:
        d = librarian._json(f"{base}?filter=issn:{i}&per-page=1{mail}")
        if d.get("results"):
            return d["results"][0]
    d = librarian._json(f"{base}?search={urllib.parse.quote(name)}&per-page=1{mail}")
    res = d.get("results") or []
    if res and norm_name(res[0].get("display_name", "")) == norm_name(name):
        return res[0]
    return None


def apply_openalex(e: dict, src: dict, year: str) -> None:
    e["openalex_id"] = src.get("id", "")
    for i in src.get("issn") or []:
        if norm_issn(i) and norm_issn(i) not in e["issn"]:
            e["issn"].append(norm_issn(i))
    ss = src.get("summary_stats") or {}
    put(e, "openalex_2yr", year, ss.get("2yr_mean_citedness"))
    put(e, "openalex_h", year, ss.get("h_index"))
    put(e, "openalex_i10", year, ss.get("i10_index"))
    for cy in src.get("counts_by_year") or []:
        put(e, "openalex_works", cy.get("year"), cy.get("works_count"))
        put(e, "openalex_cites", cy.get("year"), cy.get("cited_by_count"))
    e["fetched"]["openalex"] = time.strftime("%Y-%m-%d")


def fetch_scopus(issn: str = "", name: str = "") -> dict | None:
    """Serial Title API by ISSN, else by title (exact normalised match)."""
    key = os.environ.get("SCOPUS_API_KEY", "")
    if not key:
        raise RuntimeError("SCOPUS_API_KEY not set")
    hdr = {"X-ELS-APIKey": key, "Accept": "application/json"}
    if issn:
        d = librarian._json(f"https://api.elsevier.com/content/serial/title/issn/{issn}"
                            f"?view=CITESCORE", hdr)
        ent = _extract(d, "serial-metadata-response.entry") or []
        return ent[0] if ent else None
    if not name:
        return None
    d = librarian._json("https://api.elsevier.com/content/serial/title?view=CITESCORE&count=5&title="
                        + urllib.parse.quote(name), hdr)
    for ent in _extract(d, "serial-metadata-response.entry") or []:
        if norm_name(ent.get("dc:title", "")) == norm_name(name):
            return ent
    return None


def apply_scopus(e: dict, src: dict) -> None:
    for i in (src.get("prism:issn") or "").split(","):
        if norm_issn(i) and norm_issn(i) not in e["issn"]:
            e["issn"].append(norm_issn(i))
    for item in _extract(src, "SJRList.SJR") or []:
        put(e, "sjr", item.get("@year"), item.get("$"))
    for item in _extract(src, "SNIPList.SNIP") or []:
        put(e, "snip", item.get("@year"), item.get("$"))
    for yi in _extract(src, "citeScoreYearInfoList.citeScoreYearInfo") or []:
        if str(yi.get("@status", "")).lower().startswith("in"):   # In-Progress tracker, not a year
            continue
        val = _extract(yi, "citeScoreInformationList[0].citeScoreInfo[0].citeScore")
        put(e, "scopus_citescore", yi.get("@year"), val)
    e["fetched"]["scopus"] = time.strftime("%Y-%m-%d")


def import_scimago(text: str, year: str, store: dict, only: dict | None = None) -> int:
    """SCImago Journal Rankings CSV (semicolon-separated, comma decimals).
    `only` = {norm_name: True} restricts to journals seen in the directory."""
    rd = _csv_rows(text, "Title", ";")
    n = 0
    for row in rd:
        title = (row.get("Title") or "").strip()
        issns = [x.strip() for x in (row.get("Issn") or "").split(",") if x.strip()]
        if only is not None and norm_name(title) not in only \
                and not any(norm_issn(i) in only for i in issns):
            continue
        e = _entry(store, title, issns)
        put(e, "sjr", year, row.get("SJR"))
        put(e, "scimago_h", year, row.get("H index"))
        q = (row.get("SJR Best Quartile") or "").strip()
        if q:
            e["quartile"][str(year)] = q
        e["fetched"]["scimago"] = time.strftime("%Y-%m-%d")
        n += 1
    return n


def _csv_rows(text: str, must_have: str, delimiter: str = ",") -> csv.DictReader:
    """DictReader that starts at the header line containing `must_have` --
    JCR and other exports put title/date lines before the table -- and
    ignores a BOM."""
    lines = text.lstrip("\ufeff").splitlines()
    start = next((i for i, ln in enumerate(lines) if must_have.lower() in ln.lower()), 0)
    rd = csv.DictReader(io.StringIO("\n".join(lines[start:])), delimiter=delimiter)
    rd.fieldnames = [f.strip().strip('"') for f in (rd.fieldnames or [])]
    return rd


def import_csv(text: str, provider: str, year: str, store: dict, name_col: str,
               value_col: str, issn_col: str = "", delimiter: str = ",",
               quartile_col: str = "") -> int:
    rd = _csv_rows(text, name_col, delimiter)
    n = 0
    for row in rd:
        title = (row.get(name_col) or "").strip()
        if not title:
            continue
        issns = [x.strip() for x in (row.get(issn_col) or "").split(",")] if issn_col else []
        e = _entry(store, title, issns)
        put(e, provider, year, row.get(value_col))
        if quartile_col and (row.get(quartile_col) or "").strip():
            e["quartile"][str(year)] = row[quartile_col].strip()
        e["fetched"][provider] = time.strftime("%Y-%m-%d")
        n += 1
    return n


def import_jcr(text: str, store: dict, year: str = "") -> tuple:
    """A Journal Citation Reports 'Download' CSV: columns are detected
    (Journal name, ISSN/eISSN, '<year> JIF', JIF Quartile). Returns
    (journals imported, year used). The JIF year is read from the column
    name unless given."""
    rd = _csv_rows(text, "Journal name")
    cols = rd.fieldnames or []
    jif = next((c for c in cols if re.fullmatch(r"\d{4} JIF", c.strip())), None)
    if jif is None:
        jif = next((c for c in cols if "JIF" in c and "Quartile" not in c and "5 Year" not in c
                    and "Percentile" not in c and "Rank" not in c), None)
    if jif is None:
        raise ValueError(f"no JIF column in {cols}")
    m = re.match(r"(\d{4})", jif.strip())
    yr = year or (m.group(1) if m else time.strftime("%Y"))
    name_col = next(c for c in cols if c.lower() == "journal name")
    issn_cols = [c for c in cols if c.upper() in ("ISSN", "EISSN")]
    q_col = next((c for c in cols if "quartile" in c.lower()), "")
    n = 0
    for row in rd:
        title = (row.get(name_col) or "").strip()
        if not title or not re.match(r"\d", (row.get(jif) or "").strip()):
            continue                     # trailer lines ("Copyright ... Clarivate") and blanks
        issns = [row.get(c, "") for c in issn_cols if (row.get(c) or "").strip() not in ("", "N/A")]
        e = _entry(store, title.title() if title.isupper() else title, issns)
        put(e, "jcr_if", yr, row.get(jif))
        if q_col and (row.get(q_col) or "").strip():
            e["quartile"][str(yr)] = row[q_col].strip()
        e["fetched"]["jcr"] = time.strftime("%Y-%m-%d")
        n += 1
    return n, yr


def journal_list(outdir: Path, missing: str = "") -> str:
    """Every journal seen in the directory, with the value of each metric on
    file; --missing METRIC keeps only those without that metric (the list to
    look up by hand, e.g. in JCR)."""
    store = load_store(outdir)
    idx = alias_index(store)
    rows = []
    for name, issns in sorted(collect(outdir).items(), key=lambda kv: kv[0].lower()):
        e = lookup(store, {"journal": name, "issn": issns[0] if issns else ""}, idx)
        vals = {m: metric_value(e, m)[0] for m in METRICS} if e else {}
        if missing and vals.get(missing) is not None:
            continue
        rows.append((name, ", ".join((e or {}).get("issn") or issns), vals))
    out = [f"{len(rows)} journals" + (f" without {missing}" if missing else "") + f" in {outdir}",
           f"{'journal':55s} {'issn':20s} " + " ".join(f"{m[:12]:>12s}" for m in METRICS)]
    for name, issn, vals in rows:
        out.append(f"{name[:55]:55s} {issn[:20]:20s} "
                   + " ".join(f"{vals.get(m):>12g}" if vals.get(m) is not None else f"{'-':>12s}"
                              for m in METRICS))
    return "\n".join(out)


def fetch(outdir: Path, providers=PROVIDERS, refresh=False, log=None) -> dict:
    """Fetch every journal seen in the directory from each provider that is
    available; skip journals already fetched this year unless refresh."""
    import logging
    log = log or logging.getLogger("journals")
    store = load_store(outdir)
    todo = collect(outdir)
    year = time.strftime("%Y")
    stats = {"journals": len(todo), "openalex": 0, "scopus": 0, "missed": 0}
    log.info("%d journals in %s", len(todo), outdir)
    providers = list(providers)
    for i, (name, issns) in enumerate(sorted(todo.items()), 1):
        e = _entry(store, name, issns)
        if "openalex" in providers and (refresh or e["fetched"].get("openalex", "")[:4] != year):
            try:
                src = fetch_openalex(name, e["issn"] or issns)
                if src:
                    apply_openalex(e, src, year)
                    stats["openalex"] += 1
                else:
                    stats["missed"] += 1
                    log.debug("openalex: no match for %r", name)
            except Exception as ex:  # noqa: BLE001
                if "budget" in str(ex).lower():      # daily free budget gone: stop asking
                    log.warning("openalex: %s", str(ex).split("->")[-1].strip())
                    log.warning("openalex skipped for the remaining journals; rerun tomorrow "
                                "or set OPENALEX_API_KEY")
                    providers.remove("openalex")
                else:
                    log.warning("openalex %r: %s", name, str(ex)[:120])
            time.sleep(0.12)
        if "scopus" in providers and os.environ.get("SCOPUS_API_KEY") \
                and (refresh or e["fetched"].get("scopus", "")[:4] != year):
            try:
                src = fetch_scopus(e["issn"][0] if e["issn"] else "", name)
                if src:
                    apply_scopus(e, src)
                    stats["scopus"] += 1
                else:
                    log.debug("scopus: no match for %r", name)
            except Exception as ex:  # noqa: BLE001
                if "404" in str(ex) or "RESOURCE_NOT_FOUND" in str(ex):
                    log.debug("scopus: no match for %r", name)
                else:
                    log.warning("scopus %r: %s", name, str(ex)[:120])
            time.sleep(0.35)
        if i % 25 == 0:
            save_store(outdir, store)
            log.info("  %d/%d", i, len(todo))
    save_store(outdir, store)
    log.info("openalex %d, scopus %d, unmatched %d -> %s", stats["openalex"], stats["scopus"],
             stats["missed"], store_path(outdir))
    return stats


def show(outdir: Path, metric: str = "openalex_2yr", limit: int = 50) -> str:
    store = load_store(outdir)
    rows = []
    for e in store.values():
        v, y = metric_value(e, metric)
        if v is not None:
            rows.append((v, y, e["name"], ", ".join(e.get("issn", [])),
                         e.get("quartile", {}).get(y, "")))
    rows.sort(reverse=True)
    out = [f"{metric} ({METRICS.get(metric, metric)}), {len(rows)} journals with a value",
           f"{'value':>8s} {'year':4s}  {'journal':50s} {'issn':20s} Q"]
    for v, y, n, i, q in rows[:limit]:
        out.append(f"{v:8.2f} {y:4s}  {n[:50]:50s} {i:20s} {q}")
    return "\n".join(out)


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"scitech-librarian {VERSION}")
    common = argparse.ArgumentParser(add_help=False)
    add_common_args(common)
    sub = ap.add_subparsers(dest="cmd", parser_class=lambda **kw: argparse.ArgumentParser(
        parents=[common], **kw))
    s = sub.add_parser("fetch", help="fetch metrics for every journal seen in the directory")
    s.add_argument("--providers", nargs="+", default=list(PROVIDERS), choices=PROVIDERS)
    s.add_argument("--refresh", action="store_true", help="refetch even if done this year")
    s = sub.add_parser("import-scimago", help="import a SCImago Journal Rankings CSV")
    s.add_argument("file")
    s.add_argument("--year", required=True)
    s.add_argument("--all", action="store_true",
                   help="import every journal in the file (default: only those seen in the directory)")
    s = sub.add_parser("import-csv", help="import any name/value CSV (e.g. a JCR export)")
    s.add_argument("file")
    s.add_argument("--provider", required=True, help="metric name, e.g. jcr_if")
    s.add_argument("--year", required=True)
    s.add_argument("--name-col", required=True)
    s.add_argument("--value-col", required=True)
    s.add_argument("--issn-col", default="")
    s.add_argument("--delimiter", default=",")
    s = sub.add_parser("import-jcr", help="import a Journal Citation Reports download (CSV)")
    s.add_argument("files", nargs="+")
    s.add_argument("--year", default="", help="JIF year (default: read from the '<year> JIF' column)")
    s = sub.add_parser("list", help="journals seen in the directory and their metrics")
    s.add_argument("--missing", default="", metavar="METRIC",
                   help="only journals without this metric (e.g. jcr_if): the manual look-up list")
    s = sub.add_parser("show", help="table of journals by a metric")
    s.add_argument("--metric", default="openalex_2yr")
    s.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 2
    outdir = resolve_outdir(args.outdir)
    log = setup_logging("journals", args, outdir)
    if not args.cmd:
        ap.print_help()
        return 2
    if args.cmd == "fetch":
        fetch(outdir, args.providers, args.refresh, log)
    elif args.cmd == "import-scimago":
        store = load_store(outdir)
        only = None
        if not args.all:
            only = {}
            for name, issns in collect(outdir).items():
                only[norm_name(name)] = True
                for i in issns:
                    only[i] = True
        n = import_scimago(Path(args.file).read_text(encoding="utf-8", errors="replace"),
                           args.year, store, only)
        save_store(outdir, store)
        log.info("%d journals imported for %s", n, args.year)
    elif args.cmd == "import-csv":
        store = load_store(outdir)
        n = import_csv(Path(args.file).read_text(encoding="utf-8", errors="replace"),
                       args.provider, args.year, store, args.name_col, args.value_col,
                       args.issn_col, args.delimiter)
        save_store(outdir, store)
        log.info("%d journals imported as %s/%s", n, args.provider, args.year)
    elif args.cmd == "import-jcr":
        store = load_store(outdir)
        total = 0
        for f in args.files:
            n, yr = import_jcr(Path(f).read_text(encoding="utf-8", errors="replace"), store, args.year)
            log.info("%d journals from %s (JIF %s)", n, Path(f).name, yr)
            total += n
        save_store(outdir, store)
        log.info("%d journals imported -> %s", total, store_path(outdir))
    elif args.cmd == "list":
        print(journal_list(outdir, args.missing))
    elif args.cmd == "show":
        print(show(outdir, args.metric, args.limit))
    close_logging(log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
