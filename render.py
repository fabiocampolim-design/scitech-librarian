#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Fabio Campolim
"""
render.py -- renderers for scitech-librarian reports.

report.py builds a format-neutral document (a list of nodes); this module
turns it into Markdown, HTML, LaTeX and plain text, draws the PRISMA 2020
flow (ASCII / SVG / TikZ) and produces the PDF (LaTeX engines -> pandoc ->
a built-in stdlib writer). Not a command-line tool. Stdlib only.

Document model
--------------
  ("h", level, text)   ("p", text)   ("ul", [items])   ("code", text)
  ("table", headers, rows)   ("prisma", numbers)   ("hr",)
Table cells are strings or ("link", text, url). Paragraph text may carry
`inline code` which HTML and LaTeX render as code.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import i18n as _i18n

VERSION_LABEL = "scitech-librarian"


# ---------------------------------------------------------------------------
# PRISMA flow diagram helpers
# ---------------------------------------------------------------------------

def _tr(pn: dict):
    """The translator for a PRISMA-numbers dict (report.build stores the
    report language under pn['lang']; absent = English)."""
    return _i18n.translator(pn.get("lang"))


def _flow_boxes(pn: dict) -> list[tuple[str, list[str]]]:
    """(key, lines) for the ASCII / TikZ / SVG renderers. The 'other' boxes
    exist only when records came in via other methods."""
    _ = _tr(pn)
    m = _.num                                   # None -> '--'
    ident = [f"{b}: {m(k)}" for b, k in pn["identified_by"].items()]
    boxes = [
        ("id-left", [_("Records identified from databases"), _("(n = {n})", n=m(pn["identified"]))] + ident),
        ("id-right", [_("Records removed before screening:"),
                      _("automation tools (venue filter) (n = {n})", n=m(pn["automation_removed"])),
                      _("duplicates removed (n = {n})", n=m(pn["duplicates_removed"]))]),
        ("sc-left", [_("Records screened (n = {n})", n=m(pn["screened"]))]),
        ("sc-right", [_("Records excluded (n = {n})", n=m(pn["excluded"]))]),
        ("sc-left2", [_("Reports sought for retrieval (n = {n})", n=m(pn["sought"]))]),
        ("sc-right2", [_("Reports not retrieved (n = {n})", n=m(pn["not_retrieved"]))]),
        ("sc-left3", [_("Reports assessed for eligibility (n = {n})", n=m(pn["assessed"]))]),
        ("sc-right3", [_("Reports excluded:")] + (
            [f"{r} (n = {m(k)})" for r, k in pn["excluded_reasons"].items()] or ["(n = --)"])),
        ("in-left", [_("Studies included in review (n = {n})", n=m(pn["studies_included"])),
                     _("Reports of included studies (n = {n})", n=m(pn["reports_included"]))]),
    ]
    if pn.get("other_by"):
        boxes += [
            ("ot-id", [_("Records identified via other methods"), _("(n = {n})", n=m(pn["other"]))]
                      + [f"{k}: {m(v)}" for k, v in pn["other_by"].items()]),
            ("ot-sought", [_("Reports sought for retrieval (n = {n})", n=m(pn["other_sought"])),
                           _("not retrieved (n = {n})", n=m(pn["other_not_retrieved"]))]),
            ("ot-assessed", [_("Reports assessed for eligibility (n = {n})", n=m(pn["other_assessed"]))]
                            + [_("excluded: {r} (n = {n})", r=r, n=m(k))
                               for r, k in pn["other_excluded_reasons"].items()]),
        ]
    return boxes


def _ascii_flow(pn: dict) -> str:
    _ = _tr(pn)
    boxes = dict(_flow_boxes(pn))
    W = 44

    def box(lines):
        wrapped = [w for ln in lines for w in (textwrap.wrap(ln, W - 4) or [""])]
        top = "+" + "-" * (W - 2) + "+"
        return [top] + [f"| {w:<{W - 4}} |" for w in wrapped] + [top]

    def pair(left, right, arrow=True):
        L, R = box(left), box(right) if right else []
        h = max(len(L), len(R))
        L += [" " * W] * (h - len(L))
        R += [" " * W] * (h - len(R))
        mid = h // 2
        out = []
        for i in range(h):
            conn = " --> " if (arrow and right and i == mid) else "     "
            out.append(L[i] + conn + R[i])
        return out

    arrow = [" " * (W // 2) + "|", " " * (W // 2) + "v"]
    lines = [_("IDENTIFICATION")]
    lines += pair(boxes["id-left"], boxes["id-right"])
    if "ot-id" in boxes:
        lines += ["", _("IDENTIFICATION VIA OTHER METHODS")]
        lines += pair(boxes["ot-id"], boxes["ot-sought"])
        lines += pair(boxes["ot-assessed"], None, arrow=False)
    lines += arrow + [_("SCREENING")]
    lines += pair(boxes["sc-left"], boxes["sc-right"])
    lines += arrow
    lines += pair(boxes["sc-left2"], boxes["sc-right2"])
    lines += arrow
    lines += pair(boxes["sc-left3"], boxes["sc-right3"])
    lines += arrow + [_("INCLUDED")]
    lines += pair(boxes["in-left"], None, arrow=False)
    return "\n".join(ln.rstrip() for ln in lines)


def _svg_flow(pn: dict) -> str:
    _ = _tr(pn)
    boxes = dict(_flow_boxes(pn))
    bw, lh, pad, gap = 300, 15, 10, 60
    x_left, x_right = 110, 110 + bw + gap
    y = 20
    els, positions = [], {}
    order = [("id-left", "id-right")]
    if "ot-id" in boxes:
        order += [("ot-id", "ot-sought"), ("ot-assessed", None)]
    order += [("sc-left", "sc-right"), ("sc-left2", "sc-right2"),
              ("sc-left3", "sc-right3"), ("in-left", None)]
    labels = {"id-left": _("Identification"), "ot-id": _("Other methods"),
              "sc-left": _("Screening"), "in-left": _("Included")}

    def draw(key, x, y0):
        lines = [w for ln in boxes[key] for w in textwrap.wrap(ln, 42) or [""]]
        h = len(lines) * lh + 2 * pad
        els.append(f'<rect x="{x}" y="{y0}" width="{bw}" height="{h}" rx="4" '
                   f'fill="var(--box)" stroke="var(--line)"/>')
        for i, ln in enumerate(lines):
            els.append(f'<text x="{x + pad}" y="{y0 + pad + lh * (i + 1) - 4}" '
                       f'font-size="11" fill="var(--fg)">{html.escape(ln)}</text>')
        positions[key] = (x, y0, h)
        return h

    for left, right in order:
        if left in labels:
            els.append(f'<text x="10" y="{y + 14}" font-size="11" font-weight="bold" '
                       f'fill="var(--fg)" transform="rotate(-90 10,{y + 14})" '
                       f'text-anchor="end">{labels[left]}</text>')
        h = draw(left, x_left, y)
        if right:
            hr = draw(right, x_right, y)
            els.append(f'<line x1="{x_left + bw}" y1="{y + h // 2}" x2="{x_right}" '
                       f'y2="{y + h // 2}" stroke="var(--line)" marker-end="url(#arr)"/>')
            h = max(h, hr)
        y += h + 30
    lefts = [k for k, _ in order]
    for a, b in zip(lefts, lefts[1:]):
        xa, ya, ha = positions[a]
        xb, yb, _h = positions[b]              # not `_`: that is the translator
        els.append(f'<line x1="{xa + bw // 2}" y1="{ya + ha}" x2="{xb + bw // 2}" y2="{yb}" '
                   f'stroke="var(--line)" marker-end="url(#arr)"/>')
    width = x_right + bw + 20
    return (f'<svg class="prisma" viewBox="0 0 {width} {y}" width="100%" '
            f'style="max-width:{width}px" xmlns="http://www.w3.org/2000/svg">'
            f'<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" '
            f'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="var(--line)"/></marker></defs>'
            + "".join(els) + "</svg>")


def _tikz_flow(pn: dict) -> str:
    _ = _tr(pn)
    boxes = dict(_flow_boxes(pn))
    lab = {k: _tex(_(k)) for k in ("Identification", "Other methods", "Screening", "Included")}

    def node(key):
        return " \\\\ ".join(_tex(w) for ln in boxes[key] for w in textwrap.wrap(ln, 40))

    out = [
        "\\begin{center}\\begin{tikzpicture}[node distance=9mm and 12mm,",
        "  box/.style={draw, rounded corners=2pt, text width=62mm, align=left, font=\\scriptsize},",
        "  lab/.style={rotate=90, font=\\scriptsize\\bfseries}]",
        f"\\node[box] (id) {{{node('id-left')}}};",
        f"\\node[box, right=of id] (idr) {{{node('id-right')}}};",
    ]
    prev = "id"
    if "ot-id" in boxes:
        out += [f"\\node[box, below=of id] (ot) {{{node('ot-id')}}};",
                f"\\node[box, right=of ot] (otr) {{{node('ot-sought')}}};",
                f"\\node[box, below=of ot] (ota) {{{node('ot-assessed')}}};",
                f"\\node[lab, left=3mm of ot] {{{lab['Other methods']}}};",
                "\\draw[->] (ot) -- (otr); \\draw[->] (ot) -- (ota); \\draw[->] (id) -- (ot);"]
        prev = "ota"
    out += [
        f"\\node[box, below=of {prev}] (sc) {{{node('sc-left')}}};",
        f"\\node[box, right=of sc] (scr) {{{node('sc-right')}}};",
        f"\\node[box, below=of sc] (sc2) {{{node('sc-left2')}}};",
        f"\\node[box, right=of sc2] (sc2r) {{{node('sc-right2')}}};",
        f"\\node[box, below=of sc2] (sc3) {{{node('sc-left3')}}};",
        f"\\node[box, right=of sc3] (sc3r) {{{node('sc-right3')}}};",
        f"\\node[box, below=of sc3] (inc) {{{node('in-left')}}};",
        f"\\node[lab, left=3mm of id] {{{lab['Identification']}}};",
        f"\\node[lab, left=3mm of sc2] {{{lab['Screening']}}};",
        f"\\node[lab, left=3mm of inc] {{{lab['Included']}}};",
        "\\draw[->] (id) -- (idr); \\draw[->] (sc) -- (scr); \\draw[->] (sc2) -- (sc2r);",
        "\\draw[->] (sc3) -- (sc3r);",
        f"\\draw[->] ({prev}) -- (sc); \\draw[->] (sc) -- (sc2); \\draw[->] (sc2) -- (sc3);",
        "\\draw[->] (sc3) -- (inc);",
        "\\end{tikzpicture}\\end{center}",
    ]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _cell_text(c) -> str:
    return c[1] if isinstance(c, tuple) else str(c)


def render_md(title: str, nodes: list) -> str:
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "h":
            out.append("#" * nd[1] + " " + nd[2] + "\n")
        elif k == "p":
            out.append(nd[1] + "\n")
        elif k == "ul":
            out.append("\n".join(f"- {it}" for it in nd[1]) + "\n")
        elif k == "code":
            out.append("```\n" + nd[1] + "\n```\n")
        elif k == "table":
            esc = lambda c: (f"[{c[1]}]({c[2]})" if isinstance(c, tuple)  # noqa: E731
                             else str(c).replace("|", "\\|").replace("\n", " "))
            out.append("| " + " | ".join(nd[1]) + " |")
            out.append("|" + "---|" * len(nd[1]))
            for row in nd[2]:
                out.append("| " + " | ".join(esc(c) for c in row) + " |")
            out.append("")
        elif k == "prisma":
            out.append("```\n" + _ascii_flow(nd[1]) + "\n```\n")
        elif k == "hr":
            out.append("---\n")
    return "\n".join(out)


def render_txt(title: str, nodes: list, width: int = 88) -> str:
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "h":
            t = nd[2]
            out.append("")
            out.append(t.upper() if nd[1] == 1 else t)
            out.append(("=" if nd[1] == 1 else "-" if nd[1] == 2 else "~")[0] * min(len(t), width))
        elif k == "p":
            out.append(textwrap.fill(nd[1], width))
            out.append("")
        elif k == "ul":
            for it in nd[1]:
                out.append(textwrap.fill(it, width, initial_indent="  * ", subsequent_indent="    "))
            out.append("")
        elif k == "code":
            out.extend("    " + ln for ln in nd[1].splitlines())
            out.append("")
        elif k == "table":
            out.append(_txt_table(nd[1], nd[2], width))
        elif k == "prisma":
            out.append(_ascii_flow(nd[1]))
            out.append("")
    return "\n".join(out).strip() + "\n"


def _txt_table(headers, rows, width) -> str:
    cells = [[_cell_text(c) for c in r] for r in rows]
    ncol = len(headers)
    widths = [max([len(headers[i])] + [len(r[i]) for r in cells if i < len(r)]) for i in range(ncol)]
    while sum(widths) + 3 * (ncol - 1) > width and max(widths) > 12:
        widths[widths.index(max(widths))] -= 1
    lines = []

    def fmt(r):
        wrapped = [textwrap.wrap(r[i] if i < len(r) else "", widths[i]) or [""] for i in range(ncol)]
        h = max(len(w) for w in wrapped)
        return ["   ".join((w[j] if j < len(w) else "").ljust(widths[i])
                           for i, w in enumerate(wrapped)).rstrip() for j in range(h)]

    lines += fmt(headers)
    lines.append("   ".join("-" * w for w in widths))
    for r in cells:
        lines += fmt(r)
    return "\n".join(lines) + "\n"


_CSS = """
:root{--fg:#1b1b1b;--bg:#fff;--muted:#666;--line:#999;--box:#f6f6f6;--acc:#2a5db0}
@media(prefers-color-scheme:dark){:root{--fg:#e6e6e6;--bg:#151515;--muted:#aaa;--line:#888;--box:#222;--acc:#7aa7ff}}
body{font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg);max-width:1100px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.6rem}h2{border-bottom:1px solid var(--line);padding-bottom:.2rem;margin-top:2rem}
h4{margin:1.2rem 0 .2rem}table{border-collapse:collapse;width:100%;font-size:.88rem;margin:.6rem 0 1rem}
th,td{border:1px solid var(--line);padding:.3rem .5rem;text-align:left;vertical-align:top}
th{background:var(--box)}
pre{background:var(--box);padding:.6rem;overflow-x:auto;font-size:.82rem;white-space:pre-wrap}
a{color:var(--acc)}.wrap{overflow-x:auto}.meta{color:var(--muted)}
@media print{body{max-width:none;font-size:11pt}h2{page-break-after:avoid}}
"""


def render_html(title: str, nodes: list, lang: str = "en") -> str:
    e = html.escape
    out = [f"<!doctype html><html lang=\"{_i18n.html_lang(lang)}\"><head><meta charset=\"utf-8\">"
           f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           f"<title>{e(title)}</title><style>{_CSS}</style></head><body>"]
    for nd in nodes:
        k = nd[0]
        if k == "h":
            out.append(f"<h{nd[1]}>{e(nd[2])}</h{nd[1]}>")
        elif k == "p":
            out.append(f"<p>{_html_inline(nd[1])}</p>")
        elif k == "ul":
            out.append("<ul>" + "".join(f"<li>{_html_inline(i)}</li>" for i in nd[1]) + "</ul>")
        elif k == "code":
            out.append(f"<pre>{e(nd[1])}</pre>")
        elif k == "table":
            cell = lambda c: (f'<a href="{e(c[2])}">{e(c[1])}</a>' if isinstance(c, tuple)  # noqa: E731
                              else e(str(c)))
            out.append('<div class="wrap"><table><thead><tr>'
                       + "".join(f"<th>{e(h)}</th>" for h in nd[1]) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{cell(c)}</td>" for c in r) + "</tr>"
                                 for r in nd[2]) + "</tbody></table></div>")
        elif k == "prisma":
            out.append(_svg_flow(nd[1]))
        elif k == "hr":
            out.append("<hr>")
    out.append("</body></html>")
    return "\n".join(out)


def _html_inline(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"(https?://[^\s)]+)", r'<a href="\1">\1</a>', t)
    return t


_TEX_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
            "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\^{}",
            # a cell starting with [ right after \\ would be read as an optional
            # argument (real data: "[WITHDRAWN] ..." titles)
            "[": "{[}", "]": "{]}"}


def _tex(s: str) -> str:
    return "".join(_TEX_ESC.get(ch, ch) for ch in str(s))


def _tex_inline(s: str) -> str:
    parts = re.split(r"(`[^`]+`)", s)
    return "".join(f"\\texttt{{{_tex(p[1:-1])}}}" if p.startswith("`") and p.endswith("`") and len(p) > 1
                   else _tex(p) for p in parts)


def render_tex(title: str, nodes: list, version: str = "", lang: str = "en") -> str:
    # English keeps \today (byte-identical to earlier releases); the other
    # languages get the date written out, since no babel package is loaded.
    date = "\\today" if _i18n.normalize(lang) == "en" else _tex(_i18n.date(lang))
    out = [
        "\\documentclass[10pt,a4paper]{article}",
        "\\usepackage{iftex}",
        "\\ifPDFTeX\\usepackage[utf8]{inputenc}\\usepackage[T1]{fontenc}\\usepackage{lmodern}",
        "\\else\\usepackage{fontspec}\\fi",
        "\\usepackage[margin=2cm]{geometry}\\usepackage{longtable}\\usepackage{array}",
        "\\usepackage{tikz}\\usetikzlibrary{positioning,arrows.meta}",
        "\\usepackage{xurl}\\usepackage[hidelinks]{hyperref}\\usepackage{fancyvrb}",
        "\\setlength{\\parskip}{4pt}\\setlength{\\parindent}{0pt}\\setlength{\\tabcolsep}{3pt}",
        "\\tikzset{>={Latex}}",
        f"\\title{{{_tex(title)}}}\\author{{{VERSION_LABEL} {version}}}\\date{{{date}}}",
        "\\begin{document}\\maketitle",
    ]
    sec = {1: None, 2: "section", 3: "subsection", 4: "subsubsection"}
    for nd in nodes:
        k = nd[0]
        if k == "h":
            if sec.get(nd[1]):
                out.append(f"\\{sec[nd[1]]}*{{{_tex(nd[2])}}}")
        elif k == "p":
            out.append(_tex_inline(nd[1]) + "\n")
        elif k == "ul":
            out.append("\\begin{itemize}" + "".join(f"\\item {_tex_inline(i)}" for i in nd[1])
                       + "\\end{itemize}")
        elif k == "code":
            wrapped = "\n".join(w for ln in nd[1].splitlines()
                                for w in (textwrap.wrap(ln, 105, replace_whitespace=False,
                                                        drop_whitespace=False) or [""]))
            out.append("\\begin{Verbatim}[fontsize=\\scriptsize]\n" + wrapped
                       + "\n\\end{Verbatim}")
        elif k == "table":
            out.append(_tex_table(nd[1], nd[2]))
        elif k == "prisma":
            out.append(_tikz_flow(nd[1]))
        elif k == "hr":
            out.append("\\hrule")
    out.append("\\end{document}")
    return "\n".join(out)


def _tex_table(headers, rows) -> str:
    """Column widths proportional to content length (capped), so a table
    whose long text sits in the last column still reads."""
    n = len(headers)
    lens = []
    for i in range(n):
        vals = [len(_cell_text(r[i])) for r in rows if i < len(r)] + [len(headers[i])]
        lens.append(min(max(vals), 60) + 4)
    total = sum(lens)
    # usable width: \linewidth minus 2*\tabcolsep (3pt) per column, so a
    # ten-column counts table does not run off the page
    usable = 0.98 - 0.0125 * n
    widths = [max(0.045, usable * ln / total) for ln in lens]
    scale = usable / sum(widths)
    spec = "".join(f"p{{{w * scale:.3f}\\linewidth}}" for w in widths)
    # % starts a TeX comment even inside \href's target: an encoded DOI
    # (10.1/a%2Fb) silently ate the rest of its row (3.5.0).
    cell = lambda c: (f"\\href{{{c[2].replace('%', chr(92) + '%')}}}{{{_tex(c[1])}}}"  # noqa: E731
                      if isinstance(c, tuple) else _tex(c))
    lines = ["{\\scriptsize\\begin{longtable}{" + spec + "}", "\\hline",
             " & ".join(f"\\textbf{{{_tex(h)}}}" for h in headers) + " \\\\ \\hline",
             "\\endhead"]
    for r in rows:
        r = list(r) + [""] * (n - len(r))
        lines.append(" & ".join(cell(c) for c in r[:n]) + " \\\\")
    lines += ["\\hline", "\\end{longtable}}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PDF: LaTeX -> pandoc -> built-in text writer
# ---------------------------------------------------------------------------

def _pdf_builtin(text: str, path: Path) -> None:
    """Minimal stdlib PDF: Courier 8pt, wrapped monospaced text, page breaks.
    Ugly but dependency-free -- the guarantee that --format pdf never fails."""
    lines = [w for ln in text.splitlines() for w in (textwrap.wrap(ln, 100,
             replace_whitespace=False, drop_whitespace=False) or [""])]
    per_page = 70
    pages = [lines[i:i + per_page] for i in range(0, max(len(lines), 1), per_page)]

    def esc(s):
        # cp1252 = WinAnsiEncoding (the font's declared encoding): dashes,
        # curly quotes, ellipsis, oe ligature survive; the rest becomes '?'
        s = s.encode("cp1252", "replace").decode("cp1252")
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objs = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    # WinAnsiEncoding: the Latin-1 bytes below render as accented letters
    # (StandardEncoding, the default, leaves é ç ã ü blank or wrong)
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    page_ids = []
    kids_placeholder = add(b"")
    for pg in pages:
        stream = "BT /F1 8 Tf 10 TL 36 806 Td " + " ".join(f"({esc(ln)}) Tj T*" for ln in pg) + " ET"
        sb = stream.encode("cp1252")
        cid = add(b"<< /Length " + str(len(sb)).encode() + b" >>\nstream\n" + sb + b"\nendstream")
        pid = add(f"<< /Type /Page /Parent {kids_placeholder} 0 R /MediaBox [0 0 595 842] "
                  f"/Resources << /Font << /F1 {font} 0 R >> >> /Contents {cid} 0 R >>".encode())
        page_ids.append(pid)
    objs[kids_placeholder - 1] = (f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] "
                                  f"/Count {len(page_ids)} >>").encode()
    catalog = add(f"<< /Type /Catalog /Pages {kids_placeholder} 0 R >>".encode())
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n"
            ).encode()
    path.write_bytes(bytes(out))


def _run(cmd: list, cwd: Path, timeout: int = 1800) -> bool:
    # 30 min per pass: a full-level report on a few thousand records is >1000
    # pages and takes xelatex several minutes.
    try:
        r = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def make_pdf(tex_path: Path, md_path: Path, txt: str, pdf_path: Path) -> str:
    """Try LaTeX engines, then pandoc, then the built-in writer. Returns the
    name of the method that produced the file."""
    cwd = pdf_path.parent
    stem = tex_path.stem
    for eng in ("xelatex", "lualatex", "pdflatex"):
        if shutil.which(eng):
            ok = all(_run([eng, "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd)
                     for _ in range(2))
            produced = cwd / f"{stem}.pdf"
            for ext in (".aux", ".log", ".out", ".toc"):
                try:
                    (cwd / f"{stem}{ext}").unlink()
                except OSError:
                    pass
            if ok and produced.exists():
                if produced != pdf_path:
                    produced.replace(pdf_path)
                return eng
    if shutil.which("pandoc") and md_path.exists():
        if _run(["pandoc", md_path.name, "-o", pdf_path.name], cwd) and pdf_path.exists():
            return "pandoc"
    _pdf_builtin(txt, pdf_path)
    return "builtin"


