"""Encode folders of frames (JPG/PNG, sorted by name; several folders play one
after another) into an H.264 MP4 with Blender's built-in FFmpeg (no separate
ffmpeg needed).

"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup -P r11_video_encode.py -- <frames_dir> [<frames_dir> ...] <out.mp4> [fps] [--audio <track.wav>]

Round 13: with --audio the WAV (as long as the frames) becomes the movie's AAC soundtrack.
"""
import os
import sys
from pathlib import Path
import bpy

args = sys.argv[sys.argv.index('--') + 1:]
audio = None
if '--audio' in args:
    i = args.index('--audio')
    audio = Path(args[i + 1])
    args = args[:i] + args[i + 2:]
k = next(i for i, a in enumerate(args) if a.lower().endswith('.mp4'))
srcs, out = [Path(a) for a in args[:k]], Path(args[k]).resolve()   # round 21: a relative path went astray
fps = int(args[k + 1]) if len(args) > k + 1 else 30
out.parent.mkdir(parents=True, exist_ok=True)

scn = bpy.context.scene
se = scn.sequence_editor_create()
strips = getattr(se, 'strips', None)
if strips is None:
    strips = se.sequences
start, total, size = 1, 0, None
for n, src in enumerate(srcs):
    files = sorted(f for f in os.listdir(src) if f.lower().endswith(('.jpg', '.jpeg', '.png')))
    assert files, 'no frames in %s' % src
    if size is None:
        size = tuple(bpy.data.images.load(str(src / files[0])).size)
    strip = strips.new_image(name='frames%d' % n, filepath=str(src / files[0]), channel=1, frame_start=start)
    for f in files[1:]:
        strip.elements.append(f)
    start += len(files)
    total += len(files)
w, h = size
files = range(total)

r = scn.render
r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
r.fps, r.fps_base = fps, 1.0
scn.frame_start, scn.frame_end = 1, total
# keep the frames' colours as they are (no AgX / Filmic on top)
scn.view_settings.view_transform = 'Standard'
scn.view_settings.look = 'None'
scn.view_settings.exposure = 0.0
scn.view_settings.gamma = 1.0
try:
    scn.sequencer_colorspace_settings.name = 'sRGB'
except Exception:
    pass
ims = r.image_settings
if hasattr(ims, 'media_type'):
    ims.media_type = 'VIDEO'
ims.file_format = 'FFMPEG'
ff = r.ffmpeg
ff.format = 'MPEG4'
ff.codec = 'H264'
ff.constant_rate_factor = 'HIGH'
ff.ffmpeg_preset = 'GOOD'
ff.gopsize = fps
ff.audio_codec = 'NONE'
if audio is not None:
    snd = strips.new_sound(name='soundtrack', filepath=str(audio), channel=2, frame_start=1)
    ff.audio_codec = 'AAC'
    ff.audio_bitrate = 192
    ff.audio_channels = 'STEREO'
    ff.audio_mixrate = 48000
r.use_sequencer = True
stem = out.with_suffix('')
r.filepath = str(stem)
r.use_file_extension = True
bpy.ops.render.render(animation=True)

# Blender names movies <path><start>-<end>.mp4; give it the wanted name
made = sorted(out.parent.glob(stem.name + '*.mp4'), key=lambda p: p.stat().st_mtime)
assert made, 'no movie written'
if made[-1] != out:
    if out.exists():
        out.unlink()
    made[-1].rename(out)
print('R11_VIDEO_ENCODED', out, len(files), 'frames', '%dx%d' % (w, h), '%.1f s' % (len(files) / fps))
