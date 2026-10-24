"""Round 20: the character introduction video in each of the four game languages.

python r20_intro_post.py <EN|ZH|JA|FR> <frames_root> <timeline.json> [--stills]
  -> output/round20/videos/Intro_<lang>.mp4   (--stills: a few PNGs to look at, no video)

The footage is r20_intro.py's -- each wizard in their own arena, every action once at normal
speed, the other three wizards as opponents -- shown as it is: no captions, no narration.
The game's HUD was hidden for the capture; the ultimate cut-in card is drawn here, in the
video's language, the way BP_WizardMatchHUD.DrawUltCutIn draws it (round 13: slides in from
the left in 0.16 s, holds, slides out and fades from 1.15 s to 1.45 s, a faint white flash
under the slide-in), on the game's own clock (the HUD's CutInStart, logged every frame).
Around the footage: an opening title, a card for each wizard (the select screen's texts:
name, element, epithet, traits, ultimate) and a closing card.  The cards' parts move in
gently; every change is a short crossfade.  All text is the game's own, in the game's fonts
(rounds 15-17).
Sound: the recorded game sound frame by frame; the menu theme under the opening and the
closing card, each wizard's arena theme under their part, ducked under the effects.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import r11_video_post as P  # noqa: E402
import r13_video_post as V  # noqa: E402
import r13_synth as S  # noqa: E402
from r15_texts import TEXTS  # noqa: E402
from r19_intro_post import Typesetter, paper, portrait, LANGS, WIZ, GLOW, GOLD, DARK  # noqa: E402

VIDEOS = Path(os.environ.get('R20_VIDEOS', str(ROOT / 'output' / 'round20' / 'videos')))   # round 21: R20_VIDEOS
CUTIN = ROOT / 'output' / 'round15' / 'cutin'
W, H, FPS = 1280, 720, 30
SPF = V.SPF
OPEN, CARD, END = 120, 120, 150            # frames: the opening title, a wizard's card, the closing card
XF = 12                                    # crossfade frames
FADE_OUT = 30                              # the closing card fades to black
KEYS = ['Blaise', 'Neve', 'Gale', 'Volta']
SUFFIX = {'EN': '', 'ZH': '_ZH', 'JA': '_JA', 'FR': '_FR'}
# DrawUltCutIn (r13_wire.py)
SLIDE_IN, HOLD, SLIDE_OUT = 0.16, 1.15, 0.30
CARD_H, CARD_Y, CARD_ASPECT = 0.36, 0.26, 2.5
# a HighResShot shows the world one tick after the callback that asked for it (round 18):
# the frame logged at game time t was drawn at t + 1/30
HUD_DELAY = 1.0 / FPS
MUSIC_CARD_DB, MUSIC_PLAY_DB = -9.0, V.MUSIC_GAIN_DB
UI = {
    'eyebrow': ('LITTLE WIZARD  ·  CHARACTER INTRODUCTION', '小小魔法師・角色介紹',
                'ちいさな魔法使い・キャラクター紹介', 'PETIT SORCIER  ·  PRÉSENTATION DES PERSONNAGES'),
    'intro': ('Character Introduction', '角色介紹', 'キャラクター紹介', 'Présentation des personnages'),
    'traits': ('TRAITS', '特性', '特性', 'ATOUTS'),
}
BROWN = (122, 78, 42, 255)
LINE = (214, 182, 120, 255)


# ------------------------------------------------------------------ animated cards
def ease(t):
    return 1.0 - (1.0 - min(max(t, 0.0), 1.0)) ** 3


def layer():
    return Image.new('RGBA', (W, H), (0, 0, 0, 0))


def comp(base, im, ox, oy):
    """alpha_composite at an offset that may be negative."""
    base.alpha_composite(im, dest=(max(0, ox), max(0, oy)), source=(max(0, -ox), max(0, -oy)))


class Card:
    """A still card whose parts move in: each part is a full-frame layer that fades in while it
    slides `dx`, `dy` pixels into place, from frame `start` for `dur` frames (ease-out)."""

    def __init__(self, bg):
        self.bg = bg.convert('RGBA')
        self.parts = []
        self.final = None

    def add(self, im, start, dur=14, dx=0, dy=0):
        self.parts.append((im, start, dur, dx, dy))

    def frame(self, i):
        if self.final is not None and all(i >= s + d for _, s, d, _, _ in self.parts):
            return self.final
        im = self.bg.copy()
        for part, start, dur, dx, dy in self.parts:
            e = ease((i - start + 1) / float(dur))
            if e <= 0.0:
                continue
            if e < 1.0:
                part = part.copy()
                part.putalpha(part.getchannel('A').point(lambda v, e=e: int(v * e)))
            comp(im, part, round(dx * (1 - e)), round(dy * (1 - e)))
        out = im.convert('RGB')
        if all(i >= s + d for _, s, d, _, _ in self.parts):
            self.final = out
        return out


def text_layer(ts, x, baseline, text, size, fill, bold=False, center=False):
    im = layer()
    d = ImageDraw.Draw(im)
    if center:
        x = (W - ts.width(d, text, size, bold)) / 2
    ts.write(d, x, baseline, text, size, fill, bold)
    return im


def portrait_layer(who, height, cx, bottom, rx):
    im = layer()
    sh = layer()
    ImageDraw.Draw(sh).ellipse((cx - rx, bottom - 14, cx + rx, bottom + 14), fill=(80, 60, 40, 70))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    p = portrait(who, height)
    im.alpha_composite(p, (cx - p.width // 2, bottom - p.height))
    return im


def opening_card(lang):
    li = LANGS.index(lang)
    ts = Typesetter(lang)
    main = TEXTS['WBP_WizardMain']
    c = Card(paper([(330 + 160 * k, 480, 210, 260, GLOW[w], 0.16) for k, (w, _, _) in enumerate(WIZ)]))
    d = ImageDraw.Draw(layer())
    title = main['Title'][li].replace('\n', ' ' if lang in ('EN', 'FR') else '')
    c.add(text_layer(ts, 0, 92, main['Eyebrow'][li], 22, GOLD, True, center=True), 2, 14, dy=8)
    c.add(text_layer(ts, 0, 192, title, ts.fit(d, title, 96, True, 1100), DARK, True, center=True), 6, 16, dy=12)
    c.add(text_layer(ts, 0, 250, UI['intro'][li], 38, BROWN, True, center=True), 12, 16, dy=10)
    for k, (who, _, _) in enumerate(WIZ):
        c.add(portrait_layer(who, 400, 250 + 260 * k, 712, 110), 16 + 5 * k, 18, dy=40)
    return c


def wizard_card(lang, who, key, ink):
    li = LANGS.index(lang)
    ts = Typesetter(lang)
    sel = TEXTS['WBP_WizardSelect']
    c = Card(paper([(330, 380, 300, 330, GLOW[who], 0.22)]))
    d = ImageDraw.Draw(layer())
    x0, right = 610, 1230
    c.add(portrait_layer(who, 650, 330, 706, 150), 0, 18, dx=-50)
    eb = UI['eyebrow'][li]
    c.add(text_layer(ts, x0, 128, eb, ts.fit(d, eb, 22, True, right - x0), GOLD, True), 4, 14, dx=24)
    name = sel[key + 'Name'][li]
    c.add(text_layer(ts, x0 - 4, 238, name, ts.fit(d, name, 104, True, right - x0), ink + (255,), True), 6, 14, dx=30)
    line = '%s  ·  %s' % (sel[key + 'Element'][li], sel[key + 'Subtitle'][li])
    c.add(text_layer(ts, x0, 300, line, ts.fit(d, line, 36, True, right - x0), DARK, True), 9, 14, dx=24)
    rule = layer()
    ImageDraw.Draw(rule).line((x0, 334, x0 + 600, 334), fill=LINE, width=2)
    c.add(rule, 11, 14, dx=24)
    c.add(text_layer(ts, x0, 386, UI['traits'][li], 26, GOLD, True), 13, 14, dx=24)
    y = 438
    traits = sel[key + 'Traits'][li].split('\n')
    for i, t in enumerate(traits):
        c.add(text_layer(ts, x0, y, t, ts.fit(d, t, 32, False, right - x0), DARK), 15 + 2 * i, 14, dx=24)
        y += 46
    y += 34
    ut = sel[key + 'UltimateTitle'][li]
    c.add(text_layer(ts, x0, y, ut, ts.fit(d, ut, 26, True, right - x0), GOLD, True), 20, 14, dx=24)
    ud = sel[key + 'UltimateDesc'][li]
    c.add(text_layer(ts, x0, y + 50, ud, ts.fit(d, ud, 32, False, right - x0), DARK), 22, 14, dx=24)
    return c


def closing_card(lang):
    li = LANGS.index(lang)
    ts = Typesetter(lang)
    main, sel = TEXTS['WBP_WizardMain'], TEXTS['WBP_WizardSelect']
    c = Card(paper([(250 + 260 * k, 470, 200, 250, GLOW[w], 0.18) for k, (w, _, _) in enumerate(WIZ)]))
    d = ImageDraw.Draw(layer())
    title = main['Title'][li].replace('\n', ' ' if lang in ('EN', 'FR') else '')
    c.add(text_layer(ts, 0, 120, title, ts.fit(d, title, 80, True, 1100), DARK, True, center=True), 0, 16, dy=10)
    c.add(text_layer(ts, 0, 176, sel['Title'][li], 30, GOLD, True, center=True), 8, 16, dy=8)
    for k, (who, key, ink) in enumerate(WIZ):
        cx = 250 + 260 * k
        c.add(portrait_layer(who, 380, cx, 650, 100), 12 + 5 * k, 18, dy=36)
        name = sel[key + 'Name'][li]
        c.add(text_layer(ts, cx - ts.width(d, name, 30, True) / 2, 700, name, 30, ink + (255,), True), 18 + 5 * k, 16)
    return c


# ------------------------------------------------------------------ the footage
class CutIn:
    """The ultimate cut-in card over a frame, as DrawUltCutIn draws it at time t (s)."""

    def __init__(self, lang, d):
        sh = H * CARD_H
        self.w, self.h, self.y = sh * CARD_ASPECT, sh, H * CARD_Y
        src = Image.open(CUTIN / ('T_UltCutIn_%s%s.png' % (KEYS[d], SUFFIX[lang]))).convert('RGBA')
        self.card = src.resize((round(self.w), round(self.h)), Image.LANCZOS)
        self.rgb = np.asarray(self.card, np.float32)[..., :3]
        self.alpha = np.asarray(self.card, np.float32)[..., 3:] / 255.0

    def draw(self, im, t):
        if t is None or t < 0.0 or t >= HOLD + SLIDE_OUT:
            return im
        p = min(max(t / SLIDE_IN, 0.0), 1.0)
        q = min(max((t - HOLD) / SLIDE_OUT, 0.0), 1.0)
        x = (1.0 - (1.0 - p) ** 3 - 1.0) * self.w - q * q * self.w
        a = np.asarray(im, np.float32)
        a = a * (1.0 - (1.0 - p) * 0.14) + 255.0 * (1.0 - p) * 0.14        # the flash (DrawRect)
        x0, y0 = int(round(x)), int(round(self.y))
        cw, ch = self.card.size
        sx = max(0, -x0)                                                    # the part on screen
        if sx < cw:
            k = self.alpha[:, sx:] * (1.0 - q)                              # TintColor alpha = 1 - q
            dst = a[y0:y0 + ch, x0 + sx:x0 + cw]
            a[y0:y0 + ch, x0 + sx:x0 + cw] = dst * (1.0 - k) + self.rgb[:, sx:] * k
        return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))


def cut_times(segs):
    """Per footage frame: the time since the HUD's card started (None: no card)."""
    total = segs[-1]['start'] + segs[-1]['frames']
    out = [None] * total
    for s in segs:
        for j, (now, start) in enumerate(s.get('hud', [])[:s['frames']]):
            if start > 0.0:
                out[s['start'] + j] = now + HUD_DELAY - start
    return out


class Footage:
    def __init__(self, root, who, segs, lang, d, draw_card=True):
        self.dir = root / who
        self.n = segs[-1]['start'] + segs[-1]['frames']
        self.times = cut_times(segs)
        self.cut = CutIn(lang, d) if draw_card else None
        self.prev = None
        self.missing = 0

    def frame(self, i):
        p = self.dir / ('f_%05d.png' % i)
        if p.exists():
            im = Image.open(p).convert('RGB')
            self.prev = im
        else:
            self.missing += 1
            im = self.prev
        if self.cut is not None:
            im = self.cut.draw(im, self.times[i])
        return im


# ------------------------------------------------------------------ the whole video
def level(x):
    """The whole video at one loudness (about -18 dBFS RMS), peaks held under -2 dB (AAC
    overshoots the limiter by up to ~1.1 dB)."""
    return S.limit(x * (S.db(-18.0) / max(S.rms(x), 1e-9)), S.db(-2.0), 0.05)


def build(lang, root, timeline, hud_in_frames):
    """[(name, frames, frame(i))] played one after another with XF-frame crossfades, and the
    sound: (music beds with their gain curves, the game sound) on the same clock."""
    clips = [('opening', OPEN, opening_card(lang).frame)]
    plan = []                                   # (who index, card clip index, footage clip index)
    for d, (who, key, ink) in enumerate(WIZ):
        if who not in timeline:
            continue
        segs = timeline[who]['segments']
        clips.append((who + '_card', CARD, wizard_card(lang, who, key, ink).frame))
        ft = Footage(root, who, segs, lang, d, draw_card=not hud_in_frames)
        clips.append((who, ft.n, ft.frame))
        plan.append((d, len(clips) - 2, len(clips) - 1, ft))
    clips.append(('closing', END, closing_card(lang).frame))
    starts, t = [], 0
    for i, (_, n, _) in enumerate(clips):
        starts.append(t)
        t += n - (XF if i + 1 < len(clips) else 0)
    total = t
    return clips, starts, total, plan


def write_frames(clips, starts, total, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob('*.jpg'):
        old.unlink()
    for g in range(total):
        live = [(k, g - s) for k, s in enumerate(starts) if 0 <= g - s < clips[k][1]]
        k, i = live[0]
        im = clips[k][2](i)
        if len(live) > 1:                       # the crossfade into the next clip
            k2, i2 = live[1]
            im = Image.blend(im, clips[k2][2](i2), (i2 + 1) / float(XF + 1))
        if g >= total - FADE_OUT:                # the end: to black
            im = Image.blend(im, Image.new('RGB', (W, H)), (g - (total - FADE_OUT) + 1) / float(FADE_OUT))
        im.save(dst / ('v_%05d.jpg' % g), quality=92)
        if g % 500 == 0:
            print('  frame %d / %d' % (g, total), flush=True)


def gain_curve(n, card_frames, ramp=0.6):
    """The music under a wizard's part: louder on the card, down to the playing level once the
    footage starts (a smooth ramp)."""
    g = np.full(n, S.db(MUSIC_PLAY_DB))
    a = card_frames * SPF
    r = int(ramp * V.SR)
    g[:a] = S.db(MUSIC_CARD_DB)
    k = np.linspace(0.0, 1.0, r)
    k = k * k * (3 - 2 * k)
    g[a:a + r] = S.db(MUSIC_CARD_DB) + (S.db(MUSIC_PLAY_DB) - S.db(MUSIC_CARD_DB)) * k[:len(g[a:a + r])]
    return g[:, None]


def sound(clips, starts, total, plan, root, timeline):
    n = total * SPF
    music = np.zeros((n, 2))
    fx = np.zeros((n, 2))
    xf = XF / float(FPS)

    def put(buf, x, at):
        a = at * SPF
        m = min(len(x), n - a)
        buf[a:a + m] += x[:m]

    # the menu theme: the opening, then the closing card (fading out with the picture)
    put(music, S.fade(V.music_bed('Menu', OPEN * SPF) * S.db(MUSIC_CARD_DB), 0.3, xf), starts[0])
    last = len(clips) - 1
    put(music, S.fade(V.music_bed('Menu', END * SPF) * S.db(MUSIC_CARD_DB), xf, FADE_OUT / float(FPS)), starts[last])
    for d, ci, fi, ft in plan:
        who = WIZ[d][0]
        span = (starts[fi] + ft.n) - starts[ci]
        bed = V.music_bed(V.MUSIC[who][0], span * SPF) * gain_curve(span * SPF, starts[fi] - starts[ci] + XF)
        put(music, S.fade(bed, xf, xf), starts[ci])
        game, sr = S.read_wav(root / who / 'game_audio.wav')
        assert sr == V.SR, sr
        g = V.game_track(game, who, timeline)
        put(fx, g, starts[fi])
    return level(fx + V.duck(music, fx))


def encode(dst, wav, out):
    VIDEOS.mkdir(parents=True, exist_ok=True)
    cmd = [P.BLENDER, '-b', '--factory-startup', '-P', str(ROOT / 'r11_video_encode.py'), '--', str(dst), str(out), str(FPS),
           '--audio', str(wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    line = [x for x in r.stdout.splitlines() if 'R11_VIDEO_ENCODED' in x]
    print(line[-1] if line else r.stdout[-2000:] + r.stderr[-2000:], flush=True)


def stills(lang, clips, starts, root, out):
    """A few frames to look at: each card when settled, and every ultimate's card moment."""
    out.mkdir(parents=True, exist_ok=True)
    for k, (name, n, fn) in enumerate(clips):
        if name.endswith('_card') or name in ('opening', 'closing'):
            fn(n - 1).save(out / ('%s_%s.png' % (lang, name)))
            fn(min(10, n - 1)).save(out / ('%s_%s_in.png' % (lang, name)))
        elif hasattr(fn, '__self__') and isinstance(fn.__self__, Footage):
            ft = fn.__self__
            for i, t in enumerate(ft.times):
                if t is not None and (abs(t - 0.05) < 0.017 or abs(t - 0.6) < 0.017 or abs(t - 1.3) < 0.017):
                    fn(i).save(out / ('%s_%s_%04d_t%.2f.png' % (lang, name, i, t)))


def main():
    lang, root, tl = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    assert lang in LANGS, lang
    data = json.loads(tl.read_text(encoding='utf-8'))
    timeline = data['timeline']
    clips, starts, total, plan = build(lang, root, timeline, bool(data.get('hud_on')))
    work = root / ('intro_' + lang)
    if '--stills' in sys.argv:
        stills(lang, clips, starts, root, work / 'stills')
        print('stills in', work / 'stills')
        return
    print(lang, 'frames', total, '(%.1f s):' % (total / float(FPS)), ', '.join('%s %d' % (c[0], c[1]) for c in clips), flush=True)
    write_frames(clips, starts, total, work / 'frames')
    for d, ci, fi, ft in plan:
        if ft.missing:
            print('  %s: %d frames missing (the previous one repeated)' % (WIZ[d][0], ft.missing))
    track = sound(clips, starts, total, plan, root, timeline)
    wav = work / 'track.wav'
    S.write_wav(wav, track)
    print('sound %.2f s, peak %.1f dB' % (len(track) / float(V.SR), 20 * np.log10(S.peak(track))), flush=True)
    encode(work / 'frames', wav, VIDEOS / ('Intro_%s.mp4' % lang))


if __name__ == '__main__':
    main()
