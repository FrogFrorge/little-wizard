"""Round 13, step 2 of the ultimate cut-in: the portrait cards (PIL).

python r13_cutin_art.py <portrait shots dir>
  -> output/round13/cutin/T_UltCutIn_<Wizard>.png (1400 x 560, alpha) and a preview sheet

1. Matte: each pose was shot twice, on a black and on a white unlit backdrop; with
   B = a*F + (1-a)*b0 and W = a*F + (1-a)*w0 -> a = 1 - (W - B) / (w0 - b0), and the
   colour F = (B - (1-a)*b0) / a.
2. The wizard (waist up) gets a white sticker outline and a soft glow in their colour.
3. The card: a slanted band in the wizard's colours with speed lines and their
   element's little motifs, the portrait popping out over it, the English name big
   and slanted, the Chinese name and title under it.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'round13' / 'cutin'
W, H = 1400, 560
FONT_EN = 'C:/Windows/Fonts/seguibli.ttf'      # Segoe UI Black Italic
FONT_ZH = 'C:/Windows/Fonts/msjhbd.ttc'
# key: (shot, English, Chinese name, title, dark, mid, bright, motif)
CARDS = {
    'Blaise': ('fireboy_86', 'BLAISE', '布萊茲', '爆炎魔法師', (110, 18, 8), (232, 84, 26), (255, 196, 70), 'fire'),
    'Neve': ('icegirl_86', 'NEVE', '妮芙', '沉凍之心', (22, 36, 104), (76, 136, 232), (196, 232, 255), 'ice'),
    'Gale': ('windboy_45', 'GALE', '蓋爾', '瞬影', (8, 62, 50), (34, 168, 122), (176, 255, 214), 'wind'),
    'Volta': ('lightninggirl_30', 'VOLTA', '沃爾妲', '輪舞之流', (60, 16, 104), (150, 64, 222), (255, 222, 74), 'lightning'),
}


def matte(black, white):
    B = np.asarray(Image.open(black).convert('RGB'), float) / 255
    Wt = np.asarray(Image.open(white).convert('RGB'), float) / 255
    h, w, _ = B.shape
    corners = np.concatenate([B[:40, :40].reshape(-1, 3), B[:40, -40:].reshape(-1, 3)])
    cornersw = np.concatenate([Wt[:40, :40].reshape(-1, 3), Wt[:40, -40:].reshape(-1, 3)])
    b0, w0 = np.median(corners, 0), np.median(cornersw, 0)
    a = 1 - np.clip((Wt - B) / np.maximum(w0 - b0, 1e-3), 0, 1).mean(2)
    a = np.clip((a - 0.02) / 0.96, 0, 1)
    F = np.clip((B - (1 - a[..., None]) * b0) / np.maximum(a[..., None], 1e-3), 0, 1)
    rgba = np.concatenate([F, a[..., None]], 2)
    return Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA')


def waist_up(im, keep=0.66):
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > 40)
    top, bottom = ys.min(), ys.max()
    left, right = xs.min(), xs.max()
    cut = int(top + (bottom - top) * keep)
    pad = 24
    return im.crop((max(0, left - pad), max(0, top - pad), min(im.width, right + pad), cut))


def sticker(im, colour, outline=7, glow=22):
    """White outline + coloured glow behind the figure (the card's 'sticker' look)."""
    a = im.split()[3]
    big = Image.new('RGBA', (im.width + 2 * glow, im.height + 2 * glow), (0, 0, 0, 0))
    ab = Image.new('L', big.size, 0)
    ab.paste(a, (glow, glow))
    ring = ab.filter(ImageFilter.MaxFilter(outline * 2 + 1))
    halo = ring.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(glow * 0.6))
    out = Image.new('RGBA', big.size, (0, 0, 0, 0))
    out.paste(Image.new('RGBA', big.size, colour + (255,)), (0, 0), halo.point(lambda v: int(v * 0.85)))
    out.paste(Image.new('RGBA', big.size, (255, 255, 255, 255)), (0, 0), ring)
    # a touch more contrast and colour on the figure itself
    fig = im.copy()
    rgb = np.asarray(fig.convert('RGB'), float)
    mean = rgb.mean(2, keepdims=True)
    rgb = np.clip((rgb - 128) * 1.08 + 128 + (rgb - mean) * 0.15, 0, 255)
    fig = Image.merge('RGBA', (*Image.fromarray(rgb.astype(np.uint8)).split(), a))
    out.alpha_composite(fig, (glow, glow))
    return out


def lerp(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def band(card, dark, mid, bright, motif, seed):
    rng = np.random.default_rng(seed)
    top, bot, skew = 150, 470, 150
    # gradient band (dark at the left, bright in the middle, fading out at the right end)
    g = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    px = np.zeros((H, W, 4), np.uint8)
    xs = np.arange(W)
    for y in range(top, bot):
        off = int(skew * (bot - y) / (bot - top))       # slanted ends
        t = np.clip((xs - off) / (W - 260.0), 0, 1)
        col = np.where(t[:, None] < 0.45, np.array([lerp(dark, mid, v / 0.45) for v in np.minimum(t, 0.45)]),
                       np.array([lerp(mid, bright, (v - 0.45) / 0.55) for v in np.maximum(t, 0.45)]))
        alpha = np.clip(1.25 - t * 1.1, 0, 1) * 235
        alpha[xs > W - 120 + off - skew] = 0
        px[y, :, :3] = col
        px[y, :, 3] = alpha.astype(np.uint8)
    g = Image.fromarray(px, 'RGBA')
    d = ImageDraw.Draw(g)
    # speed lines across the band
    for k in range(46):
        y = rng.uniform(top + 6, bot - 6)
        x0 = rng.uniform(-100, W * 0.85)
        ln = rng.uniform(90, 420)
        wdt = rng.choice([1, 2, 2, 3, 4])
        a = int(rng.uniform(40, 140))
        d.line([(x0, y), (x0 + ln, y - ln * 0.08)], fill=(255, 255, 255, a), width=int(wdt))
    # bright edges
    d.line([(skew, top), (W - 140, top)], fill=bright + (255,), width=5)
    d.line([(0, bot), (W - 140 - skew, bot)], fill=bright + (255,), width=5)
    # element motifs scattered over the band
    for k in range(18):
        cx, cy = rng.uniform(420, W - 220), rng.uniform(top + 20, bot - 20)
        s = rng.uniform(10, 26)
        a = int(rng.uniform(90, 200))
        col = (255, 255, 255, a) if k % 3 else bright + (a,)
        if motif == 'fire':
            d.polygon([(cx, cy - s * 1.4), (cx + s * 0.7, cy), (cx, cy + s * 0.6), (cx - s * 0.7, cy)], fill=col)
        elif motif == 'ice':
            for ang in range(0, 180, 60):
                r = math.radians(ang)
                d.line([(cx - s * math.cos(r), cy - s * math.sin(r)), (cx + s * math.cos(r), cy + s * math.sin(r))], fill=col, width=3)
        elif motif == 'wind':
            d.arc([cx - s, cy - s * 0.6, cx + s, cy + s * 0.6], 180, 20, fill=col, width=3)
        else:
            pts = [(cx - s * 0.3, cy - s), (cx + s * 0.25, cy - s * 0.1), (cx - s * 0.15, cy - s * 0.05), (cx + s * 0.3, cy + s)]
            d.line(pts, fill=col, width=4)
    # four-point sparkles
    for k in range(10):
        cx, cy = rng.uniform(380, W - 200), rng.uniform(top - 30, bot + 30)
        s = rng.uniform(6, 16)
        d.polygon([(cx, cy - s * 2), (cx + s * 0.4, cy - s * 0.4), (cx + s * 2, cy), (cx + s * 0.4, cy + s * 0.4),
                   (cx, cy + s * 2), (cx - s * 0.4, cy + s * 0.4), (cx - s * 2, cy), (cx - s * 0.4, cy - s * 0.4)],
                  fill=(255, 255, 255, int(rng.uniform(150, 255))))
    card.alpha_composite(g)


def make_card(key, shots):
    shot, en, zh, title, dark, mid, bright, motif = CARDS[key]
    card = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    band(card, dark, mid, bright, motif, hash(key) % 1000)
    fig = waist_up(matte(shots / (shot + '_black.png'), shots / (shot + '_white.png')))
    scale = (H - 10) / fig.height
    fig = fig.resize((int(fig.width * scale), int(fig.height * scale)), Image.LANCZOS)
    fig = sticker(fig, mid)
    # the figure pops out over the band, a little to the right of the left edge
    card.alpha_composite(fig, (70 - 22, H - fig.height + 22) if fig.height <= H + 22 else (48, 0))
    # name, slanted; Chinese name and title under it
    f_en = ImageFont.truetype(FONT_EN, 132)
    name = slanted_text_font(en, f_en, (255, 255, 255, 255), dark + (255,), 7)
    x0 = max(560, 70 + fig.width - 40)
    card.alpha_composite(name, (x0, 170))
    f_zh = ImageFont.truetype(FONT_ZH, 46)
    sub = slanted_text_font('%s　「%s」' % (zh, title), f_zh, bright + (255,), dark + (255,), 5, 0.12)
    card.alpha_composite(sub, (x0 + 26, 170 + name.height - 8))
    f_tag = ImageFont.truetype(FONT_EN, 34)
    tag = slanted_text_font('ULTIMATE', f_tag, (255, 255, 255, 230), dark + (255,), 4, 0.18)
    card.alpha_composite(tag, (x0 + 10, 132))
    return card


def slanted_text_font(text, f, fill, stroke, stroke_w, shear=0.18):
    box = f.getbbox(text, stroke_width=stroke_w)
    w, h = box[2] - box[0] + 24, box[3] - box[1] + 24
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # a soft drop shadow, then the text
    d.text((12 - box[0] + 5, 12 - box[1] + 6), text, font=f, fill=(0, 0, 0, 120), stroke_width=stroke_w, stroke_fill=(0, 0, 0, 120))
    im = im.filter(ImageFilter.GaussianBlur(3))
    ImageDraw.Draw(im).text((12 - box[0], 12 - box[1]), text, font=f, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)
    extra = int(h * shear)
    return im.transform((w + extra, h), Image.AFFINE, (1, shear, -extra, 0, 1, 0), Image.BICUBIC)


def main():
    shots = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    cards = []
    for key in CARDS:
        c = make_card(key, shots)
        c.save(OUT / ('T_UltCutIn_%s.png' % key))
        cards.append(c)
        print('card', key, c.size)
    # preview: each card over a game-like grey background, as the HUD shows it
    prev = Image.new('RGBA', (W, H * len(cards)), (70, 78, 90, 255))
    for i, c in enumerate(cards):
        prev.alpha_composite(c, (0, i * H))
    prev.convert('RGB').save(OUT / 'preview.jpg', quality=90)


if __name__ == '__main__':
    main()
