"""Round 21: quick look-dev comparison for the head-only builds (system Python + PIL).

python r21_headcmp.py <kind> [out.jpg] [tag]
  3d-v2 sheet crop (scale-matched by eye-to-chin, as package_v5.ref_crop) | head_review
  front | three-quarter | side -- after `blender -b -P build_wizard_models_v5.py -- <kind> head`.
(package_v5.py builds every sheet at import, so its few helpers are repeated here.)
"""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

R = Path(__file__).resolve().parent
O = R / 'output/wizard-models/v5'
SHEETS = R / 'output/character-turnarounds/3d-v2'
BG = (238, 234, 225)
# package_v5: sheet landmarks (eye line, chin, front face centre, side nose tip, back head centre)
REF = {'wind': (214.0, 273.0, 307.5, 694.0, 1246.5), 'fire': (210.0, 270.0, 272.0, 697.0, 1257.5),
       'lightning': (209.0, 267.5, 282.0, 679.0, 1271.0), 'ice': (259.0, 305.0, 272.5, 651.0, 1250.8)}
WIN = {'wind': (1.48, .32), 'fire': (1.48, .32), 'lightning': (1.48, .32), 'ice': (1.60, .46)}


def padded(kind, pad=300):
    sheet = Image.open(SHEETS / (kind + '-3d-turnaround.png')).convert('RGB')
    paper = sheet.getpixel((1500, 100))
    big = Image.new('RGB', (sheet.width + 2 * pad, sheet.height + 2 * pad), paper)
    big.paste(sheet, (pad, pad))
    ImageDraw.Draw(big).rectangle((0, 0, big.width, pad + 55), fill=paper)
    return big


def ref_crop(kind, view, size, L):
    eye_y, chin_y, cf, nose_x, cb = REF[kind]
    k = (chin_y - eye_y) / (L['eye_z'] - L['chin_z'])
    c = {'front': cf, 'side': nose_x - L['nose_y'] * k, 'back': cb}[view]
    cz, half = WIN[kind]
    top = eye_y - (cz + half - L['eye_z']) * k
    pad = 300
    box = tuple(int(round(v)) + pad for v in (c - half * k, top, c + half * k, top + 2 * half * k))
    return padded(kind, pad).crop(box).resize((size, size), Image.LANCZOS)


def render(path, size):
    rgba = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', rgba.size, BG + (255,))
    bg.alpha_composite(rgba)
    return bg.convert('RGB').resize((size, size), Image.LANCZOS)


def main(kind, out, tag=''):
    S = 600
    H = O / kind / 'head_review'
    L = json.loads((H / 'landmarks.json').read_text())
    items = [('3d-v2 sheet', ref_crop(kind, 'front', S, L)), ('front ' + tag, render(H / 'front.png', S)),
             ('3/4 ' + tag, render(H / 'three_quarter.png', S)), ('side ' + tag, render(H / 'side.png', S))]
    sheet = Image.new('RGB', (S * len(items), S + 40), BG)
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype('C:/Windows/Fonts/msjh.ttc', 22)
    for i, (lbl, im) in enumerate(items):
        sheet.paste(im, (i * S, 40))
        d.text((i * S + 10, 8), lbl, fill=(40, 40, 40), font=f)
    sheet.save(out, quality=90)
    print('R21_HEADCMP', out)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1] if len(a) > 1 else str(R / ('r21_head_%s.jpg' % a[0])), a[2] if len(a) > 2 else '')
