#!/usr/bin/env python3
"""Build readable, reproducible PDF, EPUB 3, and Markdown series editions.

Only the six verified, sanitized articles in content/essays/ are used. Never
read the private Substack export, subscriber lists, or article summaries as
substitutes for the original author-owned texts.

The PDF contains linked references and a document table of contents. The EPUB
contains semantic XHTML chapters, linked references, and an EPUB 3 navigation
file. All editions are generated from the same preserved HTML input.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup, NavigableString, Tag
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer,

)
from reportlab.platypus.tableofcontents import TableOfContents

SERIES = "Forward Science"
AUTHOR = "Mateo H. Petel"
STAMP = (2026, 6, 27, 0, 0, 0)
ZIP_STAMP = (2026, 6, 27, 0, 0, 0)
BASE = "https://fraware.github.io/forward-science"
REMOVABLE_FOOTER = "https://mateopetel.substack.com/subscribe?"


def chapters(root: Path) -> list[dict]:
    """Return immutable chapter content in its intended editorial sequence."""
    manifest = json.loads((root / 'content/essays.json').read_text(encoding='utf-8'))
    provenance = json.loads((root / 'content/import-provenance.json').read_text(encoding='utf-8'))
    if len(manifest) != 6 or len(provenance) != 6:
        raise ValueError('Expected precisely six verified chapters')
    import hashlib
    result = []
    for essay, record in zip(manifest, provenance, strict=True):
        source = root / 'content/essays' / (essay['slug'] + '.html')
        body = source.read_text(encoding='utf-8').strip()
        if record['slug'] != essay['slug'] or hashlib.sha256(body.encode()).hexdigest() != record['rendered_sha256']:
            raise ValueError('Source provenance mismatch for ' + essay['slug'])
        soup = BeautifulSoup(body, 'html.parser')
        ps = soup.find_all('p', recursive=False)
        if ps and ps[-1].find('a', href=REMOVABLE_FOOTER):
            ps[-1].decompose()
        if not soup.find_all('p'):
            raise ValueError('Missing paragraphs: ' + essay['slug'])
        result.append({**essay, 'soup': soup})
    return result


def inline_md(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return str(node).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]')
    inside = ''.join(inline_md(child) for child in node.children)
    if node.name in ('i', 'em'):
        return '*' + inside + '*'
    if node.name in ('strong', 'b'):
        return '**' + inside + '**'
    if node.name == 'a':
        return '[' + inside + '](' + str(node.get('href', '')).replace(')', '%29') + ')'
    if node.name == 'sup':
        return '^(' + inside + ')'
    return inside


def markdown(ch: list[dict], base_url: str) -> str:
    lines = [f'# {SERIES}', '', f'{AUTHOR} · June 2026', '',
             'Six essays on scientific discovery, institutional practice, and AI.', '',
             '## Contents', '']
    for essay in ch:
        lines.append(f'- [{essay["number"]} · {essay["title"]}](#{essay["slug"]})')
    lines.append('')
    for essay in ch:
        lines += [f'<a id="{essay["slug"]}"></a>', '',
                  f'## {essay["number"]} · {essay["title"]}', '',
                  '*' + essay['subtitle'] + '*', '',
                  f'{AUTHOR} · {essay["date"]}', '']
        for p in essay['soup'].find_all('p', recursive=False):
            lines.append(''.join(inline_md(n) for n in p.children).strip())
            lines.append('')
        lines += [f'Original publication: {essay["original_url"]}', '',
                  f'Web edition: {base_url}/{essay["slug"]}/', '', '---', '']
    return '\n'.join(lines).rstrip() + '\n'


def epub_xhtml(essay: dict) -> str:
    body = ''.join(str(p) for p in essay['soup'].find_all('p', recursive=False))
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en"><head>
<title>{html.escape(essay['title'])}</title>
<link href="style.css" rel="stylesheet" type="text/css" />
</head><body><section epub:type="chapter" xmlns:epub="http://www.idpf.org/2007/ops">
<h1>{html.escape(essay['number'])} · {html.escape(essay['title'])}</h1>
<p class="subtitle">{html.escape(essay['subtitle'])}</p>
<p class="byline">{AUTHOR} · {html.escape(essay['date'])}</p>
{body}
<p class="source">Originally published at <a href="{html.escape(essay['original_url'], quote=True)}">Critical Systems</a>.</p>
</section></body></html>'''


def put(z: zipfile.ZipFile, name: str, data: str | bytes, *, compress: bool = True) -> None:
    info = zipfile.ZipInfo(name, date_time=ZIP_STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    z.writestr(info, data.encode('utf-8') if isinstance(data, str) else data)


def build_epub(path: Path, ch: list[dict]) -> None:
    nav = ''.join(f'<li><a href="{e["slug"]}.xhtml">{html.escape(e["number"])} · {html.escape(e["title"])}</a></li>' for e in ch)
    contents = f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en">
<head><title>Contents</title></head><body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol>{nav}</ol></nav></body></html>'''
    entries = '\n'.join(f'<item id="c{i}" href="{e["slug"]}.xhtml" media-type="application/xhtml+xml"/>' for i, e in enumerate(ch))
    spine = ''.join(f'<itemref idref="c{i}"/>' for i in range(len(ch)))
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">urn:uuid:5c0fdd6d-8b4e-57d8-8c13-e2098d12f6ae</dc:identifier>
<dc:title>{SERIES}</dc:title><dc:creator>{AUTHOR}</dc:creator>
<dc:language>en</dc:language><dc:date>2026-06-27</dc:date>
<meta property="dcterms:modified">2026-06-27T00:00:00Z</meta>
</metadata><manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="css" href="style.css" media-type="text/css"/>
{entries}</manifest><spine>{spine}</spine></package>'''
    container = '''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''
    css = '''body{font-family:serif;line-height:1.55;max-width:42em;margin:0 auto}
h1{font-size:1.8em;line-height:1.18}p{margin:.85em 0}
.subtitle{font-style:italic}.byline,.source{font-size:.82em;color:#555}
a{color:inherit;text-decoration:underline}'''
    with zipfile.ZipFile(path, 'w') as z:
        put(z, 'mimetype', 'application/epub+zip', compress=False)
        put(z, 'META-INF/container.xml', container)
        put(z, 'EPUB/content.opf', opf)
        put(z, 'EPUB/nav.xhtml', contents)
        put(z, 'EPUB/style.css', css)
        for essay in ch:
            put(z, 'EPUB/' + essay['slug'] + '.xhtml', epub_xhtml(essay))


class PublicationDoc(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(filename, pagesize=A5, leftMargin=43, rightMargin=43,
                         topMargin=53, bottomMargin=54,
                         title=SERIES, author=AUTHOR,
                         pageCompression=1, invariant=1)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='reading', frames=[frame], onPage=self.page_number))

    def page_number(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont('Times-Roman', 8)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(self.leftMargin, 25, SERIES)
        canvas.drawRightString(A5[0]-self.rightMargin, 25, str(doc.page))
        canvas.restoreState()

    def afterFlowable(self, flowable) -> None:
        if isinstance(flowable, Paragraph) and getattr(flowable, 'is_chapter', False):
            key = flowable.bookmark
            self.canv.bookmarkPage(key)
            self.notify('TOCEntry', (0, flowable.getPlainText(), self.page, key))


def pdf_markup(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return html.escape(str(node))
    body = ''.join(pdf_markup(child) for child in node.children)
    if node.name in ('em','i'):
        return '<i>'+body+'</i>'
    if node.name in ('b','strong'):
        return '<b>'+body+'</b>'
    if node.name == 'a':
        href = str(node.get('href',''))
        if href.startswith('https://'):
            return '<link href="'+html.escape(href, quote=True)+'">'+body+'</link>'
    if node.name == 'sup':
        return '<super>'+body+'</super>'
    return body


def build_pdf(path: Path, ch: list[dict]) -> None:
    paper = colors.HexColor('#222222')
    title = ParagraphStyle('Title', fontName='Times-Roman', fontSize=27,
                           leading=33, alignment=TA_CENTER, textColor=paper, spaceAfter=15)
    subtitle = ParagraphStyle('Sub', fontName='Times-Italic', fontSize=12,
                              leading=17, alignment=TA_CENTER, textColor=paper, spaceAfter=15)
    byline = ParagraphStyle('Byline', fontName='Times-Roman', fontSize=9,
                            leading=12, alignment=TA_CENTER, textColor=colors.HexColor('#555555'), spaceAfter=24)
    chapter_title = ParagraphStyle('Chapter', fontName='Times-Roman', fontSize=20,
                                   leading=26, textColor=paper, spaceAfter=18)
    prose = ParagraphStyle('Body', fontName='Times-Roman', fontSize=10.5,
                           leading=15.7, textColor=paper, spaceAfter=12)
    source_style = ParagraphStyle('Source', parent=prose, fontSize=8, leading=12,
                                  textColor=colors.HexColor('#555555'))
    doc = PublicationDoc(str(path))
    doc.allowSplitting = 1
    story = [Spacer(1, 105), Paragraph(SERIES, title),
             Paragraph('Six essays on scientific discovery, institutions and AI', subtitle),
             Paragraph(AUTHOR + ' · June 2026', byline), PageBreak(),
             Paragraph('Contents', chapter_title)]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle('TOCEntry', fontName='Times-Roman', fontSize=10,
                                      leading=19, leftIndent=0, firstLineIndent=0)]
    story.extend([toc, PageBreak()])
    for i, essay in enumerate(ch):
        if i:
            story.append(PageBreak())
        h = Paragraph(html.escape(essay['number']+' · '+essay['title']), chapter_title)
        h.is_chapter = True
        h.bookmark = 'chapter-'+essay['slug']
        story.extend([h, Paragraph(html.escape(essay['subtitle']), subtitle),
                      Paragraph(AUTHOR+' · '+essay['date'], byline)])
        for p in essay['soup'].find_all('p', recursive=False):
            marked = ''.join(pdf_markup(child) for child in p.children)
            story.append(Paragraph(marked, prose))
        story.append(Paragraph('Original publication: <link href="'+
                               html.escape(essay['original_url'],quote=True)+'">'+
                               html.escape(essay['original_url'])+'</link>', source_style))
    doc.multiBuild(story, maxPasses=4)


def build(root: Path, out: Path, base_url: str = BASE) -> list[Path]:
    ch = chapters(root)
    out.mkdir(parents=True, exist_ok=True)
    md = out / 'forward-science.md'
    epub = out / 'forward-science.epub'
    pdf = out / 'forward-science.pdf'
    md.write_text(markdown(ch, base_url), encoding='utf-8')
    build_epub(epub, ch)
    build_pdf(pdf, ch)
    return [md, epub, pdf]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--base-url', default=BASE)
    args = parser.parse_args()
    out = args.out or args.root / 'site/downloads'
    for path in build(args.root, out, args.base_url):
        print(path, path.stat().st_size, 'bytes')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
