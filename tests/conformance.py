# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Fabio Campolim
"""GITHUBIFY conformance checker — the 17+ playbook rules as executable checks.

Stdlib-only, single file, vendorable byte-identically into a repo's ``tests/``
(rule 14: record the single source of truth — it is
``claude/tools/GITHUBIFY/conformance.py`` — and ``cmp`` after every change).

Usage:
    python conformance.py --repo <path> [--type from-scratch|study-and-contribute]
    python conformance.py --keep <claude-root>          # portfolio-side checks
    python conformance.py --repo <path> --json out.json

The rule table ships embedded; the private scrub pattern loads only from
``rules.yaml`` (via ``--rules``, ``$GITHUBIFY_RULES``, or a copy next to this
script) and the scrub checks SKIP with a notice when it is unavailable, so a
vendored copy never carries the pattern. A repo may extend the pattern with
former product names via a gitignored ``.githubify-extra-scrub`` file (one
regex alternative per line) and allow deliberate lines via
``.githubify-scrub-allow``. Exit: 0 = no FAIL, 1 = FAIL(s), 2 = usage error.

Results per check: PASS / FAIL / SKIP (not applicable or tool missing) /
MANUAL (the playbook rule needs judgement; listed so it is never forgotten).
"""

import argparse
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys

VERSION = "1.5.1"

TEXT_EXT = {".py", ".md", ".ipynb", ".txt", ".yml", ".yaml", ".json", ".ps1",
            ".bib", ".cff", ".toml", ".cfg", ".ini", ".bat", ".sh", ".html",
            ".tex", ".rst", ".xml", ".csv"}
MIRROR_DIRS = ("mirror", "upstream", "repos", "forum", "papers",
               "book", "books", "extracted", "literature")   # 1.5.0: PRACTICALMETEOROLOGY book/, PDFEXTRACT extracted/
NB_WARN, NB_FAIL = 1_000_000, 1_500_000   # rule 25: 1 MB target, 1.5 MB hard cap (Fabio 2026-08-31)
PDF_WARN, PDF_MAX = 5_000_000, 20_000_000  # rule 7: a tracked PDF over 20 MB is literature; 5-20 MB is a built deck/manual to justify
COMMUNITY = ("CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "docs/DESIGN.md")   # rule 26
COMMUNITY_MIN = 400                        # bytes; a stub is not a pathway
PROFILE_RULES = (3, 18, 20)                # kind: profile (a GitHub profile README repo) is not software:
                                           # only scrub, held-material and archive rules apply (Fabio 2026-09-02)
IMAGE_PAYLOAD = re.compile(r'"image/[a-z0-9+.-]+"\s*:\s*(?:"[^"]*"|\[[^\]]*\])')
HELD_DIRS = ("held", "private")
MAX_FINDINGS = 8   # per check, in the report


# ---------------------------------------------------------------- rules.yaml

def slurp(path):
    # utf-8-sig: files written from PowerShell carry a UTF-8 BOM, which made
    # a .project-class read as "set=?" on 2026-08-31 (CLAUDIU). Tolerate it.
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


# The rule TABLE is not secret and ships embedded, so a vendored copy works
# without rules.yaml. The scrub PATTERN is private (it names the very tokens
# rule 3 bans from public repos) and is NEVER embedded here: it loads only
# from rules.yaml, found via --rules, the GITHUBIFY_RULES environment
# variable, or a rules.yaml sitting next to this script. Without it, the
# scrub checks SKIP with a notice instead of silently passing.
DEFAULT_RULES = [
    dict(id=1, title="Validate before claiming", applies="all",
         check="manual", check_ids=[]),
    dict(id=2, title="Show samples before pushing; naming is the owner's call",
         applies="all", check="manual", check_ids=[]),
    dict(id=3, title="Nothing personal, nothing secret (scrub)", applies="all",
         check="auto", check_ids=["scrub", "scrub-notebook-outputs",
                                  "history-identity"]),
    dict(id=4, title="Priority: correctness, inputs, outputs, convenience",
         applies="all", check="manual", check_ids=[]),
    dict(id=5, title="Failing-first tests; pyflakes always looped in",
         applies="all", check="auto",
         check_ids=["pyflakes-clean", "ci-pyflakes-step", "tests-exist"]),
    dict(id=6, title="One project at a time", applies="all",
         check="manual", check_ids=[]),
    dict(id=7, title="Downloaded literature never ships", applies="all",
         check="auto", check_ids=["no-tracked-mirrors", "large-pdfs"]),
    dict(id=8, title="Real device data gets a personal-information pass",
         applies="all", check="manual", check_ids=[]),
    dict(id=9, title="CRediT attribution from full transcripts", applies="all",
         check="manual", check_ids=[]),
    dict(id=10, title="User Manual (md -> html/pdf)", applies="from-scratch",
         check="auto", check_ids=["user-manual"]),
    dict(id=11, title="Complete CLI parameter set, no hard-coded paths",
         applies="all", check="auto", check_ids=["no-hardcoded-paths"]),
    dict(id=12, title="Every script logs and audits", applies="all",
         check="manual", check_ids=[]),
    dict(id=13, title="AGENTS.md for agents", applies="from-scratch",
         check="auto", check_ids=["agents-md"]),
    dict(id=14, title="Real-data survival; check the artefact", applies="all",
         check="manual", check_ids=[]),
    dict(id=15, title="The suite guards the docs", applies="from-scratch",
         check="auto", check_ids=["docs-guard"]),
    dict(id=16, title="Release discipline", applies="from-scratch",
         check="auto", check_ids=["changelog", "citation-cff"]),
    dict(id=17, title="Warranty + liability; licence by origin; SPDX",
         applies="all", check="auto",
         check_ids=["license-clauses", "notice-file", "readme-disclaimer",
                    "non-affiliation", "spdx-headers"]),
    dict(id=18, title="Withheld research guarded", applies="all",
         check="auto", check_ids=["held-guard"]),
    dict(id=19, title="CI matrix covers Linux + Windows + macOS",
         applies="from-scratch", check="auto", check_ids=["ci-matrix"]),
    dict(id=20, title="Archived predecessors are never tracked",
         applies="all", check="auto", check_ids=["archives-ignored"]),
    dict(id=21, title="No local copies of shared tools",
         applies="all", check="auto", check_ids=["no-stale-tool-copies", "vendored-lf-pin"]),
    dict(id=22, title="Every skill product ships an undergraduate course (AILECTURE mechanics)",
         applies="study-and-contribute", check="manual", check_ids=[]),
    dict(id=23, title="Weekly upstream watch by a scheduled local script",
         applies="study-and-contribute", check="manual", check_ids=[]),
    dict(id=24, title="Installers fail loudly and run unattended (dry-run test, "
                      "tested failure path, --skip-deps, dated platforms.md row)",
         applies="all", check="manual", check_ids=[]),
    dict(id=25, title="No shipped notebook over 1 MB (1.5 MB hard cap); courses ship as "
                      "chapter notebooks with a TOC each",
         applies="all", check="auto", check_ids=["notebook-size"]),
    dict(id=26, title="Community pathways: CONTRIBUTING.md, CODE_OF_CONDUCT.md and "
                      "docs/DESIGN.md (the design trade-offs) in every repo",
         applies="all", check="auto", check_ids=["community-files"]),
]


def find_rules_file(explicit=None):
    """Resolve rules.yaml: --rules, then $GITHUBIFY_RULES, then next to
    this script. Returns None when unavailable (public/vendored context)."""
    for cand in (explicit, os.environ.get("GITHUBIFY_RULES"),
                 os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "rules.yaml")):
        if cand and os.path.isfile(cand):
            return cand
    return None


def load_rules(path):
    """Parse rules.yaml (stdlib has no yaml); fall back to the embedded
    table — with NO scrub pattern — when path is None."""
    if path is None:
        return dict(scrub_pattern=None, scrub_allow="",
                    rules=[dict(r) for r in DEFAULT_RULES])
    text = slurp(path)

    def grab(key):
        m = re.search(r"^\s*%s:\s*'(.*)'\s*$" % re.escape(key), text, re.M)
        if not m:
            m = re.search(r'^\s*%s:\s*"(.*)"\s*$' % re.escape(key), text, re.M)
        return m.group(1) if m else None

    rules = []
    for block in re.findall(
            r"- id: (\d+)\n\s+title: (.+)\n\s+applies: (.+)\n\s+check: (\w+)"
            r"(?:\n\s+check_ids: \[(.*)\])?", text):
        rid, title, applies, check, ids = block
        rules.append(dict(id=int(rid), title=title.strip().strip('"'),
                          applies=applies.strip(), check=check,
                          check_ids=[s.strip() for s in ids.split(",")] if ids else []))
    return dict(
        scrub_pattern=grab("pattern"),
        scrub_allow=grab("allow") or "",
        rules=rules or [dict(r) for r in DEFAULT_RULES],
    )


# ---------------------------------------------------------------- utilities

def run_git(repo, *args):
    try:
        out = subprocess.run(["git", "-C", repo] + list(args),
                             capture_output=True, text=True, timeout=120)
        return out.returncode, out.stdout
    except Exception as exc:                                 # noqa: BLE001
        return 1, str(exc)


def tracked_files(repo):
    rc, out = run_git(repo, "ls-files")
    if rc == 0 and out.strip():
        return [f for f in out.splitlines() if f.strip()]
    files = []                       # not a git repo: walk, minus junk
    for base, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in
                   (".git", ".venv", "node_modules", "__pycache__", ".remember")]
        for n in names:
            files.append(os.path.relpath(os.path.join(base, n), repo))
    return files


def read_text(repo, rel):
    try:
        with open(os.path.join(repo, rel), "rb") as f:
            raw = f.read()
        if b"\x00" in raw[:4096]:
            return None
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return None


def is_texty(rel):
    return os.path.splitext(rel)[1].lower() in TEXT_EXT


# ---------------------------------------------------------------- checks
# Each check(repo, ctx) -> (status, detail)

NO_PATTERN = ("SKIP", "scrub pattern unavailable — point GITHUBIFY_RULES "
              "(or --rules) at the private rules.yaml")


def chk_scrub(repo, ctx):
    if ctx["scrub_re"] is None:
        return NO_PATTERN
    pat, allow = ctx["scrub_re"], ctx["allow_re"]
    hits = []
    for rel in ctx["files"]:
        if not is_texty(rel):
            continue
        text = read_text(repo, rel)
        if rel.endswith(".ipynb") and text:
            text = IMAGE_PAYLOAD.sub('"image/*": "<binary>"', text)   # 1.5.0: base64 can spell a scrub token by chance (cap12_frentes)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if allow is not None:
                line = allow.sub("", line)
            if pat.search(line):
                hits.append("%s:%d: %s" % (rel, i, line.strip()[:100]))
                if len(hits) > 200:
                    break
    if hits:
        return "FAIL", "%d scrub hit(s): " % len(hits) + " | ".join(hits[:MAX_FINDINGS])
    return "PASS", "no scrub-pattern match in %d tracked text files" % len(ctx["files"])


def chk_scrub_nb_outputs(repo, ctx):
    if ctx["scrub_re"] is None:
        return NO_PATTERN
    pat, hits, nbs = ctx["scrub_re"], [], 0
    for rel in ctx["files"]:
        if not rel.endswith(".ipynb"):
            continue
        text = read_text(repo, rel)
        if text is None:
            continue
        nbs += 1
        try:
            nb = json.loads(text)
        except ValueError:
            hits.append("%s: unparseable notebook" % rel)
            continue
        for ci, cell in enumerate(nb.get("cells", [])):
            for o in cell.get("outputs", []):
                t = o.get("text", "")
                blob = "".join(t) if isinstance(t, list) else str(t)
                blob += str(o.get("data", {}).get("text/plain", ""))
                if ctx["allow_re"] is not None:
                    blob = ctx["allow_re"].sub("", blob)
                m = pat.search(blob)
                if m:
                    hits.append("%s cell %d output: ...%s..." % (rel, ci, m.group(0)))
    if not nbs:
        return "SKIP", "no notebooks tracked"
    if hits:
        return "FAIL", " | ".join(hits[:MAX_FINDINGS])
    return "PASS", "outputs of %d notebook(s) clean" % nbs


def chk_pyflakes(repo, ctx):
    pys = [f for f in ctx["files"] if f.endswith(".py")]
    if not pys:
        return "SKIP", "no tracked .py files"
    if importlib.util.find_spec("pyflakes") is None:
        return "SKIP", "pyflakes not installed here"
    out = subprocess.run([sys.executable, "-m", "pyflakes"] + pys,
                         capture_output=True, text=True, cwd=repo)
    msgs = (out.stdout + out.stderr).strip().splitlines()
    if msgs:
        return "FAIL", "%d finding(s): " % len(msgs) + " | ".join(msgs[:MAX_FINDINGS])
    return "PASS", "clean over %d file(s)" % len(pys)


def _workflows(repo, ctx):
    return [f for f in ctx["files"]
            if f.replace("\\", "/").startswith(".github/workflows/")
            and f.endswith((".yml", ".yaml"))]


def chk_ci_pyflakes(repo, ctx):
    wfs = _workflows(repo, ctx)
    if not wfs:
        return "FAIL", "no .github/workflows/*.yml"
    for rel in wfs:
        text = read_text(repo, rel) or ""
        i, j = text.find("pyflakes"), max(text.find("pytest"), text.find("unittest"))
        if i >= 0 and (j < 0 or i < j):
            return "PASS", "%s runs pyflakes before the suite" % rel
        if i >= 0:
            return "FAIL", "%s runs pyflakes AFTER the suite (rule 5: before)" % rel
    return "FAIL", "no pyflakes step in any workflow"


def chk_ci_matrix(repo, ctx):
    wfs = _workflows(repo, ctx)
    if not wfs:
        return "FAIL", "no .github/workflows/*.yml"
    text = " ".join(read_text(repo, w) or "" for w in wfs)
    missing = [o for o in ("ubuntu", "windows", "macos") if o not in text.lower()]
    if missing:
        return "FAIL", "CI matrix missing: " + ", ".join(missing)
    return "PASS", "Linux + Windows + macOS present"


def chk_tests_exist(repo, ctx):
    tests = [f for f in ctx["files"]
             if re.search(r"(^|[/\\])test[^/\\]*\.py$", f)]
    if tests:
        return "PASS", "%d test file(s)" % len(tests)
    return "FAIL", "no tracked test_*.py"


def chk_no_tracked_mirrors(repo, ctx):
    bad = sorted({f.replace("\\", "/").split("/")[0] for f in ctx["files"]
                  if f.replace("\\", "/").split("/")[0] in MIRROR_DIRS})
    if bad:
        return "FAIL", "tracked files under: " + ", ".join(bad) + " (rules 7/S1)"
    return "PASS", "no mirror/upstream/repos/forum/papers content tracked"


def chk_user_manual(repo, ctx):
    have = os.path.isfile(os.path.join(repo, "docs", "USER_MANUAL.md"))
    builder = os.path.isfile(os.path.join(repo, "docs", "build_manual.py"))
    if have and builder:
        return "PASS", "docs/USER_MANUAL.md + build_manual.py"
    return "FAIL", "missing " + ", ".join(
        p for p, ok in (("docs/USER_MANUAL.md", have),
                        ("docs/build_manual.py", builder)) if not ok)


def chk_agents_md(repo, ctx):
    if os.path.isfile(os.path.join(repo, "AGENTS.md")):
        return "PASS", "AGENTS.md present"
    return "FAIL", "no AGENTS.md at repo root (rule 13)"


def chk_docs_guard(repo, ctx):
    for rel in ctx["files"]:
        if re.search(r"(^|[/\\])test[^/\\]*\.py$", rel):
            text = read_text(repo, rel) or ""
            if ("USER_MANUAL" in text or "AGENTS.md" in text
                    or "build_parser" in text):
                return "PASS", "docs guard in %s" % rel
    return "FAIL", "no test references USER_MANUAL/AGENTS.md/build_parser (rule 15)"


def chk_changelog(repo, ctx):
    if os.path.isfile(os.path.join(repo, "CHANGELOG.md")):
        return "PASS", "CHANGELOG.md present"
    return "FAIL", "no CHANGELOG.md (rule 16)"


def chk_citation(repo, ctx):
    p = os.path.join(repo, "CITATION.cff")
    if not os.path.isfile(p):
        return "FAIL", "no CITATION.cff"
    text = read_text(repo, "CITATION.cff") or ""
    missing = [k for k in ("version", "license") if k + ":" not in text]
    if missing:
        return "FAIL", "CITATION.cff missing field(s): " + ", ".join(missing)
    return "PASS", "CITATION.cff with version + license"


def _license_text(repo):
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"):
        p = os.path.join(repo, name)
        if os.path.isfile(p):
            return name, slurp(p)
    return None, ""


def chk_license_clauses(repo, ctx):
    name, text = _license_text(repo)
    if not name:
        return "FAIL", "no LICENSE file (rule 17)"
    if "Apache License" in text:
        need = ["WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND", "Limitation of Liability"]
    elif "GNU GENERAL PUBLIC LICENSE" in text or "GNU LESSER" in text:
        need = ["THERE IS NO WARRANTY", "Limitation of Liability".upper()]
        text = text.upper()
        need = [n.upper() for n in need]
    else:
        return "FAIL", "%s is neither Apache-2.0 nor GPL — licence by origin (rule 17)" % name
    missing = [n for n in need if n not in text]
    if missing:
        return "FAIL", "%s lacks: %s" % (name, "; ".join(missing))
    return "PASS", "%s carries warranty + liability clauses" % name


def chk_notice(repo, ctx):
    _, text = _license_text(repo)
    if "Apache License" not in text:
        return "SKIP", "NOTICE required only for Apache-2.0"
    if os.path.isfile(os.path.join(repo, "NOTICE")):
        return "PASS", "NOTICE present"
    return "FAIL", "Apache-2.0 without NOTICE (rule 17)"


def _readme(repo):
    p = os.path.join(repo, "README.md")
    return slurp(p) if os.path.isfile(p) else ""


def chk_readme_disclaimer(repo, ctx):
    text = _readme(repo)
    if not text:
        return "FAIL", "no README.md"
    low = text.lower()
    if "### disclaimer" not in low:
        return "FAIL", "README has no '### Disclaimer' section (rule 17)"
    missing = [s for s in ("without warrant", "liable") if s not in low]
    if missing:
        return "FAIL", "Disclaimer lacks: " + ", ".join(missing)
    return "PASS", "README Disclaimer with warranty + liability wording"


def chk_non_affiliation(repo, ctx):
    if "not affiliated" in _readme(repo).lower():
        return "PASS", "non-affiliation note present"
    return "FAIL", "README lacks a non-affiliation note (rule 17)"


def chk_spdx(repo, ctx):
    pys = [f for f in ctx["files"] if f.endswith(".py")]
    if not pys:
        return "SKIP", "no tracked .py files"
    missing = []
    for rel in pys:
        head = "\n".join((read_text(repo, rel) or "").splitlines()[:5])
        if "SPDX-License-Identifier" not in head:
            missing.append(rel)
    if missing:
        return "FAIL", "%d/%d .py without SPDX header: %s" % (
            len(missing), len(pys), ", ".join(missing[:MAX_FINDINGS]))
    return "PASS", "SPDX header in all %d .py files" % len(pys)


def chk_held_guard(repo, ctx):
    # held/ sits at the study root even when the product is a subfolder
    bases = dict.fromkeys((ctx.get("root", repo), repo))
    present = sorted({d for b in bases for d in HELD_DIRS
                      if os.path.isdir(os.path.join(b, d))})
    if not present:
        return "SKIP", "no held/ or private/ directory"
    for rel in ctx["files"]:
        low = rel.lower()
        if "held" in low and low.endswith(".py"):
            return "PASS", "guard test %s covers %s" % (rel, ", ".join(present))
        if low.endswith(".py") and "held_terms" in (read_text(repo, rel) or ""):
            return "PASS", "guard via held_terms in %s" % rel
    return "FAIL", "%s exist(s) but no held-material guard test (rule 18)" % ", ".join(present)


def chk_no_hardcoded_paths(repo, ctx):
    # Built by concatenation so this source line cannot match itself when the
    # checker is vendored into the repo it scans.
    pat = re.compile(r"[A-Za-z]:\\+Users\\+|/c/" + "Users/", re.I)
    hits = []
    for rel in ctx["files"]:
        if not rel.endswith(".py"):
            continue
        text = read_text(repo, rel) or ""
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                hits.append("%s:%d" % (rel, i))
    if hits:
        return "FAIL", "absolute user paths in code (rule 11): " + ", ".join(hits[:MAX_FINDINGS])
    return "PASS", "no absolute user paths in tracked .py"


ARCHIVE_DIR_RE = re.compile(r"(^|/)(archive|archived|_archive|old)(/|$)", re.I)
# Shared tools that live in exactly one repo each; a copy elsewhere is stale.
SHARED_TOOL_FILES = ("litscan.py", "transcript_archiver.py", "librarian.py",
                     "wos_manual.py", "journals.py")


def chk_archives_ignored(repo, ctx):
    """Rule 20: an archived predecessor folded into the repo keeps its own
    .git and is gitignored; nothing under an archive dir may be tracked."""
    tracked = [f for f in ctx["files"]
               if ARCHIVE_DIR_RE.search(f.replace("\\", "/").rsplit("/", 1)[0] + "/")]
    if tracked:
        return "FAIL", "%d tracked file(s) under an archive dir: %s" % (
            len(tracked), ", ".join(tracked[:MAX_FINDINGS]))
    return "PASS", "no tracked files under archive dirs"


def chk_no_stale_tool_copies(repo, ctx):
    """Rule 21: shared tools are not copied into other projects. A repo that
    IS one of the tools passes (the file sits at its root); a recorded
    consumer lists its copies in a gitignored .githubify-tool-consumer file."""
    allow = set()
    for base in dict.fromkeys((ctx.get("root", repo), repo)):
        p = os.path.join(base, ".githubify-tool-consumer")
        if os.path.isfile(p):
            allow |= {ln.strip().replace("\\", "/") for ln in slurp(p).splitlines()
                      if ln.strip() and not ln.startswith("#")}
    hits = []
    for rel in ctx["files"]:
        norm = rel.replace("\\", "/")
        base = norm.rsplit("/", 1)[-1]
        if base in SHARED_TOOL_FILES and "/" in norm and norm not in allow:
            hits.append(norm)
    if hits:
        return "FAIL", "shared-tool copies inside the tree (rule 21): " + ", ".join(hits[:MAX_FINDINGS])
    return "PASS", "no stray copies of shared tools"


def chk_history_identity(repo, ctx):
    """Rule 3 applies to git history too: an author/committer identity that
    matches the scrub pattern (the private e-mail) is published by the first
    push and survives every later file scrub. Found 2026-08-31: three
    unpublished repos whose every commit carried the private identity, and a
    fork branch about to be pushed. Rewrite (mailmap + filter-repo) first."""
    if ctx["scrub_re"] is None:
        return NO_PATTERN
    rc, out = run_git(repo, "log", "--all", "--format=%an <%ae> / %cn <%ce>")
    if rc != 0:
        return "SKIP", "not a git repository"
    pat, allow = ctx["scrub_re"], ctx["allow_re"]
    bad = {}
    for line in out.splitlines():
        probe = allow.sub("", line) if allow is not None else line
        if pat.search(probe):
            bad[line] = bad.get(line, 0) + 1
    if bad:
        shown = ", ".join("%s x%d" % kv for kv in sorted(bad.items())[:MAX_FINDINGS])
        return "FAIL", ("commit identities match the scrub pattern - rewrite "
                        "history before any remote: " + shown)
    return "PASS", "no scrub-pattern hit in any author/committer identity"


def chk_large_pdfs(repo, ctx):
    """Rule 7: a tracked PDF over PDF_MAX is downloaded literature or a built book, not a doc."""
    big, mid = [], []
    for rel in ctx["files"]:
        if rel.lower().endswith(".pdf"):
            try:
                n = os.path.getsize(os.path.join(repo, rel))
            except OSError:
                continue
            if n > PDF_MAX:
                big.append("%s (%.1f MB)" % (rel, n / 1e6))
            elif n > PDF_WARN:
                mid.append("%s (%.1f MB)" % (rel, n / 1e6))
    if big:
        return "FAIL", "tracked PDF(s) over %d MB: %s" % (PDF_MAX // 1_000_000, ", ".join(big[:MAX_FINDINGS]))
    if mid:
        return "WARN", "tracked PDF(s) over %d MB (built deck/manual? literature must not ship): %s" % (
            PDF_WARN // 1_000_000, ", ".join(mid[:MAX_FINDINGS]))
    return "PASS", "no tracked PDF over %d MB" % (PDF_WARN // 1_000_000)


def chk_notebook_size(repo, ctx):
    """Rule 25: no shipped notebook over 1 MB (WARN) / 1.5 MB (FAIL); courses ship as
    chapter notebooks with a TOC each. PYTHTB and KWANT monoliths crashed sessions at
    2-6 MB (2026-08-31)."""
    fail, warn, n = [], [], 0
    for rel in ctx["files"]:
        if not rel.endswith(".ipynb"):
            continue
        try:
            size = os.path.getsize(os.path.join(repo, rel))
        except OSError:
            continue
        n += 1
        if size > NB_FAIL:
            fail.append("%s (%.2f MB)" % (rel, size / 1e6))
        elif size > NB_WARN:
            warn.append("%s (%.2f MB)" % (rel, size / 1e6))
    if not n:
        return "SKIP", "no notebooks tracked"
    if fail:
        return "FAIL", "over %.1f MB: %s" % (NB_FAIL / 1e6, ", ".join(fail[:MAX_FINDINGS]))
    if warn:
        return "WARN", "over %.0f MB (1.5 MB is the cap): %s" % (NB_WARN / 1e6, ", ".join(warn[:MAX_FINDINGS]))
    return "PASS", "%d notebook(s), all under %.0f MB" % (n, NB_WARN / 1e6)


def chk_community_files(repo, ctx):
    """Rule 26: CONTRIBUTING.md, CODE_OF_CONDUCT.md and docs/DESIGN.md (the design
    trade-offs, what a JOSS/JOSE reviewer asks for) exist and are not stubs."""
    missing, stubs = [], []
    for rel in COMMUNITY:
        p = os.path.join(repo, rel)
        if not os.path.isfile(p):
            missing.append(rel)
        elif os.path.getsize(p) < COMMUNITY_MIN:
            stubs.append(rel)
    if missing or stubs:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if stubs:
            parts.append("stub (< %d bytes) " % COMMUNITY_MIN + ", ".join(stubs))
        return "FAIL", "; ".join(parts) + " (rule 26)"
    return "PASS", "CONTRIBUTING.md + CODE_OF_CONDUCT.md + docs/DESIGN.md"


def chk_vendored_lf_pin(repo, ctx):
    """Rule 21: a vendored tests/conformance.py is pinned to LF (.gitattributes) so the
    wiring test's byte-identity survives a Windows checkout (librarian-a0, 3.2.4 review)."""
    rel = "tests/conformance.py"
    if rel not in [f.replace("\\", "/") for f in ctx["files"]]:
        return "SKIP", "no vendored checker"
    rc, out = run_git(repo, "check-attr", "eol", "--", rel)
    if rc != 0:
        return "SKIP", "not a git checkout"
    if re.search(r"eol:\s*lf\s*$", out.strip()):
        return "PASS", rel + " pinned eol=lf"
    return "FAIL", rel + " not pinned to LF (.gitattributes: `tests/conformance.py text eol=lf`)"


CHECKS = {
    "scrub": chk_scrub,
    "scrub-notebook-outputs": chk_scrub_nb_outputs,
    "pyflakes-clean": chk_pyflakes,
    "ci-pyflakes-step": chk_ci_pyflakes,
    "ci-matrix": chk_ci_matrix,
    "tests-exist": chk_tests_exist,
    "no-tracked-mirrors": chk_no_tracked_mirrors,
    "large-pdfs": chk_large_pdfs,
    "user-manual": chk_user_manual,
    "agents-md": chk_agents_md,
    "docs-guard": chk_docs_guard,
    "changelog": chk_changelog,
    "citation-cff": chk_citation,
    "license-clauses": chk_license_clauses,
    "notice-file": chk_notice,
    "readme-disclaimer": chk_readme_disclaimer,
    "non-affiliation": chk_non_affiliation,
    "spdx-headers": chk_spdx,
    "held-guard": chk_held_guard,
    "no-hardcoded-paths": chk_no_hardcoded_paths,
    "archives-ignored": chk_archives_ignored,
    "no-stale-tool-copies": chk_no_stale_tool_copies,
    "vendored-lf-pin": chk_vendored_lf_pin,
    "notebook-size": chk_notebook_size,
    "community-files": chk_community_files,
    "history-identity": chk_history_identity,
}


# ---------------------------------------------------------------- repo run

def project_type(repo, override=None):
    if override:
        return override
    p = os.path.join(repo, ".project-class")
    if os.path.isfile(p):
        m = re.search(r"^type:\s*(\S+)", slurp(p), re.M)
        if m:
            return m.group(1)
    return "from-scratch"          # strictest default


def project_kind(repo, override=None):
    """`kind:` in .project-class -- `software` (default) or `profile` (a GitHub profile
    README repository: no product, no suite, no manual; only rules 3, 18 and 20 apply)."""
    if override:
        return override
    p = os.path.join(repo, ".project-class")
    if os.path.isfile(p):
        m = re.search(r"^kind:\s*(\S+)", slurp(p), re.M)
        if m:
            return m.group(1)
    return "software"


def run_repo(repo, rules, ptype, subdir=None, kind="software"):
    """Run every rule against `repo`. With `subdir`, the product folder is the
    unit under check: paths become relative to it and every file-existence
    check (LICENSE, README, .github/workflows, docs/, ...) looks there — 1.4.0
    only filtered the tracked-file list, so study repos with a `<pkg>-skill/`
    product scored four spurious FAILs (rules 5 and 17; PYTHTB, QE, 2026-08-31).
    Repo-local allow files and `held/` are honoured at both levels."""
    root = repo
    files = tracked_files(root)
    if subdir:
        pref = subdir.replace("\\", "/").rstrip("/") + "/"
        files = [f.replace("\\", "/")[len(pref):] for f in files
                 if f.replace("\\", "/").startswith(pref)]
        repo = os.path.join(root, *pref.rstrip("/").split("/"))

    def local_alts(name):
        out = []
        for base in dict.fromkeys((root, repo)):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                out += [ln.strip() for ln in slurp(p).splitlines()
                        if ln.strip() and not ln.startswith("#")]
        return out

    extra = local_alts(".githubify-extra-scrub")
    allow_alts = ([rules["scrub_allow"]] if rules["scrub_allow"] else []) + local_alts(".githubify-scrub-allow")
    scrub_alts = ([rules["scrub_pattern"]] if rules["scrub_pattern"] else []) + extra
    ctx = {
        "files": files,
        "root": root,
        "scrub_re": re.compile("|".join(scrub_alts), re.I) if scrub_alts else None,
        "allow_re": re.compile("|".join(a for a in allow_alts if a), re.I)
        if any(allow_alts) else None,
    }
    results = []
    for rule in rules["rules"]:
        applies = rule["applies"] in ("all", ptype)
        if kind == "profile" and rule["id"] not in PROFILE_RULES:
            for cid in rule["check_ids"] or ["(judgement)"]:
                results.append(dict(rule=rule["id"], check=cid, status="SKIP",
                                    detail="n/a for kind profile"))
            continue
        if rule["check"] == "manual":
            results.append(dict(rule=rule["id"], check="(judgement)",
                                status="MANUAL" if applies else "SKIP",
                                detail=rule["title"]))
            continue
        for cid in rule["check_ids"]:
            if not applies:
                results.append(dict(rule=rule["id"], check=cid, status="SKIP",
                                    detail="n/a for type " + ptype))
                continue
            status, detail = CHECKS[cid](repo, ctx)
            results.append(dict(rule=rule["id"], check=cid,
                                status=status, detail=detail))
    return results


# ---------------------------------------------------------------- KEEP mode

def run_keep(root):
    """Portfolio-side checks: markers vs parent dirs, manifest paths, yann
    isolation, orphaned session-store slugs."""
    results = []
    manifest = os.path.join(root, "KEEP", "projects.yaml")
    text = slurp(manifest) if os.path.isfile(manifest) else ""

    entries = []          # (set, name, path)
    section = None
    for line in text.splitlines():
        m = re.match(r"^(\w[\w-]*):", line)
        if m:
            section = m.group(1)
            continue
        m = re.match(r"^\s{2}(\S+):\s*\{(.*)\}\s*$", line)
        if m and section in ("githubify", "yann", "unmanaged"):
            name, body = m.groups()
            pm = re.search(r"path:\s*([^,}]+)", body)
            if pm:
                entries.append((section, name, pm.group(1).strip()))

    cat_of = {"githubify": "githubify", "yann": "yann"}
    for sec, name, relpath in entries:
        full = os.path.join(root, *relpath.replace("claude/", "", 1).split("/"))
        if not os.path.isdir(full):
            results.append(dict(rule="K1", check="path", status="FAIL",
                                detail="%s: manifest path %s missing" % (name, relpath)))
            continue
        marker = os.path.join(full, ".project-class")
        if not os.path.isfile(marker):
            results.append(dict(rule="K1", check="marker", status="FAIL",
                                detail="%s: no .project-class" % name))
            continue
        mtext = slurp(marker)
        mset = (re.search(r"^set:\s*(\S+)", mtext, re.M) or [None, "?"])[1]
        parent = relpath.split("/")[1] if "/" in relpath else ""
        want = cat_of.get(parent, "unmanaged")
        if mset != want:
            results.append(dict(rule="K1", check="marker", status="FAIL",
                                detail="%s: marker set=%s but folder implies %s" % (name, mset, want)))
        else:
            results.append(dict(rule="K1", check="marker", status="PASS",
                                detail="%s: %s" % (name, mset)))
        if sec == "yann":
            rc, out = run_git(full, "remote")
            if out.strip():
                results.append(dict(rule="K2", check="yann-no-remote", status="FAIL",
                                    detail="%s HAS a git remote: %s" % (name, out.strip())))
            else:
                results.append(dict(rule="K2", check="yann-no-remote", status="PASS",
                                    detail="%s: no remote" % name))

    store = os.path.expanduser("~/.claude/projects")
    slug_root = "C--" + root.replace(":", "").replace("\\", "-").replace("/", "-")
    orphans = []
    if os.path.isdir(store):
        for slug in os.listdir(store):
            if not slug.startswith(slug_root):
                continue
            rel = slug[len("C--"):].replace("-", "/")
            # '-' is ambiguous (dir sep vs literal); test progressively.
            parts = slug[len("C--"):].split("-")
            found = False
            for cut in range(len(parts), 0, -1):
                cand = "C:/" + "/".join(parts[:cut]) + ("-" + "-".join(parts[cut:]) if cut < len(parts) else "")
                if os.path.isdir(cand):
                    found = True
                    break
            # fallback: naive all-separators variant
            if not found and os.path.isdir("C:/" + rel):
                found = True
            if not found:
                orphans.append(slug)
    if orphans:
        results.append(dict(rule="K3", check="slugs-resolve", status="FAIL",
                            detail="orphaned store slug(s): " + ", ".join(orphans)))
    else:
        results.append(dict(rule="K3", check="slugs-resolve", status="PASS",
                            detail="every claude/* session-store slug resolves"))
    return results


# ---------------------------------------------------------------- reporting

def report(results, label, as_json=None, quiet=False):
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    if not quiet:
        w = max(len(str(r["rule"])) for r in results) if results else 2
        print("== conformance %s : %s ==" % (VERSION, label))
        for r in results:
            print("rule %-*s  %-24s %-6s %s" % (w, r["rule"], r["check"],
                                                r["status"], r["detail"]))
        print("-- %s --" % "  ".join("%s=%d" % kv for kv in sorted(counts.items())))
    if as_json:
        payload = dict(version=VERSION, target=label,
                       generated=datetime.datetime.now().isoformat(timespec="seconds"),
                       counts=counts, results=results)
        with open(as_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1)
    return 1 if counts.get("FAIL") else 0


def build_parser():
    ap = argparse.ArgumentParser(
        description="GITHUBIFY conformance checker (rules.yaml is the rule source)")
    ap.add_argument("--repo", help="repository to check")
    ap.add_argument("--keep", metavar="PORTFOLIO_ROOT",
                    help="run portfolio-side checks against the claude root")
    ap.add_argument("--type", choices=["from-scratch", "study-and-contribute"],
                    help="override the .project-class type")
    ap.add_argument("--kind", choices=["software", "profile"],
                    help="override the .project-class kind (profile = README-only repo, rules 3/18/20 only)")
    ap.add_argument("--subdir", help="restrict checks to this product subfolder "
                    "(e.g. pythtb-skill) - study repos whose product is a subset")
    ap.add_argument("--rules", help="path to rules.yaml (default: "
                    "$GITHUBIFY_RULES, then next to this script; without it "
                    "the scrub checks SKIP)")
    ap.add_argument("--json", help="also write results to this JSON file")
    ap.add_argument("--quiet", action="store_true", help="summary only via exit code/JSON")
    ap.add_argument("--version", action="version", version=VERSION)
    return ap


def main(argv=None):
    try:   # a finding with a non-cp1252 character crashed the run under PowerShell (2026-09-01)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    args = build_parser().parse_args(argv)
    if not args.repo and not args.keep:
        build_parser().print_help()
        return 2
    rules = load_rules(find_rules_file(args.rules))
    code = 0
    if args.repo:
        repo = os.path.abspath(args.repo)
        ptype = project_type(repo, args.type)
        kind = project_kind(repo, args.kind)
        res = run_repo(repo, rules, ptype, args.subdir, kind)
        label = "%s (%s%s)" % (repo, ptype, ", " + kind if kind != "software" else "")
        if args.subdir:
            label += " subdir=" + args.subdir
        code |= report(res, label, args.json, args.quiet)
    if args.keep:
        res = run_keep(os.path.abspath(args.keep))
        code |= report(res, "KEEP portfolio checks",
                       args.json if not args.repo else None, args.quiet)
    return code


if __name__ == "__main__":
    sys.exit(main())
