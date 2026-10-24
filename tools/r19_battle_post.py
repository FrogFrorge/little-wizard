"""Round 19: the simulated battle video -- a title card, then r19_battle.py's frames with a
spectator overlay drawn from the logged game state (the game's own HUD is UMG, which
HighResShot does not capture): the four wizards' health, who is out and who did it, whose
eyes we are looking through; the winner at the end.  In English (the user asked for the
battle video in English only), set in Tinos like the game's English UI.

python r19_battle_post.py <frames_root> <battle.json>  -> output/round19/videos/Battle_1v1v1v1.mp4

Sound: the recorded game sound frame by frame (round 13), the duel theme under it.
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
from r19_intro_post import Typesetter, paper, portrait, shadow, UI, GOLD, DARK, MUTED  # noqa: E402
from r15_texts import TEXTS  # noqa: E402

VIDEOS = ROOT / 'output' / 'round19' / 'videos'
PORTRAITS = ROOT / 'output' / 'round14' / 'portraits'
W, H, FPS = 1280, 720, 30
SPF = V.SPF
TITLE_FRAMES = 120
WHO = ['fireboy', 'icegirl', 'windboy', 'lightninggirl']
NAME = ['Blaise', 'Neve', 'Gale', 'Volta']
EL = ['Fire', 'Ice', 'Wind', 'Lightning']
INK = [(196, 78, 32), (58, 104, 196), (36, 132, 86), (122, 78, 196)]
LIGHT = [(255, 146, 72), (130, 178, 255), (96, 222, 156), (196, 158, 255)]
TS = Typesetter('EN')
EPITHET = [TEXTS['WBP_WizardSelect'][k + 'Subtitle'][0] for k in ('Fire', 'Ice', 'Wind', 'Lightning')]
CLOSE = 26                                # r19_battle.py: each wizard's close-up at the start
FEED_SECS = 4.0


def face_icon(who, size):
    """A round crop of the wizard's face from the illustration cut-out."""
    p = Image.open(PORTRAITS / ('%s.png' % who)).convert('RGBA')
    s = int(p.width * 0.78)
    box = ((p.width - s) // 2, int(p.height * 0.03), (p.width + s) // 2, int(p.height * 0.03) + s)
    face = p.crop(box).resize((size, size), Image.LANCZOS)
    bg = Image.new('RGBA', (size, size), (255, 248, 236, 255))
    bg.alpha_composite(face)
    mask = Image.new('L', (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(bg, (0, 0), mask.resize((size, size), Image.LANCZOS))
    return out


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


def rounded(im, box, fill, r=12):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, r, fill=fill)
    return Image.alpha_composite(im, layer)


def title_card(pov):
    im = paper([(250 + 260 * k, 520, 210, 240, LIGHT[k], 0.16) for k in range(4)])
    for k in range(4):
        p = portrait(WHO[k], 330)
        cx = 250 + 260 * k
        im = shadow(im, cx, 706, 100)
        im.alpha_composite(p, (cx - p.width // 2, 706 - p.height))
    d = ImageDraw.Draw(im)
    rows = [('LITTLE WIZARD  ·  SIMULATED BATTLE', 24, GOLD, True, 70), ('1v1v1v1  ·  LAST STAND', 72, DARK, True, 150),
            ('Four wizards, every one played by a bot. The last one standing wins.', 26, (122, 78, 42, 255), False, 198),
            ('First-person view: %s' % NAME[pov], 30, INK[pov] + (255,), True, 246),
            (UI['stage'][0], 20, MUTED, False, 286)]
    for text, size, col, bold, y in rows:
        TS.write(d, (W - TS.width(d, text, size, bold)) / 2, y, text, size, col, bold)
    for k in range(4):
        cx = 250 + 260 * k
        TS.write(d, cx - TS.width(d, NAME[k], 26, True) / 2, 712 - 330 - 12, NAME[k], 26, INK[k] + (255,), True)
    return im.convert('RGB')


def chips(im, fr, out_at):
    """Top centre: four wizards, health bars; the first-person one marked; the fallen greyed."""
    d = ImageDraw.Draw(im)
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
            TS.write(d, nx + 6, 35, 'POV', 13, LIGHT[k] + (255,), True)
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
        if ev.get('by') is not None:
            text = '%s  knocked out  %s' % (NAME[ev['by']], NAME[ev['who']])
        else:
            text = '%s  is out' % NAME[ev['who']]
        d = ImageDraw.Draw(im)
        tw = TS.width(d, text, 20, True)
        x1 = W - 20
        x0 = x1 - tw - 34 - (56 if ev.get('by') is not None else 26)
        im = rounded(im, (x0, y, x1, y + 38), (18, 20, 30, int(190 * alpha / 255)), 12)
        if ev.get('by') is not None:
            im.alpha_composite(icon(ev['by'], 28), (int(x0 + 8), y + 5))
        im.alpha_composite(icon(ev['who'], 28, grey=True), (int(x1 - 36), y + 5))
        d = ImageDraw.Draw(im)
        TS.write(d, x0 + (42 if ev.get('by') is not None else 12), y + 26, text, 20, (255, 255, 255, alpha), True)
        y += 46
    return im


def banner(im, text, sub, accent, cx=W / 2):
    d = ImageDraw.Draw(im)
    tw = max(TS.width(d, text, 46, True), TS.width(d, sub, 24) if sub else 0)
    box = (cx - tw / 2 - 40, 520, cx + tw / 2 + 40, 620 if sub else 590)
    im = rounded(im, box, (18, 20, 30, 200), 20)
    d = ImageDraw.Draw(im)
    d.rectangle((box[0] + 16, 536, box[0] + 21, box[3] - 16), fill=accent + (255,))
    TS.write(d, cx - TS.width(d, text, 46, True) / 2, 572, text, 46, (255, 255, 255, 255), True)
    if sub:
        TS.write(d, cx - TS.width(d, sub, 24) / 2, 606, sub, 24, (230, 230, 230, 255))
    return im


def frames(root, log, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob('*.jpg'):
        old.unlink()
    pov0 = log['pov0']
    card = title_card(pov0)
    n = 0
    for _ in range(TITLE_FRAMES):
        card.save(dst / ('v_%05d.jpg' % n), quality=92)
        n += 1
    events = log['events']
    win = next((ev for ev in events if ev['kind'] == 'win'), None)
    povs = [ev for ev in events if ev['kind'] == 'pov']
    fight0 = next((i for i, fr in enumerate(log['frames']) if fr['p'] == 'fight'), 0)
    prev = None
    for i, fr in enumerate(log['frames']):
        p = root / 'battle' / ('f_%05d.png' % i)
        if p.exists():
            prev = Image.open(p).convert('RGBA')
        im = prev.copy()
        t = (i - fight0) / float(FPS)
        im = chips(im, fr, None)
        if fr['p'] == 'fight':
            im = feed(im, t, events)
            cur = [ev for ev in povs if ev['t'] <= t]
            who = cur[-1]['who'] if cur else pov0
            if t < 3.0 or (len(cur) > 1 and t - cur[-1]['t'] < 3.0):
                im = banner(im, 'First-person view: %s' % NAME[who],
                            '%s is out, so now we see through %s' % (NAME[pov0], NAME[who]) if who != pov0 else None, INK[who])
        elif fr['p'] == 'intro':
            if i < 4 * CLOSE:
                k = i // CLOSE
                im = banner(im, NAME[k].upper(), '%s  ·  %s' % (EL[k], EPITHET[k]), INK[k], cx=300)
            else:
                im = banner(im, '1v1v1v1  ·  LAST STAND', 'Four wizards. Who will be the last one standing?', (255, 196, 92))
        elif fr['p'] == 'outro' and win:
            im = banner(im, 'WINNER: %s' % NAME[win['who']].upper(), '%s  ·  last wizard standing' % EL[win['who']], INK[win['who']])
        im.convert('RGB').save(dst / ('v_%05d.jpg' % n), quality=90)
        n += 1
    return n


def sound(log, game, n_frames):
    n = n_frames * SPF
    lead = TITLE_FRAMES * SPF
    fx = np.zeros((n, 2))
    ticks = [fr['tick'] for fr in log['frames']]
    parts = []
    for tk in ticks:
        a = (tk + V.AUDIO_LATENCY_TICKS) * SPF
        x = game[a:a + SPF]
        if len(x) < SPF:
            x = np.concatenate([x, np.zeros((SPF - len(x), 2))])
        parts.append(x)
    g = np.concatenate(parts)
    fx[lead:lead + len(g)] = g[:n - lead]
    m = S.fade(V.music_bed('Duel', n) * S.db(V.MUSIC_GAIN_DB), 0.5, 1.2)
    out = fx + V.duck(m, fx)
    return S.limit(out * (S.db(-18.0) / max(S.rms(out), 1e-9)), S.db(-1.0), 0.05)


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
    out = VIDEOS / os.environ.get('R19_OUT', 'Battle_1v1v1v1.mp4')
    cmd = [P.BLENDER, '-b', '--factory-startup', '-P', str(ROOT / 'r11_video_encode.py'), '--', str(dst), str(out), str(FPS),
           '--audio', str(wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    line = [x for x in r.stdout.splitlines() if 'R11_VIDEO_ENCODED' in x]
    print(line[-1] if line else r.stdout[-2000:] + r.stderr[-2000:], flush=True)


if __name__ == '__main__':
    main()
