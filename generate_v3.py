"""
VELIXIA — Premium Motion Design Generator v3
White aesthetic, kinetic typography synced to real audio phrases,
animated graphs, full VFX suite.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import AudioFileClip, VideoClip, concatenate_videoclips, ColorClip
import math, os, warnings
warnings.filterwarnings("ignore")

AUDIO = "/home/user/VELIXIA/velixia_voiceover_v1.mp3"
OUT   = "/home/user/VELIXIA/velixia_tiktok_v3.mp4"
W, H  = 1080, 1920
FPS   = 24

# ── Colors ─────────────────────────────────────────────────────────────────────
BG     = (255, 255, 255)       # pure white
INK    = (13,  13,  13)        # near black
GREEN  = (34, 197, 94)
LGREEN = (220, 252, 231)       # light green bg
RED    = (239, 68,  68)
ORANGE = (245, 158, 11)
GRAY   = (150, 150, 150)
LGRAY  = (240, 240, 240)
DGRAY  = (80,  80,  80)

# ── Fonts ──────────────────────────────────────────────────────────────────────
_fc = {}
def F(size, s='bold'):
    if (size,s) in _fc: return _fc[(size,s)]
    paths = {'bold': '/tmp/vfonts/Inter-Bold-conv.ttf',
             'light': '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
             'italic':'/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf'}
    try: f = ImageFont.truetype(paths.get(s, paths['bold']), size)
    except: f = ImageFont.load_default()
    _fc[(size,s)] = f; return f

def tsz(t, f):
    bb = f.getbbox(t); return bb[2]-bb[0], bb[3]-bb[1]

def wrap(text, font, max_w):
    words, lines, line = text.split(), [], []
    for w in words:
        test = " ".join(line+[w])
        if tsz(test,font)[0] <= max_w or not line: line.append(w)
        else: lines.append(" ".join(line)); line=[w]
    if line: lines.append(" ".join(line))
    return lines

# ── Easing ─────────────────────────────────────────────────────────────────────
def cl(v, lo=0., hi=1.): return max(lo, min(hi, v))
def rm(t, a, b, c=0., d=1.): return c+(d-c)*cl((t-a)/(b-a) if b!=a else 1.)
def eo(t, n=3): return 1-(1-cl(t))**n
def ei(t, n=3): return cl(t)**n
def sp(t):  # spring
    t = cl(t)
    if t >= 1: return 1.
    return 1-(2**(-10*t))*math.sin((t*10-0.75)*(2*math.pi/3))
def lerp(a,b,t): return a+(b-a)*cl(t)

def ca(col, a):
    if isinstance(col[0], float): col = tuple(int(c) for c in col)
    return tuple(int(v*cl(a)) for v in col)

# ── Canvas helper ─────────────────────────────────────────────────────────────
class C:
    def __init__(self, bg=BG):
        self.im = Image.new("RGB", (W,H), bg)
        self.d  = ImageDraw.Draw(self.im)
    def arr(self): return np.array(self.im)

    def text(self, txt, x, y, f, col=INK, center_x=False):
        if center_x:
            tw,_ = tsz(txt, f)
            x = (W-tw)//2
        self.d.text((x,y), txt, font=f, fill=col)

    def text_block(self, lines, f, cy, col=INK, center=True, lsp=1.4, x0=None):
        lh = int(tsz("Ag",f)[1]*lsp)
        total = lh*(len(lines))
        y = cy - total//2
        for line in lines:
            tw,th = tsz(line,f)
            x = (W-tw)//2 if center else (x0 or 80)
            self.d.text((x,y), line, font=f, fill=col)
            y += lh

    def underline(self, cx, y, w_px, h_px=5, col=GREEN, progress=1.0, radius=3):
        pw = int(w_px*cl(progress))
        if pw < 2: return
        x0 = cx-pw//2
        self.d.rounded_rectangle([(x0,y),(x0+pw,y+h_px)], radius=radius, fill=col)

    def rect(self, x,y,w,h, col, radius=0):
        if radius: self.d.rounded_rectangle([(x,y),(x+w,y+h)], radius=radius, fill=col)
        else: self.d.rectangle([(x,y),(x+w,y+h)], fill=col)

    def vbar(self, col=GREEN, w=10):
        self.d.rectangle([(0,0),(w,H)], fill=col)

    def hline(self, y, col=LGRAY, w_frac=1.0, thick=2):
        xw = int(W*w_frac)
        xo = (W-xw)//2
        self.d.rectangle([(xo,y),(xo+xw,y+thick)], fill=col)

    def dot(self, x, y, r, col=GREEN, glow=False):
        self.d.ellipse([(x-r,y-r),(x+r,y+r)], fill=col)
        if glow:
            gl = Image.new("RGBA",(W,H),(0,0,0,0))
            gd = ImageDraw.Draw(gl)
            for gr in [r*3, r*2]:
                a = int(40*(1-gr/(r*3.5)))
                gd.ellipse([(x-gr,y-gr),(x+gr,y+gr)], fill=(*col,a))
            gl = gl.filter(ImageFilter.GaussianBlur(r))
            self.im = Image.alpha_composite(self.im.convert("RGBA"),gl).convert("RGB")
            self.d  = ImageDraw.Draw(self.im)

    def circle_arc(self, cx, cy, r, start_a, end_a, col, w=16):
        """Draw arc (degrees)."""
        box = [(cx-r,cy-r),(cx+r,cy+r)]
        self.d.arc(box, start=start_a, end=end_a, fill=col, width=w)

    def shadow_text(self, txt, x, y, f, col=INK, shadow_col=(220,220,220), offset=4):
        self.d.text((x+offset, y+offset), txt, font=f, fill=shadow_col)
        self.d.text((x, y), txt, font=f, fill=col)

    def word_stream(self, text, f, cy, t_start, t_now,
                    dpw=0.10, col=INK, max_w=None, center=True, x0=None):
        max_w = max_w or int(W*0.84)
        lines = wrap(text, f, max_w)
        lh    = int(tsz("Ag",f)[1]*1.45)
        total = lh*(len(lines))
        y     = cy - total//2
        wi    = 0
        for line in lines:
            words = line.split()
            tw_line = tsz(line+" ",f)[0]
            x = (W-tw_line)//2 if center else (x0 or 80)
            for word in words:
                wt = t_start + wi*dpw
                wa = eo(rm(t_now, wt, wt+0.28))
                if wa > 0:
                    dy = int(18*(1-wa))
                    self.d.text((x, y+dy), word+" ", font=f,
                                fill=ca(col, wa))
                x += tsz(word+" ",f)[0]
                wi += 1
            y += lh


# ══════════════════════════════════════════════════════════════════════════════
# REAL PHRASE TIMINGS from librosa silence detection
# ══════════════════════════════════════════════════════════════════════════════
PH = [
    (0.07,  0.64),   # 0  "Imaginez."
    (1.21,  7.29),   # 1  "Votre futur client ouvre son téléphone... il a déjà décidé."
    (7.84,  8.85),   # 2  "Pas en trois secondes."
    (9.61, 10.56),   # 3  "Pas en une seconde."
    (11.13,12.24),   # 4  "En cinquante millisecondes."
    (12.78,14.23),   # 5  "C'est ce que l'Université de Carleton a prouvé en 2002."
    (14.74,18.29),   # 6  "La première impression visuelle d'un site se forme..."
    (18.93,21.03),   # 7  "avant même que le cerveau ait eu le temps de lire un seul mot."
    (21.55,24.91),   # 8  "Et ce n'est pas tout."
    (25.60,26.27),   # 9  (pause)
    (26.83,31.02),   # 10 "Google a analysé des millions de pages mobiles en 2017."
    (31.71,34.55),   # 11 "Leur conclusion — 53 % des visiteurs abandonnent..."
    (35.21,36.27),   # 12 "un site qui met plus de 3 secondes à charger."
    (36.87,42.17),   # 13 "Plus de la moitié. Partis. Pour toujours."
    (42.74,45.98),   # 14 "Trois secondes pour décider si vous méritez leur attention."
    (46.53,47.19),   # 15 (pause)
    (47.77,49.03),   # 16 "Trois secondes..."
    (49.75,50.92),   # 17 (pause)
    (51.62,58.63),   # 18 "pour décider si vous existez."
    (59.33,64.45),   # 19 "Et même quand ils restent... Gloria Mark..."
    (65.00,68.88),   # 20 "professeure UC Irvine, mesure depuis 20 ans."
    (69.56,71.11),   # 21 "En 2004 —"
    (71.63,72.79),   # 22 "2 minutes et demie."
    (73.73,74.05),   # 23 (pause)
    (74.63,75.97),   # 24 "En 2012 —"
    (76.49,80.45),   # 25 "75 secondes."
    (81.11,88.35),   # 26 "Aujourd'hui... 47 secondes."
    (89.18,89.64),   # 27 "Quarante-sept secondes"
    (90.38,90.85),   # 28 "pour convaincre."
    (91.51,94.41),   # 29 "Quarante-sept secondes pour vendre."
    (95.17,100.85),  # 30 "Quarante-sept secondes... pour tout."
    (102.62,103.64), # 31 "Alors posez-vous cette question."
    (104.32,112.05), # 32 "Est-ce que votre présence digitale mérite ces 47 secondes ?"
    (112.59,113.60), # 33 "Un site mal conçu."
    (114.15,116.31), # 34 "Des réseaux abandonnés."
    (117.14,118.64), # 35 "Des visuels qui ne donnent pas envie."
    (119.19,119.99), # 36 "C'est des clients perdus."
    (120.52,121.05), # 37 "Chaque jour."
    (121.67,122.91), # 38 "En silence."
    (123.48,124.80), # 39 "La plupart des agences :"
    (125.52,127.83), # 40 "3 semaines pour un site."
    (128.44,128.57), # 41 (pause)
    (129.27,132.45), # 42 "10 jours pour du contenu."
    (133.12,135.09), # 43 "1 mois pour une identité."
    (135.89,137.41), # 44 "Et plusieurs milliers d'euros."
    (138.17,138.62), # 45 "Velixia,"
    (139.44,141.40), # 46 "c'est différent."
    (142.32,142.58), # 47 "Nous avons construit une agence propulsée par l'IA"
    (143.33,143.83), # 48 "pour faire en 24 heures"
    (145.07,146.52), # 49 "ce qu'une agence classique fait en 3 semaines."
    (147.39,147.67), # 50 "À 3 fois"
    (148.68,149.12), # 51 "moins cher."
    (150.00,150.88), # 52 "velix-ia.com"
    (152.01,153.37), # 53 (outro)
]
def ph(i): return PH[i][0]  # start time of phrase i
def pd(i): return PH[i][1]-PH[i][0]  # duration


# ══════════════════════════════════════════════════════════════════════════════
# SCENES — each is a VideoClip with local time t ∈ [0, duration]
# Global time = scene_start + t
# ══════════════════════════════════════════════════════════════════════════════

def mksc(fn, dur):
    return VideoClip(lambda t: fn(t, dur), duration=dur)


# ── INTRO FLASH (0 → 0.07s) ──────────────────────────────────────────────────
def sc_intro(dur):
    def f(t, d):
        a = eo(t/max(d,0.001))
        bg = ca(BG, a)
        c = C(bg)
        return c.arr()
    return mksc(f, dur)


# ── SCENE 1 — IMAGINEZ (phrase 0 → phrase 2 = 0.07 → 7.84s) ─────────────────
def sc_imaginez(scene_start, dur):
    f_xl   = F(int(W*0.18))
    f_lg   = F(int(W*0.11))
    f_body = F(int(W*0.038),'light')
    f_acc  = F(int(W*0.095))

    def f(t, d):
        c = C(BG)
        gt = scene_start + t   # global time

        # ── "IMAGINEZ." big reveal ──────────────────────────────────────
        # phrase 0 starts at 0.07, local t = 0.07 - scene_start = 0
        a_im = sp(rm(t, 0.0, 0.5))
        if a_im > 0:
            fw,fh = tsz("IMAGINEZ.", f_xl)
            # Scale effect: starts big, settles
            scale = 1.0 + 0.12*(1-a_im)
            # Draw with manual scaling via crop
            tmp = C(BG)
            tmp.d.text(((W-fw)//2, H//2-fh//2-int(H*0.15)),
                       "IMAGINEZ.", font=f_xl, fill=ca(INK, a_im))
            # Green underline wipe
            up = eo(rm(t, 0.4, 0.9))
            tmp.underline(W//2, H//2-fh//2-int(H*0.15)+fh+12,
                          fw, 8, GREEN, up)
            # Fade in
            arr = np.array(tmp.im).astype(float)
            arr = (255*(1-a_im) + arr*a_im).astype(np.uint8)
            c.im = Image.fromarray(arr)
            c.d  = ImageDraw.Draw(c.im)

        # ── Body text word by word (phrase 1 = 1.21s, local = 1.21-0.07 = 1.14)
        lt_body = t - (ph(1) - scene_start)
        if lt_body > 0:
            lines_data = [
                ("Votre futur client",      0.00, int(W*0.038)),
                ("ouvre son téléphone…",    0.85, int(W*0.038)),
                ("tombe sur votre concurrent…", 1.80, int(W*0.038)),
            ]
            for i,(txt, delay, sz) in enumerate(lines_data):
                a = eo(rm(lt_body, delay, delay+0.45))
                if a>0:
                    fb = F(sz,'light')
                    tw,th = tsz(txt,fb)
                    dy = int(20*(1-a))
                    c.d.text(((W-tw)//2, H//2+int(H*0.04)+i*int(H*0.075)-dy),
                             txt, font=fb, fill=ca(GRAY, a))

        # ── "et en CINQUANTE MILLISECONDES" (at ~4.2 local)
        lt_50 = lt_body - 3.1
        if lt_50 > 0:
            a_pre = eo(rm(lt_50, 0, 0.4))
            if a_pre > 0:
                fp = F(int(W*0.034),'light')
                tp = "et en"
                tw,_ = tsz(tp,fp)
                c.d.text(((W-tw)//2, H//2+int(H*0.33)), tp, font=fp,
                         fill=ca(GRAY, a_pre*0.7))
            a_50 = sp(rm(lt_50, 0.25, 0.85))
            if a_50 > 0:
                f50 = F(int(W*0.075))
                t50 = "50 MILLISECONDES"
                tw,th = tsz(t50,f50)
                # Glow box behind text
                box_alpha = a_50*0.12
                c.d.rounded_rectangle(
                    [(W//2-tw//2-20, H//2+int(H*0.38)-10),
                     (W//2+tw//2+20, H//2+int(H*0.38)+th+10)],
                    radius=12, fill=ca(LGREEN, box_alpha))
                c.d.text(((W-tw)//2, H//2+int(H*0.38)), t50, font=f50,
                         fill=ca(GREEN, a_50))

        # ── "il a déjà décidé." (at ~5.1 local = phrase 1 start + 3.9)
        lt_dec = lt_body - 4.2
        if lt_dec > 0:
            a_d = eo(rm(lt_dec, 0, 0.4))
            if a_d>0:
                fd = F(int(W*0.055))
                td = "il a déjà décidé."
                tw,th = tsz(td,fd)
                c.d.text(((W-tw)//2, H//2+int(H*0.5)), td, font=fd,
                         fill=ca(INK, a_d))

        # Green dot top-right corner pulsing
        pulse = 0.7+0.3*math.sin(t*math.pi*2.2)
        c.dot(W-60, 60, int(10*pulse), GREEN, glow=True)

        return c.arr()
    return mksc(f, dur)


# ── SCENE 2 — CHIFFRES BARRÉS (7.84 → 12.78s) ────────────────────────────────
def sc_chiffres(scene_start, dur):
    f_s = F(int(W*0.045),'light')
    f_b = F(int(W*0.095))

    def f(t, d):
        c = C(BG)
        ml = int(W*0.12)
        base_y = H//2 - int(H*0.15)
        lh = int(H*0.1)

        # Phrase 2 = 7.84, local = 0
        # Phrase 3 = 9.61, local = 1.77
        # Phrase 4 = 11.13, local = 3.29
        items = [
            (0.0,  1.77, "Pas en 3 secondes."),
            (1.77, 3.29, "Pas en 1 seconde."),
        ]
        for i,(t0,t1,txt) in enumerate(items):
            a = eo(rm(t, t0, t0+0.35))
            if a <= 0: continue
            tw,th = tsz(txt,f_s)
            ty = base_y + i*lh
            # Strikethrough style: gray text + red line
            c.d.text((ml, ty), txt, font=f_s, fill=ca(GRAY, a*0.5))
            sp_p = eo(rm(t, t0+0.2, t0+0.6))
            if sp_p > 0:
                sw = int((tw+4)*sp_p)
                sy = ty + th//2 + 2
                c.d.rounded_rectangle([(ml-2,sy-3),(ml+sw,sy+3)],
                                      radius=3, fill=ca(RED,a))

        # "En 50 millisecondes." — phrase 4 = local 3.29
        a3 = sp(rm(t, 3.29, 3.95))
        if a3 > 0:
            f3 = F(int(W*0.09))
            t3 = "En 50 millisecondes."
            tw3,th3 = tsz(t3,f3)
            scale_dy = int(20*(1-a3))
            c.d.text(((W-tw3)//2, base_y+lh*2-scale_dy), t3, font=f3,
                     fill=ca(GREEN, a3))
            # Animated box behind
            box_a = eo(rm(t, 3.5, 4.1))
            if box_a > 0:
                c.d.rounded_rectangle(
                    [(W//2-tw3//2-16,base_y+lh*2-8),
                     (W//2+tw3//2+16,base_y+lh*2+th3+8)],
                    radius=14,
                    outline=ca(GREEN,box_a*0.6), width=2)

        # VFX: animated vertical line on right
        line_a = eo(rm(t, 0, 0.8))
        lh_px = int(H*0.4*line_a)
        c.d.rectangle([(W-80, H//2-lh_px//2),(W-74, H//2+lh_px//2)],
                      fill=ca(LGRAY, 0.8))

        return c.arr()
    return mksc(f, dur)


# ── SCENE 3 — CARLETON (12.78 → 21.55s) ──────────────────────────────────────
def sc_carleton(scene_start, dur):
    f_src = F(int(W*0.026),'light')
    f_bdy = F(int(W*0.034),'light')
    f_chc = F(int(W*0.040))

    def f(t, d):
        c = C(BG)
        # Green left bar (thin)
        c.d.rectangle([(0,0),(6,H)], fill=ca(GREEN, 0.35))

        # Source tag pill
        tag_a = eo(rm(t, 0.2, 0.65))
        if tag_a > 0:
            tag = "Université de Carleton  ·  2002"
            tw,th = tsz(tag,f_src)
            px,py = 22, 14
            c.d.rounded_rectangle(
                [(W//2-tw//2-px, H//2-int(H*0.28)-py),
                 (W//2+tw//2+px, H//2-int(H*0.28)+th+py)],
                radius=th+py, fill=ca(LGRAY, tag_a))
            c.d.text(((W-tw)//2, H//2-int(H*0.28)),
                     tag, font=f_src, fill=ca(GRAY, tag_a))

        # Word-by-word: phrase 5 starts at 12.78, local = 0
        # "C'est ce que l'Université de Carleton a prouvé en 2002."
        c.word_stream(
            "C'est ce que l'Université de Carleton a prouvé en 2002.",
            f_bdy, H//2-int(H*0.14),
            0.0, t, dpw=0.09, col=INK)

        # Phrase 6 = 14.74, local = 14.74-12.78 = 1.96
        # "La première impression visuelle d'un site se forme..."
        c.word_stream(
            "La première impression visuelle d'un site se forme…",
            f_bdy, H//2+int(H*0.02),
            1.96, t, dpw=0.09, col=DGRAY)

        # Phrase 7 = 18.93, local = 18.93-12.78 = 6.15
        # "avant même que le cerveau ait eu le temps de lire un seul mot."
        c.word_stream(
            "avant même que le cerveau lise un seul mot.",
            f_bdy, H//2+int(H*0.17),
            6.15, t, dpw=0.09, col=DGRAY)

        # Choc phrase with underline
        a_choc = eo(rm(t, 7.8, 8.3))
        if a_choc > 0:
            txt = "En moins de 50 millisecondes."
            tw,th = tsz(txt,f_chc)
            c.d.text(((W-tw)//2, H//2+int(H*0.31)), txt, font=f_chc,
                     fill=ca(INK, a_choc))
            up = eo(rm(t, 8.1, 8.9))
            c.underline(W//2, H//2+int(H*0.31)+th+10, tw, 7, GREEN, up)

        return c.arr()
    return mksc(f, dur)


# ── TRANSITION "Et ce n'est pas tout." (21.55 → 26.83s) ──────────────────────
def sc_transition(scene_start, dur):
    f_t = F(int(W*0.068))

    def f(t, d):
        # Dark background for contrast
        bg_p = cl(t/0.6)
        bg_col = tuple(int(BG[i]*(1-bg_p) + INK[i]*bg_p) for i in range(3))
        c = C(bg_col)

        words = ["Et", "ce", "n'est", "pas", "tout."]
        full = " ".join(words)
        tw_full,th = tsz(full,f_t)
        x = (W-tw_full)//2

        for i,word in enumerate(words):
            wt = 1.5 + i*0.25
            wa = sp(rm(t, wt, wt+0.4))
            if wa > 0:
                ww,_ = tsz(word+" ",f_t)
                col = ca(WHITE if bg_p>0.5 else INK, wa)
                c.d.text((x, H//2-th//2), word+" ", font=f_t, fill=col)
            x += tsz(word+" ",f_t)[0]

        # Green dot animation
        dot_a = eo(rm(t, 2.5, 3.0))
        if dot_a > 0:
            c.dot(W//2, H//2+int(H*0.1), int(8*dot_a), GREEN, glow=True)

        return c.arr()
    return mksc(f, dur)

WHITE = (255,255,255)

# ── SCENE 4 — GOOGLE 53% (26.83 → 42.74s) ────────────────────────────────────
def sc_google(scene_start, dur):
    f_body = F(int(W*0.032),'light')
    f_cnt  = F(int(W*0.22))
    f_sub  = F(int(W*0.036),'light')
    f_imp  = F(int(W*0.070))
    f_src  = F(int(W*0.024),'light')

    def f(t, d):
        c = C(BG)
        c.d.rectangle([(0,0),(6,H)], fill=ca(GREEN,0.35))

        # local times relative to 26.83
        # phrase 10 = 26.83 → local 0    "Google a analysé..."
        # phrase 11 = 31.71 → local 4.88 "Leur conclusion — 53%..."
        # phrase 12 = 35.21 → local 8.38 "un site qui met plus de 3s..."
        # phrase 13 = 36.87 → local 10.04 "Plus de la moitié. Partis. Pour toujours."

        # Source tag
        src_a = eo(rm(t, 0.1, 0.6))
        if src_a > 0:
            src = "Google / SOASTA Research  ·  2017"
            tw,_ = tsz(src,f_src)
            c.d.text(((W-tw)//2, H//2-int(H*0.38)),
                     src, font=f_src, fill=ca(GRAY, src_a*0.7))

        # Word stream phrase 10
        c.word_stream(
            "Google a analysé des millions de pages mobiles en 2017.",
            f_body, H//2-int(H*0.26), 0.1, t, dpw=0.08, col=DGRAY)

        # "Leur conclusion —" phrase 11
        l_a = eo(rm(t, 4.88, 5.3))
        if l_a > 0:
            txt = "Leur conclusion —"
            tw,_ = tsz(txt,f_sub)
            c.d.text(((W-tw)//2, H//2-int(H*0.14)), txt, font=f_sub,
                     fill=ca(DGRAY, l_a))

        # ── BIG COUNTER 0→53% ──────────────────────────────────────────
        counter_start = 5.3
        ct = eo(rm(t, counter_start, counter_start+1.6), 4)
        val = int(ct*53)
        cnt_txt = f"{val}%"
        tw_cnt,th_cnt = tsz(cnt_txt,f_cnt)
        cy_cnt = H//2+int(H*0.04)

        if t > counter_start:
            cnt_a = eo(rm(t, counter_start, counter_start+0.4))
            # Background circle (track)
            cr = int(W*0.33)
            c.d.ellipse([(W//2-cr,cy_cnt-cr+th_cnt//2),
                         (W//2+cr,cy_cnt+cr+th_cnt//2)],
                        outline=ca(LGRAY,0.9), width=14)
            # Progress arc: 0% = -90°, 53% = -90+53*3.6 = 100.8°
            arc_deg = ct*360
            if arc_deg > 1:
                # Green arc
                c.d.arc([(W//2-cr,cy_cnt-cr+th_cnt//2),
                          (W//2+cr,cy_cnt+cr+th_cnt//2)],
                        start=-90, end=-90+arc_deg,
                        fill=ca(GREEN, cnt_a), width=14)
            c.d.text(((W-tw_cnt)//2, cy_cnt-th_cnt//2),
                     cnt_txt, font=f_cnt, fill=ca(INK, cnt_a))

        # Sub text
        sub_a = eo(rm(t, 7.2, 7.7))
        if sub_a > 0:
            c.word_stream(
                "des visiteurs abandonnent un site qui charge en +3 secondes.",
                f_sub, H//2+int(H*0.3)+th_cnt//2,
                7.0, t, dpw=0.07, col=GRAY)

        # "Plus de la moitié. Partis. Pour toujours." phrase 13 local = 10.04
        impact_data = [
            (10.04, "Plus de la moitié.", f_imp, DGRAY),
            (11.0,  "Partis.",            F(int(W*0.11)), RED),
            (12.1,  "Pour toujours.",     f_imp, RED),
        ]
        i_y = H//2+int(H*0.44)
        for (it, itxt, iff, icol) in impact_data:
            ia = sp(rm(t, it, it+0.45))
            if ia > 0:
                tw2,th2 = tsz(itxt,iff)
                dy2 = int(15*(1-ia))
                c.d.text(((W-tw2)//2, i_y-dy2), itxt, font=iff,
                         fill=ca(icol, ia))
            i_y += int(th2*1.55) if ia>0 else int(H*0.08)

        return c.arr()
    return mksc(f, dur)


# ── SCENE 5 — "3 SECONDES" (42.74 → 59.33s) ──────────────────────────────────
def sc_3sec(scene_start, dur):
    f_num  = F(int(W*0.42))
    f_word = F(int(W*0.10))
    f_sub  = F(int(W*0.034),'light')
    f_choc = F(int(W*0.042))

    def f(t, d):
        # local 0 = phrase 14 = 42.74 "Trois secondes pour décider..."
        # local 4.03 = phrase 16 = 47.77
        # local 8.88 = phrase 18 = 51.62

        c = C(BG)

        # Giant "3" — spring pop
        a3 = sp(rm(t, 0.1, 0.75))
        if a3 > 0:
            tw,th = tsz("3",f_num)
            c.d.text(((W-tw)//2, H//2-th//2-int(H*0.12)), "3", font=f_num,
                     fill=ca(INK, a3))

        # "secondes." slide from right
        a_s = eo(rm(t, 0.7, 1.2))
        if a_s > 0:
            dx = int(50*(1-a_s))
            f_sec = F(int(W*0.08))
            tw,th = tsz("secondes.",f_sec)
            c.d.text(((W-tw)//2+dx, H//2+int(H*0.17)), "secondes.", font=f_sec,
                     fill=ca(INK, a_s))

        # Green underline
        ul_a = eo(rm(t, 1.0, 1.6))
        if ul_a > 0:
            f_sec2 = F(int(W*0.08))
            tw2,th2 = tsz("secondes.",f_sec2)
            c.underline(W//2, H//2+int(H*0.17)+th2+10,
                        int(tw2*0.9), 7, GREEN, ul_a)

        # "pour décider si vous méritez leur attention."
        c.word_stream(
            "pour décider si vous méritez leur attention.",
            f_sub, H//2+int(H*0.31), 1.5, t, dpw=0.09, col=GRAY)

        # Second "Trois secondes" (phrase 16 local = 4.03)
        lt2 = t - 4.03
        if lt2 > 0:
            a2 = sp(rm(lt2, 0.4, 0.9))
            f_num2 = F(int(W*0.065))
            tw2,th2 = tsz("Trois secondes",f_num2)
            c.d.text(((W-tw2)//2, H//2+int(H*0.44)),
                     "Trois secondes", font=f_num2,
                     fill=ca(GREEN, a2))

        # "pour décider si vous existez." (phrase 18 local = 8.88)
        lt3 = t - 8.88
        if lt3 > 0:
            c.word_stream(
                "pour décider si vous existez.",
                f_choc, H//2+int(H*0.55), 0, lt3, dpw=0.1, col=INK)
            up3 = eo(rm(lt3, 1.5, 2.2))
            f_choc2 = F(int(W*0.042))
            tw3,th3 = tsz("pour décider si vous existez.",f_choc2)
            c.underline(W//2, H//2+int(H*0.55)+th3+60+10,
                        tw3, 7, RED, up3)

        # Vertical tick marks (VFX)
        n_ticks = 6
        for i in range(n_ticks):
            ta = eo(rm(t, i*0.15, i*0.15+0.4))
            if ta > 0:
                x = 80
                y = int(H*0.12) + i*int(H*0.13)
                c.d.rectangle([(x,y),(x+30,y+3)],
                              fill=ca(LGRAY, ta))

        return c.arr()
    return mksc(f, dur)


# ── SCENE 6 — GLORIA MARK + GRAPHE (59.33 → 89.18s) ─────────────────────────
def sc_gloria(scene_start, dur):
    f_src  = F(int(W*0.026),'light')
    f_body = F(int(W*0.032),'light')
    f_year = F(int(W*0.050))
    f_time = F(int(W*0.038),'light')
    f_big  = F(int(W*0.075))

    # Attention data: year → seconds
    ADATA = [(2004, 150), (2012, 75), (2023, 47)]
    # x positions for bars
    BAR_Y_TOP = H//2+int(H*0.06)
    BAR_H_MAX = int(H*0.25)
    BAR_W     = int(W*0.18)
    BAR_GAP   = int(W*0.09)
    BARS_X    = [(W//2 - BAR_W - BAR_GAP//2 - i*(BAR_W+BAR_GAP)) for i in range(2,-1,-1)]
    MAX_VAL   = 150

    def f(t, d):
        # local 0 = phrase 19 = 59.33 "Et même quand ils restent..."
        # local 5.67 = phrase 20 = 65.00 "Gloria Mark, UC Irvine..."
        # local 10.23 = phrase 21 = 69.56 "En 2004 —"
        # local 12.30 = phrase 22 = 71.63 "2 min 30."
        # local 15.30 = phrase 24 = 74.63 "En 2012 —"
        # local 17.16 = phrase 25 = 76.49 "75 secondes."
        # local 21.78 = phrase 26 = 81.11 "Aujourd'hui... 47 secondes."

        c = C(BG)
        c.d.rectangle([(0,0),(6,H)], fill=ca(GREEN,0.35))

        # "Et même quand ils restent…"
        a0 = eo(rm(t, 0.0, 0.45))
        if a0 > 0:
            fw = F(int(W*0.036),'italic')
            txt = "Et même quand ils restent…"
            tw,_ = tsz(txt,fw)
            c.d.text(((W-tw)//2, H//2-int(H*0.37)), txt, font=fw,
                     fill=ca(GRAY, a0*0.7))

        # Gloria Mark source tag
        src_a = eo(rm(t, 1.0, 1.5))
        if src_a > 0:
            c = _pill(c, "Gloria Mark  ·  UC Irvine  ·  2023",
                      f_src, H//2-int(H*0.28), src_a)

        # "mesure notre temps d'attention sur écran depuis 20 ans."
        c.word_stream(
            "mesure notre temps d'attention sur écran depuis 20 ans.",
            f_body, H//2-int(H*0.18), 1.2, t, dpw=0.075, col=DGRAY)

        # ── ANIMATED BAR CHART ──────────────────────────────────────────
        bar_triggers = [10.23, 12.30+2.0, 21.78]  # local times for each bar

        # Chart axis
        axis_a = eo(rm(t, 9.0, 10.0))
        if axis_a > 0:
            ax_y = BAR_Y_TOP + BAR_H_MAX + 16
            c.d.rectangle([(80, ax_y),(W-80, ax_y+2)],
                          fill=ca(LGRAY, axis_a))
            # Y-axis dashes
            for vy in [0, BAR_H_MAX//2, BAR_H_MAX]:
                c.d.rectangle([(70, BAR_Y_TOP+BAR_H_MAX-vy),
                                (80, BAR_Y_TOP+BAR_H_MAX-vy+2)],
                               fill=ca(LGRAY, axis_a))

        bar_cols = [GREEN, ORANGE, RED]
        for bi, (year, secs) in enumerate(ADATA):
            bt = bar_triggers[bi]
            ba = eo(rm(t, bt, bt+0.9))
            if ba <= 0: continue

            bar_frac = (secs/MAX_VAL)*ba
            bh = int(BAR_H_MAX*bar_frac)
            bx = BARS_X[bi]
            by = BAR_Y_TOP + BAR_H_MAX - bh

            # Bar
            col = bar_cols[bi]
            c.d.rounded_rectangle([(bx,by),(bx+BAR_W, BAR_Y_TOP+BAR_H_MAX)],
                                   radius=8, fill=ca(col, 0.85))

            # Year label
            fw2 = F(int(W*0.028),'light')
            tw2,_ = tsz(str(year),fw2)
            c.d.text((bx+(BAR_W-tw2)//2,
                      BAR_Y_TOP+BAR_H_MAX+22), str(year), font=fw2,
                     fill=ca(DGRAY, ba))

            # Value on top of bar
            fv = F(int(W*0.032))
            if secs >= 60:
                mins = secs//60; secs2 = secs%60
                val_txt = f"{mins}m {secs2}s" if secs2 else f"{mins}m"
            else:
                val_txt = f"{secs}s"
            tw3,th3 = tsz(val_txt,fv)
            if bh > th3+8:
                c.d.text((bx+(BAR_W-tw3)//2, by-th3-8),
                         val_txt, font=fv, fill=ca(col, ba))

        # "47 secondes." BIG (phrase 26 local = 21.78)
        lt47 = t - 21.78
        if lt47 > 0:
            a47 = sp(rm(lt47, 0.3, 1.1))
            f47  = F(int(W*0.11))
            txt47 = "47 secondes."
            tw47,th47 = tsz(txt47,f47)
            c.d.text(((W-tw47)//2, H//2-int(H*0.06)), txt47,
                     font=f47, fill=ca(RED, a47))
            up47 = eo(rm(lt47, 0.9, 1.7))
            c.underline(W//2, H//2-int(H*0.06)+th47+10,
                        tw47, 7, RED, up47)

        # Descending arrow VFX between bars
        arr_a = eo(rm(t, 17.0, 18.0))
        if arr_a > 0 and len(BARS_X) >= 2:
            for bi in range(len(BARS_X)-1):
                x1 = BARS_X[bi]+BAR_W//2
                x2 = BARS_X[bi+1]+BAR_W//2
                y1 = BAR_Y_TOP + int(BAR_H_MAX*(1-ADATA[bi][1]/MAX_VAL)) - 10
                y2 = BAR_Y_TOP + int(BAR_H_MAX*(1-ADATA[bi+1][1]/MAX_VAL)) - 10
                c.d.line([(x1,y1),(x2,y2)], fill=ca(RED,arr_a*0.5), width=2)

        return c.arr()
    return mksc(f, dur)


def _pill(c, txt, f, cy, alpha):
    tw,th = tsz(txt,f)
    px,py = 20,10
    pw,ph = tw+px*2, th+py*2
    c.d.rounded_rectangle(
        [(W//2-pw//2, cy-ph//2),(W//2+pw//2, cy+ph//2)],
        radius=ph//2, fill=ca(LGRAY, alpha*0.9))
    c.d.text(((W-tw)//2, cy-th//2), txt, font=f,
             fill=ca(GRAY, alpha))
    return c


# ── SCENE 7 — 47 SECONDES TRIPLE (89.18 → 102.62s) ──────────────────────────
def sc_47(scene_start, dur):
    f_big  = F(int(W*0.165))
    f_line = F(int(W*0.058))
    f_sm   = F(int(W*0.034),'light')

    def f(t, d):
        # local 0 = 89.18 "Quarante-sept secondes"
        # local 1.20 = 90.38 "pour convaincre."
        # local 2.33 = 91.51 "Q-s pour vendre."
        # local 5.99 = 95.17 "Q-s pour tout."

        c = C(BG)

        # Big 47
        a47 = sp(rm(t, 0.0, 0.65))
        if a47 > 0:
            tw,th = tsz("47",f_big)
            c.d.text(((W-tw)//2, H//2-th//2-int(H*0.22)), "47",
                     font=f_big, fill=ca(GREEN, a47))
            # "secondes" smaller
            f_sec = F(int(W*0.052),'light')
            tw2,_ = tsz("secondes",f_sec)
            c.d.text(((W-tw2)//2, H//2-int(H*0.22)+th+8), "secondes",
                     font=f_sec, fill=ca(GRAY, a47))
            up = eo(rm(t, 0.5, 1.1))
            c.underline(W//2, H//2-int(H*0.22)+th+tsz("s",f_sec)[1]+18,
                        tw, 8, GREEN, up)

        ml = int(W*0.10)
        lines_d = [
            (1.20, "pour convaincre.", INK),
            (2.33+0.5, "pour vendre.", DGRAY),
            (5.99+0.5, "pour tout.", GREEN),
        ]
        ly = H//2+int(H*0.1)
        lsp = int(H*0.1)
        for i,(st,txt,col) in enumerate(lines_d):
            a = eo(rm(t, st, st+0.45))
            if a > 0:
                dx = int(38*(1-a))
                c.d.text((ml-dx, ly+i*lsp), txt, font=f_line,
                         fill=ca(col, a))
                if col == GREEN and a > 0.6:
                    dot_r = int(8*(0.8+0.2*math.sin(t*math.pi*3)))
                    tw3,th3 = tsz(txt,f_line)
                    c.dot(ml+tw3+20, ly+i*lsp+th3//2, dot_r, GREEN)

        # Countdown visual
        ct_a = eo(rm(t, 3.0, 3.8))
        if ct_a > 0:
            r = int(W*0.16)
            cx2, cy2 = W-int(W*0.22), int(H*0.22)
            # Track
            c.d.ellipse([(cx2-r,cy2-r),(cx2+r,cy2+r)],
                        outline=ca(LGRAY,0.8), width=10)
            # Arc progress
            arc_p = eo(rm(t, 3.5, 7.0))
            if arc_p > 0:
                c.d.arc([(cx2-r,cy2-r),(cx2+r,cy2+r)],
                        start=-90, end=-90+arc_p*360,
                        fill=ca(GREEN,ct_a), width=10)
            f_cd = F(int(r*0.8))
            val = int((1-arc_p)*47)
            tw_cd,th_cd = tsz(str(val),f_cd)
            c.d.text((cx2-tw_cd//2, cy2-th_cd//2), str(val),
                     font=f_cd, fill=ca(INK, ct_a))

        return c.arr()
    return mksc(f, dur)


# ── SCENE 8 — QUESTION (102.62 → 112.59s) ────────────────────────────────────
def sc_question(scene_start, dur):
    f_q = F(int(W*0.058))
    f_b = F(int(W*0.036),'light')
    f_a = F(int(W*0.044))

    def f(t, d):
        # Ivory warm white BG
        bg_t = cl(t/0.7)
        bg_c = tuple(int(BG[i]*(1-bg_t)+248*bg_t) for i in range(3))
        # Actually just use pure white with green accent top
        c = C(BG)

        # Top green accent bar
        bar_w = int(W*0.12)
        c.d.rounded_rectangle([(W//2-bar_w//2, 60),(W//2+bar_w//2, 72)],
                               radius=6, fill=ca(GREEN, eo(rm(t,0.1,0.5))))

        # "Posez-vous cette question."
        aq = sp(rm(t, 0.2, 0.75))
        if aq > 0:
            tw,th = tsz("Posez-vous cette question.",f_q)
            dy = int(20*(1-aq))
            c.d.text(((W-tw)//2, H//2-int(H*0.2)-dy),
                     "Posez-vous cette question.", font=f_q,
                     fill=ca(INK, aq))

        # "Est-ce que votre présence digitale actuelle…"
        # phrase 32 local = 104.32-102.62 = 1.70
        c.word_stream(
            "Est-ce que votre présence digitale actuelle…",
            f_b, H//2, 1.70, t, dpw=0.09, col=GRAY)

        # "mérite ces 47 secondes ?"
        lt_q = t - (112.05-102.62)
        if lt_q > 0:
            lt_q = 0  # fallback
        # Use fixed timing
        a_47 = eo(rm(t, 7.5, 8.2))
        if a_47 > 0:
            txt = "mérite ces 47 secondes ?"
            tw2,th2 = tsz(txt,f_a)
            c.d.text(((W-tw2)//2, H//2+int(H*0.17)), txt, font=f_a,
                     fill=ca(INK, a_47))
            up2 = eo(rm(t, 8.0, 8.8))
            c.underline(W//2, H//2+int(H*0.17)+th2+10,
                        tw2, 8, GREEN, up2)

        # Decorative quote mark
        fq2 = F(int(W*0.25))
        c.d.text((50, H//2-int(H*0.4)), "“", font=fq2,
                 fill=ca(LGRAY, 0.8))

        return c.arr()
    return mksc(f, dur)


# ── SCENE 9 — PROBLÈMES + AGENCES (112.59 → 138.17s) ─────────────────────────
def sc_problems(scene_start, dur):
    f_p = F(int(W*0.036),'light')
    f_e = F(int(W*0.038))
    f_c = F(int(W*0.030),'light')
    f_t = F(int(W*0.030))

    def f(t, d):
        # local 0 = 112.59 "Un site mal conçu."
        # local 1.56 = 114.15 "Des réseaux abandonnés."
        # local 4.55 = 117.14 "Des visuels..."
        # local 6.60 = 119.19 "C'est des clients perdus."
        # local 7.93 = 120.52 "Chaque jour."
        # local 9.08 = 121.67 "En silence."
        # local 10.89 = 123.48 "La plupart des agences :"
        # local 12.93 = 125.52 "3 semaines..."
        # local 20.53 = 133.12 "1 mois..."
        # local 23.30 = 135.89 "plusieurs milliers..."

        c = C(BG)
        c.d.rectangle([(0,0),(6,H)], fill=ca(RED,0.5))

        # Problems list
        problems = [
            (0.0,  "✗  Un site mal conçu."),
            (1.56, "✗  Des réseaux abandonnés."),
            (4.55, "✗  Des visuels qui ne donnent pas envie."),
        ]
        ml = 80
        py = H//2-int(H*0.33)
        ph_lh = int(H*0.08)
        for i,(pt,ptxt) in enumerate(problems):
            pa = eo(rm(t, pt, pt+0.4))
            if pa <= 0: continue
            dx = int(32*(1-pa))
            c.d.text((ml-dx, py+i*ph_lh), ptxt, font=f_p,
                     fill=ca(DGRAY, pa))

        # "= Des clients perdus. Chaque jour. En silence."
        eq_a = eo(rm(t, 6.6, 7.1))
        if eq_a > 0:
            sep_w = int((W-160)*eo(rm(t,6.3,6.8)))
            c.d.rounded_rectangle([(80,py+len(problems)*ph_lh+10),
                                    (80+sep_w, py+len(problems)*ph_lh+12)],
                                   radius=2, fill=ca(LGRAY,0.8))

            impact_lines = ["Des clients perdus.", "Chaque jour.", "En silence."]
            starts = [6.6, 7.93, 9.08]
            iy = py+len(problems)*ph_lh+30
            for j,(it,il) in enumerate(zip(starts, impact_lines)):
                ia = eo(rm(t, it, it+0.4))
                if ia > 0:
                    col = RED if j==0 else DGRAY
                    c.d.text((ml, iy+j*int(H*0.065)), il, font=f_e,
                             fill=ca(col, ia))

        # Agency cards
        agencies = [
            (12.93, "Site internet",    "3 semaines"),
            (16.44, "Contenu réseaux",  "10 jours"),
            (20.53, "Identité visuelle","1 mois"),
            (23.30, "Budget total",     "plusieurs milliers €"),
        ]
        cw, ch = int(W*0.82), int(H*0.085)
        cx = (W-cw)//2
        card_y = H//2+int(H*0.08)
        c_gap = int(ch*1.18)
        for i,(ct2,label,time) in enumerate(agencies):
            ca2 = eo(rm(t, ct2, ct2+0.5))
            if ca2 <= 0: continue
            dy2 = int(28*(1-ca2))
            ty2 = card_y + i*c_gap + dy2

            # Card bg
            c.d.rounded_rectangle([(cx,ty2),(cx+cw,ty2+ch)],
                                   radius=12,
                                   fill=ca(LGRAY, ca2*0.6),
                                   outline=ca(RED, ca2*0.2), width=1)
            # Label
            c.d.text((cx+20, ty2+ch//2-tsz(label,f_c)[1]//2),
                     label, font=f_c, fill=ca(DGRAY, ca2))
            # Time
            tw_t,th_t = tsz(time,f_t)
            c.d.text((cx+cw-tw_t-20, ty2+ch//2-th_t//2),
                     time, font=f_t, fill=ca(RED, ca2*0.8))
            # Strike-through
            sp2 = eo(rm(t, ct2+0.4, ct2+0.9))
            if sp2 > 0:
                sw2 = int(cw*sp2)
                sy2 = ty2+ch//2
                c.d.rounded_rectangle([(cx,sy2-1),(cx+sw2,sy2+2)],
                                       radius=2, fill=ca(RED,ca2*0.6))

        return c.arr()
    return mksc(f, dur)


# ── SCENE 10 — VELIXIA REVEAL (138.17 → 153.81s) ─────────────────────────────
def sc_velixia(scene_start, dur):
    f_name = F(int(W*0.16))
    f_diff = F(int(W*0.040),'italic')
    f_ia   = F(int(W*0.032),'light')
    f_cmp  = F(int(W*0.065))
    f_new  = F(int(W*0.095))
    f_ch   = F(int(W*0.070))
    f_url  = F(int(W*0.082))

    def f(t, d):
        # local 0 = 138.17 "Velixia,"
        # local 1.27 = 139.44 "c'est différent."
        # local 4.15 = 142.32 "...propulsée par l'IA pour faire en 24h..."
        # local 5.16 = 143.33 "...ce qu'une agence classique..."
        # local 6.90 = 145.07 "..."
        # local 9.22 = 147.39 "À 3 fois"
        # local 10.51 = 148.68 "moins cher."
        # local 11.83 = 150.00 "velix-ia.com"

        c = C(BG)

        # Background: large green circle burst
        glow_p = cl(t/3.0)
        if glow_p > 0:
            gr = int(W*0.6*glow_p)
            gl = Image.new("RGBA",(W,H),(0,0,0,0))
            gd = ImageDraw.Draw(gl)
            for r in [gr, gr*2//3, gr//3]:
                a2 = int(20*(1-r/gr)*glow_p)
                gd.ellipse([(W//2-r,H//4-r),(W//2+r,H//4+r)],
                           fill=(*GREEN,max(0,a2)))
            gl = gl.filter(ImageFilter.GaussianBlur(50))
            c.im = Image.alpha_composite(c.im.convert("RGBA"),gl).convert("RGB")
            c.d = ImageDraw.Draw(c.im)

        # "VELIXIA" logo pop
        av = sp(rm(t, 0.1, 0.8))
        if av > 0:
            tw,th = tsz("VELIXIA",f_name)
            sc2 = 1.0 + 0.08*(1-av)
            c.d.text(((W-tw)//2, H//2-th//2-int(H*0.2)), "VELIXIA",
                     font=f_name, fill=ca(INK, av))
            # Green dot
            c.dot(W//2+tw//2+18, H//2-int(H*0.2)+th//2,
                  int(10*(0.8+0.2*math.sin(t*5))), GREEN)
            up_v = eo(rm(t, 0.7, 1.4))
            c.underline(W//2, H//2-int(H*0.2)+th+12,
                        tw, 8, GREEN, up_v)

        # "c'est différent."
        ad = eo(rm(t, 1.27, 1.75))
        if ad > 0:
            txt = "c'est différent."
            tw,_ = tsz(txt,f_diff)
            c.d.text(((W-tw)//2, H//2-int(H*0.07)), txt, font=f_diff,
                     fill=ca(GRAY, ad))

        # "propulsée par l'intelligence artificielle"
        c.word_stream(
            "propulsée par l'intelligence artificielle",
            f_ia, H//2+int(H*0.04), 2.15, t, dpw=0.08, col=GRAY)

        # COMPARISON: "3 semaines → 24 heures"
        ac = sp(rm(t, 4.15, 4.9))
        if ac > 0:
            tw_o,th_o = tsz("3 semaines",f_cmp)
            tw_n,th_n = tsz("24 heures", f_new)
            g2 = 50
            total_w = tw_o+g2+40+tw_n
            x0 = (W-total_w)//2
            cy2 = H//2+int(H*0.2)
            # Old (struck)
            c.d.text((x0, cy2-th_o//2), "3 semaines", font=f_cmp,
                     fill=ca(RED, ac*0.6))
            # Strike
            c.d.rounded_rectangle([(x0,cy2),(x0+tw_o,cy2+3)],
                                   radius=2, fill=ca(RED, ac*0.8))
            # Arrow
            c.d.text((x0+tw_o+g2//4, cy2-th_o//4), "→", font=f_cmp,
                     fill=ca(LGRAY, ac))
            # New
            c.d.text((x0+tw_o+g2+38, cy2-th_n//2), "24 heures",
                     font=f_new, fill=ca(GREEN, ac))

        # "À 3× moins cher."
        ach = sp(rm(t, 9.22, 10.0))
        if ach > 0:
            txt = "À 3× moins cher."
            tw,th = tsz(txt,f_ch)
            c.d.text(((W-tw)//2, H//2+int(H*0.35)), txt, font=f_ch,
                     fill=ca(GREEN, ach))
            # Box
            c.d.rounded_rectangle(
                [(W//2-tw//2-16, H//2+int(H*0.35)-10),
                 (W//2+tw//2+16, H//2+int(H*0.35)+th+10)],
                radius=14, outline=ca(GREEN,ach*0.5), width=2)

        # "velix-ia.com" CTA
        aurl = sp(rm(t, 11.83, 12.7))
        if aurl > 0:
            tw,th = tsz("velix-ia.com",f_url)
            uy = H//2+int(H*0.5)
            c.d.text(((W-tw)//2, uy), "velix-ia.com", font=f_url,
                     fill=ca(GREEN, aurl))
            up_url = eo(rm(t, 12.3, 13.2))
            c.underline(W//2, uy+th+10, tw, 8, GREEN, up_url)

        # Fade to white at very end
        fe = rm(t, dur-1.5, dur)
        if fe > 0:
            c.d.rectangle([(0,0),(W,H)], fill=ca(BG, fe))

        return c.arr()
    return mksc(f, dur)


# ══════════════════════════════════════════════════════════════════════════════
# BUILD
# ══════════════════════════════════════════════════════════════════════════════
def build():
    print("Loading audio…")
    audio   = AudioFileClip(AUDIO)
    total_s = audio.duration
    print(f"  {total_s:.2f}s")

    print("Building scenes…")
    scenes = [
        sc_intro(ph(0)),                                     # 0 → 0.07
        sc_imaginez(ph(0),   ph(2)-ph(0)),                   # 0.07 → 7.84
        sc_chiffres(ph(2),   ph(5)-ph(2)),                   # 7.84 → 12.78
        sc_carleton(ph(5),   ph(8)-ph(5)),                   # 12.78 → 21.55
        sc_transition(ph(8), ph(10)-ph(8)),                  # 21.55 → 26.83
        sc_google(ph(10),    ph(14)-ph(10)),                  # 26.83 → 42.74
        sc_3sec(ph(14),      ph(19)-ph(14)),                  # 42.74 → 59.33
        sc_gloria(ph(19),    ph(27)-ph(19)),                  # 59.33 → 89.18
        sc_47(ph(27),        ph(31)-ph(27)),                  # 89.18 → 102.62
        sc_question(ph(31),  ph(33)-ph(31)),                  # 102.62 → 112.59
        sc_problems(ph(33),  ph(45)-ph(33)),                  # 112.59 → 138.17
        sc_velixia(ph(45),   total_s-ph(45)),                 # 138.17 → end
    ]

    total_built = sum(s.duration for s in scenes)
    print(f"  {len(scenes)} scenes = {total_built:.2f}s built / {total_s:.2f}s audio")

    video = concatenate_videoclips(scenes, method="compose")
    if video.duration > total_s:
        video = video.subclipped(0, total_s)
    video = video.with_audio(audio)

    print(f"Rendering {OUT}…")
    video.write_videofile(
        OUT, fps=FPS,
        codec="libx264", audio_codec="aac",
        preset="fast", threads=4, logger="bar",
    )
    print("Done ✓")

if __name__ == "__main__":
    build()
