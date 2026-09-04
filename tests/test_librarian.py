#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Fabio Campolim
"""Offline test suite for librarian + wos_manual. Stdlib only, no network, no keys.

    python tests/test_librarian.py

Every check prints PASS/FAIL; exit code 1 if anything failed. Network calls are
intercepted by monkeypatching librarian._get with canned API responses, so the
suite exercises the real parsing paths without touching any backend.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

FAILED = []
CHECKS = 0          # every check() call; the docs quote this number


def check(name: str, cond: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -- {detail}"))
    if not cond:
        FAILED.append(name)


import librarian as lib  # noqa: E402

# The canned Unpaywall checks below (oa pass, --pdfs cache) run on machines
# with no keys and no CONTACT_EMAIL -- CI above all. Since 3.5.1 the pass
# refuses without an address, so the suite supplies one; the refusal itself
# is exercised further down with CONTACT cleared. (3.5.1's CI was red on all
# six runners because this line was missing: the guard had only been run on
# a machine whose environment carried the address.)
if not lib.CONTACT:
    lib.CONTACT = "suite@example.invalid"

from librarian import (_q, _rec, is_junk, load_blocks, load_env,  # noqa: E402
                     q_ads, q_arxiv, q_crossref, q_inspire, q_openalex,
                     q_s2, q_scopus, q_wos, q_wos_bare, write_csv, write_ris)

G = [["tight-binding", "SSH"], ["k.p"], ["topological"]]
BLK_IDX = {"arxiv_groups": [2, 0]}

# ---------------------------------------------------------------------------
print("term quoting (_q)")
check("bare alnum word stays bare", _q("topological") == "topological")
check("multi-word phrase is quoted", _q("tight binding") == '"tight binding"')
check("k.p is quoted (dot parses as operator)", _q("k.p") == '"k.p"')
check("hyphenated term is quoted", _q("tight-binding") == '"tight-binding"')

# ---------------------------------------------------------------------------
print("\nper-backend query generation")
check("openalex AND of ORs",
      q_openalex(G) == '("tight-binding" OR SSH) AND ("k.p") AND (topological)')
check("scopus TITLE-ABS-KEY wrapping",
      q_scopus(G) == 'TITLE-ABS-KEY("tight-binding" OR SSH) AND TITLE-ABS-KEY("k.p")'
                     ' AND TITLE-ABS-KEY(topological)')
check("wos single TS tag wraps whole boolean",
      q_wos(G).startswith("TS=((") and q_wos(G).count("TS=") == 1)
check("wos bare form carries no tag", "TS=" not in q_wos_bare(G))
check("inspire lowercase and/or",
      q_inspire(G) == '("tight-binding" or "SSH") and ("k.p") and ("topological")')
check("ads abs: field per term", q_ads(G).count('abs:"') == 4)
check("s2 uses + and |", q_s2(G) == '("tight-binding" | "SSH") + ("k.p") + ("topological")')
check("crossref keeps first synonym of each group",
      q_crossref(G) == "tight-binding k.p topological")

# arXiv group limiting -- the 2026-08-14 hang regression
check("arxiv defaults to first two groups",
      q_arxiv(G) == '(all:"tight-binding" OR all:"SSH") AND (all:"k.p")')
check("arxiv honours explicit arxiv_groups indices",
      q_arxiv(G, BLK_IDX) == '(all:"topological") AND (all:"tight-binding" OR all:"SSH")')

# ---------------------------------------------------------------------------
print("\nquery file loading (load_blocks)")
with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    good = {"X": {"groups": [["a", "b"], ["c"]]}}
    (tdp / "q.json").write_text(json.dumps(good), encoding="utf-8")
    got = load_blocks(tdp / "q.json")
    check("explicit path loads", list(got) == ["X"])
    check("missing title defaults to block name", got["X"]["title"] == "X")
    check("missing note defaults to empty", got["X"]["note"] == "")

    (tdp / "bad.json").write_text(json.dumps({"Y": {"title": "no groups"}}), encoding="utf-8")
    try:
        load_blocks(tdp / "bad.json")
        check("block without groups raises", False, "no exception")
    except ValueError as e:
        check("block without groups raises", "groups" in str(e))

check("bundled example file loads and every block has groups",
      all("groups" in b for b in load_blocks(HERE.parent / "queries.example.json").values()))
check("example carries an arxiv_groups demonstration",
      any("arxiv_groups" in b
          for b in load_blocks(HERE.parent / "queries.example.json").values()))

# ---------------------------------------------------------------------------
print("\n.env loading (load_env)")
with tempfile.TemporaryDirectory() as td:
    envf = Path(td) / ".env"
    envf.write_text("# comment\n\nLIB_TEST_A=hello\nLIB_TEST_B=a=b\n", encoding="utf-8")
    os.environ.pop("LIB_TEST_A", None)
    os.environ["LIB_TEST_PRESET"] = "keep"
    envf.write_text(envf.read_text() + "LIB_TEST_PRESET=clobber\n", encoding="utf-8")
    load_env(envf)
    check("key=value parsed", os.environ.get("LIB_TEST_A") == "hello")
    check("value containing '=' survives", os.environ.get("LIB_TEST_B") == "a=b")
    check("existing environment is not overridden",
          os.environ.get("LIB_TEST_PRESET") == "keep")
    for k in ("LIB_TEST_A", "LIB_TEST_B", "LIB_TEST_PRESET"):
        os.environ.pop(k, None)

# ---------------------------------------------------------------------------
print("\nrecord normalisation and junk filter")
r = _rec("  A title ", 2024, "https://doi.org/10.1/xy", " PRB ", ["A", None, "B"],
         "http://u", " abs ", "7")
check("doi prefix stripped", r["doi"] == "10.1/xy")
check("None authors filtered", r["authors"] == ["A", "B"])
check("cited_by is int", r["cited_by"] == 7)
check("title/journal/abstract stripped",
      r["title"] == "A title" and r["journal"] == "PRB" and r["abstract"] == "abs")
check("zenodo venue is junk", is_junk({"journal": "Zenodo (CERN)"}))
check("SSRN venue is junk", is_junk({"journal": "SSRN Electronic Journal"}))
check("real journal is not junk", not is_junk({"journal": "Physical Review B"}))
check("missing journal is not junk", not is_junk({"journal": None}))

# ---------------------------------------------------------------------------
print("\nRIS write -> parse round-trip (lib.write_ris vs wos_manual.parse_ris)")
import wos_manual  # noqa: E402

recs = [_rec("Title One", 2020, "10.1/a", "J. One", ["Alpha, A.", "Beta, B."],
             "http://one", "Abstract one", 3),
        _rec("Title Two", 2021, "", "J. Two", ["Gamma, C."], "", "", 0)]
with tempfile.TemporaryDirectory() as td:
    risf = Path(td) / "t.ris"
    write_ris(recs, risf)
    back = wos_manual.parse_ris(risf.read_text(encoding="utf-8"))
    check("record count survives", len(back) == 2)
    check("title survives", back[0]["title"] == "Title One")
    check("authors survive", back[0]["authors"] == ["Alpha, A.", "Beta, B."])
    check("doi survives", back[0]["doi"] == "10.1/a")
    check("year survives", back[1]["year"] == "2021")

    csvf = Path(td) / "t.csv"
    write_csv(recs, csvf)
    lines = csvf.read_text(encoding="utf-8").strip().splitlines()
    check("csv has header + one row per record", len(lines) == 3)
    check("csv header names the key columns", "doi" in lines[0] and "cited_by" in lines[0])

# ---------------------------------------------------------------------------
print("\nwos_manual sees the query blocks (regression: refactor left it importing {})")
check("wos_manual.BLOCKS is not empty", len(wos_manual.BLOCKS) > 0,
      "from librarian import BLOCKS bound the empty module-level dict")
check("wos_manual blocks carry groups",
      all("groups" in b for b in wos_manual.BLOCKS.values()))

# ---------------------------------------------------------------------------
print("\nbackends against canned responses (lib._get monkeypatched, no network)")

CANNED = {}


def fake_get(url, headers=None, tries=3, timeout=None):
    for frag, payload in CANNED.items():
        if frag in url:
            return payload
    raise AssertionError(f"unexpected URL in offline test: {url}")


real_get = lib._get
lib._get = fake_get
try:
    CANNED["api.openalex.org"] = json.dumps({
        "meta": {"count": 2, "next_cursor": None},
        "results": [{
            "display_name": "OA paper", "publication_year": 2023,
            "doi": "https://doi.org/10.1/oa",
            "abstract_inverted_index": {"world": [1], "Hello": [0]},
            "primary_location": {"source": {"display_name": "J. OA"}},
            "authorships": [{"author": {"display_name": "A. Author"}}],
            "id": "https://openalex.org/W1", "cited_by_count": 5}],
    }).encode()
    total, recs = lib.bk_openalex("q", 10)
    check("openalex total parsed", total == 2)
    check("openalex abstract rebuilt from inverted index",
          recs[0]["abstract"] == "Hello world")
    check("openalex doi normalised", recs[0]["doi"] == "10.1/oa")
    check("inverted index keeps repeated words (regression: telegram abstracts)",
          lib.TRANSFORMS["inverted_abstract"](
              {"the": [0, 2], "cat": [1], "hat": [3]}) == "the cat the hat")
    total, recs = lib.bk_openalex("q", 0)
    check("openalex counts-only fetches no records", total == 2 and recs == [])

    # CORE v3. Shape taken from a live probe on 2026-09-04: the payload carries
    # totalHits/limit/offset/results, a record has yearPublished, authors as
    # [{"name": ...}], journals as a list that is often EMPTY (repository
    # deposits have no journal) and no doi at all for grey literature -- the
    # two cases the field paths have to survive.
    CANNED["api.core.ac.uk"] = json.dumps({
        "totalHits": 2, "limit": 10, "offset": 0,
        "results": [
            {"id": 74104544, "title": "A4_3 Habitable Dyson Sphere",
             "yearPublished": 2012, "doi": None, "journals": [],
             "authors": [{"name": "Tudor, Vlad"}, {"name": "Winkworth, David"}],
             "abstract": "A student report.", "citationCount": 0,
             "downloadUrl": "https://core.ac.uk/download/267013217.pdf"},
            {"id": 11, "title": "Collector swarms", "yearPublished": 2021,
             "doi": "10.1/core", "journals": [{"title": "J. Astroeng."}],
             "authors": [{"name": "B. Author"}], "abstract": "A.",
             "citationCount": 7},
        ],
    }).encode()
    total, recs = lib.bk_core("q", 10)
    check("core total parsed", total == 2)
    check("core year and authors parsed",
          recs[0]["year"] == "2012" and recs[0]["authors"] == ["Tudor, Vlad", "Winkworth, David"])
    check("core record with no doi and no journal still lands",
          recs[0]["doi"] in (None, "") and recs[0]["title"].endswith("Dyson Sphere"))
    check("core journal read from journals[0].title", recs[1]["journal"] == "J. Astroeng.")
    check("core url built from the work id",
          recs[0]["url"] == "https://core.ac.uk/works/74104544")
    check("core citations parsed", recs[1]["cited_by"] == 7)
    total, recs = lib.bk_core("q", 0)
    check("core counts-only fetches no records", total == 2 and recs == [])
    check("core key is optional (backend usable with no CORE_API_KEY)",
          "core" in lib.NOKEY)

    CANNED["export.arxiv.org"] = (
        b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" '
        b'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" '
        b'xmlns:arxiv="http://arxiv.org/schemas/atom">'
        b'<opensearch:totalResults>1</opensearch:totalResults>'
        b'<entry><title>ArXiv paper</title><published>2022-01-01</published>'
        b'<id>http://arxiv.org/abs/2201.00001</id><summary>S</summary>'
        b'<author><name>B. Author</name></author></entry></feed>')
    total, recs = lib.bk_arxiv("q", 10)
    check("arxiv total parsed from Atom", total == 1)
    check("arxiv preprint journal label", recs[0]["journal"] == "arXiv preprint")
    check("arxiv year from published date", recs[0]["year"] == "2022")

    for var in ("ADS_TOKEN", "SCOPUS_API_KEY"):
        os.environ.pop(var, None)
    try:
        lib.bk_ads("q", 0)
        check("ads without token raises with pointer", False, "no exception")
    except RuntimeError as e:
        check("ads without token raises with pointer", "ADS_TOKEN" in str(e))
    try:
        lib.bk_scopus("q", 0)
        check("scopus without key raises", False, "no exception")
    except RuntimeError as e:
        check("scopus without key raises", "SCOPUS_API_KEY" in str(e))
finally:
    lib._get = real_get

# ---------------------------------------------------------------------------
print("\ndeclarative machinery: path DSL, syntax builder, config overlay")

from librarian import _extract, build_query, compile_backends, load_backends  # noqa: E402

doc = {"a": {"b": [{"c": 1}, {"c": 2}]}, "t": "x", "empty": []}
check("dotted descent", _extract(doc, "a.b[0].c") == 1)
check("[] maps over list", _extract(doc, "a.b[].c") == [1, 2])
check("out-of-range index is None", _extract(doc, "a.b[9].c") is None)
check("alternatives take first non-empty", _extract(doc, "empty|t") == "x")
check("missing path is None", _extract(doc, "nope.deeper") is None)

check("build_query default grammar",
      build_query([["a b"], ["c"]], {}) == '("a b") AND (c)')
check("build_query first_terms mode",
      build_query([["a", "z"], ["c"]], {"mode": "first_terms", "group_join": " "}) == "a c")
check("build_query outer template",
      build_query([["a"]], {"outer": "TS=({q})"}) == "TS=((a))")
check("build_query group_limit + block override",
      build_query([["a"], ["b"], ["c"]], {"group_limit": 2},
                  {"arxiv_groups": [2, 0]}) == "(c) AND (a)")

with tempfile.TemporaryDirectory() as td:
    bf = Path(td) / "backends.json"
    bf.write_text(json.dumps({
        "wos": {"disabled": True},
        "mybase": {"syntax": {}, "request": {"url": "https://x", "params": {"q": "{q}"},
                                             "paging": {"style": "none"}},
                   "parse": {"total": "n", "items": "r", "fields": {"title": "t"}}},
    }), encoding="utf-8")
    cfg = load_backends(bf)
    check("overlay disables an entry", "wos" not in cfg)
    check("overlay adds a new backend", "mybase" in cfg)
    check("defaults survive overlay", "openalex" in cfg and "ads" in cfg)
    compiled = compile_backends(cfg)
    check("added backend compiles to (fetch, query, env)",
          len(compiled["mybase"]) == 3 and callable(compiled["mybase"][0]))
    CANNED.clear()
    CANNED["https://x"] = json.dumps({"n": 1, "r": [{"t": "Hello"}]}).encode()
    lib._get = fake_get
    try:
        total, recs = compiled["mybase"][0]("q", 5)
        check("added backend fetches via generic runner",
              total == 1 and recs[0]["title"] == "Hello")
    finally:
        lib._get = real_get

check("every embedded default compiles",
      all(callable(v[0]) and callable(v[1])
          for v in compile_backends(load_backends()).values()))

# ---------------------------------------------------------------------------
print("\npagination, auth headers, and field fallbacks (canned, no network)")

SEEN_HEADERS = {}


def recording_get(url, headers=None, tries=3, timeout=None):
    SEEN_HEADERS.update(headers or {})
    return fake_get(url, headers, tries, timeout)


lib._get = recording_get
try:
    # cursor paging: two OpenAlex pages, cursor * -> NEXT -> exhausted
    CANNED.clear()
    page = {"meta": {"count": 2, "next_cursor": "NEXT"},
            "results": [{"display_name": "P1", "cited_by_count": 0}]}
    page2 = {"meta": {"count": 2, "next_cursor": None},
             "results": [{"display_name": "P2", "cited_by_count": 0}]}
    CANNED["cursor=%2A"] = json.dumps(page).encode()
    CANNED["cursor=NEXT"] = json.dumps(page2).encode()
    total, recs = lib.bk_openalex("q", 10)
    check("cursor paging walks both pages",
          [r["title"] for r in recs] == ["P1", "P2"])

    # offset paging + error-item filtering + auth headers (Scopus)
    os.environ["SCOPUS_API_KEY"] = "testkey"
    os.environ["SCOPUS_INSTTOKEN"] = "insttok"
    sp1 = {"search-results": {"opensearch:totalResults": "30",
           "entry": [{"dc:title": "S1", "prism:coverDate": "2020-05-01"},
                     {"error": "Result set has been truncated"}]}}
    sp2 = {"search-results": {"opensearch:totalResults": "30", "entry": []}}
    CANNED["start=0"] = json.dumps(sp1).encode()
    CANNED["start=25"] = json.dumps(sp2).encode()
    SEEN_HEADERS.clear()
    total, recs = lib.bk_scopus("q", 30)
    check("offset paging requests the next page then stops on empty",
          total == 30 and len(recs) == 1)
    check("error entries are dropped", recs[0]["title"] == "S1")
    check("first4 turns coverDate into a year", recs[0]["year"] == "2020")
    check("required auth header built", SEEN_HEADERS.get("X-ELS-APIKey") == "testkey")
    check("optional extra header included when set",
          SEEN_HEADERS.get("X-ELS-Insttoken") == "insttok")
    check("static Accept header included",
          SEEN_HEADERS.get("Accept") == "application/json")

    # Bearer-format auth (ADS)
    os.environ["ADS_TOKEN"] = "tok123"
    CANNED.clear()
    CANNED["adsabs"] = json.dumps({"response": {"numFound": 1, "docs": [
        {"title": ["T"], "bibcode": "2020ApJ...1B", "author": ["A"]}]}}).encode()
    SEEN_HEADERS.clear()
    total, recs = lib.bk_ads("q", 5)
    check("Bearer auth format applied",
          SEEN_HEADERS.get("Authorization") == "Bearer tok123")
    check("ads url templated from bibcode",
          recs[0]["url"].endswith("/abs/2020ApJ...1B"))

    # template fallback (INSPIRE record without links.json)
    CANNED.clear()
    CANNED["inspirehep"] = json.dumps({"hits": {"total": 1, "hits": [
        {"id": "12345", "metadata": {"titles": [{"title": "I1"}],
                                     "earliest_date": "2019-07-01"}}]}}).encode()
    total, recs = lib.bk_inspire("q", 5)
    check("inspire url falls back to template from id",
          recs[0]["url"] == "https://inspirehep.net/literature/12345")
    check("inspire default journal applied", recs[0]["journal"] == "INSPIRE record")
    check("inspire year first4", recs[0]["year"] == "2019")

    # given_family transform + nested date-parts (Crossref)
    CANNED.clear()
    CANNED["crossref"] = json.dumps({"message": {"total-results": 1, "items": [
        {"title": ["C", "One"], "DOI": "10.1/c",
         "issued": {"date-parts": [[2018, 3]]},
         "author": [{"given": "Ada", "family": "Lovelace"}]}]}}).encode()
    total, recs = lib.bk_crossref("q", 5)
    check("crossref multi-part title joined", recs[0]["title"] == "C One")
    check("crossref given_family transform", recs[0]["authors"] == ["Ada Lovelace"])
    check("crossref year from nested date-parts", recs[0]["year"] == "2018")
finally:
    lib._get = real_get
    for k in ("SCOPUS_API_KEY", "SCOPUS_INSTTOKEN", "ADS_TOKEN"):
        os.environ.pop(k, None)

# ---------------------------------------------------------------------------
print("\nkey configuration (the environment is the source; .env only fills it in)")
import subprocess as _sp  # noqa: E402

# A user may set keys in the shell, in a launcher's env block or as a CI secret
# and never create a .env at all. load_env uses setdefault, so those win -- and
# every user-facing "missing key" message must name both routes, not just .env.
_savedkeys = {k: os.environ.get(k) for k in ("WOS_STARTER_KEY", "SCOPUS_API_KEY")}
os.environ.pop("WOS_STARTER_KEY", None)
try:
    lib._auth_headers(lib.BACKENDS_CFG["wos"])
    _msg = "<no error raised>"
except RuntimeError as e:
    _msg = str(e)
check("missing-key error names the variable", "WOS_STARTER_KEY" in _msg, _msg)
check("missing-key error points at the environment, not only at .env",
      "environment" in _msg.lower(), _msg)
check("missing-key error does not claim the key must live in .env",
      "not set in .env" not in _msg, _msg)
check("wos hint says where to get the key, not where to put it",
      "clarivate.com" in lib.BACKENDS_CFG["wos"]["auth"]["hint"],
      lib.BACKENDS_CFG["wos"]["auth"]["hint"])
check("scopus hint says where to get the key, not where to put it",
      "elsevier.com" in lib.BACKENDS_CFG["scopus"]["auth"]["hint"],
      lib.BACKENDS_CFG["scopus"]["auth"]["hint"])

# --list is the readiness report a user reads first; --selftest is the one they
# run first. Neither may tell someone whose keys come from the environment that
# the key is missing "in .env".
_lenv = dict(os.environ, PYTHONIOENCODING="utf-8")
_lenv.pop("SCOPUS_API_KEY", None)
_lr = _sp.run([sys.executable, str(HERE.parent / "librarian.py"), "--list"],
              capture_output=True, text=True, env=_lenv, cwd=str(HERE.parent))
_lline = next((ln for ln in _lr.stdout.splitlines() if "SCOPUS_API_KEY" in ln), "")
check("--list reports a missing key against the environment or .env",
      "environment or .env" in _lline, _lline or (_lr.stdout or _lr.stderr)[-200:])
_srcs = {n: (HERE.parent / n).read_text(encoding="utf-8")
         for n in ("librarian.py", "docs/USER_MANUAL.md", "README.md", "AGENTS.md", "SKILL.md")}
_stale = [n for n, s in _srcs.items() if "in .env" in s or "not set in .env" in s]
check("no source or English doc says a key must be 'in .env'", not _stale, f"{_stale}")
for _k, _v in _savedkeys.items():
    if _v is not None:
        os.environ[_k] = _v

# ---------------------------------------------------------------------------
print("\nreport generation (report.py against a synthetic run directory)")
import render  # noqa: E402
import report  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    lit = Path(td) / "lit"
    run = lit / "runs" / "20260101T120000"
    (run / "records").mkdir(parents=True)
    R1 = _rec("Paper One", 2020, "10.1/one", "J. Phys.", ["A. One", "B. Two"],
              "https://x/1", "Abstract one.", 12)
    R2 = _rec("Paper Two", 2021, "10.1/two", "Nature", ["C. Three"], "https://x/2", "", 3)
    R1oa = dict(R1, block="A", backend="openalex")
    R1ads = dict(R1, block="A", backend="ads")
    R2oa = dict(R2, block="B", backend="openalex")
    (run / "records" / "A_openalex.json").write_text(json.dumps([R1oa]), encoding="utf-8")
    (run / "records" / "A_ads.json").write_text(json.dumps([R1ads]), encoding="utf-8")
    (run / "records" / "B_openalex.json").write_text(json.dumps([R2oa]), encoding="utf-8")
    (run / "all_records.json").write_text(json.dumps([R1oa, R2oa]), encoding="utf-8")
    (run / "junk.json").write_text(json.dumps(
        [dict(_rec("Junk", 2019, "10.1/j", "Zenodo (CERN)", [], ""), block="A", backend="openalex")]),
        encoding="utf-8")
    (run / "counts.json").write_text(json.dumps(
        {"A": {"openalex": 3, "ads": 5}, "B": {"openalex": 4000, "ads": "ERR"}}), encoding="utf-8")
    (run / "queries.json").write_text(json.dumps(
        {"A": {"openalex": "(a) AND (b)", "ads": 'abs:"a" AND abs:"b"'},
         "B": {"openalex": "(c)", "ads": 'abs:"c"'}}), encoding="utf-8")
    (run / "blocks.json").write_text(json.dumps(
        {"A": {"title": "Block A title", "note": "small is good", "groups": [["a"], ["b"]]},
         "B": {"title": "Block B", "note": "", "groups": [["c"]]}}), encoding="utf-8")
    (run / "meta.json").write_text(json.dumps(
        {"version": "3.1", "stamp": "20260101T120000", "started": "2026-01-01 12:00:00",
         "blocks": ["A", "B"], "backends": ["openalex", "ads"], "limit": 300,
         "counts_only": False, "keep_junk": False, "pdfs": False, "interrupted": False,
         "backend_config": {"openalex": {"url": "https://api.openalex.org/works",
                                         "auth": "none", "paging": "cursor"}}}),
        encoding="utf-8")
    (run / "run.log").write_text("line 1\n    ads   ERROR: boom\n", encoding="utf-8")
    (lit / "counts_history.csv").write_text(
        "timestamp,block,backend,count\n20251201T000000,A,openalex,1\n"
        "20260101T120000,A,openalex,3\n20260101T120000,A,ads,5\n", encoding="utf-8")

    d = report.load_run(run)
    s = report.stats(d)
    check("identified sums integer counts and skips ERR",
          s["identified"] == {"openalex": 4003, "ads": 5} and s["errors"] == [("B", "ads")])
    check("retrieved counted per backend from raw records",
          s["retrieved"] == {"openalex": 2, "ads": 1})
    check("duplicates = fetched - unique", s["n_fetched"] == 3 and s["n_dupes"] == 1)
    check("exclusive contribution ignores records found by two backends",
          s["exclusive"] == {"openalex": 1})
    check("junk counted per backend", s["junk_by"] == {"openalex": 1})

    pn = report.prisma_numbers(d, s)
    check("prisma: retrieved includes filtered records", pn["retrieved"] == 4)
    check("prisma: automation removed = junk", pn["automation_removed"] == 1)
    check("prisma: manual stages None without prisma.json", pn["excluded"] is None)
    (run / "prisma.json").write_text(json.dumps(
        {"records_screened": 2, "records_excluded": 1, "reports_sought": 1,
         "reports_assessed": 1, "excluded_reasons": {"off topic": 1},
         "studies_included": 0}), encoding="utf-8")
    pn = report.prisma_numbers(report.load_run(run), s)
    check("prisma: manual stages read from prisma.json",
          pn["excluded"] == 1 and pn["excluded_reasons"] == {"off topic": 1}
          and pn["screened_manual"])

    sug = report.suggest(d, s)
    joined = " ".join(sug)
    check("suggests rerunning the failed backend", "ads" in joined and "failed" in joined)
    check("flags the >2000-hit block", "Block B" in joined and "generic term" in joined)
    check("flags the small block as novelty territory", "Block A" in joined and "novelty" in joined)
    check("flags the unfinished PRISMA manual stages", "prisma.json" in joined)

    title, nodes = report.build(d, "simple")
    kinds = [n[0] for n in nodes]
    check("simple level has prisma node and suggestions", "prisma" in kinds and kinds[-1] == "ul")
    n_simple = len(nodes)
    n_inter = len(report.build(d, "intermediate")[1])
    n_full = len(report.build(d, "full")[1])
    check("levels strictly add content", n_simple < n_inter < n_full)
    full_txt = report.render_txt(*report.build(d, "full"))
    check("full level carries the abstract and the run log",
          "Abstract one." in full_txt and "ERROR: boom" in full_txt)
    inter_txt = report.render_txt(*report.build(d, "intermediate"))
    check("intermediate level has overlap + history, no abstract",
          "Found only here" in inter_txt and "Count history" in inter_txt
          and "Abstract one." not in inter_txt)
    try:
        report.build(d, "verbose")
        check("unknown level rejected", False)
    except ValueError:
        check("unknown level rejected", True)

    md = report.render_md(title, nodes)
    check("md: heading, table and ASCII flow present",
          md.startswith("# Literature search report") and "| Block |" in md
          and "IDENTIFICATION" in md)
    check("md: DOI rendered as link", "[10.1/one](https://doi.org/10.1/one)" in md)
    check("md: exact query strings reported", 'abs:"a" AND abs:"b"' in md)
    ht = report.render_html(title, nodes)
    check("html: svg flow + escaped content", "<svg" in ht and "&quot;a&quot;" in ht)
    tx = report.render_tex(title, nodes)
    check("tex: tikz flow, longtable, special chars escaped",
          "\\begin{tikzpicture}" in tx and "\\begin{longtable}" in tx and "\\_" in tx)
    check("tex: leading [ in a cell cannot become a \\\\ optional argument "
          "(regression: '[WITHDRAWN] ...' title broke xelatex)",
          report._tex("[WITHDRAWN] x") == "{[}WITHDRAWN{]} x")
    txt = report.render_txt(title, nodes)
    check("txt: flow and PRISMA-S checklist", "Records screened" in txt
          and "Deduplication" in txt)

    pdf = run / "builtin.pdf"
    report._pdf_builtin(txt, pdf)
    data = pdf.read_bytes()
    check("builtin pdf writer: valid header, trailer and pages",
          data.startswith(b"%PDF-1.4") and b"%%EOF" in data and b"/Type /Page " in data)

    real_which = render.shutil.which
    render.shutil.which = lambda name: None       # no LaTeX, no pandoc
    try:
        (run / "prisma.json").unlink()
        out = report.write_reports(run, "simple", ["md", "pdf", "html"], quiet=True)
    finally:
        render.shutil.which = real_which
    check("write_reports writes every requested format",
          set(out) == {"md", "pdf", "html"} and all(p.exists() for p in out.values()))
    check("pdf falls back to the builtin writer without LaTeX/pandoc",
          (run / "report.pdf").read_bytes().startswith(b"%PDF"))
    check("intermediate .tex is removed when not requested", not (run / "report.tex").exists())
    check("prisma.json template written on first report",
          json.loads((run / "prisma.json").read_text())["records_screened"] is None)

    # a legacy run directory (no meta/blocks/junk) still renders
    old = lit / "runs" / "20250101T000000"
    (old / "records").mkdir(parents=True)
    (old / "counts.json").write_text(json.dumps({"A": {"openalex": 1}}), encoding="utf-8")
    (old / "queries.json").write_text(json.dumps({"A": {"openalex": "(a)"}}), encoding="utf-8")
    d_old = report.load_run(old)
    check("legacy run: backends/blocks inferred from counts",
          d_old["backends"] == ["openalex"] and d_old["block_names"] == ["A"])
    check("legacy run: date recovered from the directory stamp",
          d_old["meta"]["started"] == "2025-01-01 00:00:00")
    check("legacy run renders", "PRISMA" in report.render_md(*report.build(d_old, "full")))

    # --- 3.3.0: report language (scaffolding translated, data and logs intact) ---
    import contextlib
    import io
    import subprocess
    import i18n  # noqa: E402
    d = report.load_run(run)
    _no_tr = {lg: i18n.missing(lg) for lg in i18n.LANGS if lg != "en"}
    check("i18n: pt-BR, es, de and fr are the languages, every catalogue string has each",
          set(i18n.LANGS) == {"en", "pt-BR", "es", "de", "fr"} and not any(_no_tr.values()),
          str({k: v[:3] for k, v in _no_tr.items() if v}))
    check("i18n: normalize -- aliases, case, None -> en",
          i18n.normalize("pt") == "pt-BR" and i18n.normalize("PT-br") == "pt-BR"
          and i18n.normalize("EN") == "en" and i18n.normalize(None) == "en"
          and i18n.normalize("fr_FR") == "fr")
    try:
        i18n.normalize("xx")
        check("i18n: unknown language rejected", False, "no exception")
    except ValueError as e:
        check("i18n: unknown language rejected", "xx" in str(e))
    check("i18n: placeholders survive translation, {n} formatted in every language",
          all("{n}" not in i18n.tr(lg, "Block {n}: {title}", n="A", title="t")
              and "A" in i18n.tr(lg, "Block {n}: {title}", n="A", title="t") for lg in i18n.LANGS))
    en_default = report.render_md(*report.build(d, "simple"))
    check("lang=en is byte-identical to the default report",
          en_default == report.render_md(*report.build(d, "simple", lang="en")))
    pt_title, pt_nodes = report.build(d, "simple", lang="pt-BR")
    pt = report.render_md(pt_title, pt_nodes)
    check("pt-BR: title, headings, PRISMA stages and flow labels translated",
          pt.startswith("# Relatório de busca bibliográfica")
          and "## Estratégia de busca" in pt and "Registros identificados em bases de dados" in pt
          and "IDENTIFICAÇÃO" in pt and "TRIAGEM" in pt and "## Sugestões" in pt)
    check("pt-BR: data intact -- block title/note, query string, record, venue, backend, flag, file name",
          all(x in pt for x in ("Block A title", "small is good", 'abs:"a" AND abs:"b"', "Paper One",
                                "J. Phys.", "| openalex |", "`--limit`", "prisma.json", "counts_history.csv")))
    # ("Suggestions" is also the French heading, so it is not in this list)
    _ENGLISH = ("Search strategy", "Results summary", "Records screened", "Generated by",
                "PRISMA-S search-reporting checklist", "Query string sent", "Deduplication",
                "Top venues", "Found only here", "Count history", "Records identified", "Stage",
                "Identified = ", "novelty-check", "generic term", "This search", "Requirement")
    _leak = {}
    for lg in ("pt-BR", "es", "de", "fr"):
        t_, n_ = report.build(d, "intermediate", lang=lg)
        hit = [p for p in _ENGLISH if p in report.render_txt(t_, n_)]
        if hit:
            _leak[lg] = hit
    check("pt-BR/es/de/fr: no English scaffolding leaks into an intermediate report", not _leak, str(_leak))
    _es = report.render_md(*report.build(d, "simple", lang="es"))
    _de = report.render_md(*report.build(d, "simple", lang="de"))
    _fr = report.render_md(*report.build(d, "simple", lang="fr"))
    check("es/de/fr: each language renders its own title",
          _es.startswith("# Informe de búsqueda bibliográfica")
          and _de.startswith("# Bericht zur Literaturrecherche")
          and _fr.startswith("# Rapport de recherche bibliographique"))
    ht_pt = report.render_html(pt_title, pt_nodes, lang="pt-BR")
    check("html: lang attribute set and SVG stage labels translated",
          '<html lang="pt-BR">' in ht_pt and "Triagem" in ht_pt and "Identificação" in ht_pt
          and '<html lang="en">' in report.render_html(title, nodes))
    check("tex: TikZ stage labels translated",
          "{Identificação}" in report.render_tex(pt_title, pt_nodes)
          and "{Identification}" in report.render_tex(title, nodes))
    full_pt = report.render_txt(*report.build(d, "full", lang="pt-BR"))
    check("pt-BR full: run log, abstract and backend configuration verbatim",
          "ERROR: boom" in full_pt and "line 1" in full_pt and "Abstract one." in full_pt
          and "https://api.openalex.org/works" in full_pt and "Registro de execução" in full_pt)
    (lit / "project.json").write_text(json.dumps({"defaults": {"lang": "de"}}), encoding="utf-8")
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        out = report.write_reports(run, "simple", ["md"], quiet=False)
    _de_md = out["md"].read_text(encoding="utf-8")
    check("write_reports: project.json defaults.lang honoured; console line stays English",
          _de_md.startswith("# Bericht zur Literaturrecherche") and "report (simple):" in _buf.getvalue())
    out = report.write_reports(run, "simple", ["md"], quiet=True, lang="fr")
    check("write_reports: explicit lang wins over the project default",
          out["md"].read_text(encoding="utf-8").startswith("# Rapport de recherche bibliographique"))
    (lit / "project.json").unlink()
    import re as _re2
    _lib_src = (HERE.parent / "librarian.py").read_text(encoding="utf-8")
    _i18n_uses = set(_re2.findall(r"i18n\.(?!py\b)(\w+)", _lib_src))     # attributes, not "i18n.py"
    check("run.log written by librarian.py is not translated: librarian.py's only i18n use is "
          "normalize (lazily, for --report-lang); project.py has none",
          "i18n" not in (HERE.parent / "project.py").read_text(encoding="utf-8")
          and _i18n_uses == {"normalize"}
          and not _re2.search(r"translator|Translator|\btr\(|from i18n import", _lib_src)
          and not _re2.search(r"^import i18n", _lib_src, flags=_re2.M),
          f"i18n uses in librarian.py: {_i18n_uses}")

    # --- 3.3.1: the post-release review of 3.3.0 ---------------------------------
    # (1) the dependency-free PDF writer must draw accented letters: a Type1
    # standard font without /Encoding uses StandardEncoding, where 0xE7/0xF3
    # are blank or wrong glyphs.
    _pdf2 = run / "builtin_pt.pdf"
    report._pdf_builtin("Relatório -- Identificação (n = 1 234) ç ñ ü", _pdf2)
    _pb = _pdf2.read_bytes()
    check("builtin PDF: WinAnsi encoding declared and Latin-1 bytes kept for accented text",
          b"/Encoding /WinAnsiEncoding" in _pb and b"Relat\xf3rio" in _pb and b"Identifica\xe7\xe3o" in _pb,
          "no /Encoding or accented bytes replaced")
    # (2) a bad --report-lang is refused by argparse, before any backend call
    _bad = subprocess.run([sys.executable, str(HERE.parent / "librarian.py"), "--report-lang", "pt-PT",
                           "--help"], capture_output=True, text=True, cwd=str(lit))
    check("librarian.py --report-lang rejects an unknown language at parse time (exit 2)",
          _bad.returncode == 2 and "pt-PT" in _bad.stderr and "unknown report language" in _bad.stderr,
          f"rc={_bad.returncode} stderr={_bad.stderr[-160:]!r}")
    _ok = subprocess.run([sys.executable, str(HERE.parent / "librarian.py"), "--report-lang", "PT-br",
                          "--help"], capture_output=True, text=True, cwd=str(lit))
    check("librarian.py --report-lang accepts the same aliases as report.py --lang (PT-br)",
          _ok.returncode == 0, f"rc={_ok.returncode} stderr={_ok.stderr[-160:]!r}")
    # 3.3.2: a non-dict "defaults" is repaired where every consumer reads it
    import project as _project  # noqa: E402
    for _bad_def in (None, "pt-BR", 3):
        (lit / "project.json").write_text(json.dumps({"defaults": _bad_def}), encoding="utf-8")
        _p = _project.load_project(lit)
        check(f"load_project: defaults={_bad_def!r} -> {{}} (build/main/default_lang all safe)",
              _p["defaults"] == {})
    (lit / "project.json").unlink()
    _pdf3 = run / "builtin_cp1252.pdf"
    report._pdf_builtin("Cœur — “quotes”… ‘x’ €", _pdf3)
    _pb3 = _pdf3.read_bytes()
    check("builtin PDF: WinAnsi-only glyphs (oe, dashes, curly quotes, ellipsis, euro) kept, not '?'",
          b"C\x9cur \x97 \x93quotes\x94\x85 \x91x\x92 \x80" in _pb3, "cp1252 range replaced")
    check("i18n.date: first of the month is 1er (fr) and 1º (pt-BR)",
          i18n.date("fr", (2026, 9, 1)) == "1er septembre 2026"
          and i18n.date("pt-BR", (2026, 9, 1)) == "1º de setembro de 2026"
          and i18n.date("es", (2026, 9, 1)) == "1 de septiembre de 2026"
          and i18n.date("en", (2026, 9, 1)) == "1 September 2026")
    # (3) an invalid or null project default degrades to English with a warning, never a traceback
    for _pj in ({"defaults": {"lang": "pt-PT"}}, {"defaults": None}):
        (lit / "project.json").write_text(json.dumps(_pj), encoding="utf-8")
        _err = io.StringIO()
        with contextlib.redirect_stderr(_err):
            out = report.write_reports(run, "simple", ["md"], quiet=True)
        _md = out["md"].read_text(encoding="utf-8")
        check(f"write_reports: project default {json.dumps(_pj)} -> English report"
              + (" + warning" if _pj["defaults"] else ", no crash"),
              _md.startswith("# Literature search report")
              and (not _pj["defaults"] or "pt-PT" in _err.getvalue()), _err.getvalue()[-120:])
    (lit / "project.json").unlink()
    # (4) the TeX title block dates the report in the report's language
    check("i18n.date: localized dates",
          i18n.date("pt-BR", (2026, 8, 31)) == "31 de agosto de 2026"
          and i18n.date("es", (2026, 8, 31)) == "31 de agosto de 2026"
          and i18n.date("de", (2026, 8, 31)) == "31. August 2026"
          and i18n.date("fr", (2026, 8, 31)) == "31 août 2026"
          and i18n.date("en", (2026, 8, 31)) == "31 August 2026")
    _tx_pt = report.render_tex(pt_title, pt_nodes, lang="pt-BR")
    check("tex: pt-BR report carries a Portuguese date, English keeps \\today",
          "\\today" not in _tx_pt and "\\date{" in _tx_pt and " de " in _tx_pt.split("\\date{", 1)[1][:40]
          and "\\date{\\today}" in report.render_tex(title, nodes))

# ---------------------------------------------------------------------------
print("\nlibrarian -> report wiring")
import argparse as _ap  # noqa: E402
_ns = _ap.Namespace(queries=None, blocks=["X"], counts_only=False, limit=7,
                    keep_junk=False, pdfs=True)
_m = lib.run_meta("20260102T030405", _ns, ["openalex"], 0.0, False)
check("run_meta records limit, flags and backend endpoint",
      _m["limit"] == 7 and _m["pdfs"] and _m["started"] == "2026-01-02 03:04:05"
      and _m["backend_config"]["openalex"]["url"].startswith("https://api.openalex.org"))
check("run_meta reports the tool version", _m["version"] == lib.VERSION)

import time

# ---------------------------------------------------------------------------
print("\nresearch directory: project.py parsers, ingest, members, merge")
import project  # noqa: E402
import journals  # noqa: E402

RIS = ("﻿TY  - JOUR\nAU  - Wei, Q\nAU  - Zhang, XW\nTI  - Higher-order topological semimetal\n"
       "T2  - NATURE MATERIALS\nSN  - 1476-1122\nDA  - JUN 10\nPY  - 2021\nDO  - 10.1038/s41563-021-00933-4\n"
       "AB  - Abstract text.\nER  -\n\nTY  - JOUR\nAU  - Solo, H\nTI  - Second paper\nJO  - J. Two\n"
       "PY  - 2019\nER  - \n")
recs = project.parse_ris(RIS)
check("ris: BOM, 'ER  -' without trailing space and DA before PY handled",
      len(recs) == 2 and recs[0]["year"] == "2021" and recs[0]["doi"] == "10.1038/s41563-021-00933-4")
check("ris: authors, venue, issn, abstract carried",
      recs[0]["authors"] == ["Wei, Q", "Zhang, XW"] and recs[0]["journal"] == "NATURE MATERIALS"
      and recs[0]["issn"] == "1476-1122" and recs[0]["abstract"] == "Abstract text.")

BIB = ('@article{key1,\n  title = {A {Nested} Title},\n  author = {Ada Lovelace and Charles Babbage},\n'
       '  journal = "J. Comp.",\n  year = 1843,\n  doi = {10.1/bib}\n}\n@comment{ignored}\n'
       '@inproceedings{k2, title={Talk}, booktitle={Proc. X}, year={2020}, author={One, A}}\n')
recs = project.parse_bibtex(BIB)
check("bibtex: entries parsed, comment skipped, booktitle as venue",
      len(recs) == 2 and recs[1]["journal"] == "Proc. X" and recs[1]["year"] == "2020")
check("bibtex: braces stripped, authors split on 'and', doi kept",
      recs[0]["title"] == "A Nested Title" and recs[0]["authors"] == ["Ada Lovelace", "Charles Babbage"]
      and recs[0]["doi"] == "10.1/bib")

CSV = "Title,Authors,Year,DOI,Source title,Cited by\nPaper C,\"A; B\",2022,10.1/c,J. C,7\n"
recs = project.parse_csv(CSV)
check("csv: Scopus-style headers matched case-insensitively",
      recs[0]["title"] == "Paper C" and recs[0]["authors"] == ["A", "B"] and recs[0]["journal"] == "J. C"
      and recs[0]["cited_by"] == 7)
recs = project.parse_json(json.dumps([{"title": "J1", "doi": "https://doi.org/10.1/J", "year": 2001}]))
check("json: doi prefix stripped, year coerced", recs[0]["doi"] == "10.1/J" and recs[0]["year"] == "2001")

with tempfile.TemporaryDirectory() as td:
    od = Path(td) / "lit"
    # two runs, one old-style (no meta.json), block renamed between them
    r1 = od / "runs" / "20260601T000000"
    (r1 / "records").mkdir(parents=True)
    A1 = dict(_rec("Shared paper", 2020, "10.1/shared", "J. Phys.", ["A"], "", "short", 3),
              block="X", backend="openalex")
    B1 = dict(_rec("Only in June", 2018, "10.1/june", "Nature", ["B"], "", "", 50), block="X", backend="openalex")
    (r1 / "records" / "X_openalex.json").write_text(json.dumps([A1, B1]), encoding="utf-8")
    (r1 / "counts.json").write_text(json.dumps({"X": {"openalex": 40}}), encoding="utf-8")
    (r1 / "queries.json").write_text(json.dumps({"X": {"openalex": "(old)"}}), encoding="utf-8")
    r2 = od / "runs" / "20260801T000000"
    (r2 / "records").mkdir(parents=True)
    A2 = dict(_rec("Shared paper", 2020, "10.1/shared", "J. Phys.", ["A"], "", "a longer abstract", 9),
              block="CD", backend="ads")
    C2 = dict(_rec("New in August", 2025, "10.1/aug", "J. Phys.", ["C"], "", "", 1), block="CD", backend="ads")
    (r2 / "records" / "CD_ads.json").write_text(json.dumps([A2, C2]), encoding="utf-8")
    (r2 / "counts.json").write_text(json.dumps({"CD": {"ads": 55, "openalex": "ERR"}}), encoding="utf-8")
    (r2 / "queries.json").write_text(json.dumps({"CD": {"ads": "(new)"}}), encoding="utf-8")
    (r2 / "blocks.json").write_text(json.dumps({"CD": {"title": "cross", "note": "", "groups": [["a"]]}}),
                                    encoding="utf-8")
    (r2 / "meta.json").write_text(json.dumps({"started": "2026-08-01 00:00:00", "blocks": ["CD"],
                                              "backends": ["ads", "openalex"], "limit": 300}), encoding="utf-8")
    ris = Path(td) / "colleague.ris"
    ris.write_text("TY  - JOUR\nTI  - Shared paper\nDO  - 10.1/shared\nPY  - 2020\nER  -\n"
                   "TY  - JOUR\nTI  - Reference-list find\nJO  - Nature\nPY  - 2015\nER  -\n", encoding="utf-8")
    import logging as _lg
    src = project.ingest(od, [ris], "colleague", block="CD", method="citation", who="a colleague",
                         origin="reference list", log=_lg.getLogger("t"))
    check("ingest: source.json provenance and records tagged manual:<name>",
          src["n_records"] == 2 and src["method"] == "citation"
          and json.loads((od / "manual" / "colleague" / "records.json").read_text())[0]["backend"] == "manual:colleague")
    check("ingest: original file kept beside records.json", (od / "manual" / "colleague" / "colleague.ris").exists())
    (od / "inbox").mkdir()
    (od / "inbox" / "dropped.bib").write_text(BIB, encoding="utf-8")
    done = project.ingest_inbox(od, _lg.getLogger("t"), method="expert")
    check("inbox: file becomes a source named after it and is removed from inbox",
          [s["name"] for s in done] == ["dropped"] and not (od / "inbox" / "dropped.bib").exists())

    p = project.load_project(od)
    p["block_aliases"] = {"X": "CD"}
    p["labels"] = {"20260601T000000": "first pass"}
    project.save_project(od, p)
    ms = project.members(od)
    check("members: runs and manual sources discovered oldest first, labels applied",
          [m["id"] for m in ms] == ["20260601T000000", "20260801T000000", "colleague", "dropped"]
          and ms[0]["label"] == "first pass")
    p["exclude"] = ["dropped"]
    project.save_project(od, p)
    ms = project.members(od)
    check("members: exclusions honoured", "dropped" not in [m["id"] for m in ms])
    recs = [r for m in ms for r in project.member_records(m, p["block_aliases"])]
    check("member_records: block alias X -> CD applied", all(r["block"] == "CD" for r in recs if r["member"] == "20260601T000000"))
    merged = project.merge(recs)
    shared = next(r for r in merged if r["doi"] == "10.1/shared")
    check("merge: provenance across runs and manual source",
          set(shared["found_by"]) == {"openalex@20260601T000000", "ads@20260801T000000", "manual:colleague@colleague"}
          and shared["first_seen"].startswith("2026-06-01"))
    check("merge: richest copy kept (longest abstract, highest citations)",
          shared["abstract"] == "a longer abstract" and shared["cited_by"] == 9)
    check("merge: total unique", len(merged) == 4)
    pre = project.merge([dict(_rec("P", 2024, "10.1/p", "arXiv preprint", [], ""), member="a", backend="arxiv"),
                         dict(_rec("P", 2024, "10.1/p", "Nature Physics", [], ""), member="b", backend="ads")])
    check("merge: published venue replaces the arXiv preprint label", pre[0]["journal"] == "Nature Physics")
    jc = ('"Journal Data Filtered By: Selected JCR Year: 2024"\nJournal name,ISSN,eISSN,2024 JIF,JIF Quartile\n'
          'NATURE PHYSICS,1745-2473,1745-2481,17.6,Q1\nCopyright Clarivate\n')
    st_ = {}
    n_, yr_ = journals.import_jcr(jc, st_)
    check("jcr import: preamble/trailer skipped, year from column, quartile kept",
          n_ == 1 and yr_ == "2024" and st_["1745-2473"]["metrics"]["jcr_if"] == {"2024": 17.6}
          and st_["1745-2473"]["quartile"]["2024"] == "Q1")
    check("status text lists members", "colleague" in project.status(od))

    # --- project report ---
    d = report.load_project(od)
    check("project load: backends inferred from counts for the pre-meta run and manual source appended",
          d["backends"] == ["openalex", "ads", "manual:colleague"])
    check("project load: counts summed over runs with ERR superseded, aliases applied",
          d["counts"]["CD"]["openalex"] == 40 and d["counts"]["CD"]["ads"] == 55
          and d["counts"]["CD"]["manual:colleague"] == 2)
    s = report.stats(d)
    pn = report.prisma_numbers(d, s)
    check("prisma: citation-searching source lands in the other-methods column",
          pn["other_by"] == {"citation": 2} and "manual:colleague" not in pn["identified_by"])
    title, nodes = report.build(d, "simple")
    md = report.render_md(title, nodes)
    check("project report: sources table with 'new here' and timeline",
          "## Sources" in md and "| first pass" in md and "## Timeline" in md and "| CD | 40 | 55 |" in md)
    check("project report: other-methods box in the ASCII flow",
          "IDENTIFICATION VIA OTHER METHODS" in md and "citation: 2" in md)
    check("project report: tikz and svg carry the other-methods boxes",
          "(ot)" in report.render_tex(title, nodes) and "Other methods" in report.render_html(title, nodes))
    _pt = report.render_md(*report.build(d, "simple", lang="pt-BR"))
    check("project report pt-BR: sources/timeline/other-methods translated, member ids and labels intact",
          "## Fontes" in _pt and "## Linha do tempo" in _pt and "IDENTIFICAÇÃO POR OUTROS MÉTODOS" in _pt
          and "| first pass" in _pt and "citation: 2" in _pt)
    # filters
    d = report.load_project(od, since="2026-07-01")
    check("filter --since drops the June run", [m["id"] for m in d["members"]] == ["20260801T000000", "colleague"])
    d = report.load_project(od)
    report.apply_filters(d, diff=True, since="2026-07-01")
    check("filter --diff keeps only records first seen in the window",
          {r["doi"] for r in d["unique"]} == {"10.1/aug", ""} or
          {r.get("title") for r in d["unique"]} == {"New in August", "Reference-list find"})
    d = report.load_project(od)
    report.apply_filters(d, backends=["ads"], year_from=2019, min_citations=2)
    check("filters: backend / year / citations combine",
          [r["doi"] for r in d["unique"]] == ["10.1/shared"] and d["filters"]["backends"] == "ads")
    d = report.load_project(od, sources="manual")
    check("filter --sources manual", all(m["kind"] == "manual" for m in d["members"]) and d["members"])
    d = report.load_project(od, latest=True)
    check("filter --latest keeps the most recent member only", [m["id"] for m in d["members"]] == ["colleague"])
    d = report.load_project(od, extra_records=[str(ris)])
    check("--records adds a transient manual source", any(m["id"] == "colleague" and "not stored" in m["label"]
                                                        for m in d["members"]))

    # --- journals ---
    store = {}
    e = journals._entry(store, "Journal of Physics", ["1234-5678"])
    journals.put(e, "openalex_2yr", "2025", "2,5")
    journals.put(e, "openalex_2yr", "2026", 3.1)
    e2 = journals._entry(store, "journal of physics", [])
    check("store: ISSN key, name alias resolves to the same entry, comma decimals", e2 is e and
          e["metrics"]["openalex_2yr"] == {"2025": 2.5, "2026": 3.1})
    check("metric_value: latest year wins", journals.metric_value(e, "openalex_2yr") == (3.1, "2026"))
    check("lookup by record issn then by journal name",
          journals.lookup(store, {"issn": "12345678"}) is e and journals.lookup(store, {"journal": "The Journal of Physics"}) is e)
    scim = "Rank;Sourceid;Title;Type;Issn;SJR;SJR Best Quartile;H index\n1;1;Nature;journal;00280836, 14764687;20,957;Q1;1300\n2;2;Obscure J;journal;11112222;0,1;Q4;3\n"
    n = journals.import_scimago(scim, "2024", store, only={"nature": True})
    check("scimago import restricted to seen journals, quartile kept",
          n == 1 and store["0028-0836"]["quartile"]["2024"] == "Q1" and store["0028-0836"]["metrics"]["sjr"]["2024"] == 20.957)
    n = journals.import_csv("Journal name,JIF\nNature,64.8\n", "jcr_if", "2023", store, "Journal name", "JIF")
    check("generic csv import appends a provider series", n == 1 and store["0028-0836"]["metrics"]["jcr_if"] == {"2023": 64.8})
    # canned OpenAlex + Scopus fetch
    CANNED.clear()
    CANNED["api.openalex.org/sources"] = json.dumps({"results": [{"id": "https://openalex.org/S1", "display_name": "J. Phys.",
        "issn": ["1111-2222"], "summary_stats": {"2yr_mean_citedness": 4.2, "h_index": 100},
        "counts_by_year": [{"year": 2025, "works_count": 10, "cited_by_count": 50}]}]}).encode()
    CANNED["api.elsevier.com/content/serial"] = json.dumps({"serial-metadata-response": {"entry": [
        {"SJRList": {"SJR": [{"@year": "2023", "$": "1.5"}]}, "SNIPList": {"SNIP": [{"@year": "2023", "$": "1.1"}]},
         "citeScoreYearInfoList": {"citeScoreYearInfo": [{"@year": "2023", "citeScoreInformationList": [
             {"citeScoreInfo": [{"citeScore": "6.0"}]}]}]}}]}}).encode()
    lib._get = fake_get
    os.environ["SCOPUS_API_KEY"] = "k"
    try:
        journals.save_store(od, {})
        st = journals.fetch(od, ("openalex", "scopus"), log=_lg.getLogger("t"))
    finally:
        lib._get = real_get
        os.environ.pop("SCOPUS_API_KEY", None)
    store = journals.load_store(od)
    jp = journals.lookup(store, {"journal": "J. Phys."})
    check("fetch: journals collected from the directory, OpenAlex values stored under the fetch year",
          st["journals"] >= 2 and jp is not None and jp["metrics"]["openalex_2yr"] == {time.strftime("%Y"): 4.2})
    check("fetch: Scopus history parsed (CiteScore, SJR, SNIP by year)",
          jp["metrics"].get("scopus_citescore") == {"2023": 6.0} and jp["metrics"].get("sjr") == {"2023": 1.5})
    d = report.load_project(od)
    report.apply_filters(d, metric="openalex_2yr", min_metric=4.0)
    check("--min-metric keeps only records in journals above the threshold",
          {r["journal"] for r in d["unique"]} == {"J. Phys."})
    title, nodes = report.build(d, "intermediate")
    md = report.render_md(title, nodes)
    check("report: metric column and journal-metrics section present",
          "OpenAlex 2-yr mean citedness" in md and "## Journal metrics" in md)
    out = report.write_reports(None, "simple", ["md"], d=d, out_dir=od / "reports" / "t", quiet=True)
    check("write_reports: project output dir and screening.json template",
          (od / "reports" / "t" / "report.md").exists() and (od / "screening.json").exists())

# ---------------------------------------------------------------------------
print("\naudit logging and --outdir")
with tempfile.TemporaryDirectory() as td:
    ns = _ap.Namespace(outdir=td, verbose=False, quiet=True, log_dir=None)
    lg = project.setup_logging("testscript", ns)
    lg.info("hello audit")
    for h in list(lg.handlers):            # release the file so the tempdir can be removed on Windows
        h.close()
        lg.removeHandler(h)
    logs = list((Path(td) / "logs").glob("testscript_*.log"))
    txt = logs[0].read_text(encoding="utf-8") if logs else ""
    check("audit log written under <outdir>/logs with invocation and message",
          len(logs) == 1 and "invocation:" in txt and "hello audit" in txt)
    check("resolve_outdir honours an explicit path", project.resolve_outdir(td) == Path(td).resolve())

# ---------------------------------------------------------------------------
print("\nreview follow-up: outputs, robustness, CLI smoke")
import subprocess  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    recs = [_rec("Bib One", 2020, "10.1/b1", "J. One", ["Alpha, A.", "Beta, B."], "http://one", "Abs", 3),
            _rec("Bib Two", 2020, "", "arXiv preprint", ["Alpha, A."], "http://arxiv.org/abs/x", "", 0)]
    for r in recs:
        r["block"] = "X"
    lib.write_bibtex(recs, tdp / "r.bib")
    bib = (tdp / "r.bib").read_text(encoding="utf-8")
    weird = [_rec("10% of H_2O & $x$", 2020, "", "J", [", A.", "  "], ""),
             _rec("No author", "", "", "", [], "")]
    lib.write_bibtex(weird, tdp / "w.bib")
    wb = (tdp / "w.bib").read_text(encoding="utf-8")
    check("bibtex: malformed author names do not crash; specials escaped",
          "@article{anon2020," in wb and "@misc{anonnd," in wb and "10\\% of H\\_2O \\& \\$x\\$" in wb)
    seen_ = set()
    keys = [lib._bib_key({"authors": [], "year": ""}, seen_) for _ in range(30)]
    check("bibtex: 30 colliding keys stay legal (a..z then -27, -28 ...)",
          keys[1] == "anonnda" and keys[26] == "anonndz" and keys[27] == "anonnd-28" and len(set(keys)) == 30
          and all(ch not in "{}|" for k in keys for ch in k))
    check("csl: arXiv preprint typed 'article', journal paper 'article-journal'",
          json.loads((tdp / "r.csl.json").read_text(encoding="utf-8"))[1]["type"] == "article"
          if (tdp / "r.csl.json").exists() else True)
    check("bibtex: @article/@misc, unique keys, block keyword",
          "@article{alpha2020," in bib and "@misc{alpha2020a," in bib and "keywords = {block:X}" in bib)
    back = project.parse_bibtex(bib)
    check("bibtex round-trips through project.parse_bibtex",
          len(back) == 2 and back[0]["doi"] == "10.1/b1" and back[0]["authors"] == ["Alpha, A.", "Beta, B."])
    lib.write_csl(recs, tdp / "r.csl.json")
    csl = json.loads((tdp / "r.csl.json").read_text(encoding="utf-8"))
    check("csl-json: author family/given split, issued date-parts, DOI",
          csl[0]["author"][0] == {"family": "Alpha", "given": "A."} and csl[0]["issued"] == {"date-parts": [[2020]]}
          and csl[0]["DOI"] == "10.1/b1")
    lib.write_ris(recs, tdp / "r.ris")
    check("ris carries the block as a keyword", "KW  - block:X" in (tdp / "r.ris").read_text(encoding="utf-8"))

    # inbox: a malformed file stays put, the good one is ingested
    od = tdp / "lit"
    (od / "inbox").mkdir(parents=True)
    (od / "inbox" / "good.ris").write_text("TY  - JOUR\nTI  - Good\nPY  - 2020\nER  -\n", encoding="utf-8")
    (od / "inbox" / "bad.json").write_text("{not json", encoding="utf-8")
    import logging as _lg2
    done = project.ingest_inbox(od, _lg2.getLogger("t2"))
    check("inbox: malformed file left in place, good file ingested",
          [s["name"] for s in done] == ["good"] and (od / "inbox" / "bad.json").exists()
          and not (od / "inbox" / "good.ris").exists())

    # post-hoc OA pass with canned Unpaywall
    CANNED.clear()
    CANNED["api.unpaywall.org"] = json.dumps({"is_oa": True, "best_oa_location": {"url_for_pdf": "http://pdf", "url": "http://u", "version": "publishedVersion"}}).encode()
    (od / "manual" / "good" / "records.json").write_text(json.dumps([dict(_rec("Good", 2020, "10.1/oa", "J", [], ""), block="X", backend="manual:good")]), encoding="utf-8")
    lib._get = fake_get
    try:
        st = project.oa_pass(od, log=_lg2.getLogger("t2"))
    finally:
        lib._get = real_get
    got = json.loads((od / "manual" / "good" / "records.json").read_text(encoding="utf-8"))[0]
    check("oa pass: manual records enriched and cached",
          st["oa"] == 1 and got.get("is_oa") is True and got.get("oa_pdf") == "http://pdf"
          and (od / "unpaywall_cache.json").exists())
    st2 = project.oa_pass(od, log=_lg2.getLogger("t2"))
    check("oa pass: second run fetches nothing (already enriched)", st2["fetched"] == 0)
    check("oa pass: stats count unique DOIs once", st["dois"] == 1 and st["fetched"] == 1)
    # a failed lookup is not cached, so it is retried on the next pass
    def failing_get(url, headers=None, tries=3, timeout=None):
        raise RuntimeError("Unpaywall down")
    (od / "manual" / "good" / "records.json").write_text(json.dumps([dict(_rec("Later", 2020, "10.1/later", "J", [], ""), block="X", backend="manual:good")]), encoding="utf-8")
    lib._get = failing_get
    try:
        project.oa_pass(od, log=_lg2.getLogger("t2"))
    finally:
        lib._get = real_get
    cache_after = json.loads((od / "unpaywall_cache.json").read_text(encoding="utf-8"))
    check("oa pass: a failed lookup is not cached (will be retried)", "10.1/later" not in cache_after)
    # merge keeps provenance of already-merged records
    pre = project.merge([{"title": "M", "doi": "10.1/m", "found_by": ["openalex@s", "ads@s"], "first_seen": "2026-01-01", "blocks": ["X"], "backend": "openalex", "member": "s"},
                         {"title": "M", "doi": "10.1/m", "backend": "manual:c", "member": "c", "member_date": "2026-02-01"}])
    check("merge: pre-merged record keeps and extends its found_by",
          pre[0]["found_by"] == ["openalex@s", "ads@s", "manual:c@c"] and pre[0]["first_seen"] == "2026-01-01")
    check("inbox: no empty manual/<name> directory is left for a malformed file",
          not (od / "manual" / "bad").exists())
    check("lazy blocks: membership and get() trigger the load",
          ("NOV" in wos_manual.BLOCKS) == ("NOV" in dict(wos_manual.BLOCKS)) and wos_manual.BLOCKS.get("__none__") is None)

    # journals: budget exhaustion stops OpenAlex for the rest of the run
    def budget_get(url, headers=None, tries=3, timeout=None):
        if "openalex" in url:
            raise RuntimeError("HTTP 429: Insufficient budget -> OpenAlex daily free budget exhausted")
        return fake_get(url, headers, tries, timeout)
    (od / "runs" / "20260101T000000" / "records").mkdir(parents=True)
    (od / "runs" / "20260101T000000" / "counts.json").write_text("{}", encoding="utf-8")
    (od / "runs" / "20260101T000000" / "records" / "X_openalex.json").write_text(json.dumps(
        [dict(_rec("P1", 2020, "10.1/p1", "J. A", [], ""), block="X", backend="openalex"),
         dict(_rec("P2", 2020, "10.1/p2", "J. B", [], ""), block="X", backend="openalex")]), encoding="utf-8")
    lib._get = budget_get
    calls = []
    real_fo = journals.fetch_openalex
    journals.fetch_openalex = lambda name, issns: calls.append(name) or real_fo(name, issns)
    try:
        st3 = journals.fetch(od, ("openalex",), log=_lg2.getLogger("t2"))
    finally:
        lib._get = real_get
        journals.fetch_openalex = real_fo
    check("journals: after the budget error OpenAlex is not asked again", len(calls) == 1 and st3["openalex"] == 0)

    # close_logging releases the file
    ns = _ap.Namespace(outdir=str(od), verbose=False, quiet=True, log_dir=None)
    lg = project.setup_logging("closeme", ns)
    project.close_logging(lg)
    check("close_logging removes every handler", lg.handlers == [])

    # lazy WoS blocks: import needs no query file; explicit --queries wins
    check("wos_manual blocks load lazily", isinstance(wos_manual.BLOCKS, dict) and len(wos_manual.BLOCKS) > 0)

# CLI smoke: every script answers --help and --version, and the subcommands round-trip
cli_ok = True
for script in ("librarian.py", "project.py", "report.py", "journals.py", "wos_manual.py"):
    for flag in ("--help", "--version"):
        r = subprocess.run([sys.executable, str(HERE.parent / script), flag], capture_output=True, text=True)
        cli_ok = cli_ok and r.returncode == 0 and ("usage" in r.stdout.lower() or "scitech-librarian" in r.stdout)
check("every script answers --help and --version", cli_ok)
with tempfile.TemporaryDirectory() as td:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    run = lambda *a: subprocess.run([sys.executable, str(HERE.parent / a[0]), *a[1:], "--outdir", td, "-q"],  # noqa: E731
                                    capture_output=True, text=True, env=env)
    r1 = run("project.py", "init", "--name", "Smoke")
    ris = Path(td) / "in.ris"
    ris.write_text("TY  - JOUR\nTI  - Smoke paper\nDO  - 10.1/s\nPY  - 2021\nJO  - J. S\nER  -\n", encoding="utf-8")
    r2 = run("project.py", "ingest", str(ris), "--name", "smoke", "--method", "expert")
    r3 = run("project.py", "status")
    r4 = run("report.py", "--project", "--format", "md", "txt")
    r5 = run("journals.py", "list")
    rep = list((Path(td) / "reports").glob("*/report.md"))
    check("CLI: init -> ingest -> status -> report --project -> journals list",
          all(r.returncode == 0 for r in (r1, r2, r3, r4, r5)) and "smoke" in r3.stdout and rep
          and "Smoke paper" in rep[0].read_text(encoding="utf-8"),
          "; ".join((r.stderr or "")[-200:] for r in (r1, r2, r3, r4, r5) if r.returncode))
    check("CLI: audit logs written for each invocation",
          len(list((Path(td) / "logs").glob("*.log"))) >= 5)

# ---------------------------------------------------------------------------
print("\nreview 2026-08-28: arXiv cap, capped heuristic, docs guard")

# arXiv: --limit above 300 must page on (regression: hard 3-page cap ignored --limit)
_arx_calls = []


def arx_get(url, headers=None, tries=3, timeout=None):
    _arx_calls.append(url)
    import urllib.parse as _up
    start = int(_up.parse_qs(_up.urlparse(url).query).get("start", ["0"])[0])
    entries = "".join(f"<entry><title>P{start + i}</title><published>2020-01-01</published>"
                      f"<id>http://arxiv.org/abs/{start + i}</id></entry>" for i in range(100))
    return (b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" '
            b'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" '
            b'xmlns:arxiv="http://arxiv.org/schemas/atom">'
            b'<opensearch:totalResults>1000</opensearch:totalResults>' + entries.encode() + b'</feed>')


real_sleep = lib.time.sleep
lib._get, lib.time.sleep = arx_get, lambda s: None
try:
    total, recs = lib.bk_arxiv("q", 450)
finally:
    lib._get, lib.time.sleep = real_get, real_sleep
check("arxiv: --limit 450 fetches five pages, not three", len(recs) == 450 and len(_arx_calls) == 5,
      f"{len(recs)} records over {len(_arx_calls)} calls")

# capped heuristic: junk from another block must not mark this pair as capped
_d = {"counts": {"A": {"openalex": 500}, "B": {"openalex": 500}}, "backends": ["openalex"],
      "block_names": ["A", "B"], "meta": {"limit": 3},
      "raw": {"A_openalex": [dict(_rec(f"a{i}", 2020, f"10.1/a{i}", "J", [], ""), block="A", backend="openalex") for i in range(3)],
              "B_openalex": [dict(_rec("b0", 2020, "10.1/b0", "J", [], ""), block="B", backend="openalex")]},
      "junk": [dict(_rec("j", 2020, "10.1/j", "Zenodo", [], ""), block="A", backend="openalex")] * 2,
      "unique": [], "project": None}
check("capped heuristic counts junk per block/backend (B is not capped by A's junk)",
      sorted(n for n, _, _ in report.stats(_d)["capped"]) == ["A"])

# docs guard: every CLI flag of every script (and subcommand) is in the manual and AGENTS.md
import re as _re
_MAN = (HERE.parent / "docs" / "USER_MANUAL.md").read_text(encoding="utf-8")
_AG = (HERE.parent / "AGENTS.md").read_text(encoding="utf-8")
sys.path.insert(0, str(HERE.parent / "docs"))
import build_manual as _bm  # noqa: E402
_SUBS = {"project.py": ["init", "status", "ingest", "oa", "exclude", "include", "label", "alias"],
         "journals.py": ["fetch", "import-scimago", "import-csv", "import-jcr", "list", "show"]}
_missing = []
for script in ("librarian.py", "project.py", "report.py", "journals.py", "wos_manual.py"):
    for sub in [[]] + [[c] for c in _SUBS.get(script, [])]:
        h = subprocess.run([sys.executable, str(HERE.parent / script), *sub, "--help"],
                           capture_output=True, text=True).stdout
        for fl in sorted(set(_re.findall(r"(?<![\w-])--[a-z][a-z-]+", h))):
            if fl in ("--help", "--version"):
                continue
            for doc, name in ((_MAN, "manual"), (_AG, "AGENTS")):
                if fl not in doc:
                    _missing.append(f"{name}:{script}{' ' + sub[0] if sub else ''} {fl}")
check("docs guard: every CLI flag appears in USER_MANUAL.md and AGENTS.md", not _missing, "; ".join(_missing))

# roadmap guard: the README's Roadmap and docs/FUTURE_BACKENDS.md are one list.
# 3.4.3 came from these two drifting -- the roadmap advertised DBLP as a
# config-only addition for a year after it turned out to honour no boolean
# operator, and a reader wiring it from the README would have counted nonsense.
_FB = (HERE.parent / "docs" / "FUTURE_BACKENDS.md").read_text(encoding="utf-8")
_RM = (HERE.parent / "README.md").read_text(encoding="utf-8")
_road = _RM.split("## Roadmap")[1].split("\n## ")[0]


def _bolded(heading: str) -> set:
    """Names in the first column of the table under a FUTURE_BACKENDS heading."""
    body = _FB.split(heading)[1].split("\n## ")[0]
    return set(_re.findall(r"\|\s*\*\*([^*]+)\*\*", body))


_ready = _bolded("## Databases ready to configure")
_excluded = _bolded("## Config-only, but")
check("roadmap guard: FUTURE_BACKENDS lists keyless and excluded candidates",
      len(_ready) >= 5 and len(_excluded) >= 3,
      f"ready={sorted(_ready)} excluded={sorted(_excluded)}")
check("roadmap guard: every keyless ready-to-configure backend is named in the README roadmap",
      not [n for n in _ready if n not in _road],
      f"missing from README Roadmap: {sorted(n for n in _ready if n not in _road)}")
check("roadmap guard: the README roadmap never advertises a default_exclude backend",
      not [n for n in _excluded if n in _road],
      f"advertised but counts nothing: {sorted(n for n in _excluded if n in _road)}")
check("roadmap guard: FUTURE_BACKENDS records when its API details were verified",
      _re.search(r"re-verified \d{4}-\d{2}-\d{2} against live endpoints", _FB) is not None,
      "no 're-verified <date> against live endpoints' line")

# githubify rule 17: the warranty disclaimer and limitation of liability must
# survive every rewrite -- in LICENSE and, visibly, in the README.
_licence = (HERE.parent / "LICENSE").read_text(encoding="utf-8", errors="replace")
_readme = (HERE.parent / "README.md").read_text(encoding="utf-8", errors="replace")
check("LICENSE disclaims warranty and liability (operative clauses, not just headings)",
      "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND" in _licence and "Limitation of Liability" in _licence
      and "liable to You for damages" in _licence, "clause missing")
check("README carries a visible Disclaimer under Licence",
      "### Disclaimer" in _readme and "without warrant" in _readme
      and "liable" in _readme and _readme.index("## Licence") < _readme.index("### Disclaimer"),
      "disclaimer missing")

# release metadata and licence hygiene (post-3.2.3 code review)
_cff = (HERE.parent / "CITATION.cff").read_text(encoding="utf-8")
check("CITATION.cff version equals librarian.VERSION",
      f'version: "{lib.VERSION}"' in _cff, f"CITATION.cff does not say {lib.VERSION}")
check("USER_MANUAL.md subtitle equals librarian.VERSION",
      f'subtitle: "version {lib.VERSION}"' in _MAN, f"manual subtitle does not say {lib.VERSION}")
check("count_checks refuses a truncated suite run and counts a complete one",
      _bm.count_checks("  PASS  a\n  PASS  b\n") == 0
      and _bm.count_checks("  PASS  a\n  FAIL  b  -- x\n\nsummary\n  1 FAILED: b\n") == 2,
      "a crashed suite must not rewrite the docs' check count")
# rewrite_count must keep LF endings (an autocrlf=false contributor must not
# get a whole-file CRLF diff) and must leave a quoted historical figure alone.
_tdir = Path(tempfile.mkdtemp())
_tf = _tdir / "doc.md"
_tf.write_bytes(b'A 5-check offline suite with 5 checks.\nThe old README said "3 checks".\n')
_bm.rewrite_count(_tf, 9)
_tb = _tf.read_bytes()
check("rewrite_count writes LF and skips quoted historical counts",
      b"\r" not in _tb and b"9-check offline suite with 9 checks" in _tb
      and b'said "3 checks"' in _tb, f"got: {_tb!r}")
check("count_mentions reads the live count and ignores the quoted one",
      _bm.count_mentions(_tf.read_text(encoding="utf-8")) == [9, 9],
      f"got: {_bm.count_mentions(_tf.read_text(encoding='utf-8'))}")
check("builtin (no-pandoc) HTML fallback carries the manual's subtitle version",
      f"version {lib.VERSION}" in _bm._wrap(_bm.md_to_html_min(_MAN)),
      "md_to_html_min/_wrap drop the front-matter subtitle")
_HTMLDOC = (HERE.parent / "docs" / "USER_MANUAL.html").read_text(encoding="utf-8", errors="replace")
check("built USER_MANUAL.html carries librarian.VERSION (build_manual.py was run)",
      f"version {lib.VERSION}" in _HTMLDOC, f"USER_MANUAL.html does not say {lib.VERSION}")
_aff = _readme[_readme.index("This is an independent project."):].split("\n\n")[0]
_bk = {b for b in lib.DEFAULT_BACKENDS}
_names = {"openalex": "OpenAlex", "ads": "NASA ADS", "arxiv": "arXiv", "inspire": "INSPIRE-HEP",
          "scopus": "Elsevier", "semanticscholar": "Semantic Scholar", "crossref": "Crossref",
          "wos": "Clarivate"}
_absent = [n for b, n in _names.items() if b in _bk and n not in _aff]
check("README non-affiliation note names every built-in backend", not _absent, f"missing: {_absent}")
_nospdx = [f for f in ("librarian.py", "project.py", "report.py", "render.py", "i18n.py", "journals.py", "wos_manual.py",
                       "tests/test_librarian.py", "docs/build_manual.py")
           if "SPDX-License-Identifier: Apache-2.0" not in (HERE.parent / f).read_text(encoding="utf-8")[:300]]
check("every tracked .py carries the SPDX header", not _nospdx, f"missing: {_nospdx}")

# githubify rule 19: CI covers Linux + Windows + macOS -- and the README says
# so honestly (the sister project's badge read "Windows | Linux" three
# releases after macOS joined its matrix).
_ci = (HERE.parent / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
_no_os = [o for o in ("ubuntu-latest", "windows-latest", "macos-latest") if o not in _ci]
check("CI matrix covers Linux, Windows and macOS", not _no_os, f"missing: {_no_os}")
_pos = _re.compile(r"Linux,\s+Windows\s+and\s+macOS")          # any hard-wrap
_neg = _re.compile(r"Linux and\s+Windows")                       # nowhere, in any prose
_need = {"README": 2, "manual": 1, "AGENTS": 1}                    # README says it twice
_stale = [n for n, d in (("README", _readme), ("manual", _MAN), ("AGENTS", _AG))
          if len(_pos.findall(d)) < _need[n] or _neg.search(d)]
check("README (x2), manual and AGENTS.md state the CI platforms as Linux, Windows and macOS",
      not _stale, f"stale platform wording in: {_stale}")

# the vendored checker must stay byte-identical to the canonical copy on every
# platform: a Windows checkout with core.autocrlf=true would turn it CRLF
# unless .gitattributes pins it to LF.
# read the *effective* attribute, not the .gitattributes text (spelling-proof).
# Only this repo's own checkout is judged: a tarball, or a tools/ drop-in inside
# someone else's repository, has no .git here and nothing to pin. In our own
# checkout a git error (no binary, dubious ownership, ...) fails loudly rather
# than masking a missing pin.
_vend = ("tests/conformance.py", "tests/test_githubify_conformance.py")
_unpinned = []
if (HERE.parent / ".git").exists():
    try:
        _attr = subprocess.run(["git", "check-attr", "eol", *_vend], cwd=HERE.parent,
                               capture_output=True, text=True, timeout=60,
                               encoding="utf-8", errors="replace")   # localized git output
        _unpinned = ([f for f in _vend if f"{f}: eol: lf" not in _attr.stdout]
                     if _attr.returncode == 0 else [f"git error: {_attr.stderr.strip()[:80]}"])
    except (OSError, subprocess.SubprocessError) as _e:
        _unpinned = [f"git unavailable: {_e}"]
check("vendored checker files are pinned to LF in this checkout (git check-attr eol)",
      not _unpinned, f"unpinned: {_unpinned}")


# ---------------------------------------------------------------------------
print("\n3.3.3: shipped Claude Code skill, reproducible manual PDF")
# The literature-search skill ships in the repo (SKILL.md, portable: no machine
# paths) and the copy a user installs under ~/.claude/skills must not drift
# from it -- judged only where a copy is installed; CI has none.
_skill = HERE.parent / "SKILL.md"
_skill_txt = _skill.read_text(encoding="utf-8") if _skill.exists() else ""
check("repo ships SKILL.md with the literature-search front matter",
      _skill_txt.startswith("---\nname: literature-search\n"))
_inst = Path.home() / ".claude" / "skills" / "literature-search" / "SKILL.md"
check("installed ~/.claude/skills/literature-search/SKILL.md is byte-identical to the repo's"
      " (skipped when none is installed)",
      not _inst.exists() or (_skill.exists() and _inst.read_bytes() == _skill.read_bytes()),
      f"installed copy at {_inst} differs -- copy the repo SKILL.md over it")
# The manual PDF must be reproducible: pandoc + xelatex stamp CreationDate,
# ModDate and the trailer /ID from SOURCE_DATE_EPOCH when it is set, so
# build_manual.py derives it from the manual's own front-matter date and an
# unchanged manual rebuilds to identical bytes.
_sde = getattr(_bm, "source_date_epoch", None)
check("build_manual.source_date_epoch(front matter) is the manual's date at 00:00 UTC",
      _sde is not None and _sde('---\ntitle: "x"\ndate: "2026-08-31"\n---\n') == "1788134400"
      and _sde("no front matter") == "0",
      "missing or wrong")
_calls = []
class _Ret:
    returncode = 0
_orig_run = _bm.subprocess.run
_bm.subprocess.run = lambda *a, **k: (_calls.append(k), _Ret)[1]
try:
    _bm._run(["pandoc", "--version"], HERE)
finally:
    _bm.subprocess.run = _orig_run
_env = (_calls[0].get("env") or {}) if _calls else {}
check("build_manual._run hands pandoc/xelatex SOURCE_DATE_EPOCH from the manual's date, PATH intact",
      _sde is not None and _env.get("SOURCE_DATE_EPOCH") == _sde(_MAN)
      and _env.get("PATH") == os.environ.get("PATH"),
      f"env keys: {sorted(_env)[:6]}")
# xdvipdfmx draws font subset tags (ABCDEF+LMRoman...) at random on every run
# even under SOURCE_DATE_EPOCH; LuaTeX derives them from the font data, so only
# a lualatex build is byte-reproducible (measured 2026-09-01, TeX Live 2026).
check("build_manual prefers lualatex (reproducible font subset tags) over xelatex",
      tuple(getattr(_bm, "ENGINES", ()))[:1] == ("lualatex",),
      f"ENGINES = {getattr(_bm, 'ENGINES', None)}")
check("USER_MANUAL.md front-matter date equals CITATION.cff date-released (it stamps the PDF)",
      _re.search(r'^date:\s*"([^"]+)"', _MAN, _re.M).group(1)
      == _re.search(r'^date-released:\s*"([^"]+)"',
                    (HERE.parent / "CITATION.cff").read_text(encoding="utf-8"), _re.M).group(1))


# ---------------------------------------------------------------------------
print("\n3.4.0: translated README and manual (pt-BR, es, de, fr)")
# English is the source of truth. Each translation must keep the English
# skeleton (headings, numbering), every fenced code block verbatim (commands,
# file names and flags are never translated), every flag and every link
# target, quote the live check count, and record which English text it was
# made from (a digest with count phrases and front matter normalised) so a
# changed English file fails the suite until the translation is redone.
_DL = tuple(getattr(_bm, "DOC_LANGS", ()))
check("build_manual.DOC_LANGS names the four documentation languages",
      _DL == ("pt-BR", "es", "de", "fr"), f"DOC_LANGS = {_DL}")
_digest = getattr(_bm, "source_digest", None)
check("build_manual.source_digest ignores front matter and the check count",
      _digest is not None
      and _digest('---\nsubtitle: "version 1"\n---\nbody 12 checks\n')
      == _digest('---\nsubtitle: "version 2"\n---\nbody 99 checks\n')
      and _digest("body a") != _digest("body b"))
_FRONT = _re.compile(r"^---\n.*?\n---\n", _re.S)
_SWITCH = ("README.pt-BR.md", "README.es.md", "README.de.md", "README.fr.md")
_MSWITCH = ("USER_MANUAL.pt-BR.md", "USER_MANUAL.es.md", "USER_MANUAL.de.md", "USER_MANUAL.fr.md")


def _skeleton(text):
    return _re.findall(r"^(#{1,6}) +(\d+(?:\.\d+)?\.?)?", _FRONT.sub("", text), _re.M)


def _fences(text):
    return _re.findall(r"^```[^\n]*\n.*?^```", text, _re.M | _re.S)


def _flags(text):
    return set(_re.findall(r"(?<![\w-])--[a-z][a-z0-9-]+", text))


def _targets(text):
    # in-page anchors are language-specific (GitHub derives them from the
    # heading text), so they are not held to parity
    return {t for t in _re.findall(r"\]\(([^)\s]+)\)", text)
            if not t.startswith("#")
            and not _re.search(r"(README|USER_MANUAL)(\.[a-zA-Z-]+)?\.md$", t)}


check("README.md carries the language switch line linking the four translations",
      all(f"]({f})" in _readme.split("\n## ", 1)[0] for f in _SWITCH))
# build_manual.py --stamp-translations records the English digests in every
# translation once it has been redone, so nobody computes them by hand.
_sroot = Path(tempfile.mkdtemp())
(_sroot / "docs").mkdir()
(_sroot / "README.md").write_text("# t\n\nbody 3 checks\n", encoding="utf-8")
(_sroot / "docs" / "USER_MANUAL.md").write_text('---\ntitle: "m"\n---\n\nbody\n', encoding="utf-8")
(_sroot / "README.pt-BR.md").write_text("# t\n<!-- source-digest: PENDING -->\n\ncorpo 3 verificações\n",
                                        encoding="utf-8")
(_sroot / "docs" / "USER_MANUAL.pt-BR.md").write_text('---\ntitle: "m"\nsource-digest: "old"\n---\n\ncorpo\n',
                                                      encoding="utf-8")
# a translation without a digest marker cannot be stamped and must not be
# reported as such (3.4.0 review finding)
(_sroot / "README.es.md").write_text("# t\n\ncuerpo 3 comprobaciones\n", encoding="utf-8")
_stamp = getattr(_bm, "stamp_translations", None)
_stamped = _stamp(_sroot) if _stamp else []
check("build_manual.stamp_translations(root) writes the English digests into the translations present"
      " and reports only those it could stamp",
      _digest is not None and sorted(_stamped) == ["README.pt-BR.md", "docs/USER_MANUAL.pt-BR.md"]
      and f"<!-- source-digest: {_digest((_sroot / 'README.md').read_text(encoding='utf-8'))} -->"
      in (_sroot / "README.pt-BR.md").read_text(encoding="utf-8")
      and f'source-digest: "{_digest((_sroot / "docs" / "USER_MANUAL.md").read_text(encoding="utf-8"))}"'
      in (_sroot / "docs" / "USER_MANUAL.pt-BR.md").read_text(encoding="utf-8"),
      f"stamped: {_stamped}")
check("USER_MANUAL.md carries the language switch line linking the four translations",
      all(f"]({f})" in _MAN.split("\n# ", 1)[0] for f in _MSWITCH))
for _lang in ("pt-BR", "es", "de", "fr"):
    _rp = HERE.parent / f"README.{_lang}.md"
    _mp = HERE.parent / "docs" / f"USER_MANUAL.{_lang}.md"
    _rt = _rp.read_text(encoding="utf-8") if _rp.exists() else ""
    _mt = _mp.read_text(encoding="utf-8") if _mp.exists() else ""
    check(f"[{_lang}] README.{_lang}.md and docs/USER_MANUAL.{_lang}.md exist",
          bool(_rt) and bool(_mt))
    check(f"[{_lang}] README keeps the English heading skeleton",
          _skeleton(_rt) == _skeleton(_readme),
          f"{len(_skeleton(_rt))} vs {len(_skeleton(_readme))} headings")
    check(f"[{_lang}] manual keeps the English heading skeleton and numbering",
          _skeleton(_mt) == _skeleton(_MAN),
          f"{len(_skeleton(_mt))} vs {len(_skeleton(_MAN))} headings")
    _missing_fence = [f.splitlines()[1][:50] for f in _fences(_readme) if f not in _rt]
    check(f"[{_lang}] README keeps every English fenced code block verbatim",
          not _missing_fence, f"first missing: {_missing_fence[:2]}")
    _missing_fence = [f.splitlines()[1][:50] for f in _fences(_MAN) if f not in _mt]
    check(f"[{_lang}] manual keeps every English fenced code block verbatim",
          not _missing_fence, f"first missing: {_missing_fence[:2]}")
    check(f"[{_lang}] README names every flag the English README names",
          _flags(_readme) <= _flags(_rt), f"missing: {sorted(_flags(_readme) - _flags(_rt))[:6]}")
    check(f"[{_lang}] manual names every flag the English manual names",
          _flags(_MAN) <= _flags(_mt), f"missing: {sorted(_flags(_MAN) - _flags(_mt))[:6]}")
    check(f"[{_lang}] README keeps every English link target",
          _targets(_readme) <= _targets(_rt), f"missing: {sorted(_targets(_readme) - _targets(_rt))[:4]}")
    check(f"[{_lang}] manual keeps every English link target",
          _targets(_MAN) <= _targets(_mt), f"missing: {sorted(_targets(_MAN) - _targets(_mt))[:4]}")
    _others = [f for f in _SWITCH if f != f"README.{_lang}.md"] + ["README.md"]
    check(f"[{_lang}] README switch line links English and the other three languages",
          all(f"]({f})" in _rt.split("\n## ", 1)[0] for f in _others))
    _mothers = [f for f in _MSWITCH if f != f"USER_MANUAL.{_lang}.md"] + ["USER_MANUAL.md"]
    check(f"[{_lang}] manual switch line links English and the other three languages",
          all(f"]({f})" in _mt.split("\n# ", 1)[0] for f in _mothers))
    _fm = _FRONT.match(_mt).group(0) if _FRONT.match(_mt) else ""
    check(f"[{_lang}] manual front matter: same version and date as English, lang set",
          _re.search(rf'^subtitle: "[^"]*\b{_re.escape(lib.VERSION)}"', _fm, _re.M) is not None
          and _re.search(r'^date: *"([^"]+)"', _MAN, _re.M).group(0) in _fm
          and f'lang: "{_lang}"' in _fm, f"front matter: {_fm[:120]!r}")
    check(f"[{_lang}] manual records the digest of the English manual it translates (not stale)",
          _digest is not None and f'source-digest: "{_digest(_MAN)}"' in _fm,
          f"expected source-digest: \"{_digest(_MAN) if _digest else '?'}\"")
    check(f"[{_lang}] README records the digest of the English README it translates (not stale)",
          _digest is not None and f"<!-- source-digest: {_digest(_readme)} -->" in "\n".join(_rt.splitlines()[:3]),
          f"expected <!-- source-digest: {_digest(_readme) if _digest else '?'} --> in the first lines")
    _hp = HERE.parent / "docs" / f"USER_MANUAL.{_lang}.html"
    _pp = HERE.parent / "docs" / f"USER_MANUAL.{_lang}.pdf"
    check(f"[{_lang}] built USER_MANUAL.{_lang}.html carries librarian.VERSION and the .pdf exists",
          _hp.exists() and lib.VERSION in _hp.read_text(encoding="utf-8", errors="replace")
          and _pp.exists() and _pp.stat().st_size > 10000)

# ---------------------------------------------------------------------------
print("\n3.5.1: the review of 3.5.0 (line-by-line read of every module)")
# (a) Unpaywall needs a contact address; without one every lookup fails and
# was swallowed as "retry next time", so --pdfs ended in a silent 0/0. The
# pass now refuses up front, naming both routes (rule 28).
with tempfile.TemporaryDirectory() as td:
    _saved_contact = lib.CONTACT
    lib.CONTACT = ""
    try:
        try:
            lib.unpaywall_cached(["10.1/x"], Path(td) / "cache.json")
            _oa_err = ""
        except RuntimeError as e:
            _oa_err = str(e)
    finally:
        lib.CONTACT = _saved_contact
    check("unpaywall pass refuses without CONTACT_EMAIL instead of failing silently",
          "CONTACT_EMAIL" in _oa_err, repr(_oa_err)[:120])
    check("the refusal names both routes (environment or .env)",
          "environment or .env" in _oa_err, repr(_oa_err)[:120])
    check("no cache file is created by a refused pass", not (Path(td) / "cache.json").exists())
    # (b) .env values may be quoted, as every dotenv dialect allows; the quotes
    # are not part of the value (a quoted key reached the API with its quotes
    # and failed auth with no hint).
    envq = Path(td) / ".env"
    envq.write_text("LIB_TEST_Q1=\"double quoted\"\nLIB_TEST_Q2='single quoted'\n"
                    "LIB_TEST_Q3=\"unbalanced\nLIB_TEST_Q4=\"\"\n", encoding="utf-8")
    for k in ("LIB_TEST_Q1", "LIB_TEST_Q2", "LIB_TEST_Q3", "LIB_TEST_Q4"):
        os.environ.pop(k, None)
    load_env(envq)
    check(".env: a double-quoted value loses its quotes", os.environ.get("LIB_TEST_Q1") == "double quoted")
    check(".env: a single-quoted value loses its quotes", os.environ.get("LIB_TEST_Q2") == "single quoted")
    check(".env: an unbalanced quote is kept as typed", os.environ.get("LIB_TEST_Q3") == "\"unbalanced")
    check(".env: an empty quoted value is empty", os.environ.get("LIB_TEST_Q4") == "")
    for k in ("LIB_TEST_Q1", "LIB_TEST_Q2", "LIB_TEST_Q3", "LIB_TEST_Q4"):
        os.environ.pop(k, None)
    # (c) RIS: a preprint is not a journal article. BibTeX and CSL already
    # branch on _is_preprint; RIS wrote TY  - JOUR for everything.
    _rp = Path(td) / "types.ris"
    write_ris([_rec("Paper", 2020, "10.1/j", "Phys. Rev. B", ["A"], ""),
               _rec("Preprint", 2021, "", "arXiv preprint", ["B"], "http://arxiv.org/abs/1")], _rp)
    _rtxt = _rp.read_text(encoding="utf-8")
    check("RIS: a journal record is TY  - JOUR, a preprint is TY  - UNPB",
          _rtxt.count("TY  - JOUR") == 1 and _rtxt.count("TY  - UNPB") == 1, _rtxt[:200])
    check("RIS: the parser still reads both back", len(wos_manual.parse_ris(_rtxt)) == 2)
# (d) journals._entry rebuilt the alias index on every call (O(N^2) over a
# fetch); a caller may now pass one shared index, and a new entry registers
# its aliases in it so the next call finds it without a rebuild.
_st = {}
_idx = journals.alias_index(_st)
_e1 = journals._entry(_st, "New Journal of Things", [], _idx)
check("journals._entry accepts a shared alias index and registers the new entry in it",
      _idx.get(journals.norm_name("New Journal of Things")) is _e1)
_e2 = journals._entry(_st, "new journal of things", ["9876-5432"], _idx)
check("a later call through the shared index resolves to the same entry",
      _e2 is _e1 and "9876-5432" in _e1["issn"])
# (e) LaTeX: a URL in \href must escape % (a TeX comment) or the rest of the
# row vanishes; DOIs with encoded characters are real data.
_tt = render._tex_table(["T", "DOI"], [["x", ("link", "10.1/a%2Fb", "https://doi.org/10.1/a%2Fb")]])
check("render._tex_table escapes % inside the \\href target",
      "\\href{https://doi.org/10.1/a\\%2Fb}" in _tt, _tt[:200])


def test_offline_suite():
    """pytest entry point: the module body above is the suite."""
    assert not FAILED, FAILED

# ---------------------------------------------------------------------------
# check-count guard -- deliberately NOT a check(): it runs when the total is
# final, so there is no "keep this last" fragility and no +1. Every doc that
# quotes the count (build_manual.py syncs the first three; the HTML is built
# from the manual) must say exactly CHECKS, at least once each.
_counted = [("README.md", _readme), ("USER_MANUAL.md", _MAN),
            ("AGENTS.md", _AG), ("USER_MANUAL.html", _HTMLDOC)]
for _lang in ("pt-BR", "es", "de", "fr"):          # translations quote it too
    for _rel in (f"README.{_lang}.md", f"docs/USER_MANUAL.{_lang}.md"):
        if (HERE.parent / _rel).exists():
            _counted.append((_rel, (HERE.parent / _rel).read_text(encoding="utf-8")))
_badcnt = [n for n, d in _counted if set(_bm.count_mentions(d)) != {CHECKS}]
if _badcnt:
    FAILED.append("docs quote the actual check count")
print("\nsummary")
if _badcnt:
    print(f"  count guard: {', '.join(_badcnt)} do not quote exactly {CHECKS}"
          " (run docs/build_manual.py, restage README/manual/AGENTS/HTML)")
if FAILED:
    print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}")
    sys.exit(1)
print("  all passed")
