"""Round 20: the battle video -- four wizards, one life each, last one standing, seen through
the game's own third-person camera -- with a title card and a spectator overlay drawn from
the logged game state (the game's health and spell panels are UMG, which HighResShot does
not capture; its canvas HUD -- the crosshair and the ultimate cut-in card -- is in the
frames).  In English (the user asked for the battle in English only), set in Tinos like the
game's English UI; the titles are the game's own texts (the mode, the arena, the wizards).

python r20_battle_post.py <frames_root> <battle.json>  -> output/round20/videos/Battle_1v1v1v1.mp4

Overlay: the four wizards' health (top), whom the camera follows (outlined, a camera mark),
who knocked out whom (top right), short banners: each wizard at the start, the fight, the
camera moving on when the followed wizard is out, the winner.
Sound: the recorded game sound frame by frame (round 13), the battle theme under it.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import r11_video_post as P  # noqa: E402
import r13_video_post as V  # noqa: E402
import r13_synth as S  # noqa: E402
from r15_texts import TEXTS  # noqa: E402
from r19_intro_post import Typesetter, paper, GOLD, DARK  # noqa: E402
from r19_battle_post import face_icon, rounded  # noqa: E402
from r20_intro_post import Card, text_layer, portrait_layer, layer, XF  # noqa: E402

VIDEOS = Path(os.environ.get('R20_VIDEOS', str(ROOT / 'output' / 'round20' / 'videos')))   # round 21: R20_VIDEOS
W, H, FPS = 1280, 720, 30
SPF = V.SPF
TITLE_FRAMES = 135
FADE_OUT = 30
WHO = ['fireboy', 'icegirl', 'windboy', 'lightninggirl']
KEY = ['Fire', 'Ice', 'Wind', 'Lightning']
SEL = TEXTS['WBP_WizardSelect']
MODE = TEXTS['WBP_WizardMode']
MAPS = TEXTS['WBP_MapSelect']
NAME = [SEL[k + 'Name'][0].title() for k in KEY]               # Blaise, Neve, Gale, Volta
EL = [SEL[k + 'Element'][0].title() for k in KEY]               # Fire, Ice, Wind, Lightning
EPITHET = [SEL[k + 'Subtitle'][0] for k in KEY]
INK = [(196, 78, 32), (58, 104, 196), (36, 132, 86), (122, 78, 196)]
LIGHT = [(255, 146, 72), (130, 178, 255), (96, 222, 156), (196, 158, 255)]
TS = Typesetter('EN')
CLOSE = 26                                # r20_battle.py: each wizard's close-up at the start
FEED_SECS = 4.0
BANNER_SECS = 2.6


ICONS = {}


def icon(d, size, grey=False):
    key = (d, size, grey)
    if key not in ICONS:
        im = face_icon(WHO[d], size)
        if grey:
            a = im.getchannel('A')
            g = im.convert('L').point(lambda v: int(v * 0.55 + 60)).convert('RGBA')
            g.putalpha(a)
            im = g
        ICONS[key] = im
    return ICONS[key]


def title_card(arena):
    """The match: the mode and the arena (the game's own texts), the four wizards."""
    c = Card(paper([(250 + 260 * k, 520, 210, 240, LIGHT[k], 0.16) for k in range(4)]))
    main = TEXTS['WBP_WizardMain']
    c.add(text_layer(TS, 0, 70, main['Title'][0].replace('\n', ' ') + '  ·  ' + main['Eyebrow'][0], 22, GOLD, True, center=True),
          2, 14, dy=8)
    c.add(text_layer(TS, 0, 150, MODE['LastStandButtonTitle'][0], 76, DARK, True, center=True), 6, 16, dy=12)
    c.add(text_layer(TS, 0, 198, MODE['LastStandButtonSub'][0], 28, (122, 78, 42, 255), False, center=True), 12, 16, dy=10)
    where = '%s  ·  %s' % (MAPS[arena + 'Name'][0], MAPS[arena + 'Desc'][0])
    c.add(text_layer(TS, 0, 246, where, 24, GOLD, True, center=True), 16, 16, dy=10)
    for k in range(4):
        cx = 250 + 260 * k
        c.add(portrait_layer(WHO[k], 330, cx, 706, 100), 18 + 5 * k, 18, dy=36)
        c.add(text_layer(TS, cx - TS.width(ImageDraw.Draw(layer()), NAME[k], 26, True) / 2, 712 - 330 - 12, NAME[k], 26,
                         INK[k] + (255,), True), 22 + 5 * k, 16)
    return c


def camera_mark(d, x, y, col):
    """A small movie-camera glyph: whom the camera follows."""
    d.rounded_rectangle((x, y, x + 15, y + 11), 3, fill=col)
    d.polygon([(x + 16, y + 5.5), (x + 22, y + 1), (x + 22, y + 10)], fill=col)


def chips(im, fr):
    """Top centre: four wizards and their health; the followed one outlined; the fallen greyed."""
    cw, gap = 236, 14
    x0 = (W - (4 * cw + 3 * gap)) / 2
    for k in range(4):
        alive, hp, mx, _, _ = fr['w'][k]
        x = x0 + k * (cw + gap)
        pov = fr['v'] == k
        im = rounded(im, (x, 12, x + cw, 66), (18, 20, 30, 190) if not pov else (34, 26, 52, 215), 14)
        d = ImageDraw.Draw(im)
        if pov:
            d.rounded_rectangle((x, 12, x + cw, 66), 14, outline=LIGHT[k] + (255,), width=2)
        im.alpha_composite(icon(k, 44, grey=not alive), (int(x + 6), 17))
        d = ImageDraw.Draw(im)
        nx = TS.write(d, x + 58, 36, NAME[k], 18, (255, 255, 255, 255) if alive else (150, 150, 150, 255), True)
        if pov:
            camera_mark(d, nx + 8, 24, LIGHT[k] + (255,))
        bx0, bx1, by = x + 58, x + cw - 12, 46
        d.rounded_rectangle((bx0, by, bx1, by + 10), 5, fill=(60, 62, 72, 255))
        if alive and mx > 0:
            frac = max(0.0, min(1.0, hp / mx))
            col = (110, 220, 120) if frac > 0.5 else (240, 196, 70) if frac > 0.25 else (235, 90, 80)
            d.rounded_rectangle((bx0, by, bx0 + max(10, (bx1 - bx0) * frac), by + 10), 5, fill=col + (255,))
            TS.write(d, bx1 - TS.width(d, '%d' % round(hp), 14), 37, '%d' % round(hp), 14, (220, 220, 220, 255))
        else:
            TS.write(d, bx1 - TS.width(d, 'OUT', 16, True), 37, 'OUT', 16, (235, 110, 100, 255), True)
    return im


def feed(im, t, events):
    """Top right: who knocked out whom (4 s each)."""
    y = 84
    for ev in events:
        if ev['kind'] != 'out' or not (ev['t'] <= t < ev['t'] + FEED_SECS):
            continue
        alpha = int(255 * min(1.0, (ev['t'] + FEED_SECS - t) / 0.6))
        by = ev.get('by')
        text = '%s  knocked out  %s' % (NAME[by], NAME[ev['who']]) if by is not None else '%s  is out' % NAME[ev['who']]
        d = ImageDraw.Draw(im)
        tw = TS.width(d, text, 20, True)
        x1 = W - 20
        x0 = x1 - tw - 34 - (56 if by is not None else 26)
        im = rounded(im, (x0, y, x1, y + 38), (18, 20, 30, int(190 * alpha / 255)), 12)
        if by is not None:
            im.alpha_composite(icon(by, 28), (int(x0 + 8), y + 5))
        im.alpha_composite(icon(ev['who'], 28, grey=True), (int(x1 - 36), y + 5))
        d = ImageDraw.Draw(im)
        TS.write(d, x0 + (42 if by is not None else 12), y + 26, text, 20, (255, 255, 255, alpha), True)
        y += 46
    return im


def banner(im, text, sub, accent, cx=W / 2, alpha=1.0):
    """A dark plate low in the picture: a title and a line under it; fades with alpha."""
    over = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    tw = max(TS.width(d, text, 46, True), TS.width(d, sub, 24) if sub else 0)
    box = (cx - tw / 2 - 40, 520, cx + tw / 2 + 40, 620 if sub else 590)
    d.rounded_rectangle(box, 20, fill=(18, 20, 30, 200))
    d.rectangle((box[0] + 16, 536, box[0] + 21, box[3] - 16), fill=accent + (255,))
    TS.write(d, cx - TS.width(d, text, 46, True) / 2, 572, text, 46, (255, 255, 255, 255), True)
    if sub:
        TS.write(d, cx - TS.width(d, sub, 24) / 2, 606, sub, 24, (230, 230, 230, 255))
    if alpha < 1.0:
        over.putalpha(over.getchannel('A').point(lambda v: int(v * alpha)))
    return Image.alpha_composite(im, over)


def fade_in_out(t, dur, edge=0.25):
    return max(0.0, min(1.0, t / edge, (dur - t) / edge))


def overlay(im, i, fr, log, fight0):
    events = log['events']
    t = (i - fight0) / float(FPS)
    im = chips(im, fr)
    if fr['p'] == 'intro':
        if i < 4 * CLOSE:
            k = i // CLOSE
            im = banner(im, NAME[k].upper(), '%s  ·  %s' % (EL[k], EPITHET[k]), INK[k], cx=300,
                        alpha=fade_in_out((i % CLOSE + 1) / float(FPS), CLOSE / float(FPS), 0.15))
        else:
            arena = log['map']
            im = banner(im, '%s  ·  %s' % (MODE['LastStandButtonTitle'][0], MAPS[arena + 'Name'][0]),
                        MODE['LastStandButtonSub'][0], (255, 196, 92))
    elif fr['p'] == 'fight':
        im = feed(im, t, events)
        povs = [ev for ev in events if ev['kind'] == 'pov' and ev['t'] <= t]
        if povs and t - povs[-1]['t'] < BANNER_SECS:
            cur = povs[-1]
            a = fade_in_out(t - cur['t'], BANNER_SECS)
            if len(povs) == 1:
                im = banner(im, 'FIGHT!', 'Following %s' % NAME[cur['who']], INK[cur['who']], alpha=a)
            else:
                im = banner(im, '%s is out' % NAME[povs[-2]['who']], 'Now following %s' % NAME[cur['who']], INK[cur['who']], alpha=a)
    elif fr['p'] == 'outro':
        win = next((ev for ev in events if ev['kind'] == 'win'), None)
        if win:
            k = win['who']
            im = banner(im, 'WINNER: %s' % NAME[k].upper(), '%s  ·  %s' % (EL[k], EPITHET[k]), INK[k])
    return im


def frames(root, log, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob('*.jpg'):
        old.unlink()
    card = title_card(log['map'])
    fight0 = next((i for i, fr in enumerate(log['frames']) if fr['p'] == 'fight'), 0)
    nf = len(log['frames'])
    total = TITLE_FRAMES - XF + nf
    prev = None
    for g in range(total):
        i = g - (TITLE_FRAMES - XF)                 # the battle frame (negative: the title only)
        im = None
        if i >= 0:
            p = root / 'battle' / ('f_%05d.png' % i)
            if p.exists():
                prev = Image.open(p).convert('RGBA')
            im = overlay(prev.copy(), i, log['frames'][i], log, fight0).convert('RGB')
        if g < TITLE_FRAMES:
            c = card.frame(g)
            im = c if im is None else Image.blend(c, im, (i + 1) / float(XF + 1))
        if g >= total - FADE_OUT:
            im = Image.blend(im, Image.new('RGB', (W, H)), (g - (total - FADE_OUT) + 1) / float(FADE_OUT))
        im.save(dst / ('v_%05d.jpg' % g), quality=90)
        if g % 500 == 0:
            print('  frame %d / %d' % (g, total), flush=True)
    return total


def sound(log, game, n_frames):
    n = n_frames * SPF
    lead = (TITLE_FRAMES - XF) * SPF
    fx = np.zeros((n, 2))
    parts = []
    for fr in log['frames']:
        a = (fr['tick'] + V.AUDIO_LATENCY_TICKS) * SPF
        x = game[a:a + SPF]
        if len(x) < SPF:
            x = np.concatenate([x, np.zeros((SPF - len(x), 2))])
        parts.append(x)
    g = np.concatenate(parts)
    fx[lead:lead + len(g)] = g[:n - lead]
    m = S.fade(V.music_bed('Duel', n) * S.db(V.MUSIC_GAIN_DB), 0.5, FADE_OUT / float(FPS))
    out = fx + V.duck(m, fx)
    return S.limit(out * (S.db(-18.0) / max(S.rms(out), 1e-9)), S.db(-2.0), 0.05)


def main():
    root, logp = Path(sys.argv[1]), Path(sys.argv[2])
    log = json.loads(logp.read_text(encoding='utf-8'))
    dst = root / 'battle_jpg'
    n = frames(root, log, dst)
    print('battle', n, 'frames', flush=True)
    wav = root / 'battle_track.wav'
    game, sr = S.read_wav(root / 'game_audio.wav')
    assert sr == V.SR, sr
    S.write_wav(wav, sound(log, game, n))
    VIDEOS.mkdir(parents=True, exist_ok=True)
    out = VIDEOS / os.environ.get('R20_OUT', 'Battle_1v1v1v1.mp4')
    cmd = [P.BLENDER, '-b', '--factory-startup', '-P', str(ROOT / 'r11_video_encode.py'), '--', str(dst), str(out), str(FPS),
           '--audio', str(wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    line = [x for x in r.stdout.splitlines() if 'R11_VIDEO_ENCODED' in x]
    print(line[-1] if line else r.stdout[-2000:] + r.stderr[-2000:], flush=True)


if __name__ == '__main__':
    main()
