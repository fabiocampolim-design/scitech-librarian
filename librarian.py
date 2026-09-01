#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Fabio Campolim
"""
librarian.py -- automated multi-database literature scan.

    python librarian.py                          # all blocks, all available backends
    python librarian.py --counts-only            # fast: hit counts, no record fetch
    python librarian.py --blocks A CD            # selected blocks
    python librarian.py --backends openalex arxiv inspire
    python librarian.py --list                   # show blocks and configured backends

WINDOWS NOTE: cmd.exe does NOT treat '#' as a comment. Do not paste a trailing
'# explanation' after a command -- argparse will reject it. Either drop the
comment or use PowerShell.

EVERYTHING IS SAVED. Every run writes a timestamped directory under lit/runs/
containing the raw records (JSON), RIS files for Zotero, a combined CSV, the
exact query string sent to each backend, a log, and a literature-search
REPORT with a PRISMA 2020 flow (report.py; --report-level simple|intermediate|
full, --report-format md html tex pdf txt). Counts are also appended to
lit/counts_history.csv so drift over time is visible.

Backends
--------
no key needed:  openalex  arxiv  inspire  semanticscholar  crossref
                (OpenAlex has a daily free budget; OPENALEX_API_KEY raises it)
key needed:     scopus (SCOPUS_API_KEY + institutional network/VPN)
                ads    (ADS_TOKEN)
                wos    (WOS_STARTER_KEY; restricted grammar, see .env.example)

Keys live in `.env` next to this file (gitignored). See `.env.example`.
Stdlib only -- no pip install required.

LEGAL: documented public APIs only. Never point a scraper at the Web of
Science or Scopus web interfaces; that breaches their terms and can get
your institution's access suspended.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

VERSION = "3.3.3"


def _report_lang(value: str) -> str:
    """argparse type for --report-lang: validated before any backend call,
    aliases accepted (pt, PT-br, fr_FR ...). Nothing in this script is ever
    translated; i18n is imported here only, on use."""
    try:
        import i18n
    except ImportError as e:             # librarian.py copied without i18n.py
        raise argparse.ArgumentTypeError(f"i18n.py is needed next to librarian.py ({e})")
    try:
        return i18n.normalize(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))
HERE = Path(__file__).resolve().parent
# If this file lives in a tools/ subdirectory of a larger project, the .env,
# query file and lit/ output directory belong to the project root. Resolve that
# once, so the tool behaves the same as a standalone repo or as a drop-in.
ROOT = HERE.parent if HERE.name == "tools" else HERE
OUTDIR = ROOT / "lit"


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def load_env(path: Path = None) -> None:
    path = Path(path) if path else ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


load_env()
CONTACT = os.environ.get("CONTACT_EMAIL", "").strip()


# ---------------------------------------------------------------------------
# Query blocks, defined STRUCTURALLY.
# ---------------------------------------------------------------------------
# `groups` is a conjunction of disjunctions: [[a, b], [c]] means (a OR b) AND c.
# Each backend's native syntax is generated from this, so the queries stay in
# sync across eight databases instead of being maintained eight times.
#
# Where proximity operators matter (WoS NEAR/n, Scopus W/n) the hand-written
# strings in SEARCH_QUERIES.md remain authoritative for manual UI runs; the
# generated forms below drop proximity, which is why counts are NOT comparable
# across backends. Use these for discovery; quote WoS/Scopus in the paper.

def load_blocks(path: str | Path | None = None) -> dict[str, dict]:
    """Load the query definitions from JSON.

    Search order: --queries argument, ./queries.json, ./queries.example.json.

    Each block is:
      "NAME": {
        "title":  short description,
        "note":   why you are running it / what a good result looks like,
        "groups": [[synonym, synonym], [synonym]],   # AND of ORs
        "arxiv_groups": [0, 2]      # OPTIONAL: which groups to send to arXiv,
                                    # which chokes on deeply nested booleans
      }

    "groups" is a conjunction of disjunctions: [[a,b],[c]] means (a OR b) AND c.
    Every backend's native syntax is generated from this one definition, so you
    write a query once instead of once per database.
    """
    cands = [Path(path)] if path else [HERE / "queries.json", ROOT / "queries.json",
                                       HERE / "queries.example.json",
                                       ROOT / "queries.example.json"]
    for p in cands:
        if p and p.exists():
            blocks = json.loads(p.read_text(encoding="utf-8"))
            for name, b in blocks.items():
                if "groups" not in b:
                    raise ValueError(f"block {name!r} has no 'groups' key")
                b.setdefault("title", name)
                b.setdefault("note", "")
            return blocks
    raise SystemExit(
        "No query file found. Copy queries.example.json to queries.json and edit it.")


BLOCKS: dict[str, dict] = {}     # populated in main() from the JSON file


# ---------------------------------------------------------------------------
# Query generation, driven by each backend's `syntax` config
# ---------------------------------------------------------------------------
# A syntax spec is a small dict:
#   term:       "auto" (quote unless bare alphanumeric) | "always" (always
#               quote) | a template containing {t} (e.g. 'all:"{t}"')
#   term_join:  string between synonyms inside a group  (default " OR ")
#   group:      template wrapping one group              (default "({g})")
#   group_join: string between groups                    (default " AND ")
#   outer:      template wrapping the whole query        (default "{q}")
#   mode:       "boolean" (default) | "first_terms" (keep only the first
#               synonym of each group -- for engines with no boolean support)
#   group_limit: send at most N groups. WHICH groups can be stated per block
#               via `arxiv_groups` (kept under that name for compatibility);
#               default: the first N. arXiv needs this -- its search backend
#               degrades badly on deeply nested booleans (the 2026-08-14 hang),
#               and an automatic "most selective" heuristic picks wrong.

def _q(term: str) -> str:
    """Quote anything that is not a bare alphanumeric word. Periods matter:
    unquoted `k.p` is parsed as a field/operator by some engines."""
    return term if term.isalnum() else f'"{term}"'


def build_query(groups, syntax: dict, blk: dict | None = None) -> str:
    limit = syntax.get("group_limit")
    if limit:
        idx = (blk or {}).get("arxiv_groups")
        groups = [groups[i] for i in idx] if idx else groups[:limit]
    if syntax.get("mode") == "first_terms":
        return syntax.get("group_join", " ").join(grp[0] for grp in groups)
    term = syntax.get("term", "auto")
    if term == "auto":
        fmt = _q
    elif term == "always":
        fmt = lambda t: f'"{t}"'          # noqa: E731
    else:
        fmt = lambda t: term.format(t=t)  # noqa: E731
    parts = [syntax.get("group", "({g})").format(
                 g=syntax.get("term_join", " OR ").join(fmt(t) for t in grp))
             for grp in groups]
    return syntax.get("outer", "{q}").format(q=syntax.get("group_join", " AND ").join(parts))


def _syntax(backend: str) -> dict:
    return BACKENDS_CFG[backend].get("syntax", {})


# Named wrappers, kept because wos_manual.py and the tests import them.
def q_openalex(g, blk=None): return build_query(g, _syntax("openalex"), blk)
def q_arxiv(g, blk=None):    return build_query(g, _syntax("arxiv"), blk)
def q_inspire(g, blk=None):  return build_query(g, _syntax("inspire"), blk)
def q_s2(g, blk=None):       return build_query(g, _syntax("semanticscholar"), blk)
def q_ads(g, blk=None):      return build_query(g, _syntax("ads"), blk)
def q_crossref(g, blk=None): return build_query(g, _syntax("crossref"), blk)
def q_scopus(g, blk=None):   return build_query(g, _syntax("scopus"), blk)


def q_wos(g, blk=None):
    """Single field tag wrapping a nested boolean:  TS=((a OR b) AND (c OR d)).

    Preferred over the repeated-tag form TS=(...) AND TS=(...): although the
    repeated form is documented, it is fragile in the query-builder UI and
    complex multi-tag queries on All Fields can error or time out. One tag,
    nested parentheses, is unambiguous.
    """
    return build_query(g, _syntax("wos"), blk)


def q_wos_bare(g, blk=None):
    """Boolean with NO field tag. This is what you paste when the WoS UI already
    has a field chosen from a dropdown ("Topic", "All Fields"). Including a tag
    there is what produced 'Search Error: Invalid query'."""
    s = dict(_syntax("wos"))
    s.pop("outer", None)
    return build_query(g, s, blk)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

TIMEOUT = 45          # per-request socket timeout, seconds (overridable via --timeout)


def _get(url: str, headers: dict | None = None, tries: int = 3,
         timeout: float | None = None) -> bytes:
    hdr = {"User-Agent": f"scitech-librarian/{VERSION} (mailto:{CONTACT})", **(headers or {})}
    tmo = timeout or TIMEOUT
    last = None
    for attempt in range(tries):
        if attempt:
            print(f" retry {attempt+1}/{tries}...", end="", flush=True)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=tmo) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            last = f"HTTP {e.code}: {body}"
            if e.code in (401, 403):
                raise RuntimeError(
                    f"{last}\n      -> auth/entitlement. Scopus: are you on your institution's "
                    f"VPN and is the key valid? WoS: Starter keys reject complex queries."
                ) from None
            if e.code == 429 and "budget" in body.lower():
                raise RuntimeError(
                    f"{last}\n      -> OpenAlex daily free budget exhausted (resets at midnight UTC). "
                    f"Set OPENALEX_API_KEY in .env (free key, prepaid credits raise the "
                    f"budget: https://openalex.org/pricing) or rerun tomorrow.") from None
            if e.code in (429, 500, 502, 503):
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(last) from None
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {last}")


def _json(url: str, headers: dict | None = None) -> dict:
    return json.loads(_get(url, headers).decode("utf-8", "replace"))


# Repositories that OpenAlex indexes without editorial curation. On the
# 2026-08-15 run these were 15.3% of OpenAlex records (223/1455) and 0% of ADS,
# Scopus, Semantic Scholar and INSPIRE -- and they were the entire difference
# between OpenAlex's 16 hits and Scopus's 3 on the decisive CD cross-query.
JUNK_VENUE = re.compile(r"zenodo|figshare|open mind|ssrn|preprints\.org|researchgate", re.I)


def is_junk(rec: dict) -> bool:
    return bool(JUNK_VENUE.search(rec.get("journal") or ""))


def _rec(title, year, doi, journal, authors, url, abstract="", cited=0, issn="") -> dict:
    if isinstance(issn, list):
        issn = issn[0] if issn else ""
    return {"title": (title or "").strip(), "year": str(year or ""),
            "doi": (doi or "").replace("https://doi.org/", "").strip(),
            "journal": (journal or "").strip(), "authors": [a for a in (authors or []) if a],
            "url": url or "", "abstract": (abstract or "").strip(), "cited_by": int(cited or 0),
            "issn": (issn or "").strip()}


# ---------------------------------------------------------------------------
# Backends -> (total, [records])
# ---------------------------------------------------------------------------

_ATOM, _OS, _ARX = ("{http://www.w3.org/2005/Atom}",
                    "{http://a9.com/-/spec/opensearch/1.1/}",
                    "{http://arxiv.org/schemas/atom}")


def bk_arxiv(q, want):
    recs, start, total, pages = [], 0, 0, 0
    # as many 100-record pages as --limit asks for (a hard 3-page cap used to
    # silently truncate --limit > 300); the 3 s sleep between pages keeps it polite
    max_pages = max(1, -(-want // 100)) if want else 1
    while pages < max_pages:
        pages += 1
        p = urllib.parse.urlencode({"search_query": q, "start": start,
                                    "max_results": 100 if want else 1})
        # HTTPS, not HTTP: the plain-HTTP endpoint redirects and can stall behind
        # a VPN. Short timeout and 2 tries -- arXiv is the one backend that hangs
        # rather than erroring, so we fail it fast instead of waiting it out.
        root = ET.fromstring(_get(f"https://export.arxiv.org/api/query?{p}",
                                  tries=2, timeout=min(TIMEOUT, 25)))
        tot = root.find(f"{_OS}totalResults")
        total = int(tot.text) if tot is not None and tot.text else 0
        if not want:
            return total, []
        entries = root.findall(f"{_ATOM}entry")
        for e in entries:
            doi_el = e.find(f"{_ARX}doi")
            jr = e.find(f"{_ARX}journal_ref")
            recs.append(_rec(
                (e.findtext(f"{_ATOM}title") or "").replace("\n", " "),
                (e.findtext(f"{_ATOM}published") or "")[:4],
                doi_el.text if doi_el is not None else "",
                jr.text if jr is not None else "arXiv preprint",
                [a.findtext(f"{_ATOM}name") for a in e.findall(f"{_ATOM}author")],
                e.findtext(f"{_ATOM}id"),
                (e.findtext(f"{_ATOM}summary") or "").replace("\n", " ")))
        start += 100
        if not entries or len(recs) >= min(want, total):
            break
        time.sleep(3.0)  # arXiv asks for >=3 s between calls
    return total, recs[:want]


def unpaywall_cached(dois, cfile: Path, progress=None, sleep: float = 0.1) -> dict:
    """Look up DOIs via Unpaywall with a JSON cache on disk. Failed lookups are
    NOT cached, so a transient outage is retried next time. Ctrl-C keeps
    what was fetched. Returns the cache (doi -> oa fields)."""
    cache: dict = json.loads(cfile.read_text(encoding="utf-8")) if cfile.exists() else {}
    todo = [d for d in dois if d and d not in cache]
    try:
        for i, d in enumerate(todo, 1):
            try:
                cache[d] = unpaywall(d)
            except Exception:  # noqa: BLE001  -- retried on the next pass
                pass
            if progress and (i % 25 == 0 or i == len(todo)):
                progress(i, len(todo))
                cfile.write_text(json.dumps(cache), encoding="utf-8")
            time.sleep(sleep)
    except KeyboardInterrupt:
        print("\n    Unpaywall interrupted -- cache kept")
    cfile.write_text(json.dumps(cache), encoding="utf-8")
    return cache


def unpaywall(doi: str) -> dict:
    """Legal open-access PDF lookup. No key -- just an email address."""
    if not doi:
        return {}
    d = _json(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={CONTACT}")
    loc = d.get("best_oa_location") or {}
    return {"is_oa": bool(d.get("is_oa")),
            "oa_pdf": loc.get("url_for_pdf") or "",
            "oa_url": loc.get("url") or "",
            "oa_version": loc.get("version") or ""}


# ---------------------------------------------------------------------------
# Declarative backends: every JSON-REST database is DATA, not code.
# ---------------------------------------------------------------------------
# A backend entry has four parts (see also docs/ADDING_A_DATABASE.md):
#   syntax   how to render the structural query in this engine's grammar
#   request  url, param templates ({q} query, {n} page size, {page}/{start}/
#            {cursor} pagination, {contact} CONTACT_EMAIL), paging style
#   auth     env var + header template; "optional": true = use if present
#   parse    dotted paths for total / items / record fields
# Field path DSL: dots descend, [0] indexes, [] maps over a list, "a|b" tries
# alternatives. A field spec may also be a dict with path plus modifiers:
#   join (list -> string), first4 (year from a date string), limit (list cap),
#   aslist (wrap scalar), int, default, transform (named python transform),
#   template+vars (build a string from other extracted paths; used as a
#   fallback when "path" is also given and yields nothing).
# Engines that need real code (arXiv's XML) declare "driver" instead.
#
# The embedded defaults below ship with the tool; a backends.json next to the
# script (or at the project root) REPLACES entries by name and may add new
# ones or set "disabled": true. --init-backends writes the defaults out to
# backends.json so you can edit them.

DEFAULT_BACKENDS: dict[str, dict] = {
    "openalex": {
        "syntax": {},
        "auth": {"env": "OPENALEX_API_KEY", "param": "api_key", "optional": True,
                 "hint": "free key at https://openalex.org/pricing; raises the daily budget"},
        "request": {"url": "https://api.openalex.org/works",
                    "params": {"filter": "title_and_abstract.search:{q}", "per-page": "{n}",
                               "cursor": "{cursor}", "mailto": "{contact}"},
                    "paging": {"style": "cursor", "next": "meta.next_cursor",
                               "start": "*", "size": 200, "sleep": 0.15}},
        "parse": {"total": "meta.count", "items": "results",
                  "fields": {"title": "display_name", "year": "publication_year",
                             "doi": "doi",
                             "journal": "primary_location.source.display_name",
                             "issn": "primary_location.source.issn_l",
                             "authors": "authorships[].author.display_name",
                             "url": "id",
                             "abstract": {"path": "abstract_inverted_index",
                                          "transform": "inverted_abstract"},
                             "cited": "cited_by_count"}},
    },
    "arxiv": {
        "driver": "arxiv",
        "syntax": {"term": 'all:"{t}"', "group_limit": 2},
    },
    "inspire": {
        "syntax": {"term": "always", "term_join": " or ", "group_join": " and "},
        "request": {"url": "https://inspirehep.net/api/literature",
                    "params": {"q": "{q}", "size": "{n}", "page": "{page}",
                               "fields": "titles,dois,publication_info,earliest_date,authors"},
                    "paging": {"style": "page", "size": 100, "sleep": 0.4}},
        "parse": {"total": "hits.total", "items": "hits.hits",
                  "fields": {"title": "metadata.titles[0].title",
                             "year": {"path": "metadata.earliest_date", "first4": True},
                             "doi": "metadata.dois[0].value",
                             "journal": {"path": "metadata.publication_info[0].journal_title",
                                         "default": "INSPIRE record"},
                             "authors": {"path": "metadata.authors[].full_name", "limit": 12},
                             "url": {"path": "links.json",
                                     "template": "https://inspirehep.net/literature/{id}",
                                     "vars": {"id": "id"}}}},
    },
    "semanticscholar": {
        "syntax": {"term": "always", "term_join": " | ", "group_join": " + "},
        "auth": {"env": "S2_API_KEY", "header": "x-api-key", "optional": True},
        "request": {"url": "https://api.semanticscholar.org/graph/v1/paper/search/bulk",
                    "params": {"query": "{q}",
                               "fields": "title,year,abstract,externalIds,venue,authors,citationCount"},
                    "paging": {"style": "none"}},
        "parse": {"total": "total", "items": "data",
                  "fields": {"title": "title", "year": "year", "doi": "externalIds.DOI",
                             "journal": "venue", "authors": "authors[].name",
                             "url": {"template": "https://www.semanticscholar.org/paper/{pid}",
                                     "vars": {"pid": "paperId"}},
                             "abstract": "abstract", "cited": "citationCount"}},
    },
    "crossref": {
        # Crossref has no boolean support -- `query.bibliographic` is a
        # relevance search (the self-test probe returned 1.26 MILLION hits),
        # so its counts are meaningless for a novelty check: excluded from the
        # default run, kept for explicit DOI-metadata cross-checks.
        "default_exclude": True,
        "syntax": {"mode": "first_terms", "group_join": " "},
        "request": {"url": "https://api.crossref.org/works",
                    "params": {"query.bibliographic": "{q}", "rows": "{n}",
                               "mailto": "{contact}"},
                    "paging": {"style": "none", "size": 100, "count_size": 0}},
        "parse": {"total": "message.total-results", "items": "message.items",
                  "fields": {"title": {"path": "title", "join": " "},
                             "year": "issued.date-parts[0][0]", "doi": "DOI",
                             "journal": {"path": "container-title", "join": " "},
                             "issn": "ISSN[0]",
                             "authors": {"path": "author[]", "transform": "given_family"},
                             "url": "URL", "abstract": "abstract",
                             "cited": "is-referenced-by-count"}},
    },
    "ads": {
        "syntax": {"term": 'abs:"{t}"'},
        "auth": {"env": "ADS_TOKEN", "header": "Authorization", "value": "Bearer {key}",
                 "hint": "free at https://ui.adsabs.harvard.edu/user/settings/token"},
        "request": {"url": "https://api.adsabs.harvard.edu/v1/search/query",
                    "params": {"q": "{q}", "rows": "{n}",
                               "fl": "title,year,doi,bibcode,author,abstract,citation_count"},
                    "paging": {"style": "none", "size": 200}},
        "parse": {"total": "response.numFound", "items": "response.docs",
                  "fields": {"title": {"path": "title", "join": " "}, "year": "year",
                             "doi": "doi[0]", "authors": "author",
                             "url": {"template": "https://ui.adsabs.harvard.edu/abs/{b}",
                                     "vars": {"b": "bibcode"}},
                             "abstract": "abstract", "cited": "citation_count"}},
    },
    "scopus": {
        "syntax": {"group": "TITLE-ABS-KEY({g})"},
        "auth": {"env": "SCOPUS_API_KEY", "header": "X-ELS-APIKey",
                 "hint": "not set in .env",
                 "extra": [{"env": "SCOPUS_INSTTOKEN", "header": "X-ELS-Insttoken",
                            "optional": True}],
                 "static": {"Accept": "application/json"}},
        "request": {"url": "https://api.elsevier.com/content/search/scopus",
                    "params": {"query": "{q}", "count": "{n}", "start": "{start}"},
                    "paging": {"style": "offset", "size": 25, "sleep": 0.35}},
        "parse": {"total": {"path": "search-results.opensearch:totalResults", "int": True},
                  "items": "search-results.entry", "drop_error_items": True,
                  "fields": {"title": "dc:title",
                             "year": {"path": "prism:coverDate", "first4": True},
                             "doi": "prism:doi", "journal": "prism:publicationName",
                             "issn": "prism:issn",
                             "authors": {"path": "dc:creator", "aslist": True},
                             "url": "prism:url", "abstract": "dc:description",
                             "cited": "citedby-count"}},
    },
    "wos": {
        "syntax": {"outer": "TS=({q})"},
        "auth": {"env": "WOS_STARTER_KEY", "header": "X-ApiKey", "hint": "not set in .env"},
        "request": {"url": "https://api.clarivate.com/apis/wos-starter/v1/documents",
                    "params": {"q": "{q}", "db": "WOS", "limit": "{n}", "page": "{page}"},
                    "paging": {"style": "page", "size": 50, "sleep": 0.35}},
        "parse": {"total": "metadata.total", "items": "hits",
                  "fields": {"title": "title", "year": "source.publishYear",
                             "doi": "identifiers.doi", "journal": "source.sourceTitle",
                             "authors": "names.authors[].displayName",
                             "url": "links.record",
                             "cited": {"path": "citations[0].count", "default": 0}}},
    },
}


_PATH_SEG = re.compile(r"([^.\[\]|]+)|\[(\d*)\]")


def _extract(obj, path: str):
    """Dotted-path extractor: dots descend, [0] indexes, [] maps, a|b tries
    alternatives left to right and returns the first non-empty result."""
    for alt in path.split("|"):
        cur, mapped = obj, False
        for m in _PATH_SEG.finditer(alt.strip()):
            key, idx = m.group(1), m.group(2)
            def step(o):
                if o is None:
                    return None
                if key is not None:
                    return o.get(key) if isinstance(o, dict) else None
                if idx == "":                     # [] -> map over the list
                    return o if isinstance(o, list) else ([] if o is None else [o])
                try:
                    return o[int(idx)] if isinstance(o, list) else None
                except IndexError:
                    return None
            if mapped:
                cur = [step(o) for o in (cur or [])]
            elif key is None and idx == "":
                cur, mapped = step(cur), True
            else:
                cur = step(cur)
        if cur not in (None, "", [], {}):
            return cur
    return None


TRANSFORMS = {
    # every position of every word, not just the first -- otherwise repeated
    # words ("the", "of") vanish and the abstract reads like a telegram
    "inverted_abstract": lambda inv: " ".join(
        w for w, _ in sorted(((w, p) for w, ps in inv.items() for p in ps),
                             key=lambda x: x[1]))
                                     if isinstance(inv, dict) and inv else "",
    "given_family": lambda items: [f"{a.get('given', '')} {a.get('family', '')}".strip()
                                   for a in (items or []) if isinstance(a, dict)],
}


def _field(item: dict, spec):
    if isinstance(spec, str):
        return _extract(item, spec)
    val = _extract(item, spec["path"]) if "path" in spec else None
    if "transform" in spec:
        val = TRANSFORMS[spec["transform"]](val)
    if not val and "template" in spec:
        vars_ = {k: (_extract(item, p) or "") for k, p in spec.get("vars", {}).items()}
        val = spec["template"].format(**vars_)
    if val and spec.get("first4"):
        val = str(val)[:4]
    if isinstance(val, list) and "join" in spec:
        val = spec["join"].join(str(v) for v in val if v)
    if spec.get("aslist") and not isinstance(val, list):
        val = [val] if val else []
    if isinstance(val, list) and "limit" in spec:
        val = val[:spec["limit"]]
    if spec.get("int"):
        val = int(val or 0)
    if val in (None, "", []):
        val = spec.get("default", val)
    return val


def _auth_headers(entry: dict) -> dict:
    """Build headers from the auth spec; RuntimeError when a required key is
    absent so the caller reports it exactly like any backend failure."""
    auth = entry.get("auth")
    hdr = {}
    if not auth:
        return hdr
    hdr.update(auth.get("static", {}))
    specs = [auth] + list(auth.get("extra", []))
    for a in specs:
        if a.get("param"):                 # sent as a query parameter, see _auth_params
            continue
        val = os.environ.get(a["env"], "")
        if not val:
            if a.get("optional"):
                continue
            raise RuntimeError(f"{a['env']} not set -- {a.get('hint', 'see .env.example')}")
        hdr[a["header"]] = a.get("value", "{key}").format(key=val)
    return hdr


def _auth_params(entry: dict) -> dict:
    """Auth specs with "param" are query parameters (OpenAlex api_key)."""
    auth = entry.get("auth") or {}
    out = {}
    for a in [auth] + list(auth.get("extra", [])) if auth else []:
        if a.get("param") and os.environ.get(a.get("env", ""), ""):
            out[a["param"]] = os.environ[a["env"]]
    return out


def _make_fetch(entry: dict):
    """Compile one declarative backend entry into a (query, want) -> (total,
    records) function -- the same contract the hand-written backends had."""
    req, parse = entry["request"], entry["parse"]
    paging = req.get("paging", {"style": "none"})
    style = paging.get("style", "none")
    size = paging.get("size", 100)

    def fetch(q, want):
        hdr = _auth_headers(entry)
        recs, total = [], 0
        cursor = paging.get("start", "")
        page, start = 1, 0
        n = (min(want, size) if want else paging.get("count_size", 1))
        while True:
            subst = {"q": q, "n": n, "contact": CONTACT,
                     "cursor": cursor, "page": page, "start": start}
            params = {k: str(v).format(**subst) for k, v in req["params"].items()}
            params.update(_auth_params(entry))
            d = _json(req["url"] + "?" + urllib.parse.urlencode(params), hdr)
            tot = _field(d, parse["total"]) if isinstance(parse["total"], dict) \
                else _extract(d, parse["total"])
            total = int(tot or 0)
            if not want:
                return total, []
            items = _extract(d, parse["items"]) or []
            if parse.get("drop_error_items"):
                items = [i for i in items if "error" not in i]
            for it in items:
                f = {k: _field(it, s) for k, s in parse["fields"].items()}
                recs.append(_rec(f.get("title"), f.get("year"), f.get("doi"),
                                 f.get("journal"), f.get("authors"), f.get("url"),
                                 f.get("abstract") or "", f.get("cited") or 0,
                                 f.get("issn") or ""))
            if style == "none" or not items or len(recs) >= min(want, total):
                break
            if style == "cursor":
                cursor = _extract(d, paging["next"])
                if not cursor:
                    break
            elif style == "page":
                page += 1
            elif style == "offset":
                start += size
                if start >= min(want, total):
                    break
            time.sleep(paging.get("sleep", 0.2))
        return total, recs[:want]

    return fetch


DRIVERS = {"arxiv": lambda entry: bk_arxiv}


def load_backends(path: str | Path | None = None) -> dict[str, dict]:
    """Embedded defaults, overlaid by backends.json (script dir, then project
    root) or an explicit --backends-file. File entries replace same-named
    defaults wholesale; new names are added; "disabled": true removes one."""
    cfg = {k: dict(v) for k, v in DEFAULT_BACKENDS.items()}
    cands = [Path(path)] if path else [HERE / "backends.json", ROOT / "backends.json"]
    for p in cands:
        if p and p.exists():
            for name, entry in json.loads(p.read_text(encoding="utf-8")).items():
                cfg[name] = entry
            break
    return {k: v for k, v in cfg.items() if not v.get("disabled")}


def compile_backends(cfg: dict[str, dict]) -> dict:
    """-> {name: (fetch_fn, query_fn, required_env_or_None)}"""
    out = {}
    for name, entry in cfg.items():
        fetch = DRIVERS[entry["driver"]](entry) if "driver" in entry else _make_fetch(entry)
        qfn = (lambda syn: lambda g, blk=None: build_query(g, syn, blk))(entry.get("syntax", {}))
        auth = entry.get("auth") or {}
        env = auth.get("env") if not auth.get("optional") else None
        out[name] = (fetch, qfn, env)
    return out


BACKENDS_CFG = load_backends()
BACKENDS = compile_backends(BACKENDS_CFG)
NOKEY = [b for b, (_, _, k) in BACKENDS.items() if k is None]
DEFAULT_EXCLUDE = {b for b, e in BACKENDS_CFG.items() if e.get("default_exclude")}

# Aliases kept for tests and importers of the old function names.
def _alias(name):
    return lambda q, want: BACKENDS[name][0](q, want)
bk_openalex = _alias("openalex")
bk_inspire = _alias("inspire")
bk_semanticscholar = _alias("semanticscholar")
bk_crossref = _alias("crossref")
bk_ads = _alias("ads")
bk_scopus = _alias("scopus")
bk_wos = _alias("wos")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def write_ris(recs, path: Path):
    with path.open("w", encoding="utf-8") as f:
        for r in recs:
            f.write("TY  - JOUR\n")
            for a in r["authors"]:
                f.write(f"AU  - {a}\n")
            f.write(f"TI  - {r['title']}\n")
            if r["year"]:
                f.write(f"PY  - {r['year']}\n")
            if r["journal"]:
                f.write(f"JO  - {r['journal']}\n")
            if r.get("block"):
                f.write(f"KW  - block:{r['block']}\n")
            if r["doi"]:
                f.write(f"DO  - {r['doi']}\n")
            if r["url"]:
                f.write(f"UR  - {r['url']}\n")
            if r["abstract"]:
                f.write(f"AB  - {r['abstract'][:6000]}\n")
            f.write("ER  - \n\n")


def _bib_key(r: dict, seen: set) -> str:
    """<lastname><year>, then a, b, ... z, then -27, -28 ... on collisions."""
    words = (r["authors"][0].split(",")[0].split() if r.get("authors") else [])
    first = re.sub(r"[^A-Za-z0-9]", "", words[-1]).lower() if words else ""
    base = (first or "anon") + (r.get("year") or "nd")
    key, n = base, 1
    while key in seen:
        n += 1
        key = f"{base}{chr(ord('a') + n - 2)}" if n <= 27 else f"{base}-{n}"
    seen.add(key)
    return key


_BIB_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
            "_": r"\_", "~": r"\textasciitilde{}", "^": r"\^{}"}


def _bib_esc(s) -> str:
    """LaTeX-special characters escaped; braces dropped (they would unbalance the field)."""
    return "".join(_BIB_ESC.get(ch, ch) for ch in str(s).replace("{", "").replace("}", ""))


def _is_preprint(r: dict) -> bool:
    return (r.get("journal") or "").lower().startswith("arxiv")


def write_bibtex(recs, path: Path):
    """BibTeX (@article; @misc when no venue). Keys: <lastname><year>[a,b,…]."""
    esc = _bib_esc
    seen = set()
    with path.open("w", encoding="utf-8") as f:
        for r in recs:
            kind = "article" if r["journal"] and not _is_preprint(r) else "misc"
            f.write(f"@{kind}{{{_bib_key(r, seen)},\n  title = {{{esc(r['title'])}}},\n")
            if r["authors"]:
                f.write("  author = {" + " and ".join(esc(a) for a in r["authors"]) + "},\n")
            if r["journal"]:
                f.write(f"  journal = {{{esc(r['journal'])}}},\n")
            if r["year"]:
                f.write(f"  year = {{{r['year']}}},\n")
            if r["doi"]:
                f.write(f"  doi = {{{r['doi']}}},\n")
            if r["url"]:
                f.write(f"  url = {{{r['url']}}},\n")
            if r.get("block"):
                f.write(f"  keywords = {{block:{r['block']}}},\n")
            f.write("}\n\n")


def write_csl(recs, path: Path):
    """CSL-JSON (what Zotero, pandoc and citeproc consume)."""
    items = []
    for i, r in enumerate(recs, 1):
        it = {"id": r["doi"] or f"rec{i}", "type": "article" if _is_preprint(r) else "article-journal",
              "title": r["title"]}
        au = []
        for a in r["authors"]:
            if "," in a:
                fam, giv = a.split(",", 1)
            else:
                parts = a.split()
                fam, giv = (parts[-1], " ".join(parts[:-1])) if parts else (a, "")
            au.append({"family": fam.strip(), "given": giv.strip()})
        if au:
            it["author"] = au
        if r["journal"]:
            it["container-title"] = r["journal"]
        if r["year"] and r["year"].isdigit():
            it["issued"] = {"date-parts": [[int(r["year"])]]}
        if r["doi"]:
            it["DOI"] = r["doi"]
        if r["url"]:
            it["URL"] = r["url"]
        if r.get("abstract"):
            it["abstract"] = r["abstract"]
        if r.get("block"):
            it["keyword"] = f"block:{r['block']}"
        items.append(it)
    path.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")


def write_csv(recs, path: Path):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["block", "backend", "year", "cited_by", "title", "journal", "doi", "url"])
        for r in recs:
            w.writerow([r.get("block", ""), r.get("backend", ""), r["year"], r["cited_by"],
                        r["title"], r["journal"], r["doi"], r["url"]])


def run_meta(stamp: str, args, backends: list, t_start: float, interrupted: bool) -> dict:
    """Everything report.py needs to describe the run that is not in the
    counts/records themselves."""
    cfg = {}
    for b in backends:
        e = BACKENDS_CFG.get(b, {})
        auth = e.get("auth") or {}
        cfg[b] = {"url": e.get("request", {}).get("url", "(driver: %s)" % e.get("driver", "?")),
                  "auth": auth.get("env", "none"),
                  "paging": e.get("request", {}).get("paging", {}).get("style", "-")}
    return {"version": VERSION, "stamp": stamp,
            "started": time.strftime("%Y-%m-%d %H:%M:%S", time.strptime(stamp, "%Y%m%dT%H%M%S")),
            "duration_s": round(time.time() - t_start, 1),
            "query_file": str(args.queries or "queries.json"),
            "blocks": list(args.blocks), "backends": list(backends),
            "counts_only": bool(args.counts_only), "limit": args.limit,
            "keep_junk": bool(args.keep_junk), "pdfs": bool(args.pdfs),
            "interrupted": interrupted, "backend_config": cfg, "outdir": str(OUTDIR),
            "environment": {"python": sys.version.split()[0],
                            "platform": f"{sys.platform}"}}


# ---------------------------------------------------------------------------

def main() -> int:
    global TIMEOUT, BLOCKS, BACKENDS_CFG, BACKENDS, NOKEY, DEFAULT_EXCLUDE, OUTDIR
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queries", default=None,
                    help="path to the query JSON (default: ./queries.json)")
    ap.add_argument("--backends-file", default=None,
                    help="path to a backends JSON (default: ./backends.json overlaid "
                         "on the embedded defaults)")
    ap.add_argument("--init-backends", action="store_true",
                    help="write the embedded backend definitions to backends.json "
                         "(next to .env / queries.json) for editing, then exit")
    ap.add_argument("--blocks", nargs="+", default=None)
    ap.add_argument("--backends", nargs="+", default=None,
                    help=f"default: every configured backend. choices: {list(BACKENDS)}")
    ap.add_argument("--skip", nargs="+", default=[],
                    help="backends to exclude (e.g. --skip arxiv when it is misbehaving)")
    ap.add_argument("--counts-only", action="store_true", help="skip record fetch")
    ap.add_argument("--limit", type=int, default=300, help="max records per block/backend")
    ap.add_argument("--list", action="store_true", help="show blocks and backend status, then exit")
    ap.add_argument("--selftest", action="store_true",
                    help="ping every backend with a trivial query; report what works")
    ap.add_argument("--timeout", type=int, default=TIMEOUT, help="per-request timeout, seconds")
    ap.add_argument("--pdfs", action="store_true",
                    help="after fetching, look up legal open-access PDFs via Unpaywall")
    ap.add_argument("--pdf-blocks", nargs="+", default=[],
                    help="restrict the Unpaywall pass to these blocks (default: all). "
                         "One HTTP call per DOI, so restrict it for big runs.")
    ap.add_argument("--keep-junk", action="store_true",
                    help="do not filter out non-scholarly venues (Zenodo, Figshare, SSRN...). "
                         "OpenAlex indexes these uncurated; they were 15%% of its records "
                         "on 2026-08-15 and are why its counts exceeded Scopus's.")
    ap.add_argument("--report-level", choices=("simple", "intermediate", "full"),
                    default="simple",
                    help="detail of the generated report (default: simple)")
    ap.add_argument("--report-format", nargs="+", default=["md"],
                    choices=("md", "html", "tex", "pdf", "txt"),
                    help="report formats to write (default: md). pdf uses LaTeX/pandoc "
                         "if installed, else a built-in plain-text writer")
    ap.add_argument("--report-lang", default=None, type=_report_lang, metavar="LANG",
                    help="report language: en, pt-BR, es, de, fr (default: project.json "
                         "defaults.lang, else en); logs and console stay English")
    ap.add_argument("--no-report", action="store_true", help="skip report generation")
    ap.add_argument("--version", action="version", version=f"scitech-librarian {VERSION}")
    try:
        import project as _project
        _project.add_common_args(ap, "research directory for lit/ output")
    except ImportError:
        _project = None
        ap.add_argument("--outdir", default=None, help="research directory (default ./lit)")
    args = ap.parse_args()

    TIMEOUT = args.timeout
    if args.outdir:
        OUTDIR = Path(args.outdir).resolve()
    if _project:
        _project.setup_logging("librarian", args, OUTDIR)

    if args.init_backends:
        out = ROOT / "backends.json"        # next to .env and queries.json (project root for a tools/ drop-in)
        if out.exists():
            print(f"{out} already exists -- not overwriting.", file=sys.stderr)
            return 2
        out.write_text(json.dumps(DEFAULT_BACKENDS, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"Wrote {out}. Edit it to add, change or disable databases; it is\n"
              f"overlaid on the embedded defaults at startup.")
        return 0

    if args.backends_file:
        BACKENDS_CFG = load_backends(args.backends_file)
        BACKENDS = compile_backends(BACKENDS_CFG)
        NOKEY = [b for b, (_, _, k) in BACKENDS.items() if k is None]
        DEFAULT_EXCLUDE = {b for b, e in BACKENDS_CFG.items() if e.get("default_exclude")}

    BLOCKS = load_blocks(args.queries)

    configured = [b for b, (_, _, k) in BACKENDS.items()
                  if (k is None or os.environ.get(k)) and b not in DEFAULT_EXCLUDE]

    if args.selftest:
        print("Pinging each backend with a trivial query "
              f"(timeout {TIMEOUT}s). This checks keys, entitlement and reachability.\n")
        probe = [["topological insulator"], ["Wilson term"]]
        ok, bad = [], []
        for b, (fn, qgen, keyname) in BACKENDS.items():
            if b in args.skip:
                continue
            if keyname and not os.environ.get(keyname):
                print(f"  {b:16s} SKIP     no {keyname} in .env")
                bad.append((b, f"no {keyname}"))
                continue
            print(f"  {b:16s} ...", end="", flush=True)
            t0 = time.time()
            try:
                total, _ = fn(qgen(probe), 0)
                print(f"\r  {b:16s} OK       {total:>8,} hits   ({time.time()-t0:.1f}s)")
                ok.append(b)
            except Exception as e:  # noqa: BLE001
                msg = str(e).replace("\n", " ")[:150]
                print(f"\r  {b:16s} FAIL     {msg}")
                bad.append((b, msg))
        if os.environ.get("OPENALEX_API_KEY"):
            try:
                rl = _json("https://api.openalex.org/rate-limit?api_key="
                           + os.environ["OPENALEX_API_KEY"])
                print(f"  {'openalex key':16s} OK       daily budget: "
                      f"{rl.get('dailyRemainingUsd', rl.get('remaining', '?'))} remaining "
                      f"(resets {rl.get('resetsAt', rl.get('reset', 'midnight UTC'))})")
            except Exception as e:  # noqa: BLE001
                print(f"  {'openalex key':16s} FAIL     {str(e)[:120]}")
        else:
            print(f"  {'openalex key':16s} none     keyless daily budget; set OPENALEX_API_KEY "
                  f"(free, 10x budget: https://openalex.org/settings/api)")
        if CONTACT:
            print(f"  {'unpaywall':16s} ...", end="", flush=True)
            try:
                r = unpaywall("10.1103/PhysRevLett.62.2747")
                print(f"\r  {'unpaywall':16s} OK       is_oa={r.get('is_oa')}")
                ok.append("unpaywall")
            except Exception as e:  # noqa: BLE001
                print(f"\r  {'unpaywall':16s} FAIL     {str(e)[:120]}")
        print(f"\nworking: {', '.join(ok) or 'none'}")
        if bad:
            print("not working:")
            for b, m in bad:
                print(f"  {b}: {m}")
        return 0 if ok else 1

    if args.list:
        print(f"BLOCKS  (from {args.queries or 'queries.json'}):")
        for n, b in BLOCKS.items():
            print(f"  {n:4s} {b['title']}")
        print("\nBACKENDS:")
        for b, (_, _, k) in BACKENDS.items():
            state = "ready" if (k is None or os.environ.get(k)) else f"MISSING {k} in .env"
            if b in DEFAULT_EXCLUDE:
                state += "  (excluded from default run: no boolean support)"
            print(f"  {b:16s} {state}")
        return 0

    args.blocks = args.blocks or list(BLOCKS)
    backends = [b for b in (args.backends or configured) if b not in args.skip]
    bad = [b for b in args.blocks if b not in BLOCKS] + [b for b in backends if b not in BACKENDS]
    if bad:
        print(f"unknown: {bad}", file=sys.stderr)
        return 2

    want = 0 if args.counts_only else args.limit
    stamp = time.strftime("%Y%m%dT%H%M%S")
    run = OUTDIR / "runs" / stamp
    (run / "records").mkdir(parents=True, exist_ok=True)
    (run / "ris").mkdir(exist_ok=True)
    log_lines, counts, queries, everything, junk_all = [], {}, {}, [], []
    t_start = time.time()

    _audit = logging.getLogger("librarian")

    def log(s=""):
        print(s, flush=True)          # flush: otherwise Windows buffers and it LOOKS hung
        log_lines.append(s)
        for h in _audit.handlers:      # audit file only; the console already has it
            if isinstance(h, logging.FileHandler):
                h.emit(logging.LogRecord("librarian", logging.INFO, "", 0, s, None, None))

    log(f"scitech-librarian run {stamp}")
    log(f"blocks:   {' '.join(args.blocks)}")
    log(f"backends: {' '.join(backends)}")
    log(f"mode:     {'counts only' if args.counts_only else f'full fetch (limit {args.limit})'}")

    interrupted = False
    try:
        for name in args.blocks:
            blk = BLOCKS[name]
            log(f"\n=== Block {name}: {blk['title']}")
            log(f"    ({blk['note']})")
            counts[name], queries[name] = {}, {}
            for bk in backends:
                fn, qgen, _ = BACKENDS[bk]
                q = qgen(blk["groups"], blk)
                queries[name][bk] = q
                # print BEFORE the call, so a hang shows you which backend hung
                print(f"    {bk:16s} querying...", end="\r", flush=True)
                t0 = time.time()
                try:
                    total, recs = fn(q, want)
                    counts[name][bk] = total
                    log(f"    {bk:16s} {total:>8,} hits"
                        + (f"   ({len(recs)} saved)" if recs else "")
                        + f"   [{time.time()-t0:.1f}s]")
                    if recs and not args.keep_junk:
                        dropped = [r for r in recs if is_junk(r)]
                        recs = [r for r in recs if not is_junk(r)]
                        if dropped:
                            for r in dropped:
                                r["block"], r["backend"] = name, bk
                            junk_all.extend(dropped)
                            log(f"    {'':16s} (filtered {len(dropped)} non-scholarly: "
                                f"{', '.join(sorted({d['journal'].split('(')[0].strip() for d in dropped}))[:60]})")
                    if recs:
                        for r in recs:
                            r["block"], r["backend"] = name, bk
                        (run / "records" / f"{name}_{bk}.json").write_text(
                            json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
                        write_ris(recs, run / "ris" / f"{name}_{bk}.ris")
                        everything.extend(recs)
                except KeyboardInterrupt:
                    raise
                except Exception as e:  # noqa: BLE001
                    counts[name][bk] = "ERR"
                    log(f"    {bk:16s} ERROR: {e}")
                # checkpoint after every single call -- a later hang loses nothing
                (run / "counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
                time.sleep(0.2)
    except KeyboardInterrupt:
        interrupted = True
        log("\n\n*** interrupted -- saving everything fetched so far ***")

    if args.pdfs and everything:
        # Unpaywall is one HTTP call per DOI, so 3000 DOIs is ~20 min. Restrict
        # by default to the blocks you actually need PDFs for, cache to disk
        # across runs, show progress with an ETA, and stay interruptible.
        targets = args.pdf_blocks or args.blocks
        pool = sorted({r["doi"] for r in everything if r["doi"] and r["block"] in targets})
        cfile = OUTDIR / "unpaywall_cache.json"
        have = json.loads(cfile.read_text(encoding="utf-8")) if cfile.exists() else {}
        todo = [d for d in pool if d not in have]
        log(f"\nUnpaywall: {len(pool)} DOIs in blocks {' '.join(targets)}"
            f" — {len(pool) - len(todo)} cached, {len(todo)} to fetch"
            f" (~{len(todo)*0.45/60:.1f} min). Ctrl-C is safe.")
        t0 = time.time()

        def progress(i, n):
            rate = (time.time() - t0) / i
            print(f"    {i}/{n}  eta {(n-i)*rate/60:.1f} min", end="\r", flush=True)

        cache = unpaywall_cached(pool, cfile, progress)
        for r in everything:
            if r["doi"] in cache:
                r.update(cache[r["doi"]])
        hit = [cache[d] for d in pool if d in cache]
        log(f"\n    open access: {sum(1 for v in hit if v.get('is_oa'))}/{len(hit)}")

    # ---- always persist ----
    (run / "counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
    (run / "queries.json").write_text(json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8")
    (run / "blocks.json").write_text(
        json.dumps({n: BLOCKS[n] for n in args.blocks if n in BLOCKS}, indent=2,
                   ensure_ascii=False), encoding="utf-8")
    if junk_all:
        (run / "junk.json").write_text(json.dumps(junk_all, indent=1, ensure_ascii=False),
                                       encoding="utf-8")

    done = [n for n in args.blocks if n in counts]
    hdr = "| Block | " + " | ".join(backends) + " | Title |"
    sep = "|---" * (len(backends) + 2) + "|"
    rows = [f"| {n} | " + " | ".join(str(counts[n].get(b, "-")) for b in backends)
            + f" | {BLOCKS[n]['title']} |" for n in done]
    table = "\n".join([hdr, sep, *rows])
    (run / "counts.md").write_text(table + "\n", encoding="utf-8")
    log("\n\n" + table)

    uniq = []
    if everything:
        if _project:                                  # one dedup rule for runs and projects
            started = time.strftime("%Y-%m-%d %H:%M:%S", time.strptime(stamp, "%Y%m%dT%H%M%S"))
            for r in everything:
                r.setdefault("member", stamp)
                r.setdefault("member_date", started)
            uniq = _project.merge(everything)
        else:
            seen = set()
            for r in sorted(everything, key=lambda x: -x["cited_by"]):
                k = r["doi"].lower() or r["title"].lower()[:90]
                if k and k not in seen:
                    seen.add(k)
                    uniq.append(r)
        write_csv(uniq, run / "all_records.csv")
        write_ris(uniq, run / "all_records.ris")
        write_bibtex(uniq, run / "all_records.bib")
        write_csl(uniq, run / "all_records.csl.json")
        (run / "all_records.json").write_text(
            json.dumps(uniq, indent=1, ensure_ascii=False), encoding="utf-8")
        log(f"\n{len(everything)} records fetched, {len(uniq)} unique after DOI/title dedup")

    hist = OUTDIR / "counts_history.csv"
    new = not hist.exists()
    with hist.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "block", "backend", "count"])
        for n in done:
            for b in backends:
                w.writerow([stamp, n, b, counts[n].get(b, "")])

    (run / "run.log").write_text("\n".join(log_lines), encoding="utf-8")
    (run / "meta.json").write_text(json.dumps(run_meta(
        stamp, args, backends, t_start, interrupted), indent=2), encoding="utf-8")
    if interrupted:
        print(f"\nPARTIAL RUN: {len(done)}/{len(args.blocks)} blocks completed.")
    if not args.no_report:
        try:
            import report
            report.write_reports(run, args.report_level, args.report_format,
                                 lang=args.report_lang)
        except ImportError:
            print("report.py not found next to librarian.py -- no report written")
        except Exception as e:  # noqa: BLE001
            print(f"report generation failed: {e}")
    print(f"\nAll output saved to: {run}")
    print(f"Counts history appended to: {hist}")
    print("\nNOTE: proximity operators are dropped in the generated queries, so counts")
    print("are NOT comparable across backends. Discovery here; WoS/Scopus in the paper.")
    if _project:
        _project.close_logging(logging.getLogger("librarian"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
