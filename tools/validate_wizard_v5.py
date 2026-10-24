"""V5 checks: FBX round trip, the facial rig on the rebuilt head and (Lightning,
Ice) the hair chains.
blender -b -P validate_wizard_v5.py -- wind
"""
import bpy, json, sys
from pathlib import Path
from mathutils import Vector
OUT = Path(__file__).resolve().parent / 'output/wizard-models/v5'
kind = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'wind'
folder = OUT / kind
report = {}

# 1) FBX round trip: one mesh, one rig, the build's bone count, <=4 normalised influences.
built = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
NB = built['bones']
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(folder / ('SK_' + kind.title() + '.fbx')))
rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(rigs) == 1 and len(meshes) == 1, (len(rigs), len(meshes))
rig, ob = rigs[0], meshes[0]
assert len(rig.data.bones) == NB, (len(rig.data.bones), NB)
pos = [ob.matrix_world @ v.co for v in ob.data.vertices]
height = max(p.z for p in pos) - min(p.z for p in pos)
assert 1.3 < height < 2.5, height
NM = len(ob.data.materials)
assert NM == built.get('game_material_slots', 1) and NM <= 2, NM
valid = set(rig.data.bones.keys())
bad = maxinf = 0
for v in ob.data.vertices:
    w = [g for g in v.groups if g.weight > 1e-6]
    maxinf = max(maxinf, len(w))
    bad += int(not w or abs(sum(g.weight for g in w) - 1) > .02)
    assert all(ob.vertex_groups[g.group].name in valid for g in w)
assert bad == 0 and maxinf <= 4, (bad, maxinf)
sk = ob.data.shape_keys
morphs = [k.name for k in sk.key_blocks[1:]] if sk else []
assert set(morphs) >= {'Blink', 'Blink_L', 'Blink_R', 'A', 'I', 'U', 'E', 'O'}, morphs      # morph targets survive the FBX
report['fbx'] = dict(bones=NB, height_m=round(height, 4), material_slots=NM, unweighted_or_invalid=bad,
                     max_influences=maxinf, vertices=len(ob.data.vertices), morph_targets=morphs)

# 2) Facial rig on the editable source: blink, gaze, mouth.
bpy.ops.wm.open_mainfile(filepath=str(folder / (kind + '_source.blend')))
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
face_bones = [b.name for b in rig.data.bones if b.name.startswith('face_')]
assert len(face_bones) == 13, face_bones            # round 7: no jaw / eyelid bones
rig.animation_data.action = bpy.data.actions[kind.title() + '_FaceCheck']


def morph(name, value):
    """Set a morph target on every part that has it (the FaceCheck morph
    keys are stored in actions, not assigned, so this is explicit)."""
    for o in scene.objects:
        if o.type == 'MESH' and o.data.shape_keys:
            kb = o.data.shape_keys.key_blocks.get(name)
            if kb is not None:
                kb.value = value


def verts(name, frame):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    o = bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = o.to_mesh()
    vs = [v.co.copy() for v in m.vertices]
    o.to_mesh_clear()
    return vs


# blink (morph Blink): the lid's edge, measured through the middle of the eye,
# comes down past the lower lid; the lash line follows; seen from the front,
# nothing of the eye shows any more (rays over the eye hit the lid or lashes)
e0 = verts('Eye white l', 1)
h0 = max(v.z for v in e0) - min(v.z for v in e0)
xc = sum(v.x for v in e0) / len(e0)
FACE = 'Face refined cheek and jaw'
LID = [i for i, d in enumerate(bpy.data.objects[FACE].data.attributes['eyelid'].data) if d.value == 1]   # round 10: lids joined into the face


def lid_verts(frame):
    vs = verts(FACE, frame)
    return [vs[i] for i in LID]


k0 = lid_verts(1)
l0 = verts('Upper lash line l', 1)
morph('Blink', 1.0)
k1, l1 = lid_verts(1), verts('Upper lash line l', 1)
dg = bpy.context.evaluated_depsgraph_get()
xs, zs = [v.x for v in e0], [v.z for v in e0]
eye_parts = ('Eye white', 'Iris', 'Eye catchlight')
rays = shown = 0
for a in range(1, 20):
    for b in range(1, 12):
        p = Vector((min(xs) + (max(xs) - min(xs)) * a / 20, -3.0, min(zs) + (max(zs) - min(zs)) * b / 12))
        ok, loc, nrm, idx, hit, mtx = scene.ray_cast(dg, p, Vector((0, 1, 0)))
        if ok:
            rays += 1
            shown += int(hit.name.startswith(eye_parts))
morph('Blink', 0.0)
mid = [i for i, v in enumerate(k0) if abs(v.x - xc) < .006]
cover = (min(k0[i].z for i in mid) - min(k1[i].z for i in mid)) / h0
assert cover > .9, cover
assert rays > 100 and shown == 0, (rays, shown)
lash_drop = (sum(v.z for v in l0) - sum(v.z for v in l1)) / len(l0)
assert lash_drop > .004, lash_drop
i0, i1 = verts('Iris l', 1), verts('Iris l', 40)
gaze = sum((b - a).length for a, b in zip(i0, i1)) / len(i0)
assert gaze > .006, gaze
m0 = verts('Sculpted smile opening', 1)
morph('A', 1.0)
m1 = verts('Sculpted smile opening', 1)
morph('A', 0.0)
mouth = max((b - a).length for a, b in zip(m0, m1))
assert mouth > .005, mouth
report['face'] = dict(face_bones=len(face_bones), blink_lid_cover=round(cover, 3), blink_eye_rays_showing=f'{shown}/{rays}',
                      lash_follows_blink_m=round(lash_drop, 4), gaze_m=round(gaze, 4), mouth_m=round(mouth, 4))

# 3) Hair chains (girls): every chain bone carries hair, HairCheck moves the tips.
chains = built.get('hair_chains') or {}
if chains:
    act = bpy.data.actions.get(kind.title() + '_HairCheck')
    assert act is not None
    hair_obs = [o for o in scene.objects if o.type == 'MESH' and 'hair' in o.name.lower() and 'under-volume' not in o.name]
    used = set()
    for o in hair_obs:
        names = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            for g in v.groups:
                if g.weight > .05:
                    used.add(names[g.group])
    chain_bones = [b.name for b in rig.data.bones if b.name.startswith('hair_') and b.name[:-3] in chains]
    unused = [b for b in chain_bones if b not in used]
    assert not unused, unused
    rig.animation_data.action = act
    moved = 0.0
    for o in hair_obs:
        a, b = verts(o.name, 1), verts(o.name, 16)
        moved = max(moved, max((q - p).length for p, q in zip(a, b)))
    assert moved > .01, moved
    report['hair'] = dict(chains=chains, chain_bones=len(chain_bones), max_tip_move_m=round(moved, 4))
    rig.animation_data.action = bpy.data.actions[kind.title() + '_FaceCheck']

# 4) Accessory chains (round 9): straps, cords and sash ends hang on their own
#    chains acc_<name>_NN; every chain bone carries geometry, HairCheck swings it.
acc = built.get('accessory_chains') or {}
if acc:
    act = bpy.data.actions.get(kind.title() + '_HairCheck')
    assert act is not None
    used, acc_obs = set(), []
    for o in scene.objects:
        if o.type != 'MESH':
            continue
        names = {g.index: g.name for g in o.vertex_groups}
        hit = False
        for v in o.data.vertices:
            for g in v.groups:
                if g.weight > .05 and names[g.group].startswith('acc_'):
                    used.add(names[g.group])
                    hit = True
        if hit:
            acc_obs.append(o)
    acc_bones = [b.name for b in rig.data.bones if b.name.startswith('acc_')]
    unused = [b for b in acc_bones if b not in used]
    assert acc_bones and not unused, unused
    rig.animation_data.action = act
    moved = 0.0
    for o in acc_obs:
        a, b = verts(o.name, 1), verts(o.name, 16)
        moved = max(moved, max((q - p).length for p, q in zip(a, b)))
    assert moved > .01, moved
    report['accessories'] = dict(chains=acc, chain_bones=len(acc_bones), parts=len(acc_obs), max_tip_move_m=round(moved, 4))
    rig.animation_data.action = bpy.data.actions[kind.title() + '_FaceCheck']

cam = scene.camera
cam.location = (0, -4, 1.40)
cam.rotation_euler = (Vector((0, 0, 1.43)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.ortho_scale = .54
scene.render.resolution_x = scene.render.resolution_y = 600
scene.cycles.samples = 24
for label, frame, mt in [('Neutral', 1, None), ('Blink', 14, 'Blink'), ('Look', 40, None), ('Smile', 70, 'A')]:
    scene.frame_set(frame)
    if mt:
        morph(mt, 1.0)
    scene.render.filepath = str(folder / ('face_' + label + '.png'))
    bpy.ops.render.render(write_still=True)
    if mt:
        morph(mt, 0.0)
rig.animation_data.action = None
(folder / 'V5_VALIDATION.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('V5_VALIDATION_PASSED', json.dumps(report))
