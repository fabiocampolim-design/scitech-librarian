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
print("\npagination, auth headers, and field fallbacks (canned, no network)")

SEEN_HEADERS = {}


def recording_get(url, headers=None, tries=3, timeout=None):
    SEEN_HEADERS.update(headers or {})
    return fake_get(url, headers, tries, timeout)


litscan._get = recording_get
try:
    # cursor paging: two OpenAlex pages, cursor * -> NEXT -> exhausted
    CANNED.clear()
    page = {"meta": {"count": 2, "next_cursor": "NEXT"},
            "results": [{"display_name": "P1", "cited_by_count": 0}]}
    page2 = {"meta": {"count": 2, "next_cursor": None},
             "results": [{"display_name": "P2", "cited_by_count": 0}]}
    CANNED["cursor=%2A"] = json.dumps(page).encode()
    CANNED["cursor=NEXT"] = json.dumps(page2).encode()
    total, recs = litscan.bk_openalex("q", 10)
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
    total, recs = litscan.bk_scopus("q", 30)
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
    total, recs = litscan.bk_ads("q", 5)
    check("Bearer auth format applied",
          SEEN_HEADERS.get("Authorization") == "Bearer tok123")
    check("ads url templated from bibcode",
          recs[0]["url"].endswith("/abs/2020ApJ...1B"))

    # template fallback (INSPIRE record without links.json)
    CANNED.clear()
    CANNED["inspirehep"] = json.dumps({"hits": {"total": 1, "hits": [
        {"id": "12345", "metadata": {"titles": [{"title": "I1"}],
                                     "earliest_date": "2019-07-01"}}]}}).encode()
    total, recs = litscan.bk_inspire("q", 5)
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
    total, recs = litscan.bk_crossref("q", 5)
    check("crossref multi-part title joined", recs[0]["title"] == "C One")
    check("crossref given_family transform", recs[0]["authors"] == ["Ada Lovelace"])
    check("crossref year from nested date-parts", recs[0]["year"] == "2018")
finally:
    litscan._get = real_get
    for k in ("SCOPUS_API_KEY", "SCOPUS_INSTTOKEN", "ADS_TOKEN"):
        os.environ.pop(k, None)

# ---------------------------------------------------------------------------
print("\nreport generation (report.py against a synthetic run directory)")
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
    txt = report.render_txt(title, nodes)
    check("txt: flow and PRISMA-S checklist", "Records screened" in txt
          and "Deduplication" in txt)

    pdf = run / "builtin.pdf"
    report._pdf_builtin(txt, pdf)
    data = pdf.read_bytes()
    check("builtin pdf writer: valid header, trailer and pages",
          data.startswith(b"%PDF-1.4") and b"%%EOF" in data and b"/Type /Page " in data)

    real_which = report.shutil.which
    report.shutil.which = lambda name: None       # no LaTeX, no pandoc
    try:
        (run / "prisma.json").unlink()
        out = report.write_reports(run, "simple", ["md", "pdf", "html"], quiet=True)
    finally:
        report.shutil.which = real_which
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

# ---------------------------------------------------------------------------
print("\nlibrarian -> report wiring")
import argparse as _ap  # noqa: E402
_ns = _ap.Namespace(queries=None, blocks=["X"], counts_only=False, limit=7,
                    keep_junk=False, pdfs=True)
_m = litscan.run_meta("20260102T030405", _ns, ["openalex"], 0.0, False)
check("run_meta records limit, flags and backend endpoint",
      _m["limit"] == 7 and _m["pdfs"] and _m["started"] == "2026-01-02 03:04:05"
      and _m["backend_config"]["openalex"]["url"].startswith("https://api.openalex.org"))
check("run_meta reports the tool version", _m["version"] == litscan.VERSION)

# ---------------------------------------------------------------------------
print("\nsummary")
if FAILED:
    print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}")
    sys.exit(1)
print(f"  all passed")
