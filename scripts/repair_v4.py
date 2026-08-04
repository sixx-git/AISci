# -*- coding: utf-8 -*-
# Comprehensive repair of v4:
#   (1) Remove the converter residue: <w:sdt> wrapping a broken auto-TOC field
#       (1 TOC + 52 HYPERLINK + 52 PAGE; 2 hyperlinks pointed to deleted bookmarks).
#   (2) Add the standard separator endnote/footnote entries (id 0,1) that the
#       generator omitted, fixing 4 dangling semantic references in settings.xml.
# Leaves the benign w:val="1" / charset warnings untouched (Word opens those fine).
import zipfile
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
SRC = "D:/Workplace/AISci/output/联邦智研_大创申报书_v4.docx"
FIX = "D:/Workplace/AISci/output/联邦智研_大创申报书_v4_fixed.docx"

z = zipfile.ZipFile(SRC)
parts = {n: z.read(n) for n in z.namelist()}
z.close()

# --- (1) remove TOC <w:sdt> from document.xml ---
doc = etree.fromstring(parts['word/document.xml'])
body = doc.find('{%s}body' % W)
removed = 0
for sdt in body.findall('{%s}sdt' % W):
    if 'TOC' in ''.join(sdt.itertext()) and 'HYPERLINK' in ''.join(sdt.itertext()):
        body.remove(sdt); removed += 1
parts['word/document.xml'] = etree.tostring(doc, xml_declaration=True, encoding='UTF-8', standalone=True)

# --- (2) add separator endnotes / footnotes (id 0,1) ---
def add_separators(part_name, tag):
    root = etree.fromstring(parts[part_name])
    existing = [e for e in root if e.get('{%s}id' % W) in ('0', '1')]
    if existing:
        return 0
    sep = etree.SubElement(root, '{%s}%s' % (W, tag))
    sep.set('{%s}type' % W, 'separator'); sep.set('{%s}id' % W, '0')
    p = etree.SubElement(sep, '{%s}p' % W)
    pPr = etree.SubElement(p, '{%s}pPr' % W)
    sp = etree.SubElement(pPr, '{%s}spacing' % W)
    sp.set('{%s}after' % W, '0'); sp.set('{%s}line' % W, '240'); sp.set('{%s}lineRule' % W, 'auto')
    r = etree.SubElement(p, '{%s}r' % W)
    etree.SubElement(r, '{%s}separator' % W)
    cont = etree.SubElement(root, '{%s}%s' % (W, tag))
    cont.set('{%s}type' % W, 'continuationSeparator'); cont.set('{%s}id' % W, '1')
    p2 = etree.SubElement(cont, '{%s}p' % W)
    pPr2 = etree.SubElement(p2, '{%s}pPr' % W)
    sp2 = etree.SubElement(pPr2, '{%s}spacing' % W)
    sp2.set('{%s}after' % W, '0'); sp2.set('{%s}line' % W, '240'); sp2.set('{%s}lineRule' % W, 'auto')
    r2 = etree.SubElement(p2, '{%s}r' % W)
    etree.SubElement(r2, '{%s}continuationSeparator' % W)
    parts[part_name] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    return 2

n_e = add_separators('word/endnotes.xml', 'endnote')
n_f = add_separators('word/footnotes.xml', 'footnote')
print("sdt removed:", removed, "| separator endnotes added:", n_e, "| separator footnotes added:", n_f)

# --- re-pack ---
with zipfile.ZipFile(FIX, 'w', zipfile.ZIP_DEFLATED) as z:
    for n, data in parts.items():
        z.writestr(n, data)
print("Re-packed ->", FIX)
