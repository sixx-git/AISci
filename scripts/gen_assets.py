#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate AISci internet+ defense PPT assets.
Dark tech style (deep navy + electric blue + gold). All visuals are TEXT-FREE.
Backgrounds: cover / content / dark-section / thankyou + gold-line.
Page visuals: v1..v18 (main visual per slide), no text so they stay license-clean.
"""
from PIL import Image, ImageDraw, ImageFilter
import math, random, os

W, H = 2000, 1125
CANVAS = (W, H)  # current target canvas size for radial/glow overlays

NAVY   = (10, 22, 40)
DARK   = (15, 29, 53)
EBLUE  = (56, 111, 196)
CYAN   = (63, 224, 255)
GOLD   = (201, 168, 76)
LGOLD  = (232, 213, 140)
WHITE  = (255, 255, 255)
GREY   = (120, 140, 170)
DIMRED = (205, 90, 90)
MIDBLUE= (40, 70, 130)

OUT = "D:/Workplace/AISci/output/AISci_ppt/assets"
os.makedirs(OUT, exist_ok=True)

# ---------- low level helpers ----------
def new_rgba(size=(W, H)):
    return Image.new('RGBA', size, (0, 0, 0, 0))

def vgrad(img, c1, c2):
    d = ImageDraw.Draw(img)
    h = img.height; w = img.width
    for y in range(h):
        r = c1[0] + (c2[0]-c1[0]) * y/h
        g = c1[1] + (c2[1]-c1[1]) * y/h
        b = c1[2] + (c2[2]-c1[2]) * y/h
        d.line([(0, y), (w, y)], fill=(int(r), int(g), int(b), 255))
    return img

def radial(cx, cy, radius, color, maxa=30, power=1.0):
    ov = new_rgba(CANVAS); od = ImageDraw.Draw(ov)
    step = max(2, radius//200)
    for r in range(radius, 0, -step):
        a = int(maxa * (1 - r/radius)**power)
        od.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(color[0], color[1], color[2], a))
    return ov

def glow(cx, cy, r, color, maxa=150, power=1.5):
    ov = new_rgba(CANVAS); od = ImageDraw.Draw(ov)
    step = max(2, r//160)
    for rr in range(r, 0, -step):
        a = int(maxa * (1 - rr/r)**power)
        od.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], fill=(color[0], color[1], color[2], a))
    return ov

def grid(img, step=70, color=(255,255,255), alpha=10):
    ov = new_rgba(img.size); od = ImageDraw.Draw(ov)
    w = img.width; h = img.height
    for x in range(0, w, step):
        od.line([(x,0),(x,h)], fill=(color[0],color[1],color[2],alpha))
    for y in range(0, h, step):
        od.line([(0,y),(w,y)], fill=(color[0],color[1],color[2],alpha))
    return Image.alpha_composite(img, ov)

def network(img, n, seed, spread, node_color, edge_color, edge_maxa=35, node_r=5, region=None):
    random.seed(seed)
    if region is None:
        region = (0, 0, img.width, img.height)
    pts = [(random.randint(region[0], region[2]), random.randint(region[1], region[3])) for _ in range(n)]
    ov = new_rgba(); od = ImageDraw.Draw(ov)
    for i in range(n):
        for j in range(i+1, n):
            dist = math.hypot(pts[i][0]-pts[j][0], pts[i][1]-pts[j][1])
            if dist < spread:
                a = int(edge_maxa*(1-dist/spread))
                od.line([pts[i], pts[j]], fill=(edge_color[0],edge_color[1],edge_color[2],a), width=1)
    for p in pts:
        od.ellipse([p[0]-node_r, p[1]-node_r, p[0]+node_r, p[1]+node_r],
                   fill=(node_color[0],node_color[1],node_color[2],210))
    return Image.alpha_composite(img, ov)

def save(img, name):
    img.convert('RGB').save(os.path.join(OUT, name))
    print("  saved", name)

# ---------- backgrounds ----------
def bg_cover():
    img = new_rgba()
    vgrad(img, (18, 30, 58), (6, 12, 26))
    img = Image.alpha_composite(img, radial(W-520, -120, 820, EBLUE, 34, 1.1))
    img = Image.alpha_composite(img, radial(120, H-120, 620, GOLD, 22, 1.2))
    img = grid(img, 76, (150,180,230), 8)
    img = network(img, 34, 7, 460, (150,200,245), EBLUE, 40, 4)
    save(img, "cover-bg.png")

def bg_content():
    img = new_rgba()
    vgrad(img, (12, 22, 42), (8, 14, 28))
    img = Image.alpha_composite(img, radial(W-260, 90, 520, EBLUE, 20, 1.3))
    img = Image.alpha_composite(img, radial(120, H-120, 460, (40,60,110), 16, 1.3))
    img = grid(img, 80, (120,150,200), 7)
    save(img, "content-bg.png")

def bg_dark():
    img = new_rgba()
    vgrad(img, (10, 20, 45), (16, 32, 62))
    d = ImageDraw.Draw(img)
    for i in range(-H, W+H, 64):
        d.line([(i,0),(i+H,H)], fill=(22,38,70,255), width=1)
    for cx, cy in [(110,110),(W-110,110),(110,H-110),(W-110,H-110)]:
        img = Image.alpha_composite(img, radial(cx, cy, 150, GOLD, 26, 1.4))
    save(img, "dark-section-bg.png")

def bg_thank():
    img = new_rgba()
    vgrad(img, (8, 18, 38), (20, 35, 65))
    img = Image.alpha_composite(img, radial(W//2, H//2, 640, GOLD, 20, 1.2))
    od = ImageDraw.Draw(img)
    for cx, cy in [(0,0),(W,0),(0,H),(W,H)]:
        dx = 1 if cx==0 else -1; dy = 1 if cy==0 else -1
        for i in range(220):
            a = int(28*(1-i/220))
            od.line([(cx+dx*i, cy),(cx, cy+dy*i)], fill=(GOLD[0],GOLD[1],GOLD[2],a), width=1)
    save(img, "thankyou-bg.png")

def gold_line():
    g = Image.new('RGBA', (900, 8), (0,0,0,0)); gd = ImageDraw.Draw(g)
    for x in range(900):
        r = int(201 + (232-201)*x/900); gg = int(168 + (213-168)*x/900); b = int(76 + (140-76)*x/900)
        gd.line([(x,0),(x,7)], fill=(r,gg,b,255))
    g.save(os.path.join(OUT, "gold-line.png")); print("  saved gold-line.png")

# ---------- page visuals (right-half slot 1000x1125 unless noted) ----------
def vis_right(size=(1000, 1125)):
    return Image.new('RGBA', size, (0,0,0,0))

def v1_cover():
    global CANVAS; CANVAS = (1000, 1125)
    img = vis_right()
    vgrad(img, (16, 28, 54), (6, 12, 26))
    img = Image.alpha_composite(img, radial(500, 560, 460, EBLUE, 30, 1.2))
    # knowledge graph: nodes + edges
    nodes = []
    random.seed(11)
    for _ in range(22):
        nodes.append((random.randint(80, 920), random.randint(120, 1000)))
    d = ImageDraw.Draw(img)
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            dist = math.hypot(nodes[i][0]-nodes[j][0], nodes[i][1]-nodes[j][1])
            if dist < 300:
                a = int(45*(1-dist/300))
                d.line([nodes[i], nodes[j]], fill=(90,150,220,a), width=1)
    # central bright core
    img = Image.alpha_composite(img, glow(500, 560, 120, CYAN, 170, 1.6))
    for p in nodes:
        d.ellipse([p[0]-6,p[1]-6,p[0]+6,p[1]+6], fill=(180,210,245,220))
    save(img, "v1_cover.png")

def v2_value():
    global CANVAS; CANVAS = (W, H)
    # split screen: left dim/grey chaos, right bright blue pipeline
    img = Image.new('RGBA', (W, H), (0,0,0,0))
    ld = ImageDraw.Draw(img)
    # left dim
    for y in range(H):
        v = 30 + 30*(1-y/H)
        ld.line([(0,y),(W//2,y)], fill=(int(v),int(v),int(v+10),255))
    # random grey dots (chaos)
    random.seed(3)
    for _ in range(360):
        x = random.randint(40, W//2-40); y = random.randint(40, H-40)
        r = random.randint(2,7)
        ld.ellipse([x-r,y-r,x+r,y+r], fill=(90,95,105,180))
    # right bright
    rd = ImageDraw.Draw(img)
    for y in range(H):
        rd.line([(W//2,y),(W,y)], fill=(14,30,60,255))
    img = Image.alpha_composite(img, radial(500, 560, 480, EBLUE, 28, 1.2))
    # pipeline nodes on right
    ry = [180, 360, 540, 720, 900]
    centers = [(3*W//4, y) for y in ry]
    pd = ImageDraw.Draw(img)
    prev=None
    for c in centers:
        if prev: pd.line([prev,c], fill=(90,180,235,180), width=4)
        prev=c
    for c in centers:
        img = Image.alpha_composite(img, glow(c[0], c[1], 60, CYAN, 150, 1.6))
        pd.ellipse([c[0]-10,c[1]-10,c[0]+10,c[1]+10], fill=(220,240,255,235))
    # divider
    pd.line([(W//2,0),(W//2,H)], fill=(GREY[0],GREY[1],GREY[2],120), width=2)
    save(img, "v2_value.png")

def v3_policy():
    global CANVAS; CANVAS = (1000, 1125)
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    d = ImageDraw.Draw(img)
    # rising bars (glowing blue) along a baseline
    base_y = 940
    xs = [120, 280, 440, 600, 760, 880]
    hs = [240, 330, 430, 560, 700, 860]
    for x, h in zip(xs, hs):
        col = (40, 90+int(h/12), 170+int(h/8))
        d.rectangle([x, base_y-h, x+90, base_y], fill=col+(255) if False else col)
        img = Image.alpha_composite(img, glow(x+45, base_y-h//2, 60, EBLUE, 60, 1.4))
    # arrow up
    d.line([(80, base_y),(900, 200)], fill=(LGOLD[0],LGOLD[1],LGOLD[2],200), width=3)
    save(img, "v3_policy.png")

def v4_pain():
    # three stacked abstract glyphs in dim red tones
    img = vis_right()
    vgrad(img, (16,18,30),(10,12,22))
    glyphs = [(500, 250), (500, 580), (500, 910)]
    for k,(cx,cy) in enumerate(glyphs):
        img = Image.alpha_composite(img, glow(cx, cy, 150, DIMRED, 70, 1.4))
        d = ImageDraw.Draw(img)
        # tangled ring
        for a in range(0, 360, 20):
            rad = math.radians(a + k*30)
            x1 = cx + 90*math.cos(rad); y1 = cy + 90*math.sin(rad)
            x2 = cx + 90*math.cos(rad+1.2); y2 = cy + 90*math.sin(rad+1.2)
            d.line([(x1,y1),(x2,y2)], fill=(210,120,120,200), width=2)
        d.ellipse([cx-12,cy-12,cx+12,cy+12], fill=(240,160,160,230))
        # broken link for 3rd
        if k==2:
            d.line([cx-70,cy-70,cx-30,cy-30], fill=(240,180,180,220), width=5)
            d.line([cx+30,cy+30,cx+70,cy+70], fill=(240,180,180,220), width=5)
    save(img, "v4_pain.png")

def v5_radial():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    img = Image.alpha_composite(img, radial(500, 560, 480, EBLUE, 26, 1.2))
    img = Image.alpha_composite(img, glow(500, 560, 110, CYAN, 180, 1.6))
    d = ImageDraw.Draw(img)
    import math as m
    angs = [i*math.pi/2 + math.pi/4 for i in range(4)]
    for a in angs:
        nx = 500 + 330*math.cos(a); ny = 560 + 330*math.sin(a)
        d.line([(500,560),(nx,ny)], fill=(120,180,235,170), width=3)
        img = Image.alpha_composite(img, glow(int(nx), int(ny), 80, EBLUE, 150, 1.5))
        d.ellipse([nx-22,ny-22,nx+22,ny+22], fill=(200,225,250,235))
    save(img, "v5_radial.png")

def v6_matrix():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    d = ImageDraw.Draw(img)
    panels = [(150, 200), (500, 380), (260, 760)]
    for (x,y) in panels:
        d.rounded_rectangle([x,y,x+520,y+260], radius=18, outline=(120,170,220,200), width=2)
        img = Image.alpha_composite(img, radial(x+260, y+130, 260, EBLUE, 18, 1.3))
        d.line([(x+40,y+120),(x+480,y+120)], fill=(100,150,210,160), width=2)
    save(img, "v6_matrix.png")

def v7_demo():
    # abstract SaaS UI window with pipeline steps
    img = vis_right()
    vgrad(img, (14,26,48),(8,14,28))
    d = ImageDraw.Draw(img)
    # window frame
    d.rounded_rectangle([70,120,930,1000], radius=20, outline=(120,170,220,220), width=3)
    d.rectangle([70,120,930,210], fill=(20,38,70,255))
    for i in range(3):
        d.ellipse([110+i*40,160,135+i*40,185], fill=(120,150,190,220))
    # pipeline chain
    steps = [(200,420),(420,560),(600,720),(780,860)]
    prev=None
    for c in steps:
        if prev: d.line([prev,c], fill=(110,180,235,180), width=4)
        prev=c
    for c in steps:
        img = Image.alpha_composite(img, glow(c[0], c[1], 70, CYAN, 150, 1.5))
        d.ellipse([c[0]-16,c[1]-16,c[0]+16,c[1]+16], fill=(220,240,255,235))
    # side bars
    d.rounded_rectangle([500,260,880,360], radius=12, outline=(90,140,200,160), width=2)
    save(img, "v7_demo.png")

def v8_arch():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    img = Image.alpha_composite(img, radial(500, 560, 500, EBLUE, 24, 1.2))
    img = Image.alpha_composite(img, glow(500, 560, 100, CYAN, 170, 1.6))
    d = ImageDraw.Draw(img)
    # 7-stage ring
    import math as m
    ring = [(500+360*math.cos(i*2*m.pi/7 - m.pi/2), 560+360*math.sin(i*2*m.pi/7 - m.pi/2)) for i in range(7)]
    for i in range(7):
        d.line([ring[i], ring[(i+1)%7]], fill=(110,170,225,150), width=3)
        d.line([(500,560), ring[i]], fill=(80,140,200,120), width=2)
        img = Image.alpha_composite(img, glow(int(ring[i][0]), int(ring[i][1]), 60, EBLUE, 140, 1.5))
        d.ellipse([ring[i][0]-14,ring[i][1]-14,ring[i][0]+14,ring[i][1]+14], fill=(200,225,250,235))
    save(img, "v8_arch.png")

def v9_innovation():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    img = Image.alpha_composite(img, radial(500, 560, 480, EBLUE, 24, 1.2))
    img = Image.alpha_composite(img, glow(500, 560, 110, CYAN, 175, 1.6))
    d = ImageDraw.Draw(img)
    import math as m
    pos = [(500,250),(810,560),(500,870),(190,560)]
    for p in pos:
        d.line([(500,560),p], fill=(120,180,235,170), width=3)
        img = Image.alpha_composite(img, glow(int(p[0]), int(p[1]), 85, GOLD, 150, 1.5))
        d.rounded_rectangle([p[0]-70,p[1]-55,p[0]+70,p[1]+55], radius=14, outline=(LGOLD[0],LGOLD[1],LGOLD[2],220), width=3)
    save(img, "v9_innovation.png")

def v10_barrier():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    d = ImageDraw.Draw(img)
    # left dim chat bubble
    d.rounded_rectangle([140,400,420,720], radius=30, outline=(110,120,135,200), width=3)
    d.line([(360,700),(420,760)], fill=(110,120,135,200), width=3)
    # right bright agent net
    img = Image.alpha_composite(img, radial(720, 560, 320, EBLUE, 26, 1.2))
    nodes=[(620,420),(820,460),(700,640),(860,700),(640,820)]
    for i in range(len(nodes)):
        for j in range(i+1,len(nodes)):
            d.line([nodes[i],nodes[j]], fill=(110,180,235,150), width=2)
    for p in nodes:
        img = Image.alpha_composite(img, glow(p[0],p[1],55, CYAN,150,1.5))
        d.ellipse([p[0]-10,p[1]-10,p[0]+10,p[1]+10], fill=(220,240,255,235))
    save(img, "v10_barrier.png")

def v12_pyramid():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    d = ImageDraw.Draw(img)
    # three tiers, widest at bottom
    tiers = [(300, 820, 700, 1000, (30,70,140)), (380, 620, 620, 800, (45,95,170)), (470, 420, 530, 600, (70,130,210))]
    for (x1,y1,x2,y2,c) in tiers:
        d.polygon([(x1,y2),(x2,y2),((x1+x2)//2,y1)], fill=c)
        img = Image.alpha_composite(img, glow((x1+x2)//2, (y1+y2)//2, 90, EBLUE, 90, 1.3))
    save(img, "v12_pyramid.png")

def v13_gtm():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    d = ImageDraw.Draw(img)
    # ascending staircase
    steps=[(140,900),(320,760),(500,620),(680,480),(860,340)]
    prev=None
    for (x,y) in steps:
        d.rounded_rectangle([x,y,x+150,y+90], radius=10, outline=(120,170,220,200), width=2)
        if prev:
            d.line([(prev[0]+150,prev[1]),(x,y+90)], fill=(110,180,235,170), width=3)
        prev=(x,y)
    img = Image.alpha_composite(img, glow(860, 340, 120, CYAN, 150, 1.5))
    save(img, "v13_gtm.png")

def v14_result():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    d = ImageDraw.Draw(img)
    # wall of badges
    random.seed(21)
    for i in range(9):
        x = 120 + (i%3)*290; y = 160 + (i//3)*300
        d.rounded_rectangle([x,y,x+220,y+200], radius=16, outline=(120,170,220,200), width=2)
        img = Image.alpha_composite(img, glow(x+110, y+100, 70, GOLD, 90, 1.4))
        d.ellipse([x+90,y+70,x+130,y+110], fill=(220,235,250,230))
    # pipeline at bottom
    py=1010
    prev=None
    for x in [200,400,600,800]:
        c=(x,py)
        if prev: d.line([prev,c], fill=(110,180,235,180), width=4)
        prev=c
    for x in [200,400,600,800]:
        d.ellipse([x-10,py-10,x+10,py+10], fill=(220,240,255,235))
    save(img, "v14_result.png")

def v15_team():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    img = Image.alpha_composite(img, radial(500, 560, 460, EBLUE, 24, 1.2))
    d = ImageDraw.Draw(img)
    center=(500,560)
    members=[(300,360),(720,360),(280,780),(740,780),(500,250)]
    for m in members:
        d.line([center,m], fill=(120,180,235,150), width=2)
    for m in members:
        img = Image.alpha_composite(img, glow(int(m[0]), int(m[1]), 80, CYAN, 150, 1.5))
        d.ellipse([m[0]-45,m[1]-45,m[0]+45,m[1]+45], fill=(30,50,90,230))
        d.ellipse([m[0]-45,m[1]-45,m[0]+45,m[1]+45], outline=(150,200,240,220), width=3)
    img = Image.alpha_composite(img, glow(center[0], center[1], 90, LGOLD, 150, 1.5))
    d.ellipse([center[0]-50,center[1]-50,center[0]+50,center[1]+50], fill=(40,70,120,235))
    save(img, "v15_team.png")

def v16_education():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    img = Image.alpha_composite(img, radial(500, 560, 470, EBLUE, 24, 1.2))
    img = Image.alpha_composite(img, glow(500, 560, 100, CYAN, 170, 1.6))
    d = ImageDraw.Draw(img)
    import math as m
    dirs=[(500,200),(840,560),(500,920),(160,560)]
    for p in dirs:
        d.line([(500,560),p], fill=(120,180,235,170), width=3)
        img = Image.alpha_composite(img, glow(int(p[0]), int(p[1]), 80, GOLD, 150, 1.5))
        d.rounded_rectangle([p[0]-70,p[1]-55,p[0]+70,p[1]+55], radius=14, outline=(LGOLD[0],LGOLD[1],LGOLD[2],220), width=3)
    save(img, "v16_education.png")

def v17_finance():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    d = ImageDraw.Draw(img)
    # faint bars
    random.seed(31)
    for i in range(6):
        x = 130 + i*130; h = 200 + random.randint(0,420)
        d.rectangle([x, 1000-h, x+80, 1000], fill=(40,80,150,180))
        img = Image.alpha_composite(img, glow(x+40, 1000-h//2, 50, EBLUE, 70, 1.3))
    # pie hint
    d.ellipse([620,420,900,700], outline=(150,200,240,200), width=3)
    d.pieslice([620,420,900,700], 20, 160, fill=(60,110,180,150))
    save(img, "v17_finance.png")

def v18_roadmap():
    img = vis_right()
    vgrad(img, (12,24,46),(8,14,28))
    d = ImageDraw.Draw(img)
    base_y = 620
    d.line([(100,base_y),(900,base_y)], fill=(LGOLD[0],LGOLD[1],LGOLD[2],200), width=4)
    nodes=[(230,base_y),(500,base_y-40),(770,base_y-80)]
    prev=None
    for c in nodes:
        if prev: d.line([prev,c], fill=(150,200,240,170), width=3)
        prev=c
    for c in nodes:
        img = Image.alpha_composite(img, glow(int(c[0]), int(c[1]), 90, GOLD, 160, 1.5))
        d.ellipse([c[0]-26,c[1]-26,c[0]+26,c[1]+26], fill=(40,70,120,235))
        d.ellipse([c[0]-26,c[1]-26,c[0]+26,c[1]+26], outline=(LGOLD[0],LGOLD[1],LGOLD[2],230), width=3)
    save(img, "v18_roadmap.png")

if __name__ == "__main__":
    print("== backgrounds ==")
    bg_cover(); bg_content(); bg_dark(); bg_thank(); gold_line()
    print("== page visuals ==")
    v1_cover(); v2_value(); v3_policy(); v4_pain(); v5_radial(); v6_matrix()
    v7_demo(); v8_arch(); v9_innovation(); v10_barrier(); v12_pyramid(); v13_gtm()
    v14_result(); v15_team(); v16_education(); v17_finance(); v18_roadmap()
    print("ALL DONE")
