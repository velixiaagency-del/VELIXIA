"""
VELIXIA — Motion Design Video Generator v2
Full 13-scene timeline synchronized with 153.81s voiceover.
Optimized rendering: local-area glow, cached backgrounds, 15fps.
Format: 1080×1920 TikTok
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import AudioFileClip, VideoClip, concatenate_videoclips, ColorClip
import os, math, warnings
warnings.filterwarnings("ignore")

AUDIO_PATH = "/home/user/VELIXIA/velixia_voiceover_v1.mp3"
OUT_PATH   = "/home/user/VELIXIA/velixia_tiktok_final.mp4"
W, H       = 1080, 1920
FPS        = 15   # smooth for motion graphics, 4× faster render

# ── Brand ──────────────────────────────────────────────────────────────────────
NOIR   = (15, 15, 15)
IVOIRE = (248, 246, 242)
VERT   = (34, 197, 94)
MUTED  = (122, 118, 110)
WHITE  = (255, 255, 255)
ROUGE  = (239, 68, 68)
ORANGE = (245, 158, 11)

# ── Fonts ──────────────────────────────────────────────────────────────────────
_fc = {}
def fnt(size, style='bold'):
    key = (size, style)
    if key in _fc: return _fc[key]
    paths = {
        'bold':   '/tmp/vfonts/Inter-Bold-conv.ttf',
        'light':  '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        'italic': '/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf',
    }
    try: f = ImageFont.truetype(paths.get(style, paths['bold']), size)
    except: f = ImageFont.load_default()
    _fc[key] = f
    return f

# ── Cached backgrounds ─────────────────────────────────────────────────────────
_bg_cache = {}
def bg(col):
    if col in _bg_cache: return _bg_cache[col].copy()
    arr = np.zeros((H, W, 3), dtype=np.float32)
    bot = tuple(max(0, c-14) for c in col)
    for c in range(3): arr[:,:,c] = np.linspace(col[c], bot[c], H)[:,None]
    img = Image.fromarray(arr.astype(np.uint8))
    _bg_cache[col] = img
    return img.copy()

def bg_lerp(col_a, col_b, t):
    t = max(0.0, min(1.0, t))
    c = tuple(int(a*(1-t)+b*t) for a,b in zip(col_a, col_b))
    return bg(c)

# ── Easing ─────────────────────────────────────────────────────────────────────
def eo(t, n=3):  return 1-(1-clamp(t))**n
def spring(t):
    t = clamp(t)
    if t >= 1: return 1.0
    c4 = (2*math.pi)/3
    return 1-(2**(-10*t))*math.sin((t*10-0.75)*c4)
def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def remap(t, i0, i1, o0=0.0, o1=1.0):
    return o0+(o1-o0)*clamp((t-i0)/(i1-i0) if i1!=i0 else 1.0)

# ── Draw helpers ───────────────────────────────────────────────────────────────
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

def col_a(col, a): return tuple(int(v*clamp(a)) for v in col)

def glow_text(img, text, cx, cy, font, color, glow_col, radius=16):
    """Fast local-area glow — only blurs a small crop."""
    tw, th = tsz(text, font)
    tx = (W-tw)//2 if cx is None else cx
    pad = radius*2
    # Draw glow on small crop
    cw, ch = tw+pad*2, th+pad*2
    cw, ch = max(1,cw), max(1,ch)
    crop = Image.new("RGBA", (cw, ch), (0,0,0,0))
    cd = ImageDraw.Draw(crop)
    for r in range(radius, 0, -4):
        a = int(90*(1-r/radius))
        cd.text((pad, pad), text, font=font, fill=(*glow_col, a))
    crop = crop.filter(ImageFilter.GaussianBlur(radius//3+1))
    # Composite onto main image
    px, py = tx-pad, cy-pad
    base = img.convert("RGBA")
    base.paste(crop, (px, py), crop)
    img = base.convert("RGB")
    # Draw crisp text
    ImageDraw.Draw(img).text((tx, cy), text, font=font, fill=color)
    return img

def text_center(img, text, cy, font, color, glow=None, glow_r=14):
    tw, th = tsz(text, font)
    cx = (W-tw)//2
    if glow:
        img = glow_text(img, text, cx, cy, font, color, glow, glow_r)
    else:
        ImageDraw.Draw(img).text((cx, cy), text, font=font, fill=color)
    return img, tw, th

def words_reveal(img, draw, text, font, cy, start_t, t,
                 dpw=0.09, color=WHITE, max_w=None):
    """Render word-by-word reveal; returns image."""
    max_w = max_w or int(W*0.82)
    lines = wrap(text, font, max_w)
    lh = int(tsz("Ag",font)[1]*1.4)
    total_h = lh*(len(lines)-1)
    y = cy - total_h//2
    word_idx = 0
    for line in lines:
        words = line.split()
        tw_line = tsz(line, font)[0]
        x = (W-tw_line)//2
        for word in words:
            wt = start_t + word_idx*dpw
            wa = eo(remap(t, wt, wt+0.3))
            if wa > 0:
                col = col_a(color, wa)
                draw.text((x, y), word+" ", font=font, fill=col)
            pw = tsz(word+" ", font)[0]
            x += pw
            word_idx += 1
        y += lh
    return img

def vbar(draw, color=VERT, w=9, h_frac=1.0, alpha=1.0):
    c = col_a(color, alpha)
    draw.rectangle([(0,0),(w, int(H*h_frac))], fill=c)

def green_dot(img, x, y, size=11, alpha=1.0, glow=True):
    if glow:
        gl = Image.new("RGBA",(W,H),(0,0,0,0))
        gd = ImageDraw.Draw(gl)
        for r in [size+14, size+8, size+3]:
            a = int(45*(1-(r-size)/16)*alpha)
            gd.ellipse([(x-r,y-r),(x+r,y+r)], fill=(*VERT,max(0,a)))
        gl = gl.filter(ImageFilter.GaussianBlur(6))
        img = Image.alpha_composite(img.convert("RGBA"),gl).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.ellipse([(x-size//2,y-size//2),(x+size//2,y+size//2)],
                 fill=col_a(VERT,alpha))
    return img

def rounded_card(img, x, y, w, h, fill, border=None, radius=16):
    card = Image.new("RGBA",(w,h),(0,0,0,0))
    cd   = ImageDraw.Draw(card)
    cd.rounded_rectangle([(0,0),(w-1,h-1)], radius=radius, fill=fill)
    if border: cd.rounded_rectangle([(0,0),(w-1,h-1)], radius=radius, outline=border, width=1)
    img  = img.convert("RGBA")
    img.paste(card, (x,y), card)
    return img.convert("RGB")

def pill_tag(img, text, cy, font=None, on_dark=True):
    f = font or fnt(24,'light')
    tw,th = tsz(text,f)
    px, py_pad = 22, 9
    pw, ph = tw+px*2, th+py_pad*2
    fill = (20,20,20,170) if on_dark else (15,15,15,28)
    img = rounded_card(img, (W-pw)//2, cy-ph//2, pw, ph, fill, radius=ph//2)
    ImageDraw.Draw(img).text(((W-tw)//2, cy-th//2), text, font=f, fill=MUTED)
    return img

def underline_wipe(draw, cx, y, max_w, progress, color=VERT, h=4):
    w = int(max_w*clamp(progress))
    if w > 0:
        x0 = cx-max_w//2
        draw.rounded_rectangle([(x0,y),(x0+w,y+h)], radius=2, fill=color)

def make_scene(fn, duration):
    return VideoClip(lambda t: fn(t, duration), duration=duration)


# ══════════════════════════════════════════════════════════════════════════════
#  SCENES
# ══════════════════════════════════════════════════════════════════════════════

def sc_cold(dur):
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        # green bar scaleY from top
        bar_h = int(H * eo(remap(t, 0, 0.6)))
        draw.rectangle([(0,0),(9, bar_h)], fill=VERT)
        # dot
        da = eo(remap(t, 0.3, 0.7))
        if da > 0:
            pulse = 0.8+0.2*math.sin(t*math.pi*2.5)
            img = green_dot(img, 32, H-220, size=int(8*pulse), alpha=da)
            draw = ImageDraw.Draw(img)
        # brand label
        la = eo(remap(t, 0.5, 1.0))
        if la > 0:
            fl = fnt(26,'light')
            txt = "VELIXIA × IA"
            tw,_ = tsz(txt,fl)
            draw.text((W-tw-52, 58), txt, font=fl,
                      fill=col_a(WHITE, la*0.22))
        return np.array(img)
    return make_scene(f, dur)


def sc_imaginez(dur):
    f_xl   = fnt(int(W*0.155),'bold')
    f_big  = fnt(int(W*0.105),'bold')
    f_body = fnt(int(W*0.033),'light')
    f_md   = fnt(int(W*0.062),'bold')
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        pulse = 0.8+0.2*math.sin(t*math.pi*2.5)
        img = green_dot(img, 32, H-220, size=int(8*pulse)); draw=ImageDraw.Draw(img)

        cy = H//2
        gap = int(H*0.068)

        # "Imaginez."
        a1 = eo(remap(t, 0, 0.4))
        if a1>0:
            dy = int(28*(1-a1))
            img = text_center(img, "Imaginez.", cy-gap*2-dy, f_xl,
                              col_a(WHITE,a1), glow=VERT, glow_r=28)[0]
            draw=ImageDraw.Draw(img)

        lines_body = [
            (0.7, "Votre futur client",        cy-gap+0),
            (1.4, "ouvre son téléphone…",       cy+0),
            (2.1, "tombe sur votre concurrent…",cy+gap),
        ]
        for (st, txt, yp) in lines_body:
            a = eo(remap(t, st, st+0.4))
            if a>0:
                tw,th = tsz(txt,f_body)
                draw.text(((W-tw)//2, yp-th//2), txt, font=f_body,
                          fill=col_a((200,200,200),a*0.65))

        # "50 millisecondes" pop
        a3 = spring(remap(t, 2.8, 3.35))
        if a3>0:
            sc_off = int(20*(1-a3))
            img = text_center(img, "50 millisecondes",
                              cy+gap*2+sc_off, f_big,
                              col_a(VERT,a3), glow=VERT, glow_r=35)[0]
            draw=ImageDraw.Draw(img)

        # "il a déjà décidé."
        a4 = eo(remap(t, 3.8, 4.2))
        if a4>0:
            dx = int(40*(1-a4))
            tw,th = tsz("il a déjà décidé.", f_md)
            draw.text(((W-tw)//2+dx, cy+gap*3-th//2),
                      "il a déjà décidé.", font=f_md, fill=col_a(WHITE,a4))

        return np.array(img)
    return make_scene(f, dur)


def sc_chiffres(dur):
    f_struck = fnt(int(W*0.038),'light')
    f_big    = fnt(int(W*0.085),'bold')
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        ml = int(W*0.12)
        base_y = H//2 - int(H*0.1)
        lh = int(H*0.095)
        items = [(0.0,"Pas en 3 secondes."),(0.85,"Pas en 1 seconde.")]
        for i,(st,txt) in enumerate(items):
            a = eo(remap(t, st, st+0.35))
            if a<=0: continue
            tw,th = tsz(txt,f_struck)
            ty = base_y+i*lh
            draw.text((ml, ty), txt, font=f_struck, fill=col_a(WHITE,a*0.38))
            sp = eo(remap(t, st+0.2, st+0.55))
            if sp>0:
                sw = int(tw*sp)
                sy = ty+th//2
                draw.rectangle([(ml,sy-2),(ml+sw,sy+2)], fill=ROUGE)

        a3 = spring(remap(t, 1.6, 2.15))
        if a3>0:
            img = text_center(img,"En 50 millisecondes.",
                              base_y+lh*2, f_big,
                              col_a(VERT,a3), glow=VERT, glow_r=30)[0]
        return np.array(img)
    return make_scene(f, dur)


def sc_carleton(dur):
    f_body = fnt(int(W*0.032),'light')
    f_ital = fnt(int(W*0.030),'italic')
    f_choc = fnt(int(W*0.034),'bold')
    def f(t, d):
        bg_t = clamp(t/0.6)
        col_ = tuple(int(NOIR[i]*(1-bg_t)+IVOIRE[i]*bg_t) for i in range(3))
        img  = bg(col_)
        draw = ImageDraw.Draw(img)
        # black bar
        draw.rectangle([(0,0),(9,H)], fill=col_a(NOIR, eo(remap(t,0,0.5))))
        # source tag
        tag_a = eo(remap(t,0.3,0.7))
        if tag_a>0:
            img = pill_tag(img,"UNIVERSITÉ DE CARLETON — 2002",
                           H//2-int(H*0.26), on_dark=False)
            draw=ImageDraw.Draw(img)
        # words1
        img = words_reveal(img, ImageDraw.Draw(img),
                           "L'Université de Carleton a prouvé en 2002…",
                           f_body, H//2-int(H*0.1), 0.5, t,
                           dpw=0.09, color=NOIR, max_w=int(W*0.82))
        # words2
        img = words_reveal(img, ImageDraw.Draw(img),
                           "La première impression visuelle d'un site…",
                           f_ital, H//2+int(H*0.02), 1.8, t,
                           dpw=0.09, color=MUTED, max_w=int(W*0.82))
        draw=ImageDraw.Draw(img)
        # choc phrase
        ca = eo(remap(t,3.0,3.5))
        if ca>0:
            txt = "se forme avant que le cerveau lise un mot."
            tw,th = tsz(txt,f_choc)
            ty = H//2+int(H*0.14)
            draw.text(((W-tw)//2, ty), txt, font=f_choc, fill=col_a(NOIR,ca))
            up = eo(remap(t,3.3,3.9))
            underline_wipe(draw, W//2, ty+th+8, tw, up)
        return np.array(img)
    return make_scene(f, dur)


def sc_transition(dur):
    f = fnt(int(W*0.065),'bold')
    words = "Et ce n'est pas tout.".split()
    def fn(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        full = " ".join(words)
        tw,th = tsz(full,f)
        x = (W-tw)//2
        cx = x
        for i,w in enumerate(words):
            wa = spring(remap(t, i*0.13, i*0.13+0.35))
            if wa>0:
                sc = 0.7+0.3*wa
                ww,_ = tsz(w+" ",f)
                draw.text((cx, H//2-th//2), w+" ", font=f,
                          fill=col_a(WHITE,wa))
            cx += tsz(w+" ",f)[0]
        return np.array(img)
    return make_scene(fn, dur)


def sc_google(dur):
    f_body = fnt(int(W*0.031),'light')
    f_cnt  = fnt(int(W*0.195),'bold')
    f_sub  = fnt(int(W*0.034),'light')
    f_imp  = fnt(int(W*0.068),'bold')
    f_big  = fnt(int(W*0.095),'bold')
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        pulse = 0.8+0.2*math.sin(t*math.pi*2.5)
        img = green_dot(img,32,H-220,size=int(8*pulse)); draw=ImageDraw.Draw(img)

        # tag
        ta = eo(remap(t,0.2,0.6))
        if ta>0:
            txt = "Google / SOASTA Research — 2017"
            draw.text((80, H-230), txt, font=fnt(24,'light'),
                      fill=col_a(WHITE,ta*0.28))

        # words
        img = words_reveal(img, ImageDraw.Draw(img),
                           "Google a analysé des millions de pages mobiles en 2017.",
                           f_body, H//2-int(H*0.3), 0.3, t, dpw=0.075,
                           color=(200,200,200), max_w=int(W*0.82))

        # "Leur conclusion —"
        la = eo(remap(t,1.6,2.0))
        if la>0:
            tw,th = tsz("Leur conclusion —", f_sub)
            draw.text(((W-tw)//2, H//2-int(H*0.18)),
                      "Leur conclusion —", font=f_sub,
                      fill=col_a(WHITE,la*0.8))

        # counter
        ct = remap(t,2.1,3.5)
        if ct>0:
            val = int(eo(ct,4)*53)
            cnt_txt = f"{val}%"
            tw,th = tsz(cnt_txt,f_cnt)
            ty = H//2-th//2-int(H*0.04)
            img = glow_text(img,cnt_txt,(W-tw)//2, ty, f_cnt,
                            col_a(VERT,eo(ct)), VERT, radius=50)
            draw=ImageDraw.Draw(img)

        # sub
        s1a = eo(remap(t,3.6,4.0))
        if s1a>0:
            t1="des visiteurs abandonnent"
            tw,th = tsz(t1,f_sub)
            draw.text(((W-tw)//2,H//2+int(H*0.13)),t1,font=f_sub,
                      fill=col_a(WHITE,s1a*0.55))
        s2a = eo(remap(t,4.1,4.5))
        if s2a>0:
            t2="un site qui charge en +3 secondes."
            tw,_ = tsz(t2,f_sub)
            draw.text(((W-tw)//2,H//2+int(H*0.19)),t2,font=f_sub,
                      fill=col_a(WHITE,s2a*0.55))

        # "Plus de la moitié. / Partis. / Pour toujours."
        impacts = [(5.0,"Plus de la moitié.",f_imp,WHITE),
                   (5.8,"Partis.",           f_big, ROUGE),
                   (6.5,"Pour toujours.",    f_imp, ROUGE)]
        iy = H//2+int(H*0.28)
        for (st,txt,ff,col) in impacts:
            ia = spring(remap(t,st,st+0.35))
            if ia>0:
                tw,th = tsz(txt,ff)
                c = col_a(col,ia)
                if col==ROUGE:
                    img = glow_text(img,txt,(W-tw)//2,iy,ff,c,ROUGE,radius=20)
                    draw=ImageDraw.Draw(img)
                else:
                    draw.text(((W-tw)//2,iy),txt,font=ff,fill=c)
            iy += int(H*0.09)
        return np.array(img)
    return make_scene(f, dur)


def sc_3sec(dur):
    f_big  = fnt(int(W*0.38),'bold')
    f_word = fnt(int(W*0.09),'bold')
    f_sub  = fnt(int(W*0.031),'light')
    def f(t, d):
        bg_t = clamp(t/0.6)
        col_ = tuple(int(NOIR[i]*(1-bg_t)+IVOIRE[i]*bg_t) for i in range(3))
        img  = bg(col_)
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0,0),(9,H)], fill=col_a(NOIR,eo(remap(t,0,0.5))))

        cy = H//2-int(H*0.08)
        a1 = spring(remap(t,0.2,0.75))
        if a1>0:
            img = text_center(img,"3",cy-int(H*0.1),f_big,
                              col_a(NOIR,a1),glow=None)[0]
            draw=ImageDraw.Draw(img)

        a2 = eo(remap(t,1.0,1.5))
        if a2>0:
            dx = int(45*(1-a2))
            tw,th = tsz("secondes.",f_word)
            draw.text(((W-tw)//2+dx, cy+int(H*0.2)),
                      "secondes.", font=f_word, fill=col_a(NOIR,a2))

        a3 = eo(remap(t,1.8,2.3))
        if a3>0:
            dy=int(12*(1-a3))
            txt="pour décider si vous méritez leur attention."
            lines=wrap(txt,f_sub,int(W*0.78))
            ty=cy+int(H*0.3)+dy
            for l in lines:
                tw,th=tsz(l,f_sub)
                draw.text(((W-tw)//2,ty),l,font=f_sub,fill=col_a(MUTED,a3))
                ty+=int(th*1.4)

        a4 = eo(remap(t,2.7,3.2))
        if a4>0:
            f_imp=fnt(int(W*0.036),'bold')
            txt="pour décider si vous existez."
            tw,th=tsz(txt,f_imp)
            ty=cy+int(H*0.44)
            draw.text(((W-tw)//2,ty),txt,font=f_imp,fill=col_a(NOIR,a4))
            up=eo(remap(t,3.0,3.6))
            underline_wipe(draw,W//2,ty+th+8,tw,up)
        return np.array(img)
    return make_scene(f, dur)


def sc_gloria(dur):
    f_intro=fnt(int(W*0.032),'italic')
    f_body =fnt(int(W*0.028),'light')
    f_year =fnt(int(W*0.058),'bold')
    f_time =fnt(int(W*0.035),'light')
    cards = [
        (0.8,  "2004","2 min 30 sec",VERT),
        (2.2,  "2012","75 secondes",ORANGE),
        (3.8,  "2023","47 secondes",ROUGE),
    ]
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        pulse=0.8+0.2*math.sin(t*math.pi*2.5)
        img=green_dot(img,32,H-220,size=int(8*pulse)); draw=ImageDraw.Draw(img)

        ia=eo(remap(t,0,0.4))
        if ia>0:
            txt="Et même quand ils restent…"
            tw,_=tsz(txt,f_intro)
            draw.text(((W-tw)//2,H//2-int(H*0.37)),txt,font=f_intro,
                      fill=col_a(WHITE,ia*0.5))

        img=pill_tag(img,"Gloria Mark — UC Irvine — Attention Span (2023)",
                     H//2-int(H*0.28)); draw=ImageDraw.Draw(img)

        img=words_reveal(img,draw,
            "mesure notre temps d'attention sur écran depuis 20 ans.",
            f_body,H//2-int(H*0.18),0.5,t,dpw=0.07,
            color=(190,190,190),max_w=int(W*0.82))
        draw=ImageDraw.Draw(img)

        cw,ch=int(W*0.82),int(H*0.09)
        cx=(W-cw)//2
        base_y=H//2-int(H*0.02)
        gap=int(ch*1.5)
        for i,(st,year,ttime,col) in enumerate(cards):
            ca=eo(remap(t,st,st+0.4))
            if ca<=0: continue
            dy=int(35*(1-ca))
            this_ch=int(ch*(1.12 if i==2 else 1.0))
            this_y=base_y+i*gap+dy
            # card bg
            fill=(*col,int(18*ca))
            border=(*col,int(70*ca))
            img=rounded_card(img,cx,this_y,cw,this_ch,fill,border=border,radius=14)
            draw=ImageDraw.Draw(img)
            col_y=col_a(col,ca)
            draw.text((cx+28,this_y+this_ch//2-tsz(year,f_year)[1]//2),
                      year,font=f_year,fill=col_y)
            tw2,th2=tsz(ttime,f_time)
            draw.text((cx+cw-tw2-28,this_y+this_ch//2-th2//2),
                      ttime,font=f_time,fill=col_a(WHITE,ca*0.7))
            # arrow between cards
            if i<2:
                aa=eo(remap(t,st+0.3,st+0.7))
                if aa>0:
                    ay0=this_y+this_ch+6
                    ay1=ay0+int(20*aa)
                    draw.line([(W//2,ay0),(W//2,ay1)],
                              fill=col_a(ROUGE,aa*0.6),width=3)
        return np.array(img)
    return make_scene(f, dur)


def sc_47(dur):
    f_main=fnt(int(W*0.155),'bold')
    f_line=fnt(int(W*0.058),'bold')
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        ml=int(W*0.1)
        am=spring(remap(t,0,0.65))
        if am>0:
            img=glow_text(img,"47 secondes.",None,
                         H//2-int(H*0.3),f_main,
                         col_a(VERT,am),VERT,radius=50)
            draw=ImageDraw.Draw(img)
            tw,th=tsz("47 secondes.",f_main)
            up=eo(remap(t,0.5,1.1))
            underline_wipe(draw,(W-tw)//2+tw//2,
                          H//2-int(H*0.3)+th+10,tw,up)

        lines_data=[
            (1.5,"pour convaincre.",WHITE,0),
            (3.0,"pour vendre.",(200,200,200),1),
            (4.6,"pour tout.",VERT,2),
        ]
        cy_base=H//2+int(H*0.08)
        lh=int(H*0.09)
        for (st,txt,col,idx) in lines_data:
            a=eo(remap(t,st,st+0.4))
            if a<=0: continue
            dx=int(38*(1-a))
            tw,th=tsz(txt,f_line)
            c=col_a(col,a)
            draw.text((ml-dx,cy_base+idx*lh),txt,font=f_line,fill=c)
            if col==VERT and a>0.5:
                pulse=0.8+0.2*math.sin(t*math.pi*3.5)
                img=green_dot(img,ml+tw+22,
                              cy_base+idx*lh+th//2,
                              size=int(9*pulse),alpha=a)
                draw=ImageDraw.Draw(img)
        return np.array(img)
    return make_scene(f, dur)


def sc_question(dur):
    f_title=fnt(int(W*0.062),'bold')
    f_body =fnt(int(W*0.033),'light')
    f_q    =fnt(int(W*0.040),'bold')
    def f(t, d):
        bg_t=clamp(t/0.6)
        col_=tuple(int(NOIR[i]*(1-bg_t)+IVOIRE[i]*bg_t) for i in range(3))
        img=bg(col_)
        draw=ImageDraw.Draw(img)
        draw.rectangle([(0,0),(9,H)],fill=col_a(NOIR,eo(remap(t,0,0.5))))

        at=spring(remap(t,0.2,0.65))
        if at>0:
            tw,th=tsz("Posez-vous cette question.",f_title)
            dy=int(22*(1-at))
            draw.text(((W-tw)//2,H//2-int(H*0.22)-dy),
                      "Posez-vous cette question.",font=f_title,
                      fill=col_a(NOIR,at))

        img=words_reveal(img,ImageDraw.Draw(img),
            "Est-ce que votre présence digitale actuelle…",
            f_body,H//2,1.2,t,dpw=0.085,
            color=MUTED,max_w=int(W*0.82))
        draw=ImageDraw.Draw(img)

        aq=eo(remap(t,2.5,3.0))
        if aq>0:
            txt="mérite ces 47 secondes ?"
            tw,th=tsz(txt,f_q)
            ty=H//2+int(H*0.15)
            draw.text(((W-tw)//2,ty),txt,font=f_q,fill=col_a(NOIR,aq))
            up=eo(remap(t,2.9,3.5))
            underline_wipe(draw,W//2,ty+th+8,tw,up)
        return np.array(img)
    return make_scene(f, dur)


def sc_concurrents(dur):
    f_prob=fnt(int(W*0.032),'light')
    f_eq  =fnt(int(W*0.034),'bold')
    f_cb  =fnt(int(W*0.026),'light')
    f_ct  =fnt(int(W*0.026),'bold')
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        pulse=0.8+0.2*math.sin(t*math.pi*2.5)
        img=green_dot(img,32,H-220,size=int(8*pulse)); draw=ImageDraw.Draw(img)

        probs=[(0.2,"Un site mal conçu."),
               (0.9,"Des réseaux abandonnés."),
               (1.7,"Des visuels qui ne donnent pas envie.")]
        py=H//2-int(H*0.32)
        ph=int(H*0.072)
        for i,(st,txt) in enumerate(probs):
            a=eo(remap(t,st,st+0.4))
            if a<=0: continue
            dx=int(35*(1-a))
            draw.text((80-dx,py+i*ph),
                      "✗  "+txt,font=f_prob,fill=col_a(WHITE,a*0.6))

        eq_a=eo(remap(t,2.3,2.8))
        if eq_a>0:
            txt="= Des clients perdus. Chaque jour. En silence."
            lines=wrap(txt,f_eq,int(W*0.82))
            ty=py+len(probs)*ph+int(H*0.03)
            for l in lines:
                tw,th=tsz(l,f_eq)
                draw.text(((W-tw)//2,ty),l,font=f_eq,fill=col_a(ROUGE,eq_a))
                ty+=int(th*1.4)

        # separator
        sp=eo(remap(t,2.9,3.4))
        if sp>0:
            sw=int((W-160)*sp)
            draw.rectangle([(80,H//2+int(H*0.01)),
                            (80+sw,H//2+int(H*0.01)+1)],
                           fill=col_a(WHITE,0.1))

        # bad agency cards
        bad_cards=[(3.1,"Site internet","3 semaines"),
                   (3.7,"Contenu réseaux","10 jours"),
                   (4.3,"Identité visuelle","1 mois"),
                   (4.9,"Facturé","plusieurs milliers €")]
        cw=int(W*0.82); cx=(W-cw)//2
        ch=int(H*0.075)
        by=H//2+int(H*0.06)
        gap=int(ch*1.2)
        for i,(st,label,time) in enumerate(bad_cards):
            ca=eo(remap(t,st,st+0.4))
            if ca<=0: continue
            dy=int(30*(1-ca))
            ty=by+i*gap+dy
            img=rounded_card(img,cx,ty,cw,ch,
                             (255,255,255,int(8*ca)),
                             border=(239,68,68,int(35*ca)),radius=12)
            draw=ImageDraw.Draw(img)
            draw.text((cx+22,ty+ch//2-tsz(label,f_cb)[1]//2),
                      label,font=f_cb,fill=col_a(WHITE,ca*0.5))
            tw2,th2=tsz(time,f_ct)
            draw.text((cx+cw-tw2-22,ty+ch//2-th2//2),
                      time,font=f_ct,fill=col_a(ROUGE,ca*0.7))
            # X cross
            xa=eo(remap(t,st+0.5,st+0.8))
            if xa>0:
                xf=fnt(20,'bold')
                draw.text((cx+cw-50,ty+ch//2-10),"✕",font=xf,
                          fill=col_a(ROUGE,xa))
        return np.array(img)
    return make_scene(f, dur)


def sc_velixia_reveal(dur):
    f_name=fnt(int(W*0.175),'bold')
    f_diff=fnt(int(W*0.042),'italic')
    f_ia  =fnt(int(W*0.030),'light')
    f_cmp =fnt(int(W*0.070),'bold')
    f_new =fnt(int(W*0.095),'bold')
    f_ch  =fnt(int(W*0.075),'bold')
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        pulse=0.8+0.2*math.sin(t*math.pi*2.5)
        img=green_dot(img,32,H-220,size=int(8*pulse)); draw=ImageDraw.Draw(img)

        # pulsing glow ring
        pr=0.55+0.45*math.sin(t*math.pi*1.8)
        gr=int(W*0.38*pr)
        if gr>0:
            gl=Image.new("RGBA",(W,H),(0,0,0,0))
            gd=ImageDraw.Draw(gl)
            gd.ellipse([(W//2-gr,H//2-int(gr*0.55)),
                        (W//2+gr,H//2+int(gr*0.55))],
                       fill=(*VERT,int(28*pr)))
            gl=gl.filter(ImageFilter.GaussianBlur(45))
            img=Image.alpha_composite(img.convert("RGBA"),gl).convert("RGB")
            draw=ImageDraw.Draw(img)

        an=spring(remap(t,0,0.75))
        if an>0:
            tw,th=tsz("Velixia",f_name)
            img=glow_text(img,"Velixia",None,
                         H//2-th//2-int(H*0.15),f_name,
                         col_a(WHITE,an),VERT,radius=55)
            draw=ImageDraw.Draw(img)
            # dot
            img=green_dot(img,W//2+tw//2+28,H//2-int(H*0.15),
                         size=int(10*(0.8+0.2*math.sin(t*math.pi*3))),alpha=an)
            draw=ImageDraw.Draw(img)

        ad=eo(remap(t,0.9,1.3))
        if ad>0:
            txt="c'est différent."
            tw,_=tsz(txt,f_diff)
            draw.text(((W-tw)//2,H//2+int(H*0.03)),txt,font=f_diff,
                      fill=col_a(WHITE,ad*0.6))

        img=words_reveal(img,ImageDraw.Draw(img),
            "propulsée par l'intelligence artificielle",
            f_ia,H//2+int(H*0.13),1.4,t,dpw=0.06,
            color=(180,180,180),max_w=int(W*0.82))
        draw=ImageDraw.Draw(img)

        ac=spring(remap(t,2.1,2.7))
        if ac>0:
            tw_o,th_o=tsz("3 semaines",f_cmp)
            tw_n,th_n=tsz("24 heures", f_new)
            gap_x=55
            total_w=tw_o+gap_x+tw_n
            x0=(W-total_w)//2
            cy2=H//2+int(H*0.28)
            draw.text((x0,cy2-th_o//2),"3 semaines",font=f_cmp,
                      fill=col_a(ROUGE,ac*0.7))
            draw.line([(x0,cy2+4),(x0+tw_o,cy2+4)],fill=ROUGE,width=3)
            draw.text((x0+tw_o+10,cy2-th_o//4),"→",font=f_cmp,
                      fill=col_a(WHITE,ac*0.3))
            img=glow_text(img,"24 heures",x0+tw_o+gap_x,cy2-th_n//2,
                         f_new,col_a(VERT,ac),VERT,radius=30)
            draw=ImageDraw.Draw(img)

        ach=spring(remap(t,3.0,3.55))
        if ach>0:
            img=glow_text(img,"À 3× moins cher.",None,
                         H//2+int(H*0.4),f_ch,
                         col_a(VERT,ach),VERT,radius=28)
        return np.array(img)
    return make_scene(f, dur)


def sc_services(dur):
    f_ti=fnt(int(W*0.030),'bold')
    f_su=fnt(int(W*0.024),'light')
    f_tl=fnt(int(W*0.13),'bold')
    cards=[
        (0.3,"📱","Réseaux Sociaux","20 posts/mois créés & programmés"),
        (1.2,"🌐","Sites Internet","Livrés en 72h, SEO intégré"),
        (2.1,"✨","Visuels IA","Haute définition, sans shooting"),
    ]
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        cw=int(W*0.82); cx=(W-cw)//2
        ch=int(H*0.11); gap=int(ch*1.18)
        base_y=H//2-int(H*0.28)
        for i,(st,icon,title,sub) in enumerate(cards):
            ca=eo(remap(t,st,st+0.5))
            if ca<=0: continue
            dy=int(45*(1-ca))
            ty=base_y+i*gap+dy
            img=rounded_card(img,cx,ty,cw,ch,
                (34,197,94,int(20*ca)),(34,197,94,int(88*ca)),radius=20)
            draw=ImageDraw.Draw(img)
            # Icon
            fi=fnt(int(ch*0.46),'light')
            draw.text((cx+24,ty+ch//2-int(ch*0.28)),icon,font=fi,
                      fill=col_a(WHITE,ca))
            # Title & sub
            iw=tsz(icon,fi)[0]+24+16
            draw.text((cx+iw+24,ty+int(ch*0.15)),title,font=f_ti,
                      fill=col_a(WHITE,ca))
            draw.text((cx+iw+24,ty+int(ch*0.52)),sub,font=f_su,
                      fill=col_a(MUTED,ca))

        tout_a=spring(remap(t,3.0,3.6))
        if tout_a>0:
            img=glow_text(img,"TOUT.",None,H//2+int(H*0.28),f_tl,
                         col_a(WHITE,tout_a),VERT,radius=40)
        return np.array(img)
    return make_scene(f, dur)


def sc_conclusion(dur):
    f_b1=fnt(int(W*0.031),'italic')
    f_b2=fnt(int(W*0.034),'light')
    f_b3=fnt(int(W*0.037),'bold')
    def f(t, d):
        bg_t=clamp(t/0.7)
        col_=tuple(int(NOIR[i]*(1-bg_t)+IVOIRE[i]*bg_t) for i in range(3))
        img=bg(col_)
        draw=ImageDraw.Draw(img)
        draw.rectangle([(0,0),(9,H)],fill=col_a(NOIR,eo(remap(t,0,0.5))))
        img=words_reveal(img,ImageDraw.Draw(img),
            "Parce que dans un monde où l'attention dure 47 secondes…",
            f_b1,H//2-int(H*0.17),0.5,t,dpw=0.065,
            color=MUTED,max_w=int(W*0.82))
        img=words_reveal(img,ImageDraw.Draw(img),
            "chaque jour sans une présence forte…",
            f_b2,H//2,2.0,t,dpw=0.085,
            color=NOIR,max_w=int(W*0.82))
        draw=ImageDraw.Draw(img)
        a3=eo(remap(t,3.0,3.5))
        if a3>0:
            txt="est un jour offert à vos concurrents."
            lines=wrap(txt,f_b3,int(W*0.82))
            ty=H//2+int(H*0.14)
            for l in lines:
                tw,th=tsz(l,f_b3)
                draw.text(((W-tw)//2,ty),l,font=f_b3,fill=col_a(NOIR,a3))
                ty+=int(th*1.4)
            tw_full,th_full=tsz(txt,f_b3)
            up=eo(remap(t,3.4,4.1))
            underline_wipe(draw,W//2,H//2+int(H*0.14)+th_full+10,
                          tw_full,up,color=ROUGE)
        return np.array(img)
    return make_scene(f, dur)


def sc_outro(dur):
    f_logo=fnt(int(W*0.130),'bold')
    f_tag =fnt(int(W*0.028),'light')
    f_inf =fnt(int(W*0.025),'light')
    f_url =fnt(int(W*0.085),'bold')
    def f(t, d):
        img  = bg(NOIR)
        draw = ImageDraw.Draw(img)
        vbar(draw)
        # pulsing glow
        pr=0.6+0.4*math.sin(t*math.pi*2.2)
        gr=int(W*0.42*pr)
        if gr>0:
            gl=Image.new("RGBA",(W,H),(0,0,0,0))
            gd=ImageDraw.Draw(gl)
            gd.ellipse([(W//2-gr,H//2-int(gr*0.5)),
                        (W//2+gr,H//2+int(gr*0.5))],
                       fill=(*VERT,int(30*pr)))
            gl=gl.filter(ImageFilter.GaussianBlur(50))
            img=Image.alpha_composite(img.convert("RGBA"),gl).convert("RGB")
            draw=ImageDraw.Draw(img)

        al=eo(remap(t,0,0.7))
        if al>0:
            tw,th=tsz("VELIXIA",f_logo)
            img=glow_text(img,"VELIXIA",None,
                         H//2-th//2-int(H*0.18),f_logo,
                         col_a(WHITE,al),VERT,radius=55)
            draw=ImageDraw.Draw(img)
            pulse=0.8+0.2*math.sin(t*math.pi*3)
            img=green_dot(img,W//2+tw//2+28,H//2-int(H*0.18),
                         size=int(11*pulse),alpha=al)
            draw=ImageDraw.Draw(img)

        atag=eo(remap(t,0.7,1.2))
        if atag>0:
            txt="L'agence IA qui va plus vite, plus loin, pour moins cher."
            lines=wrap(txt,f_tag,int(W*0.8))
            ty=H//2+int(H*0.05)
            for l in lines:
                tw,th=tsz(l,f_tag)
                draw.text(((W-tw)//2,ty),l,font=f_tag,
                          fill=col_a(WHITE,atag*0.5))
                ty+=int(th*1.4)

        for i,info in enumerate(["Disponible 24h/24, 7j/7",
                                  "Basée à Lyon · Partout en France"]):
            ai=eo(remap(t,1.2+i*0.3,1.6+i*0.3))
            if ai>0:
                tw,_=tsz(info,f_inf)
                draw.text(((W-tw)//2,H//2+int(H*0.22)+i*int(H*0.048)),
                          info,font=f_inf,fill=col_a(WHITE,ai*0.35))

        au=spring(remap(t,1.8,2.4))
        if au>0:
            tw,th=tsz("velix-ia.com",f_url)
            uy=H//2+int(H*0.35)
            img=glow_text(img,"velix-ia.com",None,uy,f_url,
                         col_a(VERT,au),VERT,radius=35)
            draw=ImageDraw.Draw(img)
            up=eo(remap(t,2.2,2.9))
            underline_wipe(draw,W//2,uy+th+10,tw,up)

        # fade to black
        p=t/max(dur,0.001)
        if p>0.88:
            fa=(p-0.88)/0.12
            draw.rectangle([(0,0),(W,H)],fill=col_a(NOIR,fa))
        return np.array(img)
    return make_scene(f, dur)


# ══════════════════════════════════════════════════════════════════════════════
#  BUILD
# ══════════════════════════════════════════════════════════════════════════════
def build():
    print("Loading audio…")
    audio   = AudioFileClip(AUDIO_PATH)
    total_s = audio.duration
    print(f"  {total_s:.2f}s")

    # Scale every scene duration proportionally
    BASE = 85.0
    sc = total_s / BASE
    def d(secs): return secs * sc

    print("Building scenes…")
    clips = [
        sc_cold(d(2.0)),
        sc_imaginez(d(5.7)),
        sc_chiffres(d(3.0)),
        sc_carleton(d(6.5)),
        sc_transition(d(1.0)),
        sc_google(d(8.7)),
        sc_3sec(d(5.5)),
        sc_gloria(d(11.0)),
        sc_47(d(7.0)),
        sc_question(d(4.5)),
        sc_concurrents(d(8.0)),
        sc_velixia_reveal(d(7.5)),
        sc_services(d(4.5)),
        sc_conclusion(d(5.5)),
        sc_outro(d(5.0)),
    ]

    used = sum(c.duration for c in clips)
    if used < total_s:
        clips.append(ColorClip((W,H),color=NOIR,duration=total_s-used))
    print(f"  {len(clips)} scenes, total={sum(c.duration for c in clips):.1f}s")

    video = concatenate_videoclips(clips, method="compose")
    if video.duration > total_s:
        video = video.subclipped(0, total_s)
    video = video.with_audio(audio)

    print(f"Rendering {OUT_PATH}…")
    video.write_videofile(
        OUT_PATH, fps=FPS,
        codec="libx264", audio_codec="aac",
        preset="fast", threads=4, logger="bar",
    )
    print("Done ✓")

if __name__ == "__main__":
    build()
