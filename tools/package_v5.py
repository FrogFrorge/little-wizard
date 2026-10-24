"""Comparison sheets for the V5 wizards (run with the system Python + PIL).
python package_v5.py
Reference: the 3D turnarounds in output/character-turnarounds/3d-v2.
Head sheets: sheet crops scale-matched to the renders by eye-to-chin distance.
Body sheets: renders scaled so sole-to-eye height matches the sheet, soles and
leg centres aligned (shows head size, neck length and proportions).
"上一版" uses compare/round5_*.png when present (the previous delivery).
Also: side-view face close-ups of all four, and (Lightning, Ice) the hair
physics chains and HairCheck frames.
"""
import json
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

R = Path(__file__).resolve().parent
W = R / 'output/wizard-models'
O = W / 'v5'
SHEETS = R / 'output/character-turnarounds/3d-v2'
KINDS = ['wind', 'fire', 'lightning', 'ice']
NAMES = {'wind': '風', 'fire': '火', 'lightning': '雷', 'ice': '冰'}
BG = (238, 234, 225)
font = ImageFont.truetype('C:/Windows/Fonts/msjh.ttc', 30)
small = ImageFont.truetype('C:/Windows/Fonts/msjh.ttc', 24)
VIEW = {'front': '正面', 'side': '側面', 'back': '背面'}
# 3d-v2 sheet landmarks (pixels): eye line, chin, front face centre, side nose tip, back head centre
REF = {'wind': (214.0, 273.0, 307.5, 694.0, 1246.5), 'fire': (210.0, 270.0, 272.0, 697.0, 1257.5),
       'lightning': (209.0, 267.5, 282.0, 679.0, 1271.0), 'ice': (259.0, 305.0, 272.5, 651.0, 1250.8)}
# compare renders: camera centre z and half window (render_compare_v5.py FRAME)
WIN = {k: (1.48, .32) for k in KINDS}
WIN['ice'] = (1.60, .46)
# full-body geometry: column x-range per view and the sole row (sheet pixels)
COLS = {'wind': [(0, 560), (560, 990), (990, 1536)], 'fire': [(0, 540), (540, 990), (990, 1536)],
        'lightning': [(0, 580), (580, 960), (960, 1536)], 'ice': [(0, 510), (510, 975), (975, 1536)]}
SOLE = {'wind': 916, 'fire': 905, 'lightning': 916, 'ice': 915}
BODY_PPM = 1000 / 2.3                         # full-body renders: 1000 px over 2.3 m
HALF_W, TOP, BOTTOM = 260, -70, 930           # body window around the leg centre (sheet px)


def sheet_img(kind):
    return Image.open(SHEETS / (kind + '-3d-turnaround.png')).convert('RGB')


def padded(kind, pad=300):
    sheet = sheet_img(kind)
    paper = sheet.getpixel((1500, 100))
    big = Image.new('RGB', (sheet.width + 2 * pad, sheet.height + 2 * pad), paper)
    big.paste(sheet, (pad, pad))
    ImageDraw.Draw(big).rectangle((0, 0, big.width, pad + 55), fill=paper)   # hide the sheet title
    return big


def ref_crop(kind, view, size):
    eye_y, chin_y, cf, nose_x, cb = REF[kind]
    L = json.loads((O / kind / 'head_review/landmarks.json').read_text())
    k = (chin_y - eye_y) / (L['eye_z'] - L['chin_z'])
    c = {'front': cf, 'side': nose_x - L['nose_y'] * k, 'back': cb}[view]
    cz, half = WIN[kind]
    top = eye_y - (cz + half - L['eye_z']) * k
    pad = 300
    big = padded(kind, pad)
    box = tuple(int(round(v)) + pad for v in (c - half * k, top, c + half * k, top + 2 * half * k))
    return big.crop(box).resize((size, size), Image.LANCZOS)


def leg_centre_ref(kind, view):
    """Mean x of the drawing between 8% and 25% of the eye height above the sole."""
    x0, x1 = COLS[kind][list(VIEW).index(view)]
    a = np.asarray(sheet_img(kind)).astype(float)[:, x0:x1]
    paper = np.median(a[60:120].reshape(-1, 3), axis=0)
    m = np.abs(a - paper).sum(axis=2) > 40
    e = SOLE[kind] - REF[kind][0]
    ys, xs = np.nonzero(m[int(SOLE[kind] - .25 * e):int(SOLE[kind] - .08 * e)])
    return x0 + xs.mean()


def ref_body(kind, view):
    c = leg_centre_ref(kind, view)
    pad = 300
    big = padded(kind, pad)
    x0 = int(round(c)) - HALF_W
    return big.crop((x0 + pad, TOP + pad, x0 + 2 * HALF_W + pad, BOTTOM + pad))


def model_body(kind, view, png, eye_z, sole_z):
    """RGBA render placed in the reference body window at the sheet's scale."""
    e = SOLE[kind] - REF[kind][0]
    k = e / ((eye_z - sole_z) * BODY_PPM)
    im = Image.open(png).convert('RGBA')
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    a = np.asarray(im)[..., 3] > 128
    ys, xs = np.nonzero(a)
    msole = ys.max()
    band = (ys > msole - .25 * e) & (ys < msole - .08 * e)
    mcx = xs[band].mean()
    canvas = Image.new('RGBA', (2 * HALF_W, BOTTOM - TOP), (0, 0, 0, 0))
    ox, oy = round(HALF_W - mcx), round(SOLE[kind] - TOP - msole)
    canvas.alpha_composite(im, (max(0, ox), max(0, oy)), (max(0, -ox), max(0, -oy)))
    return canvas


def on_bg(rgba, colour=BG):
    bg = Image.new('RGBA', rgba.size, colour + (255,))
    bg.alpha_composite(rgba)
    return bg.convert('RGB')


def outline_on(ref, rgba, colour=(220, 30, 30)):
    a = np.asarray(rgba)[..., 3] > 128
    edge = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES)) > 0
    edge = np.asarray(Image.fromarray((edge * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    arr = np.asarray(ref).copy()
    arr[edge] = colour
    return Image.fromarray(arr)


def grid(cols, cw, ch, items, title, path):
    head = 70
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cw, head + rows * (ch + 46)), BG)
    d = ImageDraw.Draw(sheet)
    d.text((24, 18), title, fill=(40, 52, 40), font=font)
    for i, (label, im) in enumerate(items):
        r, c = divmod(i, cols)
        x, y = c * cw, head + r * (ch + 46)
        d.text((x + 14, y + 8), label, fill=(55, 60, 55), font=small)
        sheet.paste(im.resize((cw, ch), Image.LANCZOS), (x, y + 46))
    sheet.save(path, quality=92)


def render(path, size):
    return on_bg(Image.open(path).convert('RGBA')).resize((size, size), Image.LANCZOS)


PREV = 'round20'


def prev(C, name):
    """Previous delivery if rendered (<PREV>_*), else V4."""
    p = C / ('%s_%s.png' % (PREV, name))
    return (p, '上一版') if p.exists() else (C / ('v4_%s.png' % name), 'V4')


def face_box(kind):
    """Side-view face window in the 900 px compare renders (from the head landmarks)."""
    L = json.loads((O / kind / 'head_review/landmarks.json').read_text())
    ppm = L['res'] / L['ortho']
    eye_px = L['res'] / 2 - (L['eye_z'] - L['center']) * ppm
    e = (L['eye_z'] - L['chin_z']) * ppm
    nose_px = L['res'] / 2 + L['nose_y'] * ppm
    return (nose_px - .55 * e, eye_px - .95 * e, nose_px + 1.85 * e, eye_px + 1.45 * e), e, eye_px, nose_px


def side_face(kind, png, size):
    box = face_box(kind)[0]
    return on_bg(Image.open(png).convert('RGBA')).crop(tuple(int(v) for v in box)).resize((size, size), Image.LANCZOS)


def ref_side_face(kind, size):
    box, e, eye_px, nose_px = face_box(kind)
    eye_y, chin_y, cf, nose_x, cb = REF[kind]
    k = e / (chin_y - eye_y)
    pad = 300
    big = padded(kind, pad)
    x0 = nose_x + (box[0] - nose_px) / k + pad
    y0 = eye_y + (box[1] - eye_px) / k + pad
    w = (box[2] - box[0]) / k
    return big.crop((int(x0), int(y0), int(x0 + w), int(y0 + w))).resize((size, size), Image.LANCZOS)


CHAIN_COLOURS = {'side': (40, 110, 230), 'back': (30, 160, 70), 'front': (240, 140, 20), 'bang': (210, 40, 160)}


def chains_on(png, H, view):
    """Render with the hair chain bones drawn on it (orthographic projection)."""
    im = on_bg(Image.open(png).convert('RGBA'))
    d = ImageDraw.Draw(im)
    res, ppm, cz = H['res'], H['res'] / H['ortho'], H['center']

    def px(q):
        x, y, z = q
        u = {'front': x, 'side': y, 'back': -x}[view]
        return (res / 2 + u * ppm, res / 2 - (z - cz) * ppm)
    for name, (h, t) in sorted(H['bones'].items()):
        ym = .5 * (h[1] + t[1])
        if (view == 'front' and ym > .03) or (view == 'back' and ym < .03):
            continue                      # only the chains on the visible side of the head
        col = next((c for k, c in CHAIN_COLOURS.items() if name.startswith('hair_' + k)), (200, 30, 30))
        a, b = px(h), px(t)
        d.line([a, b], fill=col, width=4)
        d.ellipse((a[0] - 5, a[1] - 5, a[0] + 5, a[1] + 5), fill=col)
    return im


S = 540
for kind in KINDS:
    D = O / kind
    C = D / 'compare'
    nm = NAMES[kind]
    title = kind.title()
    items = []
    for v in VIEW:
        items.append(('新三視圖 · ' + VIEW[v], ref_crop(kind, v, S)))
    for v in VIEW:
        p, lbl = prev(C, v)
        items.append(('%s · %s' % (lbl, VIEW[v]), render(p, S)))
    for v in VIEW:
        items.append(('本次 · ' + VIEW[v], render(C / ('v5_%s.png' % v), S)))
    grid(3, S, S, items, '%s魔法師頭部：新三視圖 / 上一版 / 本次（同比例）' % nm, D / ('%s_V5_Head_Comparison.jpg' % title))
    p, lbl = prev(C, 'three_quarter')
    grid(2, 720, 720, [('%s · 3/4 視角' % lbl, render(p, 720)), ('本次 · 3/4 視角', render(C / 'v5_three_quarter.png', 720))],
         '%s魔法師 3/4 視角' % nm, D / ('%s_V5_ThreeQuarter.jpg' % title))
    items = []
    for v in VIEW:
        im = Image.open(C / ('v5_%s.png' % v)).convert('RGBA').resize((S, S), Image.LANCZOS)
        items.append(('新三視圖 + 本次輪廓（紅線）· ' + VIEW[v], outline_on(ref_crop(kind, v, S), im)))
    grid(3, S, S, items, '%s魔法師頭部：本次輪廓疊在新三視圖上' % nm, D / ('%s_V5_Overlay.jpg' % title))
    marks = json.loads((C / 'body_marks.json').read_text())['v5']
    items_ov, items_m = [], []
    for v in VIEW:
        mb = model_body(kind, v, C / ('v5_body_%s.png' % v), marks['eye_z'], marks['sole_z'])
        items_ov.append(('新三視圖 + 本次輪廓（紅線）· ' + VIEW[v], outline_on(ref_body(kind, v), mb)))
        items_m.append(('本次 · ' + VIEW[v], on_bg(mb)))
    grid(3, 380, 731, items_ov + items_m, '%s魔法師全身：本次輪廓疊在新三視圖上（以腳底到眼睛的高度對齊）' % nm,
         D / ('%s_V5_Body_Overlay.jpg' % title))
    body = [Image.open(D / ('%s_%s.png' % (kind, v))).convert('RGB') for v in VIEW]
    w, h = body[0].size
    ref = sheet_img(kind)
    ref = ref.resize((w * 3, int(ref.height * w * 3 / ref.width)), Image.LANCZOS)
    sheet = Image.new('RGB', (w * 3, ref.height + h + 140), BG)
    d = ImageDraw.Draw(sheet)
    d.text((24, 16), '新三視圖（3d-v2）', fill=(40, 52, 40), font=font)
    sheet.paste(ref, (0, 66))
    d.text((24, ref.height + 80), 'V5 模型實際渲染（正 / 側 / 背）', fill=(40, 52, 40), font=font)
    for i, im in enumerate(body):
        sheet.paste(im, (i * w, ref.height + 130))
    sheet.save(D / ('%s_V5_FullBody.jpg' % title), quality=90)
    faces = [(lbl, Image.open(D / ('face_%s.png' % f)).convert('RGB').resize((480, 480), Image.LANCZOS))
             for lbl, f in [('預設', 'Neutral'), ('眨眼', 'Blink'), ('視線', 'Look'), ('張嘴', 'Smile')]]
    grid(4, 480, 480, faces, '%s魔法師 V5 臉部骨架測試（FaceCheck 動作）' % nm, D / ('%s_V5_Expressions.jpg' % title))

# Overview: sheet / previous / this round (front) and this round 3/4
cell = 420
items = []
for kind in KINDS:
    C = O / kind / 'compare'
    nm = NAMES[kind]
    p, lbl = prev(C, 'front')
    items += [('%s · 新三視圖' % nm, ref_crop(kind, 'front', cell)), ('%s · %s' % (nm, lbl), render(p, cell)),
              ('%s · 本次' % nm, render(C / 'v5_front.png', cell)), ('%s · 本次 3/4' % nm, render(C / 'v5_three_quarter.png', cell))]
grid(4, cell, cell, items, '四位魔法師頭部：新三視圖 / 上一版 / 本次', O / 'Four_Wizards_V5_Heads.jpg')
# Full-body line-up: sheet / previous / this round (front view, same scale)
rows = {'ref': [], 'prev': [], 'now': []}
for kind in KINDS:
    C = O / kind / 'compare'
    marks = json.loads((C / 'body_marks.json').read_text())
    rows['ref'].append(('%s · 新三視圖' % NAMES[kind], ref_body(kind, 'front')))
    pb = C / ('%s_body_front.png' % PREV)
    if pb.exists() and PREV in marks:
        pm, lbl = marks[PREV], '上一版'
    else:
        pb, pm, lbl = C / 'v4_body_front.png', marks['v4'], 'V4'
    rows['prev'].append(('%s · %s' % (NAMES[kind], lbl), on_bg(model_body(kind, 'front', pb, pm['eye_z'], pm['sole_z']))))
    rows['now'].append(('%s · 本次' % NAMES[kind], on_bg(model_body(kind, 'front', C / 'v5_body_front.png',
                                                                  marks['v5']['eye_z'], marks['v5']['sole_z']))))
grid(4, 312, 600, rows['ref'] + rows['prev'] + rows['now'],
     '四位魔法師全身：新三視圖 / 上一版 / 本次（以腳底到眼睛的高度對齊）', O / 'Four_Wizards_V5_Bodies.jpg')
# Side-view faces: sheet / previous / this round (the facial relief)
cell = 360
items = []
for kind in KINDS:
    C = O / kind / 'compare'
    p, lbl = prev(C, 'side')
    items += [('%s · 新三視圖' % NAMES[kind], ref_side_face(kind, cell)), ('%s · %s' % (NAMES[kind], lbl), side_face(kind, p, cell)),
              ('%s · 本次' % NAMES[kind], side_face(kind, C / 'v5_side.png', cell))]
grid(3, cell, cell, items, '四位魔法師側臉：新三視圖 / 上一版 / 本次（鼻子、嘴、下巴的起伏）', O / 'Four_Wizards_V5_Side_Faces.jpg')
# Hair physics (Lightning, Ice): chain bones and the HairCheck test clip
for kind in KINDS:
    C = O / kind / 'compare'
    J = C / 'hair_chains.json'
    if not J.exists():
        continue
    H = json.loads(J.read_text())
    items = [('骨骼鏈 · ' + VIEW[v], chains_on(C / ('hair_%s_01.png' % v), H, v)) for v in VIEW]
    for v in ('side', 'back'):
        for fr, lbl in ((16, '前後擺'), (31, '左右擺'), (46, '反向擺')):
            items.append(('HairCheck 第 %d 格 · %s · %s' % (fr, VIEW[v], lbl), on_bg(Image.open(C / ('hair_%s_%02d.png' % (v, fr))).convert('RGBA'))))
    grid(3, 500, 500, items, '%s魔法師頭髮物理：骨骼鏈（藍＝側、綠＝後、橘＝臉旁、紫＝瀏海）與 HairCheck 擺動測試' % NAMES[kind],
         O / kind / ('%s_V5_Hair_Physics.jpg' % kind.title()))
beauty = [Image.open(O / k / ('%s_beauty.png' % k)).convert('RGB') for k in KINDS]
w, h = beauty[0].size
sheet = Image.new('RGB', (w * 4, h), BG)
for i, im in enumerate(beauty):
    sheet.paste(im, (i * w, 0))
sheet.resize((w * 2, h // 2)).save(O / 'Four_Wizards_V5_Beauty.jpg', quality=90)
print('SHEETS_DONE')
