#!/usr/bin/env python3
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


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -- {detail}"))
    if not cond:
        FAILED.append(name)


import librarian as litscan  # noqa: E402
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
    envf.write_text("# comment\n\nLITSCAN_TEST_A=hello\nLITSCAN_TEST_B=a=b\n", encoding="utf-8")
    os.environ.pop("LITSCAN_TEST_A", None)
    os.environ["LITSCAN_TEST_PRESET"] = "keep"
    envf.write_text(envf.read_text() + "LITSCAN_TEST_PRESET=clobber\n", encoding="utf-8")
    load_env(envf)
    check("key=value parsed", os.environ.get("LITSCAN_TEST_A") == "hello")
    check("value containing '=' survives", os.environ.get("LITSCAN_TEST_B") == "a=b")
    check("existing environment is not overridden",
          os.environ.get("LITSCAN_TEST_PRESET") == "keep")
    for k in ("LITSCAN_TEST_A", "LITSCAN_TEST_B", "LITSCAN_TEST_PRESET"):
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
print("\nRIS write -> parse round-trip (litscan.write_ris vs wos_manual.parse_ris)")
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
print("\nbackends against canned responses (litscan._get monkeypatched, no network)")

CANNED = {}


def fake_get(url, headers=None, tries=3, timeout=None):
    for frag, payload in CANNED.items():
        if frag in url:
            return payload
    raise AssertionError(f"unexpected URL in offline test: {url}")


real_get = litscan._get
litscan._get = fake_get
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
    total, recs = litscan.bk_openalex("q", 10)
    check("openalex total parsed", total == 2)
    check("openalex abstract rebuilt from inverted index",
          recs[0]["abstract"] == "Hello world")
    check("openalex doi normalised", recs[0]["doi"] == "10.1/oa")
    total, recs = litscan.bk_openalex("q", 0)
    check("openalex counts-only fetches no records", total == 2 and recs == [])

    CANNED["export.arxiv.org"] = (
        b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" '
        b'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" '
        b'xmlns:arxiv="http://arxiv.org/schemas/atom">'
        b'<opensearch:totalResults>1</opensearch:totalResults>'
        b'<entry><title>ArXiv paper</title><published>2022-01-01</published>'
        b'<id>http://arxiv.org/abs/2201.00001</id><summary>S</summary>'
        b'<author><name>B. Author</name></author></entry></feed>')
    total, recs = litscan.bk_arxiv("q", 10)
    check("arxiv total parsed from Atom", total == 1)
    check("arxiv preprint journal label", recs[0]["journal"] == "arXiv preprint")
    check("arxiv year from published date", recs[0]["year"] == "2022")

    for var in ("ADS_TOKEN", "SCOPUS_API_KEY"):
        os.environ.pop(var, None)
    try:
        litscan.bk_ads("q", 0)
        check("ads without token raises with pointer", False, "no exception")
    except RuntimeError as e:
        check("ads without token raises with pointer", "ADS_TOKEN" in str(e))
    try:
        litscan.bk_scopus("q", 0)
        check("scopus without key raises", False, "no exception")
    except RuntimeError as e:
        check("scopus without key raises", "SCOPUS_API_KEY" in str(e))
finally:
    litscan._get = real_get

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
    litscan._get = fake_get
    try:
        total, recs = compiled["mybase"][0]("q", 5)
        check("added backend fetches via generic runner",
              total == 1 and recs[0]["title"] == "Hello")
    finally:
        litscan._get = real_get

check("every embedded default compiles",
      all(callable(v[0]) and callable(v[1])
          for v in compile_backends(load_backends()).values()))

# ---------------------------------------------------------------------------
print("\nsummary")
if FAILED:
    print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}")
    sys.exit(1)
print(f"  all passed")
