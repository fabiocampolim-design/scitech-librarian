#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Fabio Campolim
"""
project.py -- the research directory: index, ingest, status.

A research directory (default lit/, --outdir) holds every search a project
makes over time -- automated runs from librarian.py under runs/, records
brought in from outside under manual/ -- plus project.json (index),
screening.json (PRISMA manual stages), journals/ (metrics) and logs/.
report.py --project merges all of it. See docs/DESIGN_RESEARCH_DIRECTORY.md.

    python project.py init --name "Topological materials review"
    python project.py status
    python project.py ingest export.ris --name zotero-aug --block CD --method citation
    python project.py ingest --inbox                 # everything dropped in lit/inbox/
    python project.py exclude 20260814T223331        # hide a run from project reports
    python project.py label 20260828T095041 "August full scan"

Ingest accepts RIS (Zotero, Mendeley, EndNote, Web of Science exports),
BibTeX, CSV (title, year, doi, journal, authors, url, abstract, block) and
JSON (a list of records, e.g. all_records.json from another machine). Kind
is detected from the extension unless --kind is given. Every ingested source
keeps the original file, a source.json with provenance (who, when, origin,
method, note) and records.json in the common schema, tagged
backend = "manual:<name>" so every report table treats it as one more source.

--method uses PRISMA 2020's "identification via other methods" categories:
database | citation | website | organisation | expert | other.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path

try:
    from librarian import VERSION          # single source of the version number
except ImportError:
    try:
        from litscan import VERSION        # type: ignore
    except ImportError:
        VERSION = "unknown"
METHODS = ("database", "citation", "website", "organisation", "expert", "other")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name == "tools" else HERE
DEFAULT_OUTDIR = ROOT / "lit"


# ---------------------------------------------------------------------------
# Logging / audit -- shared by every script (they import this)
# ---------------------------------------------------------------------------

def add_common_args(ap: argparse.ArgumentParser, outdir_help: str = "research directory") -> None:
    ap.add_argument("--outdir", default=None,
                    help=f"{outdir_help} (default: ./lit next to the scripts, or the "
                         f"project root when installed under tools/)")
    ap.add_argument("--verbose", "-v", action="store_true", help="chatty console output")
    ap.add_argument("--quiet", "-q", action="store_true", help="errors only on the console")
    ap.add_argument("--log-dir", default=None,
                    help="where audit logs go (default: <outdir>/logs)")


def resolve_outdir(value) -> Path:
    return Path(value).resolve() if value else DEFAULT_OUTDIR


def setup_logging(script: str, args, outdir: Path | None = None) -> logging.Logger:
    """Console at INFO (WARNING with --quiet, DEBUG with --verbose) and a full
    DEBUG audit file <log-dir>/<script>_<stamp>.log that records the exact
    invocation, versions and every message. Returns the logger."""
    outdir = outdir or resolve_outdir(getattr(args, "outdir", None))
    log_dir = Path(args.log_dir) if getattr(args, "log_dir", None) else outdir / "logs"
    for stream in (sys.stdout, sys.stderr):      # journal and author names are not cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    log = logging.getLogger(script)
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    con = logging.StreamHandler(sys.stdout)
    con.setLevel(logging.DEBUG if getattr(args, "verbose", False)
                 else logging.WARNING if getattr(args, "quiet", False) else logging.INFO)
    con.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(con)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / f"{script}_{time.strftime('%Y%m%dT%H%M%S')}_{os.getpid()}.log",
                                 encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(fh)
        log.debug("invocation: %s", " ".join(sys.argv))
        log.debug("script %s v%s, python %s", script, VERSION, sys.version.split()[0])
        log.debug("outdir %s", outdir)
    except OSError as e:  # noqa: BLE001
        log.warning("audit log not written: %s", e)
    return log


def close_logging(log: logging.Logger) -> None:
    """Flush and release the audit file (Windows keeps it locked otherwise)."""
    for h in list(log.handlers):
        try:
            h.flush()
            h.close()
        except (OSError, ValueError):
            pass
        log.removeHandler(h)


# ---------------------------------------------------------------------------
# Record parsers -> common schema
# ---------------------------------------------------------------------------

FIELDS = ("title", "year", "doi", "journal", "authors", "url", "abstract", "cited_by",
          "issn", "block", "backend")


def norm_rec(r: dict) -> dict:
    """Coerce anything record-like into the common schema."""
    au = r.get("authors") or []
    if isinstance(au, str):
        au = [a.strip() for a in re.split(r";|\band\b", au) if a.strip()]
    doi = (r.get("doi") or "").strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    try:
        cited = int(r.get("cited_by") or r.get("cited") or r.get("citations") or 0)
    except (TypeError, ValueError):
        cited = 0
    return {"title": (r.get("title") or "").strip(), "year": str(r.get("year") or "")[:4],
            "doi": doi, "journal": (r.get("journal") or r.get("venue") or "").strip(),
            "authors": [a for a in au if a], "url": (r.get("url") or "").strip(),
            "abstract": (r.get("abstract") or "").strip(), "cited_by": cited,
            "issn": (r.get("issn") or "").strip(),
            "block": r.get("block", ""), "backend": r.get("backend", "")}


def parse_ris(text: str) -> list[dict]:
    """RIS -> common schema (Zotero, Mendeley, EndNote, Web of Science)."""
    recs, cur, authors = [], {}, []
    tag_re = re.compile(r"^﻿?([A-Z][A-Z0-9])  -\s?(.*)$")
    for raw in text.splitlines():
        m = tag_re.match(raw)
        if not m:          # continuation lines and blanks; "ER  -" without a trailing space counts
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur, authors = {}, []
        elif tag in ("AU", "A1", "A2"):
            authors.append(val)
        elif tag in ("TI", "T1"):
            cur["title"] = val
        elif tag in ("PY", "Y1"):
            cur["year"] = val[:4]
        elif tag == "DA" and re.match(r"\d{4}", val):     # WoS writes DA as "JUN 10"
            cur.setdefault("year", val[:4])
        elif tag in ("JO", "JF", "T2", "J9", "JA"):
            cur.setdefault("journal", val)
        elif tag == "DO":
            cur["doi"] = val
        elif tag in ("AB", "N2"):
            cur.setdefault("abstract", val)
        elif tag == "UR":
            cur.setdefault("url", val)
        elif tag == "SN":
            cur.setdefault("issn", val)
        elif tag == "ER":
            cur["authors"] = authors
            recs.append(norm_rec(cur))
            cur, authors = {}, []
    return recs


_BIB_FIELD = re.compile(r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|[^,\n]+)\s*,?", re.S)


def _bib_entries(text: str):
    """Yield (kind, body) by brace matching -- robust to one-line entries and
    nested braces, which a regex is not."""
    i = 0
    while True:
        at = text.find("@", i)
        if at < 0:
            return
        open_ = text.find("{", at)
        if open_ < 0:
            return
        kind = text[at + 1:open_].strip().lower()
        depth, j = 1, open_ + 1
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        body = text[open_ + 1:j - 1]
        comma = body.find(",")
        yield kind, (body[comma + 1:] if comma >= 0 else "")
        i = j


def parse_bibtex(text: str) -> list[dict]:
    """BibTeX -> common schema. Handles braces/quotes, nested braces one deep,
    'and'-separated authors, doi/url/abstract/journal/booktitle/year."""
    recs = []
    for kind, body in _bib_entries(text):
        if kind in ("comment", "string", "preamble"):
            continue
        f = {}
        for fm in _BIB_FIELD.finditer(body):
            k, v = fm.group(1).lower(), fm.group(2).strip()
            if v[:1] in "{\"" and v[-1:] in "}\"":
                v = v[1:-1]
            f[k] = re.sub(r"[{}]", "", v).replace("\n", " ").strip()
        recs.append(norm_rec({"title": f.get("title"), "year": f.get("year"),
                              "doi": f.get("doi"), "journal": f.get("journal") or f.get("booktitle"),
                              "authors": [a.strip() for a in re.split(r"\s+and\s+", f.get("author", ""))
                                          if a.strip()],
                              "url": f.get("url"), "abstract": f.get("abstract"),
                              "issn": f.get("issn")}))
    return recs


_CSV_ALIASES = {"title": ("title", "article title", "document title", "ti"),
                "year": ("year", "publication year", "py", "date"),
                "doi": ("doi", "di"),
                "journal": ("journal", "source title", "venue", "so", "publication"),
                "authors": ("authors", "author", "au", "author full names"),
                "url": ("url", "link"), "abstract": ("abstract", "ab"),
                "cited_by": ("cited_by", "cited by", "times cited", "citations", "tc"),
                "issn": ("issn", "sn"), "block": ("block",)}


def parse_csv(text: str) -> list[dict]:
    """CSV with a header row; column names matched case-insensitively against
    common aliases (Scopus and WoS exports included)."""
    rd = csv.DictReader(io.StringIO(text))
    if not rd.fieldnames:
        return []
    cols = {c.lower().strip(): c for c in rd.fieldnames}
    pick = {}
    for field, names in _CSV_ALIASES.items():
        for n in names:
            if n in cols:
                pick[field] = cols[n]
                break
    return [norm_rec({f: row.get(c, "") for f, c in pick.items()}) for row in rd]


def parse_json(text: str) -> list[dict]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("records") or data.get("items") or list(data.values())
    return [norm_rec(r) for r in data if isinstance(r, dict)]


PARSERS = {"ris": parse_ris, "bib": parse_bibtex, "bibtex": parse_bibtex,
           "csv": parse_csv, "json": parse_json, "txt": parse_ris}


def parse_records(path: Path, kind: str = "auto") -> list[dict]:
    path = Path(path)
    k = path.suffix.lstrip(".").lower() if kind == "auto" else kind
    if k not in PARSERS:
        raise ValueError(f"cannot parse {path.name}: unknown kind {k!r} "
                         f"(use --kind ris|bibtex|csv|json)")
    return PARSERS[k](path.read_text(encoding="utf-8", errors="replace"))


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def ingest(outdir: Path, files: list, name: str, block: str = "MANUAL", kind: str = "auto",
           who: str = "", origin: str = "", method: str = "other", note: str = "",
           log: logging.Logger | None = None) -> dict:
    """Parse FILES into manual/<name>/ with provenance. Returns source.json."""
    log = log or logging.getLogger("project")
    if method not in METHODS:
        raise ValueError(f"--method must be one of {METHODS}")
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "manual"
    dest = Path(outdir) / "manual" / name
    parsed = [(Path(f), parse_records(Path(f), kind)) for f in files]   # parse first: no litter on failure
    dest.mkdir(parents=True, exist_ok=True)
    recs, kept = [], []
    for f, got in parsed:
        for r in got:
            r["block"] = r.get("block") or block
            r["backend"] = f"manual:{name}"
        recs.extend(got)
        target = dest / f.name
        if f.resolve() != target.resolve():
            shutil.copy2(f, target)
        kept.append(f.name)
        log.info("  %-24s %5d records  <- %s", name, len(got), f.name)
    (dest / "records.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    src = {"name": name, "kind": kind, "files": kept, "who": who, "origin": origin,
           "method": method, "note": note, "block": block, "n_records": len(recs),
           "ingested": time.strftime("%Y-%m-%d %H:%M:%S"), "tool_version": VERSION}
    (dest / "source.json").write_text(json.dumps(src, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    log.info("%d records -> %s", len(recs), dest)
    return src


def ingest_inbox(outdir: Path, log: logging.Logger | None = None, **kw) -> list:
    """Every parseable file in <outdir>/inbox becomes its own manual source
    named after the file; the file is moved into manual/<name>/."""
    log = log or logging.getLogger("project")
    inbox = Path(outdir) / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    done = []
    for f in sorted(inbox.iterdir()):
        if not f.is_file() or f.suffix.lstrip(".").lower() not in PARSERS:
            continue
        try:
            src = ingest(outdir, [f], f.stem, log=log, **kw)
        except ValueError as e:
            if "--method" in str(e):
                raise                                # a bad option, not a bad file
            log.warning("inbox: %s left in place -- %s", f.name, str(e)[:120])
            continue
        except Exception as e:  # noqa: BLE001  -- a malformed file stays in the inbox
            log.warning("inbox: %s left in place -- %s", f.name, str(e)[:120])
            continue
        f.unlink()
        done.append(src)
    if not done:
        log.info("inbox empty: drop .ris / .bib / .csv / .json files into %s", inbox)
    return done


# ---------------------------------------------------------------------------
# Project index and members
# ---------------------------------------------------------------------------

def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, ValueError):
        return default


def load_project(outdir: Path) -> dict:
    p = _json(Path(outdir) / "project.json", {})
    p.setdefault("name", Path(outdir).resolve().name)
    p.setdefault("description", "")
    p.setdefault("exclude", [])
    p.setdefault("labels", {})
    p.setdefault("block_aliases", {})
    p.setdefault("defaults", {})
    return p


def save_project(outdir: Path, p: dict) -> None:
    (Path(outdir) / "project.json").write_text(json.dumps(p, indent=2, ensure_ascii=False),
                                               encoding="utf-8")


def _stamp_to_date(stamp: str) -> str:
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", stamp)
    return "{}-{}-{} {}:{}:{}".format(*m.groups()) if m else stamp


def members(outdir: Path, project: dict | None = None) -> list[dict]:
    """Every run and manual source in the directory, oldest first, minus
    project.json's exclusions."""
    outdir = Path(outdir)
    p = project or load_project(outdir)
    out = []
    for d in sorted((outdir / "runs").glob("*")) if (outdir / "runs").exists() else []:
        if not (d / "counts.json").exists() or d.name in p["exclude"]:
            continue
        meta = _json(d / "meta.json", {})
        out.append({"id": d.name, "kind": "run", "path": d,
                    "date": meta.get("started") or _stamp_to_date(d.name),
                    "label": p["labels"].get(d.name, ""), "meta": meta,
                    "method": "database"})
    for d in sorted((outdir / "manual").glob("*")) if (outdir / "manual").exists() else []:
        if not (d / "records.json").exists() or d.name in p["exclude"]:
            continue
        src = _json(d / "source.json", {})
        out.append({"id": d.name, "kind": "manual", "path": d,
                    "date": src.get("ingested", ""), "label": p["labels"].get(d.name, ""),
                    "source": src, "method": src.get("method", "other")})
    return sorted(out, key=lambda m: m["date"])


def member_records(m: dict, aliases: dict | None = None) -> list[dict]:
    """Raw (pre-dedup) records of one member, block aliases applied."""
    aliases = aliases or {}
    recs = []
    if m["kind"] == "run":
        for f in sorted((m["path"] / "records").glob("*.json")):
            for r in _json(f, []):
                r.setdefault("block", f.stem.rsplit("_", 1)[0])
                r.setdefault("backend", f.stem.rsplit("_", 1)[-1])
                recs.append(r)
    else:
        recs = _json(m["path"] / "records.json", [])
    for r in recs:
        r["block"] = aliases.get(r.get("block", ""), r.get("block", ""))
        r["member"] = m["id"]
        r["member_date"] = m["date"]
    return recs


def rec_key(r: dict) -> str:
    return (r.get("doi") or "").lower() or (r.get("title") or "").lower()[:90]


def merge(records: list[dict]) -> list[dict]:
    """Deduplicate across members. Keeps the richest copy (longest abstract,
    highest citation count, first DOI seen) and records provenance:
    found_by = ["backend@member", ...], first_seen = earliest member date."""
    by = {}
    for r in records:
        k = rec_key(r)
        if not k:
            continue
        tags = list(r.get("found_by") or [f"{r.get('backend', '?')}@{r.get('member', '?')}"])
        if k not in by:
            c = dict(r)
            c["found_by"] = tags                      # an already-merged record keeps its provenance
            c["first_seen"] = r.get("first_seen") or r.get("member_date", "")
            c["blocks"] = list(r.get("blocks") or [r.get("block", "")])
            by[k] = c
        else:
            c = by[k]
            for tag in tags:
                if tag not in c["found_by"]:
                    c["found_by"].append(tag)
            if r.get("block") and r["block"] not in c["blocks"]:
                c["blocks"].append(r["block"])
            if len(r.get("abstract") or "") > len(c.get("abstract") or ""):
                c["abstract"] = r["abstract"]
            if (r.get("cited_by") or 0) > (c.get("cited_by") or 0):
                c["cited_by"] = r["cited_by"]
            for f in ("doi", "issn", "url", "journal", "year"):
                if not c.get(f) and r.get(f):
                    c[f] = r[f]
            # a preprint label loses to the published venue another source knows
            if (c.get("journal") or "").lower().startswith("arxiv") and r.get("journal") \
                    and not r["journal"].lower().startswith("arxiv"):
                c["journal"] = r["journal"]
            if r.get("member_date", "") and (not c["first_seen"] or r["member_date"] < c["first_seen"]):
                c["first_seen"] = r["member_date"]
    return sorted(by.values(), key=lambda x: -(x.get("cited_by") or 0))


def oa_pass(outdir: Path, member_ids=None, log: logging.Logger | None = None) -> dict:
    """Post-hoc open-access lookup (Unpaywall, legal copies only) over every
    member's records that lack it -- runs made without --pdfs and manual
    sources alike. Results are written back into the member files and
    cached in <outdir>/unpaywall_cache.json like librarian.py does."""
    log = log or logging.getLogger("project")
    try:
        import librarian
    except ImportError:
        import litscan as librarian  # type: ignore
    cfile = Path(outdir) / "unpaywall_cache.json"
    stats = {"members": 0, "dois": 0, "fetched": 0, "oa": 0}
    for m in members(outdir):
        if member_ids and m["id"] not in member_ids:
            continue
        files = sorted((m["path"] / "records").glob("*.json")) + [m["path"] / "all_records.json"] \
            if m["kind"] == "run" else [m["path"] / "records.json"]
        files = [f for f in files if f.exists()]
        loaded = [(f, json.loads(f.read_text(encoding="utf-8"))) for f in files]
        dois = {(r.get("doi") or "").strip() for _, recs in loaded for r in recs
                if (r.get("doi") or "").strip() and "is_oa" not in r}
        before = json.loads(cfile.read_text(encoding="utf-8")) if cfile.exists() else {}
        cache = librarian.unpaywall_cached(sorted(dois), cfile)
        stats["fetched"] += sum(1 for d in dois if d in cache and d not in before)
        touched = False
        for f, recs in loaded:
            changed = False
            for r in recs:
                d = (r.get("doi") or "").strip()
                if d and "is_oa" not in r and cache.get(d):
                    r.update(cache[d])
                    changed = True
            if changed:
                f.write_text(json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
                touched = True
        stats["members"] += 1
        stats["dois"] += len(dois)
        stats["oa"] += sum(1 for d in dois if cache.get(d, {}).get("is_oa"))
        log.info("  %-24s %s", m["id"], "updated" if touched else "nothing to add")
    log.info("%d members, %d DOIs looked at, %d fetched, %d open access",
             stats["members"], stats["dois"], stats["fetched"], stats["oa"])
    return stats


def status(outdir: Path) -> str:
    p = load_project(outdir)
    ms = members(outdir, p)
    lines = [f"project: {p['name']}  ({outdir})", p["description"] or "", ""]
    lines.append(f"{'member':28s} {'kind':7s} {'date':19s} {'records':>8s}  {'method':12s} label")
    for m in ms:
        n = len(member_records(m))
        lines.append(f"{m['id']:28s} {m['kind']:7s} {m['date'][:19]:19s} {n:8d}  "
                     f"{m['method']:12s} {m['label']}")
    if p["exclude"]:
        lines.append(f"\nexcluded: {', '.join(p['exclude'])}")
    inbox = Path(outdir) / "inbox"
    if inbox.exists() and any(inbox.iterdir()):
        lines.append("\ninbox has files waiting: python project.py ingest --inbox")
    reports = sorted((Path(outdir) / "reports").glob("*")) if (Path(outdir) / "reports").exists() else []
    if reports:
        lines.append(f"\nlast project report: {reports[-1]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"scitech-librarian {VERSION}")
    common = argparse.ArgumentParser(add_help=False)
    add_common_args(common)
    sub = ap.add_subparsers(dest="cmd", parser_class=lambda **kw: argparse.ArgumentParser(
        parents=[common], **kw))
    s = sub.add_parser("init", help="write project.json")
    s.add_argument("--name", required=True)
    s.add_argument("--description", default="")
    sub.add_parser("status", help="members, counts, inbox, last report")
    s = sub.add_parser("ingest", help="bring external records in as a manual source")
    s.add_argument("files", nargs="*", help="RIS / BibTeX / CSV / JSON files")
    s.add_argument("--inbox", action="store_true", help="ingest every file in <outdir>/inbox")
    s.add_argument("--name", default=None, help="source name (default: first file's stem)")
    s.add_argument("--block", default="MANUAL", help="block to file the records under")
    s.add_argument("--kind", default="auto", choices=("auto", "ris", "bibtex", "bib", "csv", "json"))
    s.add_argument("--who", default="", help="who obtained these records")
    s.add_argument("--origin", default="", help="where from (e.g. 'Zotero library X', 'WoS UI')")
    s.add_argument("--method", default="other", choices=METHODS,
                   help="PRISMA 2020 identification method (default: other)")
    s.add_argument("--note", default="")
    s = sub.add_parser("oa", help="open-access lookup (Unpaywall) over members that lack it")
    s.add_argument("--members", nargs="+", default=None, help="restrict to these member ids")
    s = sub.add_parser("exclude", help="hide a member from project reports")
    s.add_argument("member")
    s = sub.add_parser("include", help="undo exclude")
    s.add_argument("member")
    s = sub.add_parser("label", help="attach a label to a member")
    s.add_argument("member")
    s.add_argument("text")
    s = sub.add_parser("alias", help="map an old block name to a canonical one")
    s.add_argument("old")
    s.add_argument("new")
    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 2
    outdir = resolve_outdir(args.outdir)
    log = setup_logging("project", args, outdir)
    if not args.cmd:
        ap.print_help()
        return 2
    p = load_project(outdir)
    if args.cmd == "init":
        outdir.mkdir(parents=True, exist_ok=True)
        p.update({"name": args.name, "description": args.description,
                  "created": p.get("created") or time.strftime("%Y-%m-%d")})
        save_project(outdir, p)
        for sub_ in ("runs", "manual", "inbox", "logs"):
            (outdir / sub_).mkdir(exist_ok=True)
        log.info("initialised %s -> %s", p["name"], outdir / "project.json")
    elif args.cmd == "status":
        print(status(outdir))
    elif args.cmd == "ingest":
        if args.inbox:
            done = ingest_inbox(outdir, log, block=args.block, kind=args.kind, who=args.who,
                                origin=args.origin, method=args.method, note=args.note)
            log.info("%d source(s) ingested from inbox", len(done))
        elif args.files:
            name = args.name or Path(args.files[0]).stem
            ingest(outdir, args.files, name, args.block, args.kind, args.who, args.origin,
                   args.method, args.note, log)
        else:
            log.error("give files or --inbox")
            return 2
    elif args.cmd == "oa":
        oa_pass(outdir, args.members, log)
    elif args.cmd in ("exclude", "include"):
        ex = set(p["exclude"])
        (ex.add if args.cmd == "exclude" else ex.discard)(args.member)
        p["exclude"] = sorted(ex)
        save_project(outdir, p)
        log.info("%s %s", args.cmd, args.member)
    elif args.cmd == "label":
        p["labels"][args.member] = args.text
        save_project(outdir, p)
    elif args.cmd == "alias":
        p["block_aliases"][args.old] = args.new
        save_project(outdir, p)
    close_logging(log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
