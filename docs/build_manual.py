#!/usr/bin/env python3
"""
build_manual.py -- render docs/USER_MANUAL.md to USER_MANUAL.html and USER_MANUAL.pdf.

    python docs/build_manual.py

Development-time script (the manual's source of truth is the Markdown; the
built files are committed so readers need no tooling). Uses pandoc for the
HTML and pandoc + xelatex for the PDF when available; otherwise falls back
to a minimal stdlib Markdown-to-HTML conversion and report.py's built-in
PDF writer, so the command never fails -- it just says what it used.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
SRC = HERE / "USER_MANUAL.md"
OUT_HTML, OUT_PDF = HERE / "USER_MANUAL.html", HERE / "USER_MANUAL.pdf"

CSS = """body{font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:860px;
margin:2rem auto;padding:0 1rem;color:#1b1b1b;background:#fff}
h1{font-size:1.6rem;border-bottom:1px solid #999;padding-bottom:.2rem;margin-top:2rem}
h2{font-size:1.25rem;margin-top:1.6rem}table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{border:1px solid #bbb;padding:.3rem .5rem;text-align:left;vertical-align:top}th{background:#f3f3f3}
pre,code{font-family:ui-monospace,Consolas,monospace;font-size:.86rem}pre{background:#f6f6f6;padding:.6rem;overflow-x:auto}
@media(prefers-color-scheme:dark){body{color:#e6e6e6;background:#151515}th{background:#222}pre{background:#222}}"""


def _run(cmd, cwd):
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=600).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def md_to_html_min(text: str) -> str:
    """Just enough Markdown for the manual: headings, paragraphs, lists,
    fenced code, pipe tables, inline code/links/bold. Used only without pandoc."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)   # front matter
    out, lines, i = [], text.splitlines(), 0

    def inline(s):
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"&lt;(https?://[^&]+)&gt;", r'<a href="\1">\1</a>', s)
        return s

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre>" + html.escape("\n".join(lines[i + 1:j])) + "</pre>")
            i = j + 1
        elif ln.startswith("#"):
            lvl = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{lvl}>{inline(ln.lstrip('#').strip())}</h{lvl}>")
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[-| :]+\|$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            hdr, body = rows[0], rows[1:]
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in hdr) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</table>")
        elif re.match(r"^\s*(-|\d+\.)\s", ln):
            items = []
            while i < len(lines) and (re.match(r"^\s*(-|\d+\.)\s", lines[i]) or lines[i].startswith("  ")):
                if re.match(r"^\s*(-|\d+\.)\s", lines[i]):
                    items.append(re.sub(r"^\s*(-|\d+\.)\s", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if re.match(r"^\s*\d+\.", ln) else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(it)}</li>" for it in items) + f"</{tag}>")
        elif ln.strip():
            para = [ln]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|```|\||\s*-\s|\s*\d+\.\s)", lines[i]):
                para.append(lines[i])
                i += 1
            out.append("<p>" + inline(" ".join(para)) + "</p>")
        else:
            i += 1
    return "\n".join(out)


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    if shutil.which("pandoc"):
        css = HERE / "_manual.css"
        css.write_text(CSS, encoding="utf-8")
        ok = _run(["pandoc", SRC.name, "-s", "--toc", "--toc-depth=2", "-c", css.name,
                   "--embed-resources", "--metadata", "title=scitech-librarian - User Manual",
                   "-o", OUT_HTML.name], HERE)
        css.unlink()
        print(f"html via {'pandoc' if ok else 'pandoc FAILED'}")
        if not ok:
            OUT_HTML.write_text(_wrap(md_to_html_min(text)), encoding="utf-8")
    else:
        OUT_HTML.write_text(_wrap(md_to_html_min(text)), encoding="utf-8")
        print("html via builtin converter (install pandoc for a nicer one)")
    engine = next((e for e in ("xelatex", "lualatex", "pdflatex") if shutil.which(e)), None)
    if shutil.which("pandoc") and engine:
        ok = _run(["pandoc", SRC.name, "--toc", "--toc-depth=2", f"--pdf-engine={engine}",
                   "-V", "geometry:margin=2.2cm", "-V", "colorlinks=true", "-V", "mainfont=",
                   "-o", OUT_PDF.name], HERE)
        print(f"pdf via pandoc+{engine}" if ok else "pdf via pandoc FAILED")
    else:
        ok = False
    if not ok:
        import report
        report._pdf_builtin(re.sub(r"<[^>]+>", "", md_to_html_min(text)), OUT_PDF)
        print("pdf via builtin writer (install pandoc + a TeX engine for a typeset manual)")
    return 0


def _wrap(body: str) -> str:
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>scitech-librarian - User Manual</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")


if __name__ == "__main__":
    sys.exit(main())
