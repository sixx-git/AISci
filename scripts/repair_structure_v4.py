# -*- coding: utf-8 -*-
"""Repair structural corruption in v4_fixed.docx (v2, precise):
- Real section headings carry a GUID pStyle; manual-TOC lines are Normal (no pStyle).
- Mis-matching TOC lines earlier grabbed half the doc; now we require is_heading().
1) Delete orphaned duplicate code tree stuck between Ch8 bridge and real 9.2.
2) Move the real 九 block (九 heading -> 前端交互入口) to right after the Ch8 bridge.
3) Fix reversed 1.2 summary bullet order.
lxml + re-pack (no python-docx save) to preserve val='1'.
"""
import zipfile, shutil
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
SRC = "D:/Workplace/AISci/output/联邦智研_大创申报书_v4_fixed.docx"
BAK = SRC + ".pre_structfix.bak"
shutil.copyfile(SRC, BAK)

z = zipfile.ZipFile(SRC)
doc = etree.fromstring(z.read("word/document.xml"))
body = doc.find('{%s}body' % W)

def ptext(p):
    return ''.join(p.itertext())

def is_heading(p):
    ppr = p.find('{%s}pPr' % W)
    if ppr is None:
        return False
    ps = ppr.find('{%s}pStyle' % W)
    if ps is None:
        return False
    return ps.get('{%s}val' % W) not in (None, 'Normal')

ps = body.findall('{%s}p' % W)

# 1) bridge paragraph (Ch8 -> 附录二 pointer)
bridge = next(p for p in ps if '移入附录二' in ptext(p))
# 2) REAL 九 heading (heading style + text)
ch9 = next(p for p in ps if ptext(p).strip().startswith('九、源代码') and is_heading(p))
# 3) end of 九 block
end9 = next(p for p in ps if ptext(p).strip() == '前端交互入口')
# 4) REAL 9.2 heading (after which 9.3, 十, 附录 follow)
h92 = next(p for p in ps if ptext(p).strip().startswith('9.2 ') and is_heading(p))

# --- delete orphan duplicate code tree between bridge and real 9.2 ---
tree_a = []
cap = False
for p in ps:
    if p is bridge:
        cap = True
        continue
    if cap and p is h92:
        break
    if cap:
        t = ptext(p).strip()
        if t.startswith(('├', '│', '└')) or t == 'AISci/':
            tree_a.append(p)
for p in tree_a:
    p.getparent().remove(p)

# --- re-collect after deletion, then move real 九 block after bridge ---
ps = body.findall('{%s}p' % W)
ch9 = next(p for p in ps if ptext(p).strip().startswith('九、源代码') and is_heading(p))
end9 = next(p for p in ps if ptext(p).strip() == '前端交互入口')
block = []
cap = False
for p in ps:
    if p is ch9:
        cap = True
    if cap:
        block.append(p)
    if p is end9:
        break
anchor = bridge
for p in block:
    anchor.addnext(p)
    anchor = p

# --- fix reversed 1.2 summary bullets ---
ps = body.findall('{%s}p' % W)
h12 = next(p for p in ps if ptext(p).strip() == '1.2 核心研究问题' and is_heading(p))
h13 = next(p for p in ps if ptext(p).strip() == '1.3 技术路线与解决思路' and is_heading(p))
bullets = []
cap = False
for p in ps:
    if p is h12:
        cap = True
        continue
    if cap and p is h13:
        break
    if cap and ptext(p).strip().startswith('•'):
        bullets.append(p)
desired = ['证据溯源', '质量控制', '迭代优化']
bullets_sorted = sorted(bullets, key=lambda p: desired.index(
    next(k for k in desired if k in ptext(p))))
for p in bullets:
    p.getparent().remove(p)
anchor = h13
for p in reversed(bullets_sorted):
    anchor.addprevious(p)
    anchor = p

# --- write back ---
xml = etree.tostring(doc, xml_declaration=True, encoding='UTF-8', standalone=True)
parts = {n: (xml if n == 'word/document.xml' else z.read(n)) for n in z.namelist()}
with zipfile.ZipFile(SRC, 'w', zipfile.ZIP_DEFLATED) as z2:
    for n, data in parts.items():
        z2.writestr(n, data)

print("STRUCTURE REPAIR v2 DONE")
print("  removed orphan code-tree paras:", len(tree_a))
print("  moved 九 block paras:", len(block))
print("  reordered 1.2 bullets:", len(bullets))
