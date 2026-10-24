"""Test videos, step 2: captions and a title card on the frames captured by
r11_video.py, then the MP4s (r11_video_encode.py in Blender).

python r11_video_post.py <frames_root> [fireboy icegirl windboy lightninggirl] [--all]
  -> output/round12/videos/Round12_Test_<Who>.mp4 (and Round12_Test_All.mp4 with --all)
env R11_VIDEO_TIMELINE (default output/round11/video/video.json), R11_VIDEO_OUT (default output/round12/videos)
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
ROUND = 12
TIMELINE = Path(os.environ.get('R11_VIDEO_TIMELINE', str(ROOT / 'output/round11/video/video.json')))
VIDEOS = Path(os.environ.get('R11_VIDEO_OUT', str(ROOT / ('output/round%d/videos' % ROUND))))
BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
FONT = 'C:/Windows/Fonts/msjh.ttc'
FONT_B = 'C:/Windows/Fonts/msjhbd.ttc'
# round 12: the names (English first, the Chinese a transliteration), titles and personalities
WHO = {'fireboy': ('布萊茲', 'Blaise_FireBoy', (255, 140, 60), 'Blaise', '火男', '爆炎魔法師', '大剌剌・外向・衝動'),
       'icegirl': ('妮芙', 'Neve_IceGirl', (120, 170, 255), 'Neve', '冰女', '沉凍之心', '慵懶・愛睡覺・內向'),
       'windboy': ('蓋爾', 'Gale_WindBoy', (90, 220, 150), 'Gale', '風男', '瞬影', '陰沉・冷漠・沉默'),
       'lightninggirl': ('沃爾妲', 'Volta_LightningGirl', (255, 215, 60), 'Volta', '雷女', '輪舞之流', '瘋瘋癲癲・愛熱鬧')}
TITLE_FRAMES = 60


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def rounded_box(im, box, fill, r=14):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, r, fill=fill)
    return Image.alpha_composite(im, layer)


def caption(im, text, accent, slow):
    """Top-left box: '火男｜大招：冰' on the first line, the rest on the second."""
    im = im.convert('RGBA')
    parts = text.split('｜')
    head = '｜'.join(parts[:2])
    rest = '｜'.join(parts[2:])
    f1, f2 = font(34, True), font(26)
    d = ImageDraw.Draw(im)
    w1 = d.textlength(head, font=f1)
    w2 = d.textlength(rest, font=f2) if rest else 0
    while w2 > 1180 and f2.size > 18:
        f2 = font(f2.size - 1)
        w2 = d.textlength(rest, font=f2)
    h = 58 + (40 if rest else 0)
    im = rounded_box(im, (20, 18, 20 + max(w1, w2) + 36, 18 + h), (16, 18, 26, 175))
    d = ImageDraw.Draw(im)
    d.rectangle((20, 18 + 14, 25, 18 + h - 14), fill=accent + (255,))
    d.text((40, 24), head, font=f1, fill=(255, 255, 255, 255))
    if rest:
        d.text((40, 70), rest, font=f2, fill=(235, 235, 235, 255))
    if slow:
        f3 = font(26, True)
        t = '慢動作 ×%.1f' % slow
        tw = d.textlength(t, font=f3)
        im = rounded_box(im, (1280 - tw - 64, 20, 1260, 66), (255, 205, 60, 230), r=22)
        ImageDraw.Draw(im).text((1280 - tw - 42, 25), t, font=f3, fill=(40, 30, 10, 255))
    return im.convert('RGB')


def title_card(first, who):
    zh, _, accent, en, role, title, mood = WHO[who]
    bg = first.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.35))
    im = bg.convert('RGBA')
    d = ImageDraw.Draw(im)
    for text, f, y, col in (('「%s」' % title, font(40, True), 120, (255, 255, 255, 255)),
                            (en, font(116, True), 172, accent + (255,)),
                            ('%s（%s）' % (zh, role), font(46, True), 318, accent + (255,)),
                            (mood, font(32), 392, (235, 235, 235, 255)),
                            ('小小魔法師　第 %d 輪測試影片' % ROUND, font(34), 476, (255, 255, 255, 255)),
                            ('特性 → 看向準星 → 移動 → 普攻 ×4 → 招牌動作 → 大招 ×4', font(26), 536, (210, 210, 210, 255))):
        w = d.textlength(text, font=f)
        d.text(((1280 - w) / 2, y), text, font=f, fill=col)
    return im.convert('RGB')


def build(root, who, timeline):
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
    for i in range(TITLE_FRAMES):
        card.save(dst / ('v_%05d.jpg' % n), quality=90)
        n += 1
    prev = first
    missing = 0
    for f in range(total):
        p = src / ('f_%05d.png' % f)
        if p.exists():
            prev = Image.open(p).convert('RGB')
        else:
            missing += 1
        seg = next(s for s in segs if s['start'] <= f < s['start'] + s['frames'])
        im = caption(prev, seg['caption'], WHO[who][2], seg['dilation'] if seg['dilation'] < 0.99 else 0)
        im.save(dst / ('v_%05d.jpg' % n), quality=90)
        n += 1
    print(who, n, 'frames', missing, 'missing')
    return dst


def encode(dirs, out):
    VIDEOS.mkdir(parents=True, exist_ok=True)
    cmd = [BLENDER, '-b', '--factory-startup', '-P', str(ROOT / 'r11_video_encode.py'), '--'] + [str(d) for d in dirs] + [str(out), '30']
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    line = [x for x in r.stdout.splitlines() if 'R11_VIDEO_ENCODED' in x]
    print(line[-1] if line else r.stdout[-2000:] + r.stderr[-2000:])


def main():
    root = Path(sys.argv[1])
    names = [a for a in sys.argv[2:] if a in WHO] or list(WHO)
    timeline = json.loads(TIMELINE.read_text(encoding='utf-8'))['timeline']
    done = []
    for who in names:
        if who not in timeline:
            print('no timeline for', who)
            continue
        dst = build(root, who, timeline)
        encode([dst], VIDEOS / ('Round%d_Test_%s.mp4' % (ROUND, WHO[who][1])))
        done.append(dst)
    if '--all' in sys.argv and done:
        encode(done, VIDEOS / ('Round%d_Test_All.mp4' % ROUND))


if __name__ == '__main__':      # r13_video_post.py imports the captions and the title card
    main()
