"""Render V4 and V5 with identical cameras for review: head views, a neck
close-up and transparent full-body views (plus eye / sole heights for scaling).
Lightning / Ice: also the hair chain bones (hair_chains.json) and HairCheck
frames (hair_<view>_<frame>.png).
blender -b -P render_compare_v5.py [-- fire ice ...]
"""
import bpy, sys, json
from pathlib import Path
from mathutils import Vector
W = Path(__file__).resolve().parent / 'output/wizard-models'
KINDS = ['wind', 'fire', 'lightning', 'ice']
if '--' in sys.argv:
    KINDS = [k for k in sys.argv[sys.argv.index('--') + 1:] if k in KINDS] or KINDS
views = {'front': (0, -4, 1.52), 'side': (4, 0, 1.52), 'back': (0, 4, 1.52), 'three_quarter': (2.3, -3.3, 1.58)}
FRAME = {'default': (1.48, .64), 'ice': (1.60, .92)}         # head shots: camera centre z, ortho size
HAIR_FRAME = {'lightning': (1.48, .64), 'ice': (1.12, 1.50)}  # HairCheck shots
for kind in KINDS:
    dest = W / 'v5' / kind / 'compare'
    dest.mkdir(parents=True, exist_ok=True)
    mpath = dest / 'body_marks.json'
    marks = json.loads(mpath.read_text()) if mpath.exists() else {}     # keeps e.g. 'round2'
    for version in ['v4', 'v5']:
        bpy.ops.wm.open_mainfile(filepath=str(W / version / kind / (kind + '_source.blend')))
        sc = bpy.context.scene
        for ob in sc.objects:
            if ob.name.startswith('Studio ground'):
                ob.hide_render = True              # keep the backdrop clean in tilted views
        cam = sc.camera
        cam.data.type = 'ORTHO'
        cz, ortho = FRAME.get(kind, FRAME['default'])
        cam.data.ortho_scale = ortho
        sc.render.resolution_x = sc.render.resolution_y = 900
        sc.render.film_transparent = True
        sc.render.image_settings.color_mode = 'RGBA'
        sc.cycles.samples = 48
        for label, loc in views.items():
            cam.location = (loc[0], loc[1], loc[2] - 1.52 + cz)
            cam.rotation_euler = (Vector((0, 0, cz)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = str(dest / ('%s_%s.png' % (version, label)))
            bpy.ops.render.render(write_still=True)
        # neck close-up (front), same framing for both versions
        cam.data.ortho_scale = .42
        cam.location = (0, -4, 1.24)
        cam.rotation_euler = (Vector((0, 0, 1.24)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = str(dest / ('%s_neck.png' % version))
        bpy.ops.render.render(write_still=True)
        # full body (orthographic 2.3 m window centred at z 1.0) for proportion overlays
        cam.data.ortho_scale = 2.3
        sc.render.resolution_x = sc.render.resolution_y = 1000
        sc.cycles.samples = 24
        for label, loc in [('front', (0, -6, 1.0)), ('side', (6, 0, 1.0)), ('back', (0, 6, 1.0))]:
            cam.location = loc
            cam.rotation_euler = (Vector((0, 0, 1.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = str(dest / ('%s_body_%s.png' % (version, label)))
            bpy.ops.render.render(write_still=True)
        rig = next((o for o in sc.objects if o.type == 'ARMATURE'), None)
        act = bpy.data.actions.get(kind.title() + '_HairCheck')
        if version == 'v5' and rig is not None and act is not None:
            chains = {b.name: [list(rig.matrix_world @ b.head_local), list(rig.matrix_world @ b.tail_local)]
                      for b in rig.data.bones if b.name.startswith('hair_')}
            hz, ho = HAIR_FRAME.get(kind, FRAME['default'])
            (dest / 'hair_chains.json').write_text(json.dumps(dict(bones=chains, center=hz, ortho=ho, res=600)))
            rig.animation_data.action = act
            cam.data.ortho_scale = ho
            sc.render.resolution_x = sc.render.resolution_y = 600
            sc.cycles.samples = 24
            for fr in (1, 16, 31, 46):
                sc.frame_set(fr)
                for label, loc in (('front', (0, -4, hz)), ('side', (4, 0, hz)), ('back', (0, 4, hz))):
                    cam.location = loc
                    cam.rotation_euler = (Vector((0, 0, hz)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
                    sc.render.filepath = str(dest / ('hair_%s_%02d.png' % (label, fr)))
                    bpy.ops.render.render(write_still=True)
            rig.animation_data.action = None
            for pb in rig.pose.bones:
                pb.rotation_euler = (0, 0, 0)
            sc.frame_set(1)
        eyes = [o for o in sc.objects if o.type == 'MESH' and o.name.startswith('Eye white')]
        ez = sum(sum((o.matrix_world @ v.co).z for v in o.data.vertices) / len(o.data.vertices) for o in eyes) / len(eyes)
        sole = min((o.matrix_world @ v.co).z for o in sc.objects if o.type == 'MESH' and not o.name.startswith('Studio')
                   for v in o.data.vertices)
        marks[version] = dict(eye_z=ez, sole_z=sole)
    mpath.write_text(json.dumps(marks, indent=1))
print('COMPARE_RENDERS_DONE', KINDS)
