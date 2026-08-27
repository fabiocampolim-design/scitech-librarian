#!/usr/bin/env python3
"""
wos_manual.py -- minimise the hand-work for Web of Science.

WoS Expanded API is not licensed to us, so WoS queries must be run in the web
UI. This script reduces that to: paste, export, next. It never touches the WoS
website itself -- scraping it would breach Clarivate's terms.

    python wos_manual.py prep         write query files + a checklist
    python wos_manual.py walk         interactive: copies each query to the
                                      clipboard in turn, you paste and export
    python wos_manual.py ingest       read exported RIS back into librarian's
                                      record schema so analysis is identical
    python wos_manual.py status       what has been collected so far

Typical session
---------------
1. `python wos_manual.py prep`
2. Open Web of Science -> Advanced search. Set database to
   **Web of Science Core Collection** (NOT "All Databases" -- NEAR/n is
   unsupported there). Editions: SCI-EXPANDED + ESCI on, CPCI-S off.
3. `python wos_manual.py walk` -- for each block it puts the query on your
   clipboard. Ctrl-V into WoS, run it, type the hit count back into the script,
   then Export -> RIS -> save into lit/manual_wos/ris/<BLOCK>.ris
4. `python wos_manual.py ingest`

Stdlib only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from librarian import OUTDIR, load_blocks, q_wos, q_wos_bare, write_csv

# librarian.py populates its module-level BLOCKS only inside main(), so importing
# that name would bind an empty dict. Load the query file directly instead --
# same search order (queries.json, then queries.example.json), same schema.
BLOCKS = load_blocks()

HERE = Path(__file__).resolve().parent
BASE = OUTDIR / "manual_wos"    # same lit/ root as librarian's automated runs
QDIR, RDIR = BASE / "queries", BASE / "ris"
UI_URL = "https://www.webofscience.com/wos/woscc/advanced-search"


def to_clipboard(text: str) -> bool:
    """Windows `clip`, macOS `pbcopy`, Linux `xclip`. Returns success."""
    for cmd in (["clip"], ["pbcopy"], ["xclip", "-selection", "clipboard"]):
        try:
            p = subprocess.run(cmd, input=text.encode("utf-16-le" if cmd[0] == "clip" else "utf-8"),
                               check=True, capture_output=True)
            return p.returncode == 0
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return False


def prep() -> None:
    QDIR.mkdir(parents=True, exist_ok=True)
    RDIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Web of Science — manual run checklist", "",
        f"Advanced search: <{UI_URL}>", "",
        "Settings that MUST be right, or the queries silently misbehave:", "",
        "- Database: **Web of Science Core Collection** (not *All Databases* — `NEAR/n` is unsupported there)",
        "- Search mode: **Advanced** (not Basic — `TS=` tags only work there)",
        "- Editions: SCI-EXPANDED ✅, ESCI ✅, CPCI-S ❌, BKCI ❌, SSCI ❌, A&HCI ❌",
        "", "Then for each block: paste the query, record the count, Export → RIS →",
        f"save as `lit/manual_wos/ris/<BLOCK>.ris`.", "",
        "| Block | Hits | RIS saved | Title |", "|---|---:|:---:|---|",
    ]
    lines.insert(4, "**Two forms are provided for every block. Pick by which box you are in:**\n"
                    "- *Advanced search* free-text query box → use the **TAGGED** form (`TS=(...)`)\n"
                    "- Any box where a field is already chosen from a dropdown "
                    "(\"Topic\", \"All Fields\") → use the **BARE** form, with no tag.\n\n"
                    "Pasting a tagged query into a dropdown-selected field gives "
                    "*Search Error: Invalid query*.\n")
    for name, blk in BLOCKS.items():
        (QDIR / f"{name}.txt").write_text(
            f"# TAGGED (Advanced search free-text box)\n{q_wos(blk['groups'], blk)}\n\n"
            f"# BARE (a field is already selected from the dropdown)\n"
            f"{q_wos_bare(blk['groups'], blk)}\n", encoding="utf-8")
        lines.append(f"| {name} |  | ☐ | {blk['title']} |")
    lines += ["", "## Queries", ""]
    for name, blk in BLOCKS.items():
        lines += [f"### {name} — {blk['title']}", "",
                  "Tagged (Advanced search box):", "```",
                  q_wos(blk["groups"], blk), "```", "",
                  "Bare (field chosen from dropdown):", "```",
                  q_wos_bare(blk["groups"], blk), "```", ""]
    (BASE / "CHECKLIST.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(BLOCKS)} query files -> {QDIR}")
    print(f"Checklist -> {BASE / 'CHECKLIST.md'}")
    print("\nNOTE: the generated queries drop proximity operators (NEAR/n). If you "
          "maintain\nhand-tuned proximity queries for the paper, keep those authoritative.")


def walk() -> None:
    prep()
    counts: dict[str, str] = {}
    cfile = BASE / "counts.json"
    if cfile.exists():
        counts = json.loads(cfile.read_text())
    print(f"\nOpen {UI_URL}\n(Core Collection + Advanced search + SCI-EXPANDED/ESCI)\n")
    print("Enter = copy next query.  s = skip.  q = quit (progress is saved).\n")
    for name, blk in BLOCKS.items():
        if name in counts:
            print(f"  {name:4s} already recorded: {counts[name]} hits — skipping")
            continue
        print(f"\n--- Block {name}: {blk['title']}")
        cmd = input("    [Enter=tagged / b=bare / s=skip / q=quit] ").strip().lower()
        if cmd == "q":
            break
        if cmd == "s":
            continue
        bare = cmd == "b"
        q = q_wos_bare(blk["groups"], blk) if bare else q_wos(blk["groups"], blk)
        if to_clipboard(q):
            print(f"    {'BARE' if bare else 'TAGGED'} query copied to clipboard"
                  f" — paste into {'the dropdown-selected field' if bare else 'Advanced search'}")
        else:
            print("    (clipboard unavailable, query below)\n")
            print(f"    {q}")
        n = input("    hits (Enter to skip): ").strip()
        if n:
            counts[name] = n
            cfile.write_text(json.dumps(counts, indent=2), encoding="utf-8")
            print(f"    recorded. Now Export → RIS → {RDIR / (name + '.ris')}")
    print(f"\nCounts saved to {cfile}")


def parse_ris(text: str) -> list[dict]:
    """RIS -> librarian record schema, so manual and automated results merge."""
    recs, cur, authors = [], {}, []
    for raw in text.splitlines():
        if len(raw) < 6 or raw[4:6] != "- ":
            continue
        tag, val = raw[:2].strip(), raw[6:].strip()
        if tag == "TY":
            cur, authors = {}, []
        elif tag in ("AU", "A1"):
            authors.append(val)
        elif tag in ("TI", "T1"):
            cur["title"] = val
        elif tag in ("PY", "Y1"):
            cur["year"] = val[:4]
        elif tag in ("JO", "JF", "T2", "J9"):
            cur.setdefault("journal", val)
        elif tag == "DO":
            cur["doi"] = val
        elif tag in ("AB", "N2"):
            cur["abstract"] = val
        elif tag == "UR":
            cur.setdefault("url", val)
        elif tag == "ER":
            recs.append({"title": cur.get("title", ""), "year": cur.get("year", ""),
                         "doi": cur.get("doi", ""), "journal": cur.get("journal", ""),
                         "authors": authors, "url": cur.get("url", ""),
                         "abstract": cur.get("abstract", ""), "cited_by": 0})
            cur, authors = {}, []
    return recs


def ingest() -> None:
    if not RDIR.exists():
        print(f"No {RDIR} — run `prep` first, then export RIS files there.")
        return
    files = sorted(RDIR.glob("*.ris"))
    if not files:
        print(f"No .ris files in {RDIR}. Export from WoS as RIS, named <BLOCK>.ris")
        return
    allrecs = []
    for f in files:
        block = f.stem.upper()
        recs = parse_ris(f.read_text(encoding="utf-8", errors="replace"))
        for r in recs:
            r["block"], r["backend"] = block, "wos_manual"
        (BASE / f"{block}_wos.json").write_text(
            json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
        allrecs.extend(recs)
        print(f"  {block:5s} {len(recs):4d} records  <- {f.name}")
    seen, uniq = set(), []
    for r in allrecs:
        k = r["doi"].lower() or r["title"].lower()[:90]
        if k and k not in seen:
            seen.add(k)
            uniq.append(r)
    (BASE / "all_wos.json").write_text(json.dumps(uniq, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    write_csv(uniq, BASE / "all_wos.csv")
    print(f"\n{len(allrecs)} records, {len(uniq)} unique -> {BASE / 'all_wos.json'}")


def status() -> None:
    cfile = BASE / "counts.json"
    counts = json.loads(cfile.read_text()) if cfile.exists() else {}
    print(f"{'Block':6s} {'Hits':>8s}  RIS")
    for name in BLOCKS:
        ris = RDIR / f"{name}.ris"
        print(f"{name:6s} {counts.get(name, '-'):>8s}  {'yes' if ris.exists() else 'no'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prep"
    fn = {"prep": prep, "walk": walk, "ingest": ingest, "status": status}.get(cmd)
    if not fn:
        print(__doc__)
        sys.exit(2)
    fn()
