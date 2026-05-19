"""
VELIXIA – Motion Design Video Generator
Style: dark premium SaaS/IA agency
Colors: #0F0F0F (noir), #F8F6F2 (ivoire), #22C55E (vert), #7a766e (muted)
Format: 1080×1920 TikTok + 1080×1080 Instagram
Audio: velixia_voiceover_v1.mp3 (6.3s preview)
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageColor
from moviepy import AudioFileClip, VideoClip, concatenate_videoclips, ColorClip
import os, math, random, warnings
warnings.filterwarnings("ignore")

AUDIO_PATH = "/home/user/VELIXIA/velixia_voiceover_v1.mp3"

# ── Brand colors ───────────────────────────────────────────────────────────────
NOIR   = (15, 15, 15)
IVOIRE = (248, 246, 242)
VERT   = (34, 197, 94)
MUTED  = (122, 118, 110)
WHITE  = (255, 255, 255)
ROUGE  = (239, 68, 68)
ORANGE = (245, 158, 11)

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_BOLD  = "/tmp/vfonts/Inter-Bold-conv.ttf"
FONT_SANS  = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_LIGHT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_ITALIC= "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf"

_fc = {}
def fnt(size, style='bold'):
    key = (size, style)
    if key in _fc: return _fc[key]
    path = {
        'bold':   FONT_BOLD,
        'sans':   FONT_SANS,
        'light':  FONT_LIGHT,
        'italic': FONT_ITALIC,
    }.get(style, FONT_BOLD)
    try:
        f = ImageFont.truetype(path, size)
    except:
        f = ImageFont.load_default()
    _fc[key] = f
    return f

# ── Helpers ────────────────────────────────────────────────────────────────────
def tsz(text, font):
    bb = font.getbbox(text)
    return bb[2]-bb[0], bb[3]-bb[1]

def wrap(text, font, max_w):
    words, lines, line = text.split(), [], []
    for w in words:
        test = " ".join(line+[w])
        if tsz(test, font)[0] <= max_w or not line:
            line.append(w)
        else:
            lines.append(" ".join(line)); line=[w]
    if line: lines.append(" ".join(line))
    return lines

def alpha_blend(base, overlay_color, alpha):
    """blend overlay_color onto base with alpha [0..1]"""
    r = tuple(int(b*(1-alpha) + o*alpha) for b,o in zip(base, overlay_color))
    return r

def make_gradient(w, h, top_col, bot_col):
    arr = np.zeros((h, w, 3), dtype=np.float32)
    for c in range(3):
        col = np.linspace(top_col[c], bot_col[c], h)
        arr[:,:,c] = col[:,None]
    return Image.fromarray(arr.astype(np.uint8))


class Canvas:
    """Helper wrapper around a PIL Image."""
    def __init__(self, w, h, bg=NOIR):
        self.w = w
        self.h = h
        self.img = make_gradient(w, h, bg, tuple(max(0, c-12) for c in bg))
        self.draw = ImageDraw.Draw(self.img)

    def glow_text(self, text, x, y, font, color=WHITE, glow=VERT, radius=20, center=True):
        """Draw text with optional glow."""
        tw, th = tsz(text, font)
        tx = (self.w - tw) // 2 if center else x
        ty = y
        if glow:
            gl = Image.new("RGBA", (self.w, self.h), (0,0,0,0))
            gd = ImageDraw.Draw(gl)
            for r in range(radius, 0, -5):
                a = int(70 * (1 - r/radius))
                gd.text((tx, ty), text, font=font, fill=(*glow, a))
            gl = gl.filter(ImageFilter.GaussianBlur(radius//3))
            self.img = Image.alpha_composite(self.img.convert("RGBA"), gl).convert("RGB")
            self.draw = ImageDraw.Draw(self.img)
        self.draw.text((tx, ty), text, font=font, fill=color)
        return tw, th

    def text_block(self, lines, font, cy, color=WHITE, glow=None, line_sp=1.4, center=True, x_offset=0):
        lh = tsz("Ag", font)[1]
        step = int(lh * line_sp)
        total = step * len(lines)
        y = cy - total // 2
        for line in lines:
            tw, _ = tsz(line, font)
            tx = (self.w - tw) // 2 + x_offset if center else x_offset
            if glow:
                self.glow_text(line, tx, y, font, color=color, glow=glow, center=False)
            else:
                self.draw.text((tx, y), line, font=font, fill=color)
            y += step
        return total

    def vbar(self, color=VERT, width=8, alpha=1.0, h_frac=1.0):
        h = int(self.h * h_frac)
        col = tuple(int(c*alpha) for c in color)
        self.draw.rectangle([(0,0),(width, h)], fill=col)

    def green_dot(self, x, y, size=10, glow=True, alpha=1.0):
        col = tuple(int(c*alpha) for c in VERT)
        self.draw.ellipse([(x-size//2, y-size//2),(x+size//2, y+size//2)], fill=col)
        if glow:
            gl = Image.new("RGBA",(self.w,self.h),(0,0,0,0))
            gd = ImageDraw.Draw(gl)
            for r in [20,14,8]:
                a = int(50 * (1-r/22) * alpha)
                gd.ellipse([(x-r,y-r),(x+r,y+r)], fill=(*VERT,a))
            gl = gl.filter(ImageFilter.GaussianBlur(8))
            self.img = Image.alpha_composite(self.img.convert("RGBA"),gl).convert("RGB")
            self.draw = ImageDraw.Draw(self.img)

    def label(self, text, x, y, alpha=1.0):
        f = fnt(13*2, 'light')  # scaled
        col = tuple(int(255*alpha) for _ in range(3))
        col = tuple(int(c*alpha) for c in (200,200,200))
        self.draw.text((x,y), text, font=f, fill=col)

    def source_tag(self, text, cy, on_dark=True):
        f = fnt(22, 'light')
        tw, th = tsz(text, f)
        tx = (self.w - tw) // 2
        ty = cy - th // 2
        pad = 8
        bg = (20,20,20,180) if on_dark else (15,15,15,25)
        # Pill background
        pill = Image.new("RGBA",(tw+pad*2+20, th+pad*2), (0,0,0,0))
        pd = ImageDraw.Draw(pill)
        br = (th+pad*2)//2
        pd.rounded_rectangle([(0,0),(tw+pad*2+19, th+pad*2-1)], radius=br,
                              fill=bg)
        self.img = self.img.convert("RGBA")
        self.img.paste(pill, (tx-pad-10, ty-pad), pill)
        self.img = self.img.convert("RGB")
        self.draw = ImageDraw.Draw(self.img)
        col = MUTED if on_dark else MUTED
        self.draw.text((tx, ty), text, font=f, fill=col)

    def horizontal_line(self, y, alpha=0.15, color=WHITE, width=1):
        col = tuple(int(c*alpha) for c in color)
        self.draw.line([(80,y),(self.w-80,y)], fill=col, width=width)

    def underline(self, cx, y, length, color=VERT, height=3):
        x0 = cx - length//2
        x1 = cx + length//2
        self.draw.rounded_rectangle([(x0,y),(x1,y+height)], radius=1, fill=color)

    def arr(self):
        return np.array(self.img)


# ══════════════════════════════════════════════════════════════════════════════
#  Scene builders — each returns a make_frame(t) function
# ══════════════════════════════════════════════════════════════════════════════

def ease_out(t, exp=3):
    return 1 - (1-min(t,1))**exp

def ease_spring(t):
    if t <= 0: return 0
    if t >= 1: return 1
    c4 = (2*math.pi)/3
    return 1 - (2**(-10*t)) * math.sin((t*10-0.75)*c4) + 0.0

def lerp(a, b, t): return a + (b-a)*t
def clamp(v,lo=0,hi=1): return max(lo,min(hi,v))
def remap(t, in0, in1, out0=0, out1=1):
    if in1 == in0: return out0
    return out0 + (out1-out0) * clamp((t-in0)/(in1-in0))


def make_scene(fn, duration, fps=24):
    def mf(t):
        return fn(t, duration)
    return VideoClip(mf, duration=duration)


# ── SCENE 0 — COLD OPEN ─────────────────────────────────────────────────────
def scene_cold(W, H, duration):
    def mf(t, dur):
        p = t / max(dur, 0.001)
        c = Canvas(W, H, NOIR)
        # Green bar animates in from top
        bar_h = int(H * min(1.0, ease_out(t/0.5)))
        c.draw.rectangle([(0,0),(8, bar_h)], fill=VERT)
        # Dot
        dot_a = clamp(remap(t, 0.3, 0.6))
        pulse = 0.8 + 0.2 * math.sin(t * math.pi * 2.5)
        dot_s = int(7 * pulse)
        c.green_dot(32, H-200, size=dot_s, alpha=dot_a)
        # Label
        la = clamp(remap(t, 0.5, 0.9))
        if la > 0:
            f = fnt(22, 'light')
            col = tuple(int(255*la*0.2) for _ in range(3))
            text = "VELIXIA × IA"
            tw,_ = tsz(text,f)
            c.draw.text((W-tw-48, 55), text, font=f, fill=col)
        return c.arr()
    return make_scene(mf, duration)


# ── SCENE 1 — IMAGINEZ ───────────────────────────────────────────────────────
def scene_imaginez(W, H, duration):
    LINES = [
        # (start_t, text, style, size_key, color, center, y_pos_frac)
        (0.0,  "Imaginez.",           'bold',  'xl',   WHITE,  True),
        (0.8,  "Votre futur client",  'light', 'body', (200,200,200,180), True),
        (1.4,  "ouvre son téléphone…","light", 'body', (160,160,160,150), True),
        (2.1,  "tombe sur votre concurrent…", 'light','body',(140,140,140,130),True),
    ]
    def mf(t, dur):
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        pulse = 0.8 + 0.2*math.sin(t*math.pi*2.5)
        c.green_dot(32, H-200, size=int(7*pulse), alpha=1.0)

        sizes = {'xl': int(W*0.16), 'body': int(W*0.032)}

        # Element positions
        center_y = H // 2
        gap = int(H * 0.07)
        positions = [center_y - gap*2, center_y - gap, center_y, center_y + gap]

        for i, (start_t, text, style, sz_key, color, cntr) in enumerate(LINES):
            local_t = t - start_t
            if local_t < 0: continue
            a = ease_out(clamp(local_t / 0.4))
            dy = int(30 * (1-a))

            f = fnt(sizes[sz_key], style)
            tw, th = tsz(text, f)
            tx = (W - tw) // 2 if cntr else 80
            ty = positions[i] - th//2 + dy

            if isinstance(color, tuple) and len(color)==4:
                col = tuple(int(v*a) for v in color[:3])
            else:
                col = tuple(int(v*a) for v in color)

            if sz_key == 'xl' and a > 0:
                c.glow_text(text, tx, ty, f, color=col, glow=VERT, radius=25, center=cntr)
            else:
                c.draw.text((tx, ty), text, font=f, fill=col)

        # "cinquante millisecondes" on second part
        if t >= 2.8:
            a2 = ease_spring(clamp((t-2.8)/0.5))
            big_f = fnt(int(W*0.11), 'bold')
            text2 = "50 ms"
            tw2,th2 = tsz(text2, big_f)
            tx2 = (W-tw2)//2
            ty2 = center_y + gap*1.8
            scale_off = int(30*(1-a2))
            col2 = tuple(int(v*a2) for v in VERT)
            c.glow_text(text2, tx2, ty2-scale_off, big_f, color=col2, glow=VERT, radius=35, center=True)

            if t >= 3.5:
                a3 = ease_out(clamp((t-3.5)/0.4))
                f3 = fnt(int(W*0.065), 'bold')
                text3 = "il a déjà décidé."
                tw3,_ = tsz(text3,f3)
                col3 = tuple(int(v*a3) for v in WHITE)
                c.draw.text(((W-tw3)//2, ty2+th2+20), text3, font=f3, fill=col3)

        return c.arr()
    return make_scene(mf, duration)


# ── SCENE 2 — CHIFFRES BARRÉS ─────────────────────────────────────────────────
def scene_chiffres(W, H, duration):
    def mf(t, dur):
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        f_struck = fnt(int(W*0.038), 'light')
        f_big    = fnt(int(W*0.09), 'bold')

        margin_l = int(W*0.12)
        items = [
            (0.0, "Pas en 3 secondes."),
            (0.9, "Pas en 1 seconde."),
        ]
        cy = H//2 - int(H*0.12)
        lh = int(H*0.1)

        for i, (start_t, text) in enumerate(items):
            a = ease_out(clamp((t-start_t)/0.35))
            if a <= 0: continue
            col = tuple(int(v*a*0.4) for v in WHITE)
            tw, th = tsz(text, f_struck)
            ty = cy + i*lh
            c.draw.text((margin_l, ty), text, font=f_struck, fill=col)
            # Strike-through line
            strike_p = ease_out(clamp((t-start_t-0.2)/0.4))
            if strike_p > 0:
                strike_w = int(tw * strike_p)
                sy = ty + th//2
                c.draw.rectangle([(margin_l, sy-2),(margin_l+strike_w, sy+2)], fill=ROUGE)

        # "50 ms" big
        big_t = 1.7
        a3 = ease_spring(clamp((t-big_t)/0.5))
        if a3 > 0:
            col3 = tuple(int(v*a3) for v in VERT)
            text3 = "En 50 millisecondes."
            tw3,th3 = tsz(text3, f_big)
            c.glow_text(text3, (W-tw3)//2, cy+lh*2, f_big, color=col3, glow=VERT, radius=30, center=True)

        return c.arr()
    return make_scene(mf, duration)


# ── SCENE 3 — CARLETON (fond ivoire) ──────────────────────────────────────────
def scene_carleton(W, H, duration):
    def mf(t, dur):
        # Crossfade background
        bg_p = clamp(t/0.5)
        bg_col = tuple(int(lerp(NOIR[i], IVOIRE[i], bg_p)) for i in range(3))
        c = Canvas(W, H, bg_col)
        # Black bar
        ba = clamp(t/0.4)
        c.draw.rectangle([(0,0),(8,H)], fill=tuple(int(v*ba) for v in NOIR))

        # Source tag
        tag_a = clamp(remap(t, 0.3, 0.7))
        if tag_a > 0:
            f_tag = fnt(22, 'light')
            tag_text = "UNIVERSITÉ DE CARLETON — 2002"
            tw_tag, th_tag = tsz(tag_text, f_tag)
            tx_tag = (W - tw_tag)//2
            ty_tag = H//2 - int(H*0.25)
            pill_h = th_tag + 18
            pill_w = tw_tag + 44
            pill = Image.new("RGBA",(pill_w, pill_h),(0,0,0,0))
            pd = ImageDraw.Draw(pill)
            pd.rounded_rectangle([(0,0),(pill_w-1, pill_h-1)], radius=pill_h//2,
                                  fill=(15,15,15,int(25*tag_a)))
            c.img = c.img.convert("RGBA")
            c.img.paste(pill, ((W-pill_w)//2, ty_tag-9), pill)
            c.img = c.img.convert("RGB")
            c.draw = ImageDraw.Draw(c.img)
            col_tag = tuple(int(v*tag_a) for v in MUTED)
            c.draw.text((tx_tag, ty_tag), tag_text, font=f_tag, fill=col_tag)

        # Word-by-word text
        center_y = H // 2
        words1 = "L'Université de Carleton a prouvé en 2002…".split()
        words2 = "La première impression visuelle d'un site…".split()
        f_body = fnt(int(W*0.033), 'light')
        delay_per_word = 0.09

        def draw_words(words, start_t, col_fn, cx, cy_start):
            line_text = " ".join(words)
            tw, th = tsz(line_text, f_body)
            x = (W - tw)//2
            for i, word in enumerate(words):
                wt = start_t + i * delay_per_word
                wa = ease_out(clamp((t-wt)/0.3))
                if wa <= 0: continue
                prev_words = " ".join(words[:i])
                ox = tsz(prev_words+" ", f_body)[0] if prev_words else 0
                ww, wh = tsz(word+" ", f_body)
                c.draw.text((x+ox, cy_start), word+" ", font=f_body, fill=col_fn(wa))

        draw_words(words1, 0.5,
                   lambda a: tuple(int(v*a) for v in NOIR),
                   W//2, center_y - int(H*0.1))
        draw_words(words2, 1.8,
                   lambda a: tuple(int(v*a) for v in MUTED),
                   W//2, center_y + int(H*0.01))

        # Choc phrase
        choc_a = clamp(remap(t, 3.0, 3.5))
        if choc_a > 0:
            f_choc = fnt(int(W*0.035), 'bold')
            text_choc = "se forme avant que le cerveau lise un mot."
            tw_c, th_c = tsz(text_choc, f_choc)
            ty_c = center_y + int(H*0.12)
            col_c = tuple(int(v*choc_a) for v in NOIR)
            c.draw.text(((W-tw_c)//2, ty_c), text_choc, font=f_choc, fill=col_c)
            # Underline
            under_p = ease_out(clamp(remap(t, 3.3, 3.9)))
            if under_p > 0:
                ux0 = (W-tw_c)//2
                ux1 = ux0 + int(tw_c * under_p)
                uy = ty_c + th_c + 6
                c.draw.rounded_rectangle([(ux0,uy),(ux1,uy+4)], radius=2, fill=VERT)

        return c.arr()
    return make_scene(mf, duration)


# ── SCENE — STAT COUNTER ──────────────────────────────────────────────────────
def scene_stat(W, H, big_text, sub_text, source_text, duration,
               count_to=None, count_suffix='%', count_start_t=1.0):
    def mf(t, dur):
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        pulse = 0.8+0.2*math.sin(t*math.pi*2.5)
        c.green_dot(32, H-200, size=int(7*pulse), alpha=1.0)

        center_y = H//2

        # Source tag
        tag_a = clamp(remap(t, 0.2, 0.6))
        if tag_a > 0:
            f_tag = fnt(22,'light')
            col_tag = tuple(int(v*tag_a*0.28) for v in WHITE)
            tw_t,_ = tsz(source_text, f_tag)
            c.draw.text((80, H-200), source_text.upper(), font=f_tag, fill=col_tag)

        # Big number / counter
        f_big = fnt(int(W*0.20), 'bold')
        if count_to is not None:
            p_count = ease_out(clamp(remap(t, count_start_t, count_start_t+1.2)),4)
            shown_val = int(p_count * count_to)
            display = f"{shown_val}{count_suffix}"
        else:
            p_big = ease_out(clamp((t-0.5)/0.6))
            display = big_text
        big_a = ease_out(clamp((t-0.5)/0.6))
        if big_a > 0:
            tw_b, th_b = tsz(display, f_big)
            col_b = tuple(int(v*big_a) for v in VERT)
            c.glow_text(display, (W-tw_b)//2, center_y - th_b//2 - int(H*0.06),
                        f_big, color=col_b, glow=VERT, radius=50, center=True)

        # Sub text
        f_sub = fnt(int(W*0.034), 'light')
        max_w = int(W*0.82)
        sub_lines = wrap(sub_text, f_sub, max_w)
        sub_a = ease_out(clamp(remap(t, 1.5, 2.0)))
        if sub_a > 0:
            lh = int(H*0.042)
            gy = center_y + int(H*0.14)
            for line in sub_lines:
                tw_s,_ = tsz(line, f_sub)
                col_s = tuple(int(v*sub_a*0.55) for v in WHITE)
                c.draw.text(((W-tw_s)//2, gy), line, font=f_sub, fill=col_s)
                gy += lh

        return c.arr()
    return make_scene(mf, duration)


# ── SCENE — IMPACT WORDS ──────────────────────────────────────────────────────
def scene_impact_words(W, H, words, duration, colors=None):
    if colors is None: colors = [WHITE]*len(words)
    f = fnt(int(W*0.15), 'bold')
    fpw = duration / len(words)
    def mf(t, dur):
        wi = min(int(t/fpw), len(words)-1)
        lt = (t - wi*fpw)/fpw
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        word = words[wi]
        col = colors[wi % len(colors)]
        sc = 1.0 + 0.06*math.exp(-lt*6)
        a = ease_spring(clamp(lt/0.35))
        col_a = tuple(int(v*a) for v in col)
        tw,th = tsz(word, f)
        cx = (W-tw)//2
        cy = H//2 - th//2
        if col == VERT:
            c.glow_text(word, cx, cy, f, color=col_a, glow=VERT, radius=40, center=True)
        else:
            c.draw.text((cx, cy), word, font=f, fill=col_a)
        # flash on new word
        if lt < 0.08:
            flash_a = (1-lt/0.08)*0.25
            c.draw.rectangle([(0,0),(W,H)], fill=tuple(int(v*flash_a) for v in WHITE))
        return c.arr()
    return make_scene(mf, duration)


# ── SCENE — TIMER ─────────────────────────────────────────────────────────────
def scene_timer(W, H, total_secs, duration, label_text=""):
    def mf(t, dur):
        p = t / max(dur, 0.001)
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        cx, cy = W//2, H//2
        # Outer ring
        r = int(W*0.32)
        box = [(cx-r, cy-r),(cx+r, cy+r)]
        # Background arc
        c.draw.arc(box, start=0, end=360, fill=(30,30,30), width=16)
        # Progress arc (countdown)
        end_ang = -90 + 360*(1-p)
        gl = Image.new("RGBA",(W,H),(0,0,0,0))
        gd = ImageDraw.Draw(gl)
        gd.arc(box, start=-90, end=end_ang, fill=(*VERT,220), width=16)
        gl = gl.filter(ImageFilter.GaussianBlur(4))
        c.img = Image.alpha_composite(c.img.convert("RGBA"), gl).convert("RGB")
        c.draw = ImageDraw.Draw(c.img)
        c.draw.arc(box, start=-90, end=end_ang, fill=VERT, width=16)
        # Tick marks
        for tick in range(10):
            ang = math.radians(-90 + tick*36)
            i0 = (int(cx+(r-22)*math.cos(ang)), int(cy+(r-22)*math.sin(ang)))
            i1 = (int(cx+(r+8)*math.cos(ang)),  int(cy+(r+8)*math.sin(ang)))
            col_t = VERT if tick < int(10*(1-p))+1 else (40,40,40)
            c.draw.line([i0,i1], fill=col_t, width=3)
        # Timer digit
        secs_left = total_secs*(1-p)
        disp = f"{secs_left:.0f}"
        f_timer = fnt(int(r*1.2), 'bold')
        tw,th = tsz(disp, f_timer)
        c.glow_text(disp, (W-tw)//2, cy-th//2, f_timer, color=WHITE, glow=VERT, radius=50, center=True)
        # Label
        if label_text:
            f_lbl = fnt(int(W*0.03), 'light')
            lbl_lines = wrap(label_text, f_lbl, int(W*0.7))
            lbl_y = cy + r + 40
            for ll in lbl_lines:
                tw2,_ = tsz(ll, f_lbl)
                c.draw.text(((W-tw2)//2, lbl_y), ll, font=f_lbl, fill=MUTED)
                lbl_y += int(W*0.038)
        return c.arr()
    return make_scene(mf, duration)


# ── SCENE — CARTES GLORIA MARK ────────────────────────────────────────────────
def scene_gloria(W, H, duration):
    cards = [
        (0.5,  "2004", "2 min 30 sec", VERT,   1.0),
        (1.5,  "2012", "75 secondes",  ORANGE, 1.0),
        (2.5,  "2023", "47 secondes",  ROUGE,  1.1),
    ]
    def mf(t, dur):
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        # Intro text
        intro_a = ease_out(clamp(t/0.4))
        if intro_a > 0:
            f_intro = fnt(int(W*0.032), 'italic')
            text = "Et même quand ils restent…"
            tw,_ = tsz(text, f_intro)
            col = tuple(int(v*intro_a*0.5) for v in WHITE)
            c.draw.text(((W-tw)//2, H//2-int(H*0.35)), text, font=f_intro, fill=col)

        card_w = int(W*0.82)
        card_h = int(H*0.1)
        card_x = (W-card_w)//2
        card_y_base = H//2 - int(H*0.15)
        card_gap = int(card_h*1.35)

        f_year = fnt(int(card_h*0.5), 'bold')
        f_time = fnt(int(card_h*0.32), 'light')

        for i, (start_t, year, time_txt, col, scale) in enumerate(cards):
            card_a = ease_out(clamp((t-start_t)/0.4))
            if card_a <= 0: continue
            dy = int(40*(1-card_a))
            cy_card = card_y_base + i*card_gap + dy
            # Card bg
            ch = int(card_h*scale)
            card_img = Image.new("RGBA",(card_w, ch),(0,0,0,0))
            cd = ImageDraw.Draw(card_img)
            cd.rounded_rectangle([(0,0),(card_w-1,ch-1)], radius=14,
                                  fill=(34,197,94, int(20*card_a)) if col==VERT else
                                       (245,158,11,int(12*card_a)) if col==ORANGE else
                                       (239,68,68, int(12*card_a)))
            border_col = (*col, int(80*card_a))
            cd.rounded_rectangle([(0,0),(card_w-1,ch-1)], radius=14,
                                  outline=border_col, width=1)
            c.img = c.img.convert("RGBA")
            c.img.paste(card_img, (card_x, cy_card), card_img)
            c.img = c.img.convert("RGB")
            c.draw = ImageDraw.Draw(c.img)

            # Year
            col_y = tuple(int(v*card_a) for v in col)
            c.draw.text((card_x+28, cy_card+ch//2-tsz(year,f_year)[1]//2),
                        year, font=f_year, fill=col_y)
            # Time
            col_t = tuple(int(v*card_a*0.7) for v in WHITE)
            tw2,th2 = tsz(time_txt, f_time)
            c.draw.text((card_x+card_w-tw2-28, cy_card+ch//2-th2//2),
                        time_txt, font=f_time, fill=col_t)

            # Arrow between cards
            if i < len(cards)-1:
                arrow_a = ease_out(clamp((t-start_t-0.1)/0.3))
                if arrow_a > 0:
                    ay0 = cy_card+ch+6
                    ay1 = ay0 + int(20*arrow_a)
                    arr_col = tuple(int(v*arrow_a*0.6) for v in ROUGE)
                    c.draw.line([(W//2, ay0),(W//2, ay1)], fill=arr_col, width=3)

        return c.arr()
    return make_scene(mf, duration)


# ── SCENE — 47 SECONDES ───────────────────────────────────────────────────────
def scene_47(W, H, duration):
    def mf(t, dur):
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        margin_l = int(W*0.1)

        f_big = fnt(int(W*0.16), 'bold')
        a_big = ease_spring(clamp(t/0.6))
        if a_big > 0:
            col_b = tuple(int(v*a_big) for v in VERT)
            c.glow_text("47 secondes.", 0, H//2-int(H*0.25),
                        f_big, color=col_b, glow=VERT, radius=45, center=True)
            # Underline
            under_p = ease_out(clamp((t-0.5)/0.5))
            if under_p > 0:
                f_ul_text = "47 secondes."
                tw_ul,_ = tsz(f_ul_text, f_big)
                ux = (W-tw_ul)//2
                uy = H//2-int(H*0.25)+tsz(f_ul_text,f_big)[1]+10
                c.draw.rounded_rectangle(
                    [(ux, uy),(ux+int(tw_ul*under_p), uy+4)],
                    radius=2, fill=VERT)

        f_line = fnt(int(W*0.055), 'bold')
        lines_data = [
            (1.4, "pour convaincre.",  WHITE,  -1),
            (2.9, "pour vendre.",      (200,200,200), 0),
            (4.4, "pour tout.",        VERT,   +1),
        ]
        cy_base = H//2 + int(H*0.04)
        lh = int(H*0.08)
        for (start_t, text, col, pos) in lines_data:
            a = ease_out(clamp((t-start_t)/0.4))
            if a <= 0: continue
            dx = int(40*(1-a))
            tw,th = tsz(text, f_line)
            col_a = tuple(int(v*a) for v in col)
            c.draw.text((margin_l-dx, cy_base+(pos+1)*lh), text, font=f_line, fill=col_a)
            # Green dot for "pour tout."
            if col == VERT and a > 0.5:
                dot_x = margin_l + tw + 20
                dot_y = cy_base+(pos+1)*lh + th//2
                pulse = 0.8+0.2*math.sin(t*math.pi*3)
                c.green_dot(dot_x, dot_y, size=int(8*pulse), alpha=a)

        return c.arr()
    return make_scene(mf, duration)


# ── SCENE — VELIXIA REVEAL ────────────────────────────────────────────────────
def scene_velixia_reveal(W, H, duration):
    def mf(t, dur):
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        # Pulsing glow
        pulse = 0.6+0.4*math.sin(t*math.pi*2)
        gl_size = int(W*0.45*pulse)
        if gl_size > 0:
            gl = Image.new("RGBA",(W,H),(0,0,0,0))
            gd = ImageDraw.Draw(gl)
            for r in [gl_size, gl_size//2, gl_size//4]:
                a = int(25*(1-r/gl_size))
                gd.ellipse([(W//2-r, H//2-r*0.6),(W//2+r, H//2+r*0.6)],
                           fill=(*VERT, a))
            gl = gl.filter(ImageFilter.GaussianBlur(40))
            c.img = Image.alpha_composite(c.img.convert("RGBA"),gl).convert("RGB")
            c.draw = ImageDraw.Draw(c.img)

        f_name = fnt(int(W*0.18), 'bold')
        a_name = ease_spring(clamp(t/0.7))
        if a_name > 0:
            tw,th = tsz("Velixia", f_name)
            col_n = tuple(int(v*a_name) for v in WHITE)
            c.glow_text("Velixia", 0, H//2-th//2-int(H*0.12),
                        f_name, color=col_n, glow=VERT, radius=60, center=True)

        a_diff = ease_out(clamp((t-0.9)/0.4))
        if a_diff > 0:
            f_diff = fnt(int(W*0.04), 'italic')
            col_d = tuple(int(v*a_diff*0.6) for v in WHITE)
            tw2,_ = tsz("c'est différent.", f_diff)
            c.draw.text(((W-tw2)//2, H//2+int(H*0.04)), "c'est différent.", font=f_diff, fill=col_d)

        # Comparison
        if t >= 1.8:
            a_cmp = ease_spring(clamp((t-1.8)/0.5))
            f_old = fnt(int(W*0.065), 'bold')
            f_new = fnt(int(W*0.09), 'bold')
            col_old = tuple(int(v*a_cmp*0.7) for v in ROUGE)
            col_new = tuple(int(v*a_cmp) for v in VERT)
            tw_old,th_old = tsz("3 semaines", f_old)
            tw_new,th_new = tsz("24 heures", f_new)
            gap = 60
            total_w = tw_old + gap + tw_new
            x0 = (W-total_w)//2
            cy2 = H//2 + int(H*0.18)
            # Old crossed
            c.draw.text((x0, cy2-th_old//2), "3 semaines", font=f_old, fill=col_old)
            c.draw.line([(x0, cy2+4),(x0+tw_old, cy2+4)], fill=ROUGE, width=3)
            # Arrow
            arr_x = x0+tw_old+gap//2-10
            c.draw.text((arr_x, cy2-th_old//2), "→", font=f_old, fill=(80,80,80))
            # New
            c.glow_text("24 heures", x0+tw_old+gap, cy2-th_new//2,
                        f_new, color=col_new, glow=VERT, radius=30, center=False)

        if t >= 2.6:
            a_ch = ease_spring(clamp((t-2.6)/0.4))
            f_cheap = fnt(int(W*0.07), 'bold')
            col_ch = tuple(int(v*a_ch) for v in VERT)
            tw_ch,_ = tsz("À 3× moins cher.", f_cheap)
            c.glow_text("À 3× moins cher.", 0, H//2+int(H*0.34),
                        f_cheap, color=col_ch, glow=VERT, radius=30, center=True)

        return c.arr()
    return make_scene(mf, duration)


# ── SCENE — OUTRO ─────────────────────────────────────────────────────────────
def scene_outro(W, H, duration):
    def mf(t, dur):
        p = t/max(dur,0.001)
        c = Canvas(W, H, NOIR)
        c.vbar(h_frac=1.0)
        # Glow
        pulse = 0.7+0.3*math.sin(t*math.pi*2.5)
        gr = int(W*0.35*pulse)
        gl = Image.new("RGBA",(W,H),(0,0,0,0))
        gd = ImageDraw.Draw(gl)
        gd.ellipse([(W//2-gr, H//2-int(gr*0.6)),(W//2+gr, H//2+int(gr*0.6))],
                   fill=(*VERT, int(40*min(p*3,1.0))))
        gl = gl.filter(ImageFilter.GaussianBlur(50))
        c.img = Image.alpha_composite(c.img.convert("RGBA"),gl).convert("RGB")
        c.draw = ImageDraw.Draw(c.img)

        # Logo
        f_logo = fnt(int(W*0.13), 'bold')
        a_logo = ease_out(clamp(p*3))
        col_logo = tuple(int(v*a_logo) for v in WHITE)
        tw_logo,th_logo = tsz("VELIXIA", f_logo)
        c.glow_text("VELIXIA", 0, H//2-th_logo//2-int(H*0.1),
                    f_logo, color=col_logo, glow=VERT, radius=60, center=True)
        # Green dot next to logo
        if a_logo > 0.5:
            dot_pulse = 0.8+0.2*math.sin(t*math.pi*3)
            c.green_dot(W//2+tw_logo//2+25, H//2-int(H*0.1),
                        size=int(10*dot_pulse), alpha=a_logo)

        # Tagline
        a_tag = ease_out(clamp(remap(t, 0.6, 1.1)))
        if a_tag > 0:
            f_tag = fnt(int(W*0.028), 'light')
            tag = "L'agence IA qui va plus vite, plus loin, pour moins cher."
            tag_lines = wrap(tag, f_tag, int(W*0.82))
            tag_y = H//2+int(H*0.04)
            for tl in tag_lines:
                tw_t,th_t = tsz(tl, f_tag)
                col_t = tuple(int(v*a_tag*0.5) for v in WHITE)
                c.draw.text(((W-tw_t)//2, tag_y), tl, font=f_tag, fill=col_t)
                tag_y += int(th_t*1.4)

        # Info lines
        infos = ["Disponible 24h/24, 7j/7", "Basée à Lyon · Partout en France"]
        for i, info in enumerate(infos):
            a_inf = ease_out(clamp(remap(t, 1.0+i*0.3, 1.4+i*0.3)))
            if a_inf > 0:
                f_inf = fnt(int(W*0.024), 'light')
                tw_i,_ = tsz(info, f_inf)
                col_i = tuple(int(v*a_inf*0.35) for v in WHITE)
                c.draw.text(((W-tw_i)//2, H//2+int(H*0.16)+i*int(H*0.038)),
                            info, font=f_inf, fill=col_i)

        # URL
        a_url = ease_spring(clamp(remap(t, 1.5, 2.0)))
        if a_url > 0:
            f_url = fnt(int(W*0.08), 'bold')
            url = "velix-ia.com"
            tw_u,th_u = tsz(url, f_url)
            col_u = tuple(int(v*a_url) for v in VERT)
            uy = H//2+int(H*0.3)
            c.glow_text(url, 0, uy, f_url, color=col_u, glow=VERT, radius=35, center=True)
            # Underline
            under_p = ease_out(clamp(remap(t, 1.8, 2.4)))
            if under_p > 0:
                ux0 = (W-tw_u)//2
                ux1 = ux0+int(tw_u*under_p)
                c.draw.rounded_rectangle([(ux0,uy+th_u+8),(ux1,uy+th_u+12)],
                                          radius=2, fill=VERT)

        # Fade to black at the end
        if p > 0.85:
            fade_a = (p-0.85)/0.15
            c.draw.rectangle([(0,0),(W,H)], fill=tuple(int(v*fade_a) for v in NOIR))

        return c.arr()
    return make_scene(mf, duration)


# ══════════════════════════════════════════════════════════════════════════════
#  BUILD & RENDER
# ══════════════════════════════════════════════════════════════════════════════
def build_video(W, H, out_path, fps=24):
    print(f"Loading audio: {AUDIO_PATH}")
    audio = AudioFileClip(AUDIO_PATH)
    total_s = audio.duration
    print(f"  duration: {total_s:.2f}s")

    # Timeline fitted to audio length
    # Full script is ~75s but audio preview is 6.3s
    # We show the first scenes proportionally compressed
    scale = total_s / 85.0   # compress to match audio
    def t(sec): return sec * scale

    print(f"Building scenes (scale={scale:.3f})…")
    clips = [
        scene_cold(W, H, t(1.0)),
        scene_imaginez(W, H, t(5.7)),
    ]
    if total_s > 10:
        clips += [
            scene_chiffres(W, H, t(3.0)),
            scene_carleton(W, H, t(6.5)),
        ]
    if total_s > 20:
        clips += [
            scene_stat(W, H, "53%",
                       "des visiteurs abandonnent un site qui charge en +3 secondes.",
                       "Google / SOASTA Research — 2017",
                       t(8.7), count_to=53, count_suffix='%', count_start_t=1.2),
        ]
    if total_s > 30:
        clips += [
            scene_timer(W, H, 10, t(6.0),
                        "secondes pour convaincre un visiteur de rester"),
            scene_gloria(W, H, t(11.0)),
        ]
    if total_s > 50:
        clips += [
            scene_47(W, H, t(7.0)),
            scene_velixia_reveal(W, H, t(7.5)),
        ]

    # Always end with outro, fitting remaining time
    used = sum(c.duration for c in clips)
    outro_dur = max(3.0, total_s - used)
    clips.append(scene_outro(W, H, outro_dur))

    print(f"Concatenating {len(clips)} scenes…")
    video = concatenate_videoclips(clips, method="compose")

    # Trim/pad to exact audio length
    if video.duration > total_s:
        video = video.subclipped(0, total_s)
    elif video.duration < total_s:
        pad = ColorClip((W,H), color=NOIR, duration=total_s-video.duration)
        video = concatenate_videoclips([video, pad], method="compose")

    video = video.with_audio(audio)

    print(f"Rendering {out_path}…")
    video.write_videofile(
        out_path, fps=fps,
        codec="libx264", audio_codec="aac",
        preset="fast", threads=2, logger="bar",
    )
    print("Done ✓")

if __name__ == "__main__":
    # TikTok
    build_video(
        W=1080, H=1920,
        out_path="/home/user/VELIXIA/velixia_tiktok.mp4",
    )
    # Instagram
    build_video(
        W=1080, H=1080,
        out_path="/home/user/VELIXIA/velixia_instagram.mp4",
    )
