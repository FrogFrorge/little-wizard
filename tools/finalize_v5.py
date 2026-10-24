"""Put each 3D turnaround (3d-v2) into its <kind>_source.blend as scale-matched overlays.
blender -b -P finalize_v5.py [-- wind fire ...]
Toggle the collection 'Approved reference (overlay)'; in Front ortho (Numpad 1)
or Right ortho (Numpad 3) the drawing lines up with the model: scaled so the
sole-to-eye height matches, soles on the ground, centred on the face / nose.
"""
import bpy, math, sys
from pathlib import Path
from mathutils import Vector
R = Path(__file__).resolve().parent
O = R / 'output/wizard-models/v5'
# 3d-v2 turnaround landmarks (sheet pixels): eye line, sole, front face centre, side nose tip
REF = {'wind': (214.0, 916.0, 307.5, 694.0), 'fire': (210.0, 905.0, 272.0, 697.0),
       'lightning': (209.0, 916.0, 282.0, 679.0), 'ice': (259.0, 915.0, 272.5, 651.0)}
KINDS = list(REF)
if '--' in sys.argv:
    KINDS = [k for k in sys.argv[sys.argv.index('--') + 1:] if k in REF] or KINDS
W_PX, H_PX = 1536, 1024
for kind in KINDS:
    EYE_Y, SOLE_Y, CX, NOSE_X = REF[kind]
    bpy.ops.wm.open_mainfile(filepath=str(O / kind / (kind + '_source.blend')))
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == 'MESH' and not o.name.startswith('Studio')]
    eyes = [o for o in meshes if o.name.startswith('Eye white')]
    eye_z = sum(sum((o.matrix_world @ v.co).z for v in o.data.vertices) / len(o.data.vertices) for o in eyes) / len(eyes)
    sole_z = min((o.matrix_world @ v.co).z for o in meshes for v in o.data.vertices)
    face = next(o for o in meshes if o.name.startswith('Face refined'))
    nose_y = min((face.matrix_world @ v.co).y for v in face.data.vertices if abs((face.matrix_world @ v.co).x) < .01)
    k = (SOLE_Y - EYE_Y) / (eye_z - sole_z)               # sheet px per metre
    zc = eye_z - (H_PX / 2 - EYE_Y) / k                   # world z of the sheet's centre row
    old = bpy.data.collections.get('Approved reference (overlay)')
    if old:
        bpy.data.collections.remove(old)
    refs = bpy.data.collections.new('Approved reference (overlay)')
    sc.collection.children.link(refs)
    refs.hide_render = True
    im = bpy.data.images.load(str(R / 'output/character-turnarounds/3d-v2' / (kind + '-3d-turnaround.png')))
    im.pack()
    for name, loc, rot in [
            ('Reference overlay - front (Numpad 1)', ((W_PX / 2 - CX) / k, -.60, zc), (math.pi / 2, 0, 0)),
            ('Reference overlay - side (Numpad 3)', (.60, nose_y + (W_PX / 2 - NOSE_X) / k, zc), (math.pi / 2, 0, math.pi / 2))]:
        ob = bpy.data.objects.new(name, None)
        refs.objects.link(ob)
        ob.empty_display_type = 'IMAGE'
        ob.data = im
        ob.empty_display_size = W_PX / k
        ob.location = loc
        ob.rotation_euler = rot
        ob.use_empty_image_alpha = True
        ob.color[3] = .5
    refs.hide_viewport = True
    cam = sc.camera
    cz = 1.46 if kind != 'ice' else 1.56
    cam.location = (.12, -4, cz)
    cam.rotation_euler = (Vector((0, 0, cz)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = .64 if kind != 'ice' else .92
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                sp = area.spaces.active
                sp.region_3d.view_distance = 1.0
                sp.region_3d.view_location = (0, 0, cz)
                sp.region_3d.view_rotation = cam.rotation_euler.to_quaternion()
                sp.shading.type = 'MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(O / kind / (kind + '_source.blend')))
    print('REFERENCE_READY', kind, 'px_per_m=%.1f' % k)
