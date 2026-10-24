"""Round 13 test videos WITH SOUND: captions and title cards (from r11_video_post.py), the
game's own sound, the new music, then the MP4s (r11_video_encode.py --audio).

python r13_video_post.py <frames_root> [fireboy icegirl windboy lightninggirl] [--all]
  -> output/round13/videos/Round13_Test_<Wizard>.mp4 (+ Round13_Test_All.mp4)

Sound:
- the game: <frames_root>/game_audio.wav was recorded in step with the frames (r11_video.py,
  R13_AUDIO=1): frame k of a segment owns the 1600 samples of its tick (timeline 'ticks');
  the recorded frames' blocks are cut out and joined, with 6 ms fades at the cuts
- the music: each wizard's element map theme (Blaise -> EmberRuins, Neve -> FrostGarden,
  Gale -> SkyGrove, Volta -> NeonFoundry), one continuous track under the whole video
  (title card included), ducked a little while the effects are loud
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import r11_video_post as P
import r13_synth as S

ROOT = Path(__file__).resolve().parent
TIMELINE = Path(os.environ.get('R11_VIDEO_TIMELINE', str(ROOT / 'output/round11/video/video.json')))
VIDEOS = ROOT / 'output' / 'round13' / 'videos'
SR = 48000
FPS = 30
SPF = SR // FPS                     # samples per frame / tick
MUSIC = {'fireboy': ('EmberRuins', '熔岩遺跡'), 'icegirl': ('FrostGarden', '霜之花園'),
         'windboy': ('SkyGrove', '天空樹林'), 'lightninggirl': ('NeonFoundry', '霓虹工廠')}
MUSIC_GAIN_DB = -11.0
GAME_GAIN_DB = 0.0
# round 14: a sound started in game frame k is in the recording ~4.2 frames later (the audio
# thread renders a few buffers behind; measured on the cast sounds, cast at frame 3 ->
# onset at 7.2-7.4): read every frame's sound 4 ticks later so picture and sound line up
AUDIO_LATENCY_TICKS = 4


def title_card(first, who):
    zh, _, accent, en, role, title, mood = P.WHO[who]
    m_en, m_zh = MUSIC[who]
    bg = first.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.35))
    im = bg.convert('RGBA')
    d = ImageDraw.Draw(im)
    rows = (('「%s」' % title, P.font(40, True), 110, (255, 255, 255, 255)),
            (en, P.font(116, True), 160, accent + (255,)),
            ('%s（%s）' % (zh, role), P.font(46, True), 306, accent + (255,)),
            (mood, P.font(32), 378, (235, 235, 235, 255)),
            ('小小魔法師　第 13 輪測試影片（有聲音）', P.font(34), 452, (255, 255, 255, 255)),
            ('新音效 → 大招起手式音效 → 左側立繪 → 新音樂', P.font(26), 510, (210, 210, 210, 255)),
            ('背景音樂：%s（Music_%s）' % (m_zh, m_en), P.font(26), 556, accent + (255,)))
    for text, f, y, col in rows:
        w = d.textlength(text, font=f)
        d.text(((1280 - w) / 2, y), text, font=f, fill=col)
    return im.convert('RGB')


def frames(root, who, timeline):
    """The JPG frames (title + captioned shots), like r11_video_post.build."""
    src = root / who
    dst = root / (who + '_jpg')
    dst.mkdir(exist_ok=True)
    for old in dst.glob('*.jpg'):
        old.unlink()
    segs = timeline[who]['segments']
    total = segs[-1]['start'] + segs[-1]['frames']
    first = Image.open(src / 'f_00000.png').convert('RGB')
    card = title_card(first, who)
    n = 0
    for i in range(P.TITLE_FRAMES):
        card.save(dst / ('v_%05d.jpg' % n), quality=90)
        n += 1
    prev = first
    for f in range(total):
        p = src / ('f_%05d.png' % f)
        if p.exists():
            prev = Image.open(p).convert('RGB')
        seg = next(s for s in segs if s['start'] <= f < s['start'] + s['frames'])
        im = P.caption(prev, seg['caption'], P.WHO[who][2], seg['dilation'] if seg['dilation'] < 0.99 else 0)
        im.save(dst / ('v_%05d.jpg' % n), quality=90)
        n += 1
    return dst, n


def game_track(game, who, timeline):
    """The recorded frames' sound, in video order."""
    parts = []
    for s in timeline[who]['segments']:
        t = s['ticks']
        assert len(t) == s['frames'] and t == list(range(t[0], t[0] + len(t))), (who, s['kind'])
        a, b = (t[0] + AUDIO_LATENCY_TICKS) * SPF, (t[-1] + 1 + AUDIO_LATENCY_TICKS) * SPF
        x = game[a:b]
        if len(x) < b - a:
            x = np.concatenate([x, np.zeros((b - a - len(x), 2))])
        parts.append(S.fade(x, 0.006, 0.006))
    return np.concatenate(parts)


def music_bed(name, n):
    x, sr = S.read_wav(ROOT / 'audio-r13' / 'music' / ('Music_%s.wav' % name))
    assert sr == SR
    reps = int(np.ceil(n / len(x))) + 1
    return np.tile(x, (reps, 1))[:n]


def duck(music, fx, depth_db=8.0):
    """Lower the music up to depth_db while the effects are loud (smooth)."""
    p = np.mean(fx ** 2, axis=1)
    c = np.cumsum(np.concatenate([[0.0], p]))
    k = 2400                                        # 50 ms moving average
    avg = np.empty_like(p)
    avg[k:] = (c[k + 1:] - c[1:-k]) / k
    avg[:k] = c[1:k + 1] / np.arange(1, k + 1)
    e = np.sqrt(np.maximum(avg, 0)) + 1e-9
    lev = 20 * np.log10(e)
    amount = np.clip((lev + 38.0) / 20.0, 0, 1)
    # attack fast, release slow: max-filter then smooth
    from scipy.ndimage import maximum_filter1d
    from scipy.signal import lfilter
    amount = maximum_filter1d(amount, size=SR // 5)
    g = np.exp(-1 / (0.25 * SR))
    amount = lfilter([1 - g], [1, -g], amount)
    return music * (10 ** (-depth_db * amount / 20))[:, None]


def mix(who, timeline, game, n_frames):
    n = n_frames * SPF
    title_n = P.TITLE_FRAMES * SPF
    fx = np.zeros((n, 2))
    g = game_track(game, who, timeline) * S.db(GAME_GAIN_DB)
    fx[title_n:title_n + len(g)] = g[:n - title_n]
    m = music_bed(MUSIC[who][0], n) * S.db(MUSIC_GAIN_DB)
    m = S.fade(m, 0.4, 0.8)
    out = fx + duck(m, fx)
    # the whole video at one loudness (about -18 dBFS RMS), peaks held under -1 dB
    out = out * (S.db(-18.0) / S.rms(out))
    return S.limit(out, S.db(-1.0), 0.05)


def encode(dirs, wav, out):
    VIDEOS.mkdir(parents=True, exist_ok=True)
    cmd = [P.BLENDER, '-b', '--factory-startup', '-P', str(ROOT / 'r11_video_encode.py'), '--'] + [str(d) for d in dirs] + \
        [str(out), '30', '--audio', str(wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    line = [x for x in r.stdout.splitlines() if 'R11_VIDEO_ENCODED' in x]
    print(line[-1] if line else r.stdout[-2000:] + r.stderr[-2000:])


def main():
    root = Path(sys.argv[1])
    names = [a for a in sys.argv[2:] if a in P.WHO] or list(P.WHO)
    timeline = json.loads(TIMELINE.read_text(encoding='utf-8'))['timeline']
    game, sr = S.read_wav(root / 'game_audio.wav')
    assert sr == SR, sr
    print('game audio %.1f s' % (len(game) / SR))
    done = []
    for who in names:
        if who not in timeline:
            print('no timeline for', who)
            continue
        dst, n = frames(root, who, timeline)
        track = mix(who, timeline, game, n)
        wav = root / ('%s_track.wav' % who)
        S.write_wav(wav, track)
        print(who, n, 'frames, sound %.2f s (peak %.1f dB)' % (len(track) / SR, 20 * np.log10(S.peak(track))))
        encode([dst], wav, VIDEOS / ('Round13_Test_%s.mp4' % P.WHO[who][1]))
        done.append((dst, track))
    if '--all' in sys.argv and done:
        allwav = root / 'all_track.wav'
        S.write_wav(allwav, np.concatenate([t for _, t in done]))
        encode([d for d, _ in done], allwav, VIDEOS / 'Round13_Test_All.mp4')


if __name__ == '__main__':
    main()
