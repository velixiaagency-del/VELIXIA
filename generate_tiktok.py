"""
Velixia – TikTok viral video generator
Streaming frame generation (low memory) via VideoClip(make_frame)
Format: 9:16 vertical 1080x1920, synced with voiceover MP3
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import AudioFileClip, VideoClip, concatenate_videoclips, ColorClip
import os, math, random, warnings
warnings.filterwarnings("ignore")

# ─── Config ───────────────────────────────────────────────────────────────────
W, H       = 1080, 1920
FPS        = 24          # 24fps to reduce memory pressure
AUDIO_PATH = "/root/.claude/uploads/52b15a7f-6369-4bf9-a996-374b141396ee/49898954-ElevenLabs_20260519T20_08_53_Adrien_Clairon__Podcast_Narrator_pvc_sp110_s50_sb75_se48_m2.mp3"
OUT_PATH   = "/home/user/VELIXIA/velixia_tiktok.mp4"

BG    = (8,   8,  12)
WHITE = (255, 255, 255)
BLUE  = (30,  120, 255)
BLUE2 = (0,   180, 255)
GRAY  = (60,   60,  70)
DGRAY = (20,   20,  28)
RED   = (180,  30,  30)

# ─── Fonts ────────────────────────────────────────────────────────────────────
_font_cache = {}
def get_font(size):
    if size in _font_cache:
        return _font_cache[size]
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]:
        if os.path.exists(p):
            f = ImageFont.truetype(p, size)
            _font_cache[size] = f
            return f
    return ImageFont.load_default()

# ─── Helpers ──────────────────────────────────────────────────────────────────
def new_bg():
    top = np.array(BG, dtype=np.float32)
    bot = np.array([14, 14, 22], dtype=np.float32)
    ys  = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]  # (H,1,1)
    # broadcast to (H, W, 3)
    row = (top * (1 - ys) + bot * ys)           # (H, 1, 3)
    arr = np.broadcast_to(row, (H, W, 3)).copy()
    return Image.fromarray(arr.astype(np.uint8))

def scan_lines(img, opacity=18):
    draw = ImageDraw.Draw(img)
    for y in range(0, H, 4):
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, opacity))
    return img

def corner_marks(draw, size=40, color=BLUE):
    for (cx, cy), (dx, dy) in [((0,0),(1,1)),((W,0),(-1,1)),((0,H),(1,-1)),((W,H),(-1,-1))]:
        draw.line([(cx, cy),(cx+dx*size, cy)], fill=color, width=3)
        draw.line([(cx, cy),(cx, cy+dy*size)], fill=color, width=3)

def text_size(txt, font):
    bb = font.getbbox(txt)
    return bb[2]-bb[0], bb[3]-bb[1]

def wrap(text, font, max_w):
    words, lines, line = text.split(), [], []
    for w in words:
        test = " ".join(line+[w])
        if text_size(test, font)[0] <= max_w or not line:
            line.append(w)
        else:
            lines.append(" ".join(line)); line=[w]
    if line: lines.append(" ".join(line))
    return lines

def draw_lines(img, lines, font, cy, color=WHITE, glow=False, glow_col=BLUE2):
    fh = text_size("Ag", font)[1]
    lh = int(fh * 1.35)
    total = lh * len(lines)
    y = cy - total // 2
    for line in lines:
        w, _ = text_size(line, font)
        x = (W - w) // 2
        if glow:
            gl = Image.new("RGBA", (W, H), (0,0,0,0))
            gd = ImageDraw.Draw(gl)
            for off in range(20, 0, -4):
                a = int(80 * (1 - off/20))
                gd.text((x, y), line, font=font, fill=(*glow_col, a))
            gl = gl.filter(ImageFilter.GaussianBlur(radius=10))
            img = Image.alpha_composite(img.convert("RGBA"), gl).convert("RGB")
        ImageDraw.Draw(img).text((x, y), line, font=font, fill=color)
        y += lh
    return img

def glitch(arr, intensity=6):
    arr = arr.copy()
    for _ in range(random.randint(2,7)):
        y0 = random.randint(0, H-20)
        y1 = y0 + random.randint(2, 18)
        s  = random.randint(-intensity, intensity)
        if s: arr[y0:y1,:,0] = np.roll(arr[y0:y1,:,0], s, axis=1)
    return arr

def zoom_crop(img, scale):
    if abs(scale - 1.0) < 0.001:
        return img
    cw, ch = int(W/scale), int(H/scale)
    ox, oy = (W-cw)//2, (H-ch)//2
    return img.crop((ox, oy, ox+cw, oy+ch)).resize((W, H), Image.LANCZOS)

# ─── Scene factories (return make_frame(t) closures) ─────────────────────────

def scene_zoom_text(text, duration, font_size=80, glow_col=BLUE2,
                    zoom_s=1.0, zoom_e=1.07):
    font  = get_font(font_size)
    lines = wrap(text, font, int(W*0.86))
    def make_frame(t):
        p   = t / max(duration - 1/FPS, 1e-3)
        sc  = zoom_s + (zoom_e - zoom_s) * p
        img = new_bg()
        corner_marks(ImageDraw.Draw(img))
        img = draw_lines(img, lines, font, H//2, glow=True, glow_col=glow_col)
        img = zoom_crop(img, sc)
        arr = np.array(img)
        fade = min(1.0, t / 0.25)
        return (arr * fade).astype(np.uint8)
    return VideoClip(make_frame, duration=duration)

def scene_stat(big_text, small_text, duration, glitch_on=False):
    bfont = get_font(110)
    sfont = get_font(46)
    slines = wrap(small_text, sfont, int(W*0.82))
    is_pct = big_text.endswith("%")
    try:    val = int(big_text[:-1])
    except: val = 0
    def make_frame(t):
        p   = t / max(duration - 1/FPS, 1e-3)
        img = new_bg()
        draw = ImageDraw.Draw(img)
        corner_marks(draw)
        draw.rectangle([(80,H//2-200),(W-80,H//2-197)], fill=BLUE2)
        draw.rectangle([(80,H//2+160),(W-80,H//2+163)], fill=BLUE)
        shown = f"{int(val * min(p*2.5,1))}%" if is_pct else big_text
        bw, _ = text_size(shown, bfont)
        img = draw_lines(img, [shown], bfont, H//2-60, glow=True, glow_col=BLUE2)
        img = draw_lines(img, slines, sfont, H//2+270, color=GRAY)
        arr = np.array(img)
        if glitch_on and int(t*FPS)%6==0:
            arr = glitch(arr)
        return arr
    return VideoClip(make_frame, duration=duration)

def scene_words(words, duration, colors=None):
    font = get_font(150)
    if colors is None:
        colors = [WHITE]*len(words)
    fpw  = duration / len(words)
    def make_frame(t):
        wi  = min(int(t / fpw), len(words)-1)
        lt  = (t - wi*fpw) / fpw
        img = new_bg()
        draw = ImageDraw.Draw(img)
        corner_marks(draw)
        word = words[wi]
        sc   = 1.0 + 0.05 * math.exp(-lt * 5)
        c    = colors[wi % len(colors)]
        img  = draw_lines(img, [word], font, H//2, color=c, glow=True, glow_col=BLUE2)
        img  = zoom_crop(img, sc)
        arr  = np.array(img)
        if lt < 0.08:
            arr = glitch(arr, intensity=10)
        return arr
    return VideoClip(make_frame, duration=duration)

def scene_timer(duration, title=None):
    bfont = get_font(190)
    lfont = get_font(44)
    tlines = wrap(title, lfont, int(W*0.82)) if title else []
    def make_frame(t):
        p  = t / max(duration - 1/FPS, 1e-3)
        sl = duration * (1 - p)
        img = new_bg()
        draw = ImageDraw.Draw(img)
        corner_marks(draw, color=BLUE2)
        cx, cy, r = W//2, H//2, 340
        draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], outline=DGRAY, width=12)
        end_a = -90 + 360*(1-p)
        draw.arc([(cx-r,cy-r),(cx+r,cy+r)], start=-90, end=end_a, fill=BLUE2, width=12)
        r2 = 300
        draw.ellipse([(cx-r2,cy-r2),(cx+r2,cy+r2)], outline=GRAY, width=3)
        for tick in range(10):
            a = math.radians(-90 + tick*36)
            i0 = (int(cx+(r-20)*math.cos(a)), int(cy+(r-20)*math.sin(a)))
            i1 = (int(cx+(r+8) *math.cos(a)), int(cy+(r+8) *math.sin(a)))
            draw.line([i0, i1], fill=BLUE2 if tick<int(10*(1-p))+1 else GRAY, width=3)
        disp = f"{sl:.1f}"
        bw,_ = text_size(disp, bfont)
        img = draw_lines(img, [disp], bfont, cy-20, glow=True, glow_col=BLUE2)
        sfont2 = get_font(52)
        sw,_ = text_size("secondes", sfont2)
        ImageDraw.Draw(img).text(((W-sw)//2, cy+110), "secondes", font=sfont2, fill=GRAY)
        if tlines:
            img = draw_lines(img, tlines, lfont, cy+260, color=BLUE2)
        arr = np.array(img)
        if int(t*FPS)%15==0:
            arr = glitch(arr, 4)
        return arr
    return VideoClip(make_frame, duration=duration)

def scene_disappear(text, duration):
    font  = get_font(78)
    lines = wrap(text, font, int(W*0.82))
    xfont = get_font(150)
    def make_frame(t):
        p   = t / max(duration - 1/FPS, 1e-3)
        img = new_bg()
        draw = ImageDraw.Draw(img)
        corner_marks(draw)
        img = draw_lines(img, lines, font, H//2, glow=True)
        if p > 0.4:
            xp  = min(1.0, (p-0.4)/0.3)
            xw, _ = text_size("✕", xfont)
            ImageDraw.Draw(img).text(((W-xw)//2, H//2+160), "✕",
                                      font=xfont, fill=tuple(int(c*xp) for c in RED))
        arr  = np.array(img)
        fade = max(0.0, 1.0 - p*2.2)
        arr  = (arr * fade).astype(np.uint8) if fade < 1.0 else arr
        if p > 0.3 and int(t*FPS)%3==0:
            arr = glitch(arr, 12)
        return arr
    return VideoClip(make_frame, duration=duration)

def scene_dashboard(text, duration):
    font  = get_font(60)
    lfont = get_font(52)
    lines = wrap(text, font, int(W*0.82))
    bars  = [0.4, 0.65, 0.5, 0.8, 0.55, 0.9, 0.7]
    def make_frame(t):
        p   = t / max(duration - 1/FPS, 1e-3)
        img = new_bg()
        draw = ImageDraw.Draw(img)
        corner_marks(draw, color=BLUE)
        for gx in range(80, W, 180):
            draw.line([(gx,0),(gx,H)], fill=(20,25,40))
        for gy in range(80, H, 180):
            draw.line([(0,gy),(W,gy)], fill=(20,25,40))
        bw, bg2 = 80, 30
        total_bw = len(bars)*(bw+bg2)
        bx0 = (W-total_bw)//2
        ct, ch = H-400, 280
        for bi, val in enumerate(bars):
            ah = int(ch * val * min(p*2, 1.0))
            x0 = bx0 + bi*(bw+bg2)
            x1 = x0 + bw
            y0 = ct + ch - ah
            c  = BLUE2 if bi==5 else (40,60,120)
            draw.rectangle([(x0,y0),(x1,ct+ch)], fill=c)
            if bi==5:
                draw.rectangle([(x0,y0),(x1,y0+4)], fill=WHITE)
        draw.line([(bx0-10, ct+ch),(bx0+total_bw+10, ct+ch)], fill=GRAY, width=2)
        label = "+400%"
        lw,_  = text_size(label, lfont)
        img   = draw_lines(img, [label], lfont, ct-50, color=BLUE2, glow=True)
        img   = draw_lines(img, lines, font, H//2-180, glow=True)
        return np.array(img)
    return VideoClip(make_frame, duration=duration)

def scene_graph_drop(text, duration):
    font  = get_font(60)
    lines = wrap(text, font, int(W*0.82))
    xs    = np.linspace(80, W-80, 30)
    def graph_y(x, p):
        idx = (x-80)/(W-160)
        base = H-800
        if idx < 0.65:
            return base - int(idx*200)
        drop = (idx-0.65)/0.35
        return base - 130 + int(drop * min(p*2,1.0) * 340)
    def make_frame(t):
        p   = t / max(duration - 1/FPS, 1e-3)
        img = new_bg()
        draw = ImageDraw.Draw(img)
        corner_marks(draw, color=BLUE)
        pts = [(int(x), graph_y(x, p)) for x in xs]
        for i in range(len(pts)-1):
            c = RED if pts[i][0] > W*0.65 else BLUE2
            draw.line([pts[i], pts[i+1]], fill=c, width=5)
        ex, ey = pts[-1]
        draw.ellipse([(ex-8,ey-8),(ex+8,ey+8)], fill=RED)
        if p > 0.5:
            af = min(1.0,(p-0.5)/0.3)
            ax = W//2; ay = H-700
            draw.polygon([(ax,ay+int(80*af)),(ax-40,ay),(ax+40,ay)], fill=RED)
        img = draw_lines(img, lines, font, H//2+300, glow=True)
        return np.array(img)
    return VideoClip(make_frame, duration=duration)

def scene_ux_flow(text, duration):
    font   = get_font(56)
    sfont  = get_font(70)
    lines  = wrap(text, font, int(W*0.82))
    steps  = ["AUDIT", "FRICTION", "REBUILD"]
    scols  = [BLUE2, (255,180,0), (80,255,80)]
    def make_frame(t):
        p   = t / max(duration - 1/FPS, 1e-3)
        img = new_bg()
        draw = ImageDraw.Draw(img)
        corner_marks(draw, color=BLUE)
        total_w = sum(text_size(s, sfont)[0]+60 for s in steps)
        sx = (W-total_w)//2
        sy = H//2-100
        for si, (step, sc) in enumerate(zip(steps, scols)):
            reveal = min(1.0, max(0.0, p*3 - si*0.8))
            if reveal > 0:
                c = tuple(int(v*reveal) for v in sc)
                draw.text((sx, sy), step, font=sfont, fill=c)
            sw,_ = text_size(step, sfont)
            nx   = sx + sw + 60
            if si < len(steps)-1 and reveal > 0.3:
                ar = min(1.0,(reveal-0.3)/0.4)
                ax = nx-55; ay = sy+35
                gc = tuple(int(v*ar) for v in GRAY)
                draw.line([(ax,ay),(ax+30,ay)], fill=gc, width=3)
                draw.polygon([(ax+30,ay-8),(ax+45,ay),(ax+30,ay+8)], fill=gc)
            sx = nx
        img = draw_lines(img, lines, font, H//2+180, glow=True)
        return np.array(img)
    return VideoClip(make_frame, duration=duration)

def scene_outro(duration):
    bfont = get_font(108)
    tfont = get_font(46)
    ufont = get_font(38)
    tag   = "Pas de la décoration. De l'ingénierie."
    url   = "velixia.com"
    def make_frame(t):
        p   = t / max(duration - 1/FPS, 1e-3)
        img = new_bg()
        draw = ImageDraw.Draw(img)
        for by in [H//2-200, H//2+200]:
            bw = int(W*0.7*min(p*2,1.0))
            bx0 = (W-bw)//2
            draw.rectangle([(bx0,by-1),(bx0+bw,by+1)], fill=BLUE2)
        pulse  = 0.85 + 0.15*math.sin(p*math.pi*6)
        gr     = int(60*pulse*min(p*2,1.0))
        gl     = Image.new("RGBA",(W,H),(0,0,0,0))
        gd     = ImageDraw.Draw(gl)
        gd.ellipse([(W//2-gr*3, H//2-gr*2),(W//2+gr*3, H//2+gr*2)],
                   fill=(*BLUE, int(60*min(p*2,1.0))))
        gl     = gl.filter(ImageFilter.GaussianBlur(radius=40))
        img    = Image.alpha_composite(img.convert("RGBA"), gl).convert("RGB")
        img    = draw_lines(img, ["VELIX-IA"], bfont, H//2, glow=True, glow_col=BLUE2)
        if p > 0.3:
            ta = min(1.0,(p-0.3)/0.4)
            tl = wrap(tag, tfont, int(W*0.82))
            img= draw_lines(img, tl, tfont, H//2+120,
                            color=tuple(int(c*ta) for c in BLUE2))
        if p > 0.6:
            ua = min(1.0,(p-0.6)/0.3)
            uw,_ = text_size(url, ufont)
            ImageDraw.Draw(img).text(((W-uw)//2, H//2+200), url,
                                      font=ufont,
                                      fill=tuple(int(c*ua) for c in GRAY))
        arr = np.array(img)
        if t < 0.25:
            arr = glitch(arr, 8)
        return arr
    return VideoClip(make_frame, duration=duration)

# ─── Scene table ─────────────────────────────────────────────────────────────
def build_scenes(total_audio):
    raw = [
        (0.0,  3.0,  lambda d: scene_zoom_text(
            "Vous savez pourquoi votre site perd des clients en silence ?",
            d, font_size=74, glow_col=BLUE2)),
        (3.0,  8.0,  lambda d: scene_stat(
            "53%","des visiteurs quittent si la page met + de 3 sec à charger",
            d, glitch_on=True)),
        (8.0, 10.0,  lambda d: scene_words(["3", "secondes."], d,
            colors=[BLUE2, WHITE])),
        (10.0, 12.0, lambda d: scene_words(["Pas 10.", "Pas 5.", "TROIS."], d,
            colors=[GRAY, GRAY, BLUE2])),
        (12.0, 18.0, lambda d: scene_timer(d,
            title="10 secondes pour convaincre un visiteur de rester")),
        (18.0, 21.0, lambda d: scene_zoom_text(
            "10 secondes pour justifier votre existence sur son écran.",
            d, font_size=70, glow_col=BLUE, zoom_s=1.0, zoom_e=1.09)),
        (21.0, 24.0, lambda d: scene_disappear(
            "Après ça il est parti. Définitivement.", d)),
        (24.0, 29.0, lambda d: scene_dashboard(
            "Chez Velix-IA on a une obsession avec ces chiffres.", d)),
        (29.0, 33.0, lambda d: scene_graph_drop(
            "Chaque seconde perdue, c'est un client perdu.", d)),
        (33.0, 39.0, lambda d: scene_ux_flow(
            "On audite. On identifie chaque friction. On reconstruit.", d)),
        (39.0, 43.0, lambda d: scene_words(
            ["VITESSE.", "CLARTÉ.", "CONVICTION."], d,
            colors=[WHITE, BLUE2, WHITE])),
        (43.0, 49.0, lambda d: scene_stat(
            "400%","d'augmentation des conversions (Forrester Research)", d)),
        (49.0, 51.0, lambda d: scene_words(["400 %"], d, colors=[BLUE2])),
        (51.0, 57.0, lambda d: scene_zoom_text(
            "Votre site est soit votre meilleur commercial, soit votre pire saboteur.",
            d, font_size=66, glow_col=RED, zoom_s=0.98, zoom_e=1.06)),
        (57.0, 63.0, lambda d: scene_dashboard(
            "Velix-IA transforme votre site en machine à convertir.", d)),
        (63.0, min(68.0, total_audio), lambda d: scene_outro(d)),
    ]
    clips = []
    for start, end, factory in raw:
        dur = min(end, total_audio) - start
        if dur > 0:
            clips.append(factory(dur))
    return clips

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading audio…")
    audio   = AudioFileClip(AUDIO_PATH)
    total_s = audio.duration
    print(f"  duration: {total_s:.2f}s")

    print("Building scene clips…")
    clips = build_scenes(total_s)

    print("Concatenating…")
    video = concatenate_videoclips(clips, method="compose")
    if video.duration < total_s:
        pad   = ColorClip((W, H), color=BG, duration=total_s-video.duration)
        video = concatenate_videoclips([video, pad], method="compose")
    else:
        video = video.subclipped(0, total_s)

    video = video.with_audio(audio)

    print(f"Writing {OUT_PATH}…")
    video.write_videofile(
        OUT_PATH,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=2,
        logger="bar",
    )
    print("Done ✓")
