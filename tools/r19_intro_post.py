"""Round 19: the character introduction video in each of the four game languages.

python r19_intro_post.py <EN|ZH|JA|FR> <frames_root> <timeline.json>
  -> output/round19/videos/Intro_<lang>.mp4

The footage is the round-18 demo (r18_demo.py, every action once at normal speed; R18_LANG
gives the in-game cut-in cards the video's language) with no captions.  An opening card
says what this is and the test stage; each wizard's card gives the traits.  All text is
the game's own (r15_texts: the select screen) in the game's own fonts:
  EN / FR  Tinos            ZH  霞鶩文楷 TC + Tinos (Latin, digits)
  JA       Noto Sans JP + Roboto (Latin, digits; as F_Wizard_JA)
Sound as rounds 13 / 18: the recorded game sound frame by frame, the wizard's arena theme
under it (ducked under the effects); the opening card has the menu theme.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

import r11_video_post as P  # noqa: E402
import r13_video_post as V  # noqa: E402
import r13_synth as S  # noqa: E402
from r15_texts import TEXTS  # noqa: E402

VIDEOS = ROOT / 'output' / 'round19' / 'videos'
F16 = ROOT / 'output' / 'round16' / 'fonts'
ENGINE_FONTS = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
PORTRAITS = ROOT / 'output' / 'round14' / 'portraits'
W, H, FPS = 1280, 720, 30
SPF = V.SPF
LANGS = ['EN', 'ZH', 'JA', 'FR']
OPEN_FRAMES = 105                        # 3.5 s
CARD_FRAMES = 105
# (main regular, main bold, Latin regular, Latin bold)
FONTS = {'EN': (F16 / 'Tinos-Regular.ttf', F16 / 'Tinos-Bold.ttf', None, None),
         'FR': (F16 / 'Tinos-Regular.ttf', F16 / 'Tinos-Bold.ttf', None, None),
         'ZH': (F16 / 'LXGWWenKaiTC-Regular.ttf', F16 / 'LXGWWenKaiTC-Medium.ttf', F16 / 'Tinos-Regular.ttf', F16 / 'Tinos-Bold.ttf'),
         'JA': (F16 / 'NotoSansJP-Regular.ttf', F16 / 'NotoSansJP-Bold.ttf', ENGINE_FONTS / 'Roboto-Regular.ttf',
                ENGINE_FONTS / 'Roboto-Bold.ttf')}
# who, the select screen's key, accent on cream
WIZ = [('fireboy', 'Fire', (196, 78, 32)), ('icegirl', 'Ice', (58, 104, 196)),
       ('windboy', 'Wind', (36, 132, 86)), ('lightninggirl', 'Lightning', (122, 78, 196))]
GLOW = {'fireboy': (255, 146, 72), 'icegirl': (130, 178, 255), 'windboy': (96, 222, 156), 'lightninggirl': (196, 158, 255)}
UI = {
    'eyebrow': ('LITTLE WIZARD  ·  CHARACTER INTRODUCTION', '小小魔法師・角色介紹',
                'ちいさな魔法使い・キャラクター紹介', 'PETIT SORCIER  ·  PRÉSENTATION DES PERSONNAGES'),
    'intro': ('Character Introduction', '角色介紹', 'キャラクター紹介', 'Présentation des personnages'),
    'stage': ('Internal test build  ·  Round 19  ·  October 2026', '內部測試版・第 19 輪・2026 年 10 月',
              '内部テスト版・第19回・2026年10月', 'Version de test interne  ·  itération 19  ·  octobre 2026'),
    'wip': ('Work in progress: visuals and balance may still change.', '仍在開發中，畫面與數值都可能再調整。',
            '開発中のため、見た目やバランスは今後変わる可能性があります。',
            'Jeu en développement : visuels et équilibrage peuvent encore changer.'),
    'traits': ('TRAITS', '特性', '特性', 'ATOUTS'),
}
GOLD, DARK, MUTED = (176, 122, 42, 255), (43, 33, 64, 255), (107, 94, 87, 255)


class Typesetter:
    """Mixed text in one language's fonts: Latin letters and digits in the Latin face."""

    def __init__(self, lang):
        self.files = FONTS[lang]
        self.latin = set(TTFont(self.files[2]).getBestCmap()) if self.files[2] else None
        self.cache = {}

    def font(self, latin, size, bold):
        key = (latin, size, bold)
        if key not in self.cache:
            i = (3 if bold else 2) if latin else (1 if bold else 0)
            self.cache[key] = ImageFont.truetype(str(self.files[i]), size)
        return self.cache[key]

    def runs(self, text):
        out = []
        for ch in text:
            lat = self.latin is not None and ord(ch) < 0x2E80 and ord(ch) in self.latin and ch != '・'
            if out and out[-1][0] == lat:
                out[-1][1] += ch
            else:
                out.append([lat, ch])
        return out

    def width(self, d, text, size, bold=False):
        return sum(d.textlength(t, font=self.font(lat, size, bold)) for lat, t in self.runs(text))

    def write(self, d, x, baseline, text, size, fill, bold=False):
        for lat, t in self.runs(text):
            f = self.font(lat, size, bold)
            d.text((x, baseline), t, font=f, fill=fill, anchor='ls')
            x += d.textlength(t, font=f)
        return x

    def fit(self, d, text, size, bold, max_w):
        while size > 12 and self.width(d, text, size, bold) > max_w:
            size -= 1
        return size


def paper(glows):
    """The menus' cream paper with soft glows: [(x, y, rx, ry, rgb, strength)]."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = (xx / W * 0.6 + yy / H * 0.4)[..., None]
    base = np.array([255, 249, 238], np.float32) * (1 - t) + np.array([246, 235, 219], np.float32) * t
    for x, y, rx, ry, rgb, k in glows:
        g = np.exp(-(((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2))[..., None] * k
        base = base * (1 - g) + np.array(rgb, np.float32) * g
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert('RGBA')


def portrait(who, height):
    p = Image.open(PORTRAITS / ('%s.png' % who)).convert('RGBA')
    return p.resize((round(p.width * height / p.height), height), Image.LANCZOS)


def shadow(im, cx, y, rx):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((cx - rx, y - 14, cx + rx, y + 14), fill=(80, 60, 40, 70))
    return Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(8)))


def opening_card(lang):
    li = LANGS.index(lang)
    ts = Typesetter(lang)
    im = paper([(330 + 160 * k, 470, 210, 260, GLOW[w], 0.16) for k, (w, _, _) in enumerate(WIZ)])
    for k, (who, _, _) in enumerate(WIZ):
        p = portrait(who, 360)
        cx = 250 + 260 * k
        im = shadow(im, cx, 706, 110)
        im.alpha_composite(p, (cx - p.width // 2, 706 - p.height))
    d = ImageDraw.Draw(im)
    main = TEXTS['WBP_WizardMain']
    title = main['Title'][li].replace('\n', ' ' if lang in ('EN', 'FR') else '')
    ts.write(d, (W - ts.width(d, main['Eyebrow'][li], 22, True)) / 2, 74, main['Eyebrow'][li], 22, GOLD, True)
    size = ts.fit(d, title, 92, True, 1100)
    ts.write(d, (W - ts.width(d, title, size, True)) / 2, 168, title, size, DARK, True)
    intro = UI['intro'][li]
    ts.write(d, (W - ts.width(d, intro, 38, True)) / 2, 222, intro, 38, (122, 78, 42, 255), True)
    stage = UI['stage'][li]
    sw = ts.width(d, stage, 24, True)
    box = ((W - sw) / 2 - 22, 246, (W + sw) / 2 + 22, 288)
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, 21, fill=(255, 196, 92, 235))
    im = Image.alpha_composite(im, layer)
    d = ImageDraw.Draw(im)
    ts.write(d, (W - sw) / 2, 276, stage, 24, (64, 40, 12, 255), True)
    wip = UI['wip'][li]
    ts.write(d, (W - ts.width(d, wip, 20)) / 2, 318, wip, 20, MUTED)
    return im.convert('RGB')


def wizard_card(lang, who, key, ink):
    li = LANGS.index(lang)
    ts = Typesetter(lang)
    sel = TEXTS['WBP_WizardSelect']
    im = paper([(330, 380, 300, 330, GLOW[who], 0.22)])
    p = portrait(who, 650)
    im = shadow(im, 330, 706, 150)
    im.alpha_composite(p, (330 - p.width // 2, 706 - p.height))
    d = ImageDraw.Draw(im)
    x0, right = 610, 1230
    ts.write(d, x0, 128, UI['eyebrow'][li], ts.fit(d, UI['eyebrow'][li], 22, True, right - x0), GOLD, True)
    name = sel[key + 'Name'][li]
    ts.write(d, x0 - 4, 238, name, ts.fit(d, name, 104, True, right - x0), ink + (255,), True)
    line = '%s  ·  %s' % (sel[key + 'Element'][li], sel[key + 'Subtitle'][li])
    ts.write(d, x0, 300, line, ts.fit(d, line, 36, True, right - x0), DARK, True)
    d.line((x0, 334, x0 + 600, 334), fill=(214, 182, 120, 255), width=2)
    ts.write(d, x0, 386, UI['traits'][li], 26, GOLD, True)
    for i, t in enumerate(sel[key + 'Traits'][li].split('\n')):
        ts.write(d, x0, 438 + 46 * i, t, ts.fit(d, t, 32, False, right - x0), DARK)
    stage = UI['stage'][li]
    ts.write(d, x0, 640, stage, ts.fit(d, stage, 20, False, right - x0), MUTED)
    return im.convert('RGB')


REUSE = os.environ.get('R19_REUSE') == '1'      # frames already written: only remix the sound


def write_frames(dst, images_and_counts):
    if REUSE and dst.is_dir() and len(list(dst.glob('*.jpg'))) == sum(c for _, c in images_and_counts):
        return sum(c for _, c in images_and_counts)
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob('*.jpg'):
        old.unlink()
    n = 0
    for im, count in images_and_counts:
        for _ in range(count):
            im.save(dst / ('v_%05d.jpg' % n), quality=92)
            n += 1
    return n


def footage(root, who, segs, dst, card):
    """The wizard's card, then the captured frames as they are (no captions)."""
    total = segs[-1]['start'] + segs[-1]['frames']
    if REUSE and dst.is_dir() and len(list(dst.glob('*.jpg'))) == CARD_FRAMES + total:
        return CARD_FRAMES + total, 0
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob('*.jpg'):
        old.unlink()
    n = 0
    for _ in range(CARD_FRAMES):
        card.save(dst / ('v_%05d.jpg' % n), quality=92)
        n += 1
    total = segs[-1]['start'] + segs[-1]['frames']
    prev, missing = None, 0
    for f in range(total):
        p = root / who / ('f_%05d.png' % f)
        if p.exists():
            prev = Image.open(p).convert('RGB')
        else:
            missing += 1
        prev.save(dst / ('v_%05d.jpg' % n), quality=90)
        n += 1
    return n, missing


def level(x):
    """The whole video at one loudness (about -18 dBFS RMS), peaks held under -1.5 dB (AAC
    overshoots the limiter by up to ~1 dB)."""
    return S.limit(x * (S.db(-18.0) / max(S.rms(x), 1e-9)), S.db(-1.5), 0.05)


def wizard_sound(who, timeline, game, n_frames):
    n = n_frames * SPF
    lead = CARD_FRAMES * SPF
    fx = np.zeros((n, 2))
    g = V.game_track(game, who, timeline)
    fx[lead:lead + len(g)] = g[:n - lead]
    m = S.fade(V.music_bed(V.MUSIC[who][0], n) * S.db(V.MUSIC_GAIN_DB), 0.4, 0.8)
    return level(fx + V.duck(m, fx))


def encode(dirs, wav, out):
    VIDEOS.mkdir(parents=True, exist_ok=True)
    cmd = [P.BLENDER, '-b', '--factory-startup', '-P', str(ROOT / 'r11_video_encode.py'), '--'] + [str(d) for d in dirs] + \
        [str(out), str(FPS), '--audio', str(wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    line = [x for x in r.stdout.splitlines() if 'R11_VIDEO_ENCODED' in x]
    print(line[-1] if line else r.stdout[-2000:] + r.stderr[-2000:], flush=True)


def main():
    lang, root, tl = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    assert lang in LANGS, lang
    timeline = json.loads(tl.read_text(encoding='utf-8'))['timeline']
    game, sr = S.read_wav(root / 'game_audio.wav')
    assert sr == V.SR, sr
    work = root / ('intro_' + lang)
    dirs, tracks = [], []
    d0 = work / '00_opening'
    write_frames(d0, [(opening_card(lang), OPEN_FRAMES)])
    menu = S.fade(V.music_bed('Menu', OPEN_FRAMES * SPF), 0.3, 0.6)
    dirs.append(d0)
    tracks.append(level(menu))
    for k, (who, key, ink) in enumerate(WIZ):
        dst = work / ('%02d_%s' % (k + 1, who))
        n, missing = footage(root, who, timeline[who]['segments'], dst, wizard_card(lang, who, key, ink))
        dirs.append(dst)
        tracks.append(wizard_sound(who, timeline, game, n))
        print(lang, who, n, 'frames,', missing, 'missing', flush=True)
    wav = work / 'track.wav'
    S.write_wav(wav, np.concatenate(tracks))
    encode(dirs, wav, VIDEOS / ('Intro_%s.mp4' % lang))


if __name__ == '__main__':
    main()
