"""Round 15: the ultimate cut-in cards in four languages (each card one language only).

python r15_cutin_art.py  -> output/round15/cutin/T_UltCutIn_<Key>.png (English) and
                            T_UltCutIn_<Key>_<ZH|JA|FR>.png, + preview.jpg

Round 14's card (r14_cutin_art: the band, the illustration waist up with its sticker
outline); the lettering per language: tag (ULTIMATE / 大招 / 必殺技 / ULTIME), the big name
(BLAISE / 布萊茲 / ブレイズ / BLAISE) and the epithet line.  Fonts: Tinos Bold / Italic (Times
New Roman shapes) for English and French; Chinese LXGW WenKai TC Medium (a 楷體), Japanese Noto Sans JP
Bold (round 16, the game's own fonts).  BP_WizardMatchHUD.StartUltCutIn picks the card by the player's Language.
"""
from pathlib import Path

from PIL import Image, ImageFont

import r13_cutin_art as C
import r14_cutin_art as R14
from r15_texts import CUTIN, LANGS

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'round15' / 'cutin'
F16 = ROOT / 'output' / 'round16' / 'fonts'
W, H = C.W, C.H
FONTS = {
    # round 17: Tinos (Times New Roman shapes, OFL) for English and French; the epithet in its
    # true italic (not slanted again)
    'EN': (str(F16 / 'Tinos-Bold.ttf'), 132, str(F16 / 'Tinos-Italic.ttf'), 48, str(F16 / 'Tinos-Bold.ttf'), 34),
    'FR': (str(F16 / 'Tinos-Bold.ttf'), 132, str(F16 / 'Tinos-Italic.ttf'), 48, str(F16 / 'Tinos-Bold.ttf'), 34),
    # round 16: the game's own Chinese / Japanese fonts (OFL, shipped with the game: r16_fonts.py)
    'ZH': (str(F16 / 'LXGWWenKaiTC-Medium.ttf'), 126, str(F16 / 'LXGWWenKaiTC-Medium.ttf'), 48, str(F16 / 'LXGWWenKaiTC-Medium.ttf'), 36),
    'JA': (str(F16 / 'NotoSansJP-Bold.ttf'), 116, str(F16 / 'NotoSansJP-Bold.ttf'), 44, str(F16 / 'NotoSansJP-Bold.ttf'), 32),
}


def make_card(key, lang):
    _, en, zh, title, dark, mid, bright, motif = C.CARDS[key]
    tag_s, name_s, sub_s = CUTIN[key][lang]
    who, keep, dx = R14.FIGURE[key]
    card = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    C.band(card, dark, mid, bright, motif, sum(map(ord, key)) % 1000)
    fig = R14.waist_up(Image.open(R14.PORTRAITS / (who + '.png')).convert('RGBA'), keep)
    scale = (H - 10) / fig.height
    fig = fig.resize((int(fig.width * scale), int(fig.height * scale)), Image.LANCZOS)
    fig = R14.sticker(fig, mid)
    card.alpha_composite(fig, (48 + dx, H - fig.height + 22))
    f_name, s_name, f_sub, s_sub, f_tag, s_tag = FONTS[lang]
    name = C.slanted_text_font(name_s, ImageFont.truetype(f_name, s_name), (255, 255, 255, 255), dark + (255,), 7)
    x0 = max(560, 48 + dx + fig.width - 30)
    y0 = 170 if lang in ('EN', 'FR') else 176
    card.alpha_composite(name, (x0, y0))
    sub = C.slanted_text_font(sub_s, ImageFont.truetype(f_sub, s_sub), bright + (255,), dark + (255,), 5,
                              0.0 if lang in ('EN', 'FR') else 0.12)
    card.alpha_composite(sub, (x0 + 26, y0 + name.height - 8))
    tag = C.slanted_text_font(tag_s, ImageFont.truetype(f_tag, s_tag), (255, 255, 255, 230), dark + (255,), 4, 0.18)
    card.alpha_composite(tag, (x0 + 10, y0 - 38))
    return card


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for key in C.CARDS:
        for lang in LANGS:
            c = make_card(key, lang)
            name = 'T_UltCutIn_%s.png' % key if lang == 'EN' else 'T_UltCutIn_%s_%s.png' % (key, lang)
            c.save(OUT / name)
            rows.append(c)
    # preview: 4 wizards x 4 languages, half size, on a game-like grey
    pw, ph = W // 2, H // 2
    prev = Image.new('RGBA', (pw * 4, ph * 4), (70, 78, 90, 255))
    for i, c in enumerate(rows):
        prev.alpha_composite(c.resize((pw, ph), Image.LANCZOS), ((i % 4) * pw, (i // 4) * ph))
    prev.convert('RGB').save(OUT / 'preview.jpg', quality=88)
    print('cards', len(rows))


if __name__ == '__main__':
    main()
