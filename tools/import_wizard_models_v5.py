"""Little Wizards V5 in the game (round 10).

1. Import the four V5 models into /Game/Characters/LittleWizardsV5/<Kind>
   (own skeleton each, materials from the baked textures, extra LODs).
2. One Animation Blueprint per wizard (ABP_<Kind>V5).  Every frame, after the
   game's Quinn mesh -- still driven by ABP_Unarmed and every wizard action --
   has been animated, it
   - copies Quinn's pose onto the wizard skeleton: component-space rotations
     with fixed per-bone offsets computed here from the two reference poses
     (bone directions aligned), pelvis height scaled;
   - plants the feet with two-bone IK (targets follow Quinn's feet, stride
     a little longer than plain scaling, so they slide less);
   - simulates the hair chains and the straps / cords / sash ends
     (AnimDynamics, spring back to the styled shape);
   - blinks now and then and opens the mouth a little during casts
     (morph targets Blink and A).
3. BP_WizardCharacter: Quinn keeps animating but is no longer drawn; the
   wizard (WizardMeshV5, attached to Quinn) follows it; ApplyWizardAppearance
   switches the mesh and the anim blueprint by WizardType; the spell point
   (FirePoint) sits at the wizards' hand height.

UnrealEditor-Cmd <Little_Wizard.uproject> -run=pythonscript -script=import_wizard_models_v5.py
"""
import unreal as u
import json
import math
import re
import shutil
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/wizard-models/v5'
BASE = '/Game/Characters/LittleWizardsV5'
KINDS = ['fire', 'ice', 'wind', 'lightning']          # WizardType 0..3 (ApplyWizardAppearance order)
CH = '/Game/ThirdPerson/Blueprints/BP_WizardCharacter'
QUINN = '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
OLD_RETARGET = BASE + '/BP_WizardRetargetV5'           # round 9 (pose copy without anim blueprint)
REPORT = OUT / 'unreal-import-v5.json'
# reruns: kinds listed in this file are not imported again
SKIP_IMPORT = set((OUT / 'unreal-import-v5.skip').read_text().split()) if (OUT / 'unreal-import-v5.skip').exists() else set()
LODS = 3                    # LOD 0 + two reduced ones: see set_lods()
FIREPOINT_Z = 28.0          # spell point above the capsule centre: the wizards' hand height (Quinn's was 50)
# test switches (output/wizard-models/v5/unreal-abp-options.json), e.g. {"physics": false, "ik": false}
OPTIONS = json.loads((OUT / 'unreal-abp-options.json').read_text()) if (OUT / 'unreal-abp-options.json').exists() else {}
L = u.BlueprintEditorLibrary
E = u.BlueprintGraphEditor
EAL = u.EditorAssetLibrary
at = u.AssetToolsHelpers.get_asset_tools()
report = {'steps': []}


def log(msg):
    u.log('WIZV5 ' + str(msg))
    report['steps'].append(str(msg))
    REPORT.write_text(json.dumps(report, indent=1, default=str), encoding='utf-8')


# ------------------------------------------------------------------ import
def imp(file, dest, opts=None, name=None):
    t = u.AssetImportTask()
    t.set_editor_properties(dict(filename=str(file), destination_path=dest, destination_name=name or file.stem,
                                 automated=True, replace_existing=True, save=True))
    if opts:
        t.set_editor_property('options', opts)
        t.set_editor_property('factory', u.FbxFactory())
    at.import_asset_tasks([t])
    return list(t.get_editor_property('imported_object_paths'))


def texture(path, srgb=True):
    t = u.load_asset(path)
    if not srgb:
        t.set_editor_property('srgb', False)
        t.set_editor_property('compression_settings', u.TextureCompressionSettings.TC_MASKS)
    EAL.save_loaded_asset(t, False)          # (unsaved, the material sampled it as colour and failed)
    return t


# round 10: star colour of the small prints (wizard_fabric_v5.FABRIC_PRINT)
PRINT_COLOUR = {'fire': (.86, .60, .20), 'ice': (.56, .54, .84), 'wind': (.82, .62, .24), 'lightning': (.95, .76, .30)}


def material(name, dest, base, orm=None, masked=False, detail=None, print_colour=(1, 1, 1)):
    """Atlas material.  detail = (T_Detail, T_DetailN): fabric weave, small
    prints and fine wrinkles through UV1, where the vertex colour says so
    (R cloth, G print) -- see wizard_fabric_v5."""
    path = dest + '/' + name
    m = u.load_asset(path) if EAL.does_asset_exist(path) else at.create_asset(name, dest, u.Material, u.MaterialFactoryNew())
    mel = u.MaterialEditingLibrary
    mel.delete_all_material_expressions(m)
    a = mel.create_material_expression(m, u.MaterialExpressionTextureSample, -500, -100)
    a.set_editor_property('texture', base)
    if detail:
        def ex(cls, x, y, **props):
            e = mel.create_material_expression(m, cls, x, y)
            for k, v in props.items():
                e.set_editor_property(k, v)
            return e

        def wire(e1, out, e2, inp):
            assert mel.connect_material_expressions(e1, out, e2, inp), (name, out, inp)
        uv1 = ex(u.MaterialExpressionTextureCoordinate, -1400, 500, coordinate_index=1)
        d = ex(u.MaterialExpressionTextureSample, -1100, 400, texture=detail[0],
               sampler_type=u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        nmap = ex(u.MaterialExpressionTextureSample, -1100, 800, texture=detail[1],
                  sampler_type=u.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        wire(uv1, '', d, 'UVs')
        wire(uv1, '', nmap, 'UVs')
        vc = ex(u.MaterialExpressionVertexColor, -1100, 1100)
        # tone: 1 + ((weave - .5) * .16 + (mottle - .5) * .14) * cloth
        w0 = ex(u.MaterialExpressionSubtract, -800, 350, const_b=.5)
        wire(d, 'R', w0, 'A')
        w1 = ex(u.MaterialExpressionMultiply, -650, 350, const_b=.16)
        wire(w0, '', w1, 'A')
        m0 = ex(u.MaterialExpressionSubtract, -800, 470, const_b=.5)
        wire(d, 'A', m0, 'A')
        m1 = ex(u.MaterialExpressionMultiply, -650, 470, const_b=.14)
        wire(m0, '', m1, 'A')
        t0 = ex(u.MaterialExpressionAdd, -500, 400)
        wire(w1, '', t0, 'A')
        wire(m1, '', t0, 'B')
        t1 = ex(u.MaterialExpressionMultiply, -350, 400)
        wire(t0, '', t1, 'A')
        wire(vc, 'R', t1, 'B')
        t2 = ex(u.MaterialExpressionAdd, -200, 400, const_a=1.0)
        wire(t1, '', t2, 'B')
        c1 = ex(u.MaterialExpressionMultiply, -50, 0)
        wire(a, 'RGB', c1, 'A')
        wire(t2, '', c1, 'B')
        # small prints: star mask x print amount, in the print colour
        st = ex(u.MaterialExpressionMultiply, -350, 600)
        wire(d, 'G', st, 'A')
        wire(vc, 'G', st, 'B')
        pc = ex(u.MaterialExpressionConstant3Vector, -200, 650, constant=u.LinearColor(*print_colour, 1.0))
        bc = ex(u.MaterialExpressionLinearInterpolate, 150, 100)
        wire(c1, '', bc, 'A')
        wire(pc, '', bc, 'B')
        wire(st, '', bc, 'Alpha')
        mel.connect_material_property(bc, '', u.MaterialProperty.MP_BASE_COLOR)
        # normal: the detail normal on cloth only
        flat = ex(u.MaterialExpressionConstant3Vector, -800, 900, constant=u.LinearColor(0.0, 0.0, 1.0, 1.0))
        nb = ex(u.MaterialExpressionLinearInterpolate, -500, 850)
        wire(flat, '', nb, 'A')
        wire(nmap, 'RGB', nb, 'B')
        wire(vc, 'R', nb, 'Alpha')
        mel.connect_material_property(nb, '', u.MaterialProperty.MP_NORMAL)
    else:
        mel.connect_material_property(a, 'RGB', u.MaterialProperty.MP_BASE_COLOR)
    if orm:
        b = mel.create_material_expression(m, u.MaterialExpressionTextureSample, -500, 200)
        b.set_editor_property('texture', orm)
        b.set_editor_property('sampler_type', u.MaterialSamplerType.SAMPLERTYPE_MASKS)
        mel.connect_material_property(b, 'R', u.MaterialProperty.MP_AMBIENT_OCCLUSION)
        mel.connect_material_property(b, 'G', u.MaterialProperty.MP_ROUGHNESS)
        mel.connect_material_property(b, 'B', u.MaterialProperty.MP_METALLIC)
    if masked:
        m.set_editor_property('blend_mode', u.BlendMode.BLEND_MASKED)
        m.set_editor_property('opacity_mask_clip_value', .35)
        mel.connect_material_property(a, 'A', u.MaterialProperty.MP_OPACITY_MASK)
        r = mel.create_material_expression(m, u.MaterialExpressionConstant, -300, 300)
        r.set_editor_property('r', .55)
        mel.connect_material_property(r, '', u.MaterialProperty.MP_ROUGHNESS)
    m.set_editor_property('two_sided', True)
    usage(m)
    return m


def usage(m):
    """Skeletal mesh + morph target usage (without the second the game falls
    back to the default grey material on meshes with morph targets)."""
    mel = u.MaterialEditingLibrary
    for flag in (u.MaterialUsage.MATUSAGE_SKELETAL_MESH, u.MaterialUsage.MATUSAGE_MORPH_TARGETS):
        mel.set_material_usage(m, flag)
    mel.recompile_material(m)
    EAL.save_loaded_asset(m, False)


def set_lods(mesh):
    """LOD count (OPTIONS['lods'], default 3): LOD 1 and 2 are UE's automatic
    reductions, switching at its default screen sizes (1, 0.5, 0.25).  The
    reduced LODs keep every bone, so the physics bodies run on all of them."""
    n = int(OPTIONS.get('lods', LODS))
    try:
        ss = u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem)
        ok = ss.regenerate_lod(mesh, n, True, False)
        EAL.save_loaded_asset(mesh, False)
        return (ok, ss.get_lod_count(mesh))
    except Exception as e:
        return 'LOD change skipped: %s' % e


def import_models():
    u.SystemLibrary.execute_console_command(None, 'Interchange.FeatureFlags.Import.FBX 0')
    meshes = {}
    for kind in KINDS:
        title = kind.title()
        folder = OUT / kind
        dest = BASE + '/' + title
        if kind in SKIP_IMPORT and EAL.does_asset_exist(dest + '/SK_' + title):
            meshes[kind] = u.load_asset(dest + '/SK_' + title)
            for sm in meshes[kind].get_editor_property('materials'):
                mi = sm.get_editor_property('material_interface')
                if isinstance(mi, u.Material):
                    usage(mi)
            set_lods(meshes[kind])
            continue
        opts = u.FbxImportUI()
        opts.set_editor_properties(dict(automated_import_should_detect_type=False, import_mesh=True, import_as_skeletal=True,
                                        import_animations=False, import_materials=False, import_textures=False,
                                        create_physics_asset=False, mesh_type_to_import=u.FBXImportType.FBXIT_SKELETAL_MESH))
        # front stays +Y like the Quinn mesh it follows (no forced front X)
        opts.skeletal_mesh_import_data.set_editor_properties(dict(import_uniform_scale=1.0, convert_scene=True,
                                                                  convert_scene_unit=True, force_front_x_axis=False,
                                                                  update_skeleton_reference_pose=False,
                                                                  use_t0_as_ref_pose=False, import_morph_targets=True,
                                                                  # round 10: the fabric masks ride in the vertex colours
                                                                  vertex_color_import_option=u.VertexColorImportOption.REPLACE))
        imp(folder / ('SK_' + title + '.fbx'), dest, opts)
        mesh = u.load_asset(dest + '/SK_' + title)
        assert mesh, kind
        tex = {s: imp(folder / 'Textures' / ('T_%s_%s.png' % (title, s)), dest + '/Textures') and
               u.load_asset(dest + '/Textures/T_%s_%s' % (title, s)) for s in ['BaseColor', 'ORM']}
        tex['ORM'] = texture(tex['ORM'].get_path_name(), srgb=False)
        detail = None
        if (folder / 'Textures' / ('T_%s_Detail.png' % title)).exists():
            for sfx in ('Detail', 'DetailN'):
                imp(folder / 'Textures' / ('T_%s_%s.png' % (title, sfx)), dest + '/Textures')
            dt = u.load_asset(dest + '/Textures/T_%s_Detail' % title)
            dt.set_editor_property('srgb', False)
            EAL.save_loaded_asset(dt, False)
            dn = u.load_asset(dest + '/Textures/T_%s_DetailN' % title)
            dn.set_editor_property('srgb', False)
            dn.set_editor_property('compression_settings', u.TextureCompressionSettings.TC_NORMALMAP)
            dn.set_editor_property('flip_green_channel', True)        # Blender writes OpenGL normals
            EAL.save_loaded_asset(dn, False)
            detail = (dt, dn)
        mats = {'atlas': material('M_' + title, dest, tex['BaseColor'], tex['ORM'], detail=detail,
                                  print_colour=PRINT_COLOUR.get(kind, (1, 1, 1)))}
        hair_png = folder / 'Textures' / ('T_%s_HairStrands.png' % title)
        if hair_png.exists():
            imp(hair_png, dest + '/Textures')
            mats['hair'] = material('M_%s_Hair' % title, dest, u.load_asset(dest + '/Textures/T_%s_HairStrands' % title),
                                    masked=True)
        slots = list(mesh.get_editor_property('materials'))
        names = []
        for sl in slots:
            nm = str(sl.get_editor_property('material_slot_name'))
            names.append(nm)
            sl.set_editor_property('material_interface', mats['hair'] if ('hair' in nm.lower() and 'hair' in mats) else mats['atlas'])
        mesh.set_editor_property('materials', slots)
        lods = set_lods(mesh)
        b = mesh.get_bounds()
        EAL.save_loaded_asset(mesh, False)
        sk = mesh.get_editor_property('skeleton')
        EAL.save_loaded_asset(sk, False)
        meshes[kind] = mesh
        report.setdefault('meshes', {})[kind] = dict(mesh=mesh.get_path_name(), skeleton=sk.get_path_name(), slots=names,
                                                    materials=sorted(mats), lods=lods,
                                                    height_cm=round(b.box_extent.z * 2, 1))
        log('imported %s' % kind)
    return meshes


# ------------------------------------------------------- retarget offsets
# target bone <- source bone, parents before children
MAP = [('pelvis', 'pelvis'), ('spine_01', 'spine_01'), ('spine_02', 'spine_03'), ('spine_03', 'spine_05'),
       ('neck_01', 'neck_01'), ('head', 'head')]
for s in ('l', 'r'):
    MAP += [('clavicle_' + s, 'clavicle_' + s), ('upperarm_' + s, 'upperarm_' + s), ('lowerarm_' + s, 'lowerarm_' + s),
            ('hand_' + s, 'hand_' + s)]
    for f in ('index', 'middle', 'ring', 'pinky', 'thumb'):
        MAP += [('%s_01_%s' % (f, s), '%s_01_%s' % (f, s)), ('%s_02_%s' % (f, s), '%s_02_%s' % (f, s))]
for s in ('l', 'r'):
    MAP += [('thigh_' + s, 'thigh_' + s), ('calf_' + s, 'calf_' + s), ('foot_' + s, 'foot_' + s), ('ball_' + s, 'ball_' + s)]
# the bone each one points at (for aligning the two reference poses); None: keep the parent's alignment
AIM = {'pelvis': 'spine_01', 'spine_01': 'spine_02', 'spine_02': 'spine_03', 'spine_03': 'neck_01', 'neck_01': 'head'}
for s in ('l', 'r'):
    AIM.update({'clavicle_' + s: 'upperarm_' + s, 'upperarm_' + s: 'lowerarm_' + s, 'lowerarm_' + s: 'hand_' + s,
                'hand_' + s: 'middle_01_' + s, 'thigh_' + s: 'calf_' + s, 'calf_' + s: 'foot_' + s, 'foot_' + s: 'ball_' + s})
    for f in ('index', 'middle', 'ring', 'pinky', 'thumb'):
        AIM['%s_01_%s' % (f, s)] = '%s_02_%s' % (f, s)
PARENT = {}
for s in ('l', 'r'):
    PARENT.update({'head': 'neck_01', 'ball_' + s: 'foot_' + s})
    for f in ('index', 'middle', 'ring', 'pinky', 'thumb'):
        PARENT['%s_02_%s' % (f, s)] = '%s_01_%s' % (f, s)
SRC_OF = dict(MAP)
FEET = ('foot_l', 'ball_l', 'foot_r', 'ball_r')     # re-applied after the leg IK


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def qinv(a):
    return (-a[0], -a[1], -a[2], a[3])


def qrot(q, v):
    """Rotate vector v by unit quaternion q."""
    r = qmul(qmul(q, (v[0], v[1], v[2], 0.0)), qinv(q))
    return (r[0], r[1], r[2])


def qbetween(v0, v1):
    """Shortest rotation taking direction v0 onto v1."""
    def norm(v):
        n = math.sqrt(sum(c * c for c in v)) or 1.0
        return [c / n for c in v]
    a, b = norm(v0), norm(v1)
    d = sum(x * y for x, y in zip(a, b))
    if d < -.9999:
        return (1.0, 0.0, 0.0, 0.0) if abs(a[0]) < .9 else (0.0, 1.0, 0.0, 0.0)
    c = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    q = (c[0], c[1], c[2], 1.0 + d)
    n = math.sqrt(sum(x * x for x in q))
    return tuple(x / n for x in q)


def ref_pose(mesh):
    """Component-space reference transforms of every bone of a mesh (spawned
    in the editor world, nothing animating it) and the parent of each bone."""
    eas = u.get_editor_subsystem(u.EditorActorSubsystem)
    act = eas.spawn_actor_from_class(u.SkeletalMeshActor, u.Vector(0, 0, -5000))
    comp = act.skeletal_mesh_component
    comp.set_skeletal_mesh_asset(mesh)
    out, parents = {}, {}
    for i in range(comp.get_num_bones()):
        b = str(comp.get_bone_name(i))
        t = comp.get_socket_transform(b, u.RelativeTransformSpace.RTS_COMPONENT)
        r = t.rotation
        out[b] = ((t.translation.x, t.translation.y, t.translation.z), (r.x, r.y, r.z, r.w))
        parents[b] = str(comp.get_parent_bone(b))
    eas.destroy_actor(act)
    return out, parents


def offsets(src, tgt):
    """K per mapped bone: target = source * K (component space), with the
    target's reference bone direction aligned onto the source's."""
    A = {}
    K = []
    for tb, sb in MAP:
        if tb in AIM:
            tc = AIM[tb]
            sc = SRC_OF[tc]
            dt = [tgt[tc][0][i] - tgt[tb][0][i] for i in range(3)]
            ds = [src[sc][0][i] - src[sb][0][i] for i in range(3)]
            A[tb] = qbetween(dt, ds)
        else:
            A[tb] = A.get(PARENT.get(tb), (0.0, 0.0, 0.0, 1.0))
        k = qmul(qmul(qinv(src[sb][1]), A[tb]), tgt[tb][1])
        r = u.Quat(k[0], k[1], k[2], k[3]).rotator()
        d = qmul(src[sb][1], k)                    # the rotation with the source at rest
        rd = u.Quat(d[0], d[1], d[2], d[3]).rotator()
        K.append(((r.pitch, r.yaw, r.roll), (rd.pitch, rd.yaw, rd.roll)))
    return K


# ------------------------------------------------------------- physics chains
# One AnimDynamics node per bone, root to tip (each body hangs from its bone,
# which follows the simulated parent).  Not AnimDynamics' chain mode: there the
# springs of the lower bodies pull toward fixed directions in component space
# and the twist between neighbours is held at zero -- bones whose rest
# orientations differ (curved straps) were wrenched round and blew up.
# Per style: swing frequency (Hz), damping ratio, gravity scale, swing limit
# (degrees).  The spring constant per bone follows from its length, so short
# and long bones swing alike; gravity stays low because the modelled shape
# already hangs (sag per bone is in the report).
CHAIN_STYLE = {
    # round 12: the hair was too floaty ("太飄逸、太活躍，不像真實的頭髮"): stiffer,
    # close to critically damped, small swings -- it sways a little and settles
    'long': (2.6, .70, .10, 12.0),          # ice's long hair
    'hair': (3.4, .70, .06, 8.0),           # short / styled hair
    'bang': (4.2, .75, .04, 5.0),           # fringe
    'acc': (1.2, .30, .55, 35.0),           # straps, cords, sash ends: they dangle
    # round 12: the clothes had no life -- the coat / robe / waist-cloth panels
    # (the cloth_* bones the garments were always weighted to) and the fire
    # boy's scarf tails swing now: heavy fabric, a slower swing that settles
    'cloth': (1.7, .45, .40, 24.0),
    'scarf': (1.4, .35, .50, 30.0),
}
# how much the body's own motion drives a chain: (linear acceleration scale,
# linear velocity scale, angular alpha) -- low for hair (it lags only a little)
MOTION = {'long': (.30, .05, .25), 'hair': (.25, .04, .20), 'bang': (.20, .03, .20),
          'acc': (.50, .12, .40), 'cloth': (.60, .14, .45), 'scarf': (.55, .12, .40)}
CLOTH_KINDS = ('fire', 'ice', 'wind')       # the lightning girl's hoodie is not on the cloth bones


def chains_of(bones, kind=''):
    """hair_<group>_NN and acc_<name>_NN chains, root to tip; the coat panels
    cloth_<front|back>_NN_<side> (fire, ice, wind) and the scarf_NN tails (fire)."""
    out = {}
    for b in bones:
        m = re.match(r'^((?:hair|acc)_.+)_(\d\d)$', b)
        if m:
            out.setdefault(m.group(1), []).append((int(m.group(2)), b))
            continue
        m = re.match(r'^cloth_(front|back)_(\d\d)_([lr])$', b)
        if m and kind in CLOTH_KINDS:
            out.setdefault('cloth_%s_%s' % (m.group(1), m.group(3)), []).append((int(m.group(2)), b))
            continue
        m = re.match(r'^scarf_(\d\d)$', b)
        if m and kind == 'fire':
            out.setdefault('scarf', []).append((int(m.group(1)), b))
    return {k: [b for _, b in sorted(v)] for k, v in out.items() if len(v) >= 2}


def chain_style(kind, name):
    if name.startswith('cloth_'):
        return 'cloth'
    if name == 'scarf':
        return 'scarf'
    if name.startswith('acc_'):
        return 'acc'
    if 'bang' in name:
        return 'bang'
    return 'long' if kind == 'ice' else 'hair'


def collision_spheres(style, members, pose, parents):
    """(driving bone, centre in component space, largest radius) for the
    spheres a chain's bodies stay outside of: the long hair round the skull
    and the chest; straps round the thigh they hang from; cords and sash ends
    round the hips and between the knees (so they swing along the clothes,
    not into the legs)."""
    def mid(a, b, t=.5):
        return [a[k] + (b[k] - a[k]) * t for k in range(3)]
    if style == 'long' and 'head' in pose and 'spine_03' in pose:
        return [('head', [pose['head'][0][k] + (0.0, 1.5, 9.0)[k] for k in range(3)], 12.0),
                ('spine_03', [pose['spine_03'][0][k] + (0.0, 2.0, 2.0)[k] for k in range(3)], 13.0)]
    if style == 'cloth':
        # the panel stays outside its own thigh (upper and lower thigh), so the
        # leg pushes the coat instead of poking through it when running
        sd = members[0][-1]
        th, ca = 'thigh_' + sd, 'calf_' + sd
        if th in pose and ca in pose:
            return [(th, mid(pose[th][0], pose[ca][0], .30), 11.0), (th, mid(pose[th][0], pose[ca][0], .75), 10.0)]
        return []
    if style == 'scarf':
        # the tails stay in front of the chest and the belly
        return [(b, list(pose[b][0]), 14.0) for b in ('spine_03', 'spine_01', 'pelvis') if b in pose]
    if style == 'acc':
        par = parents.get(members[0], '')
        if par.startswith('thigh_') and 'calf_' + par[6:] in pose:
            return [(par, mid(pose[par][0], pose['calf_' + par[6:]][0]), 30.0)]
        if par == 'pelvis' and 'calf_l' in pose and 'calf_r' in pose:
            knees = mid(pose['calf_l'][0], pose['calf_r'][0])
            return [('pelvis', list(pose['pelvis'][0]), 30.0), ('pelvis', mid(pose['pelvis'][0], knees, .6), 30.0)]
    return []


def anim_dynamics_nodes(kind, name, members, pose, parents=None):
    """Texts for FAnimNode_AnimDynamics, one node per bone of the chain (root
    first): a box from the bone toward the next one (the joint at the bone),
    swing limits and an angular spring around the bone's animated rest
    orientation, the twist held.  Returns [(bone, text, info)]."""
    style = chain_style(kind, name)
    hz, zeta, gravity, swing = CHAIN_STYLE[style]
    ov = OPTIONS.get('override', {}).get(name, {})          # test switches per chain
    gravity, swing = ov.get('gravity', gravity), ov.get('swing', swing)
    # solver passes: UE's default for hair; one each for the hanging
    # accessories -- with gravity on them, more passes made the long hanging
    # bodies overshoot and blow up (round 10 tests: 12/6 diverged, 1/1 held)
    iters = ov.get('iters', (1, 1) if style in ('acc', 'cloth', 'scarf') else (4, 1))
    acc_s, vel_s, ang_a = MOTION[style]
    w = 2 * math.pi * hz
    damp = 1 - math.exp(-2 * zeta * w)                 # AnimPhys keeps (1 - damping)^dt of the momentum
    out = []
    last_len = None
    for i, b in enumerate(members):
        if i + 1 < len(members):                       # toward the next bone
            d = [pose[members[i + 1]][0][k] - pose[b][0][k] for k in range(3)]
            ln = math.sqrt(sum(x * x for x in d))
        else:                                          # the tip: on along the last bone
            d = [pose[b][0][k] - pose[members[i - 1]][0][k] for k in range(3)]
            ln = (last_len or 6.0) * .8
        n = math.sqrt(sum(x * x for x in d)) or 1.0
        ln = max(ln, 1.0)
        last_len = ln
        loc = [x / n for x in qrot(qinv(pose[b][1]), d)]          # bone space
        axis = max(range(3), key=lambda k: abs(loc[k]))
        # a stout box: a long thin one spins fast about its own axis (tiny
        # inertia there) and the long hanging cords tumbled
        ext = [max(2.5, ln * .40)] * 3
        ext[axis] = max(2.5, ln * .60)
        r = ln * .5
        joint = [loc[k] * r for k in range(3)]                    # UE: body = bone + offset (joint at the bone)
        inertia = (ext[(axis + 1) % 3] ** 2 + ext[axis] ** 2) / 12 + r * r
        spring = w * w * inertia * ov.get('k_scale', 1.0)
        lim = [swing, swing, swing]
        lim[axis] = 0.0                                           # (the twist is held anyway)
        target = ['0.0', '0.0', '0.0']
        target[axis] = '1.0'                                      # spring: the box axis back to the bone's own axis
        # collision spheres, each no bigger than this body's own rest distance
        # minus 1 cm (a sphere reaching past the rest pose kept pushing the
        # hair out: it never settled)
        sph = ''
        com = [pose[b][0][k] + d[k] / n * r for k in range(3)]
        lims = []
        for drv, c, rmax in collision_spheres(style, members, pose, parents or {}):
            rad = min(rmax, math.dist(com, c) - 1.0)
            if rad > 3.0:
                lo = qrot(qinv(pose[drv][1]), [c[k] - pose[drv][0][k] for k in range(3)])
                lims.append('(DrivingBone=(BoneName="%s"),SphereLocalOffset=(X=%.2f,Y=%.2f,Z=%.2f),LimitRadius=%.2f,LimitType=Outer)'
                            % ((drv,) + tuple(lo) + (rad,)))
        if lims:
            sph = ',bUseSphericalLimits=True,SphericalLimits=(%s)' % ','.join(lims)
        body = ('(BoundBone=(BoneName="%s"),BoxExtents=(X=%.3f,Y=%.3f,Z=%.3f),LocalJointOffset=(X=%.3f,Y=%.3f,Z=%.3f),'
                'ConstraintSetup=(LinearXLimitType=Limited,LinearYLimitType=Limited,LinearZLimitType=Limited,'
                'AngularConstraintType=Angular,TwistAxis=%s,AngularTargetAxis=%s,AngularTarget=(X=%s,Y=%s,Z=%s),'
                'AngularLimitsMin=(X=%.1f,Y=%.1f,Z=%.1f),AngularLimitsMax=(X=%.1f,Y=%.1f,Z=%.1f)),'
                'CollisionType=CoM,SphereCollisionRadius=2.0)'
                % (b, ext[0], ext[1], ext[2], joint[0], joint[1], joint[2], 'Axis' + 'XYZ'[axis], 'Axis' + 'XYZ'[axis],
                   target[0], target[1], target[2], -lim[0], -lim[1], -lim[2], lim[0], lim[1], lim[2]))
        txt = ('(BoundBone=(BoneName="%s"),ChainEnd=(BoneName="%s"),bChain=False,PhysicsBodyDefinitions=(%s),'
               'GravityScale=%.3f,bAngularSpring=%s,AngularSpringConstant=%.1f,bOverrideAngularDamping=True,'
               'AngularDampingOverride=%.6f,bOverrideLinearDamping=True,LinearDampingOverride=%.6f,'
               'ComponentLinearAccScale=(X=%.2f,Y=%.2f,Z=%.2f),ComponentLinearVelScale=(X=%.2f,Y=%.2f,Z=%.2f),'
               'ComponentAppliedLinearAccClamp=(X=800.0,Y=800.0,Z=800.0),'
               'SimSpaceSettings=(SimSpaceAngularAlpha=%.2f,MaxAngularVelocity=8.0,MaxAngularAcceleration=60.0),'
               'NumSolverIterationsPreUpdate=%d,NumSolverIterationsPostUpdate=%d,'
               'SimulationSpace=Component,bUsePlanarLimit=False,LODThreshold=-1%s%s)'
               % (b, b, body, gravity, 'False' if ov.get('spring_off') else 'True', spring, damp, damp,
                  *([ov.get('acc_scale', acc_s)] * 3), *([ov.get('vel_scale', vel_s)] * 3), ov.get('angular_alpha', ang_a),
                  iters[0], iters[1], sph, ov.get('extra', '')))
        sag = math.degrees(980 * gravity * r / spring)
        out.append((b, txt, dict(style=style, length=round(ln, 2), spring=round(spring, 1), sag_deg_if_level=round(sag, 1),
                                 spheres=len(lims))))
    return out


# --------------------------------------------------------- graph helpers
ASSETS = {}


def load(p):
    if p not in ASSETS:
        ASSETS[p] = u.load_asset(p)
    assert ASSETS[p], p
    return ASSETS[p]


def cls(p):
    return load(p).generated_class()


def cp(p):
    return cls(p).get_path_name()


def typ(n):
    return L.get_basic_type_by_name(n)


def pin(n, name, out=False):
    p = n.find_output_pin(name) if out else n.find_input_pin(name)
    assert p.is_valid(), (n.get_node_title(), name, [str(x.get_pin_name()) for x in n.list_all_pins()])
    return p


def link(a, b):
    assert a.is_valid() and b.is_valid()
    assert a.try_create_connection(b), (a.get_owning_node().get_node_title(), a.get_pin_name(),
                                        b.get_owning_node().get_node_title(), b.get_pin_name())


def value(p, v):
    if isinstance(v, u.BlueprintGraphPin):
        link(v, p)
    else:
        assert p.set_pin_value(str(v).lower() if isinstance(v, bool) else str(v)), (p.get_pin_name(), v)


def result(n):
    return n.find_result_pin()


def then(n):
    for p in n.list_output_pins():
        if str(p.get_pin_name()) in ['then', 'Completed']:
            return p
    return u.BlueprintGraphPin()


def ex(n):
    for p in n.list_input_pins():
        if str(p.get_pin_name()).lower() in ['execute', 'exec', 'in', 'do']:
            return p
    raise AssertionError(('No execute pin', n.get_node_title()))


def chain(start, *nodes):
    """start: an exec output pin, or a list of them (all lead into the first node)."""
    p = start
    for n in nodes:
        for q in (p if isinstance(p, list) else [p]):
            link(q, ex(n))
        p = then(n)
    return p


class Graph:
    def __init__(self, bp, name='EventGraph'):
        self.bp, self.name, self.i = bp, name, 0
        self.e = E.get_graph_editor_by_name(bp, name)
        assert self.e, name

    def place(self, n, x=None, y=None):
        assert n, (self.name, self.i)
        if x is None:
            x, y = (self.i % 10) * 340, (self.i // 10) * 260
        n.set_node_pos(u.IntPoint(int(x), int(y)))
        self.i += 1
        return n

    def call(me, path, **args):          # 'me': a 'self' pin can be passed as a keyword
        n = me.place(me.e.add_call_function_node(path))
        # links first: operator nodes only take a literal once their type is known
        for k, v in sorted(args.items(), key=lambda kv: 0 if isinstance(kv[1], u.BlueprintGraphPin) else 1):
            value(pin(n, k), v)
        return n

    def math(self, name, **args):
        return result(self.call('/Script/Engine.KismetMathLibrary.' + name, **args))

    def get(self, name, owner=''):
        n = self.place(self.e.add_get_member_variable_node(name, owner))
        return pin(n, name, True)

    def set(self, name, v):
        n = self.place(self.e.add_set_member_variable_node(name, ''))
        value(pin(n, name), v)
        return n

    def branch(self, cond):
        n = self.place(self.e.add_branch_node())
        value(n.find_condition_pin(), cond)
        return n

    def node(self, menu, x=None, y=None):
        return self.place(self.e.create_node_from_name(menu, u.Vector2D(0, 0), []), x, y)


def merge(g, pins):
    """Several exec outputs that all lead on to the next node (chain() links
    every pin of a list into it)."""
    return list(pins)


def compile_bp(bp, what=''):
    assert L.compile_blueprint(bp), 'Compile failed: ' + what


def fv(v):
    return '(X=%.4f,Y=%.4f,Z=%.4f)' % tuple(v)


# ------------------------------------------------------- the anim blueprints
def build_abp(kind, mesh, src, tgt, tgt_parents):
    """ABP_<Kind>V5 (see the module doc)."""
    title = kind.title()
    folder = BASE + '/' + title
    path = folder + '/ABP_%sV5' % title
    if EAL.does_asset_exist(path):
        # rebuild in place (a deleted asset's name stays taken in this session)
        abp = u.load_asset(path)
        eg0 = E.get_graph_editor_by_name(abp, 'EventGraph')
        eg0.remove_nodes([n for n in eg0.list_all_nodes() if n.get_class().get_name() != 'K2Node_Event'])
        ag0 = E.get_graph_editor_by_name(abp, 'AnimGraph')
        ag0.remove_nodes([n for n in ag0.list_all_nodes() if n.get_class().get_name() != 'AnimGraphNode_Root'])
        for v in [str(x) for x in L.list_member_variable_names(abp, False)]:
            eg0.remove_member_variable(v)
        compile_bp(abp, path)
    else:
        f = u.AnimBlueprintFactory()
        f.set_editor_property('target_skeleton', mesh.get_editor_property('skeleton'))
        f.set_editor_property('preview_skeletal_mesh', mesh)
        abp = at.create_asset('ABP_%sV5' % title, folder, u.AnimBlueprint, f)
    assert abp, path
    K = offsets(src, tgt)
    N = len(MAP)
    s = tgt['pelvis'][0][2] / src['pelvis'][0][2]
    VEC = L.get_struct_type(u.Vector.static_struct())
    ROT = L.get_struct_type(u.Rotator.static_struct())
    F = typ('real')
    eg = E.get_graph_editor_by_name(abp, 'EventGraph')
    var = []
    for i in range(N):
        # R starts as the rest pose (the first evaluation may come before the
        # first update; AnimDynamics initialises its bodies on it)
        var.append(('K%02d' % i, ROT, '(Pitch=%.6f,Yaw=%.6f,Roll=%.6f)' % K[i][0]))
        var.append(('R%02d' % i, ROT, '(Pitch=%.6f,Yaw=%.6f,Roll=%.6f)' % K[i][1]))
    # feet: the IK target follows Quinn's foot relative to its reference spot,
    # sideways x0.95, forward x0.85 (longer stride than plain scaling: less
    # sliding), up and down by the height ratio; knees aim forward
    fs = (.95, .85, s)
    var += [('SrcPelvisRef', VEC, fv(src['pelvis'][0])), ('TgtPelvisRef', VEC, fv(tgt['pelvis'][0])), ('PelvisScale', F, '%.6f' % s),
            ('FootScale', VEC, fv(fs)), ('KneeForward', VEC, fv((0.0, 25.0, 0.0))),
            ('PelvisLoc', VEC, fv(tgt['pelvis'][0])), ('BlinkT', F, '0.0'), ('BlinkNext', F, '2.5'), ('MouthW', F, '0.0'),
            ('Warm', typ('int'), '0')]
    # round 12: the head looks where the player aims (the crosshair).  LookFwd: the
    # face's forward in the head bone's own space (the wizards face +Y at rest)
    QUAT = L.get_struct_type(u.Quat.static_struct())
    look_fwd = qrot(qinv(tgt['head'][1]), (0.0, 1.0, 0.0))
    var += [('LookQ', QUAT, '(X=0.000000,Y=0.000000,Z=0.000000,W=1.000000)'), ('LookFwd', VEC, fv(look_fwd)),
            ('AimRot', ROT, '(Pitch=0.0,Yaw=0.0,Roll=0.0)')]
    for side in ('l', 'r'):
        var += [('QFoot0_' + side, VEC, fv(src['foot_' + side][0])), ('TFoot0_' + side, VEC, fv(tgt['foot_' + side][0])),
                ('QKnee0_' + side, VEC, fv(src['calf_' + side][0])), ('TKnee0_' + side, VEC, fv(tgt['calf_' + side][0])),
                ('Foot_' + side, VEC, fv(tgt['foot_' + side][0])), ('Knee_' + side, VEC, fv(tgt['calf_' + side][0]))]
    for name, t, d in var:
        assert eg.add_member_variable(name, t, d), name
    compile_bp(abp, path)

    # ---------------- EventGraph: pose copy, feet targets, blink, mouth
    g = Graph(abp, 'EventGraph')
    ev = next(n for n in g.e.list_all_nodes() if n.get_class().get_name() == 'K2Node_Event')
    g.place(ev, -600, 0)
    dt = pin(ev, 'DeltaTimeX', True)
    comp = result(g.call('/Script/Engine.AnimInstance.GetOwningComponent'))
    srcc = result(g.call('/Script/Engine.SceneComponent.GetAttachParent', self=comp))
    ok = g.branch(result(g.call('/Script/Engine.KismetSystemLibrary.IsValid', Object=srcc)))
    end = chain(then(ev), ok)

    def src_tf(bone):
        st = g.call('/Script/Engine.SceneComponent.GetSocketTransform', self=srcc, InSocketName=bone, TransformSpace='RTS_Component')
        return g.call('/Script/Engine.KismetMathLibrary.BreakTransform', InTransform=result(st))
    for i, (tb, sb) in enumerate(MAP):
        br = src_tf(sb)
        r = g.math('ComposeRotators', A=g.get('K%02d' % i), B=pin(br, 'Rotation', True))
        end = chain(end, g.set('R%02d' % i, r))
    # round 12: turn the head (and a third of it the neck) toward the aim direction
    # -- the crosshair for the player, the controller's facing for the dummies --
    # at most 50 degrees, smoothly (the copied pose had them looking at the floor)
    mi = {tb: i for i, (tb, sb) in enumerate(MAP)}
    if OPTIONS.get('look', True) and 'head' in mi and 'neck_01' in mi:
        ID = g.math('Conv_RotatorToQuaternion', InRot='0,0,0')        # the identity (quat pins take no literal)
        pawn = result(g.call('/Script/Engine.AnimInstance.TryGetPawnOwner'))
        has = g.branch(result(g.call('/Script/Engine.KismetSystemLibrary.IsValid', Object=pawn)))
        end = chain(end, has)
        # the aim: the controller's rotation where there is one (the player's crosshair --
        # the camera follows it -- or a dummy's facing); other machines' copies of a
        # player have no controller: their replicated aim (GetBaseAimRotation)
        ctrl = result(g.call('/Script/Engine.Pawn.GetController', self=pawn))
        hasc = g.branch(result(g.call('/Script/Engine.KismetSystemLibrary.IsValid', Object=ctrl)))
        link(pin(has, 'then', True), ex(hasc))
        a1 = g.set('AimRot', result(g.call('/Script/Engine.Controller.GetControlRotation', self=ctrl)))
        a2 = g.set('AimRot', result(g.call('/Script/Engine.Pawn.GetBaseAimRotation', self=pawn)))
        link(pin(hasc, 'then', True), ex(a1))
        link(pin(hasc, 'else', True), ex(a2))
        aim = g.math('GetForwardVector', InRot=g.get('AimRot'))
        cq = g.math('Conv_RotatorToQuaternion', InRot=result(g.call('/Script/Engine.SceneComponent.K2_GetComponentRotation', self=comp)))
        aim_cs = g.math('Normal', A=g.math('Quat_UnrotateVector', Q=cq, V=aim), Tolerance=0.0001)
        hq = g.math('Conv_RotatorToQuaternion', InRot=g.get('R%02d' % mi['head']))
        fwd = g.math('Normal', A=g.math('Quat_RotateVector', Q=hq, V=g.get('LookFwd')), Tolerance=0.0001)
        # an aim behind the wizard (over 90 degrees from the body's front, +Y here) eases
        # back to looking level ahead by 120 -- never the copied pose's look at the floor,
        # and never a turn so far that it goes round through the floor
        body = '0,1,0'          # a vector pin's literal (a tuple's str() does not parse)
        w = g.math('FClamp', Value=g.math('Divide_DoubleDouble', A=g.math('Add_DoubleDouble', A=g.math('Dot_VectorVector', A=aim_cs, B=body),
                                                                                              B=0.5), B=0.5), Min=0.0, Max=1.0)
        look_to = g.math('Normal', A=g.math('VLerp', A=body, B=aim_cs, Alpha=w), Tolerance=0.0001)
        dq = g.math('Quat_FindBetweenNormals', StartNormal=fwd, EndNormal=look_to)
        ang = g.math('Quat_GetAngle', Q=dq)
        # at most 50 degrees
        k = g.math('FMin', A=1.0, B=g.math('Divide_DoubleDouble', A=0.87, B=g.math('FMax', A=ang, B=0.001)))
        dqc = g.math('Quat_Slerp', A=ID, B=dq, Alpha=k)
        lq = g.set('LookQ', g.math('Quat_Slerp', A=g.get('LookQ'), B=dqc,
                                   Alpha=g.math('FMin', A=1.0, B=g.math('Multiply_DoubleDouble', A=dt, B=9.0))))
        sh = g.set('R%02d' % mi['head'], g.math('Quat_Rotator', Q=g.math('Multiply_QuatQuat', A=g.get('LookQ'), B=hq)))
        nq = g.math('Conv_RotatorToQuaternion', InRot=g.get('R%02d' % mi['neck_01']))
        sn = g.set('R%02d' % mi['neck_01'], g.math('Quat_Rotator', Q=g.math('Multiply_QuatQuat',
                                                                          A=g.math('Quat_Slerp', A=ID, B=g.get('LookQ'), Alpha=0.35), B=nq)))
        look_end = chain([then(a1), then(a2)], lq, sh, sn)
        end = merge(g, [pin(has, 'else', True), look_end])
    pl = pin(src_tf('pelvis'), 'Location', True)
    loc = g.math('Add_VectorVector', A=g.math('Multiply_VectorFloat', A=g.math('Subtract_VectorVector', A=pl, B=g.get('SrcPelvisRef')),
                                              B=g.get('PelvisScale')), B=g.get('TgtPelvisRef'))
    end = chain(end, g.set('PelvisLoc', loc))
    for side in ('l', 'r'):
        qf = pin(src_tf('foot_' + side), 'Location', True)
        ft = g.math('Add_VectorVector', A=g.math('Multiply_VectorVector', A=g.math('Subtract_VectorVector', A=qf, B=g.get('QFoot0_' + side)),
                                                 B=g.get('FootScale')), B=g.get('TFoot0_' + side))
        qk = pin(src_tf('calf_' + side), 'Location', True)
        kt = g.math('Add_VectorVector', A=g.math('Add_VectorVector', A=g.math('Multiply_VectorVector',
                                                                              A=g.math('Subtract_VectorVector', A=qk, B=g.get('QKnee0_' + side)),
                                                                              B=g.get('FootScale')), B=g.get('TKnee0_' + side)),
                    B=g.get('KneeForward'))
        end = chain(end, g.set('Foot_' + side, ft), g.set('Knee_' + side, kt))
    # blink: a quick close and open every 1.8 - 4.5 s
    t1 = g.set('BlinkT', g.math('Add_DoubleDouble', A=g.get('BlinkT'), B=dt))
    w = g.math('FClamp', Value=g.math('Subtract_DoubleDouble', A=1.0, B=g.math('Abs', A=g.math('Divide_DoubleDouble',
                                                                                         A=g.math('Subtract_DoubleDouble', A=g.get('BlinkT'), B=g.get('BlinkNext')),
                                                                                         B=.075))), Min=0.0, Max=1.0)
    mb = g.call('/Script/Engine.SkeletalMeshComponent.SetMorphTarget', self=comp, MorphTargetName='Blink', Value=w, bRemoveZeroWeight=False)
    over = g.branch(g.math('Greater_DoubleDouble', A=g.get('BlinkT'), B=g.math('Add_DoubleDouble', A=g.get('BlinkNext'), B=.1)))
    end = chain(end, t1, mb, over)
    reset_end = chain(then(over), g.set('BlinkT', 0.0), g.set('BlinkNext', g.math('RandomFloatInRange', Min=1.8, Max=4.5)))
    # mouth: a little open while Quinn plays a montage (casts, ultimates)
    cast = g.node('Utilities|Casting|CastToSkeletalMeshComponent')
    value(pin(cast, 'Object'), srcc)
    asmesh = next(p for p in cast.list_output_pins() if str(p.get_pin_name()).startswith('As'))
    inst = result(g.call('/Script/Engine.SkeletalMeshComponent.GetAnimInstance', self=asmesh))
    playing = result(g.call('/Script/Engine.AnimInstance.Montage_IsPlaying', self=inst))
    tgtw = g.math('SelectFloat', A=.45, B=0.0, bPickA=playing)
    mw = g.set('MouthW', g.math('FInterpTo', Current=g.get('MouthW'), Target=tgtw, DeltaTime=dt, InterpSpeed=10.0))
    ma = g.call('/Script/Engine.SkeletalMeshComponent.SetMorphTarget', self=comp, MorphTargetName='A', Value=g.get('MouthW'),
                bRemoveZeroWeight=False)
    link(pin(over, 'else', True), ex(cast))
    link(reset_end, ex(cast))
    tail = chain(then(cast), mw, ma)
    # the physics bodies start again from the copied pose on the first three
    # updates (a new wizard's first evaluation may still be the rest pose)
    warm = g.branch(g.math('Less_IntInt', A=g.get('Warm'), B=3))
    link(tail, ex(warm))
    chain(then(warm), g.set('Warm', g.math('Add_IntInt', A=g.get('Warm'), B=1)),
          g.call('/Script/Engine.SkeletalMeshComponent.ResetAnimInstanceDynamics', self=comp, InTeleportType='ResetPhysics'))

    # ---------------- AnimGraph: ref pose -> copied pose -> leg IK -> feet -> physics -> output
    ag = Graph(abp, 'AnimGraph')
    root = next(n for n in ag.e.list_all_nodes() if n.get_class().get_name() == 'AnimGraphNode_Root')
    x = 0
    ref = ag.node('Animation|Poses|LocalSpaceRefPose', x, 0)
    l2c = ag.node('Animation|ConvertSpaces|LocalToComponent', x + 300, 0)
    link(pin(ref, 'Pose', True), pin(l2c, 'LocalPose'))
    cur = pin(l2c, 'ComponentPose', True)
    x += 600

    def modify(bone, rvar, tvar=None):
        nonlocal cur, x
        n = ag.node('Animation|SkeletalControls|Transform(Modify)Bone', x, 0)
        st = n.get_editor_property('node')
        assert st.import_text('(BoneToModify=(BoneName="%s"),RotationMode=BMM_Replace,RotationSpace=BCS_ComponentSpace,'
                              'TranslationMode=%s,TranslationSpace=BCS_ComponentSpace)' % (bone, 'BMM_Replace' if tvar else 'BMM_Ignore'))
        n.set_editor_property('node', st)
        link(cur, pin(n, 'ComponentPose'))
        vn = ag.place(ag.e.add_get_member_variable_node(rvar, ''), x, 220)
        link(pin(vn, rvar, True), pin(n, 'Rotation'))
        if tvar:
            tn = ag.place(ag.e.add_get_member_variable_node(tvar, ''), x, 320)
            link(pin(tn, tvar, True), pin(n, 'Translation'))
        cur = pin(n, 'Pose', True)
        x += 300
    for i, (tb, sb) in enumerate(MAP):
        modify(tb, 'R%02d' % i, 'PelvisLoc' if tb == 'pelvis' else None)
    for side in (('l', 'r') if OPTIONS.get('ik', True) else ()):
        n = ag.node('Animation|SkeletalControls|TwoBoneIK', x, 0)
        st = n.get_editor_property('node')
        assert st.import_text('(IKBone=(BoneName="foot_%s"),EffectorLocationSpace=BCS_ComponentSpace,'
                              'JointTargetLocationSpace=BCS_ComponentSpace,bAllowStretching=False,bAllowTwist=True)' % side)
        n.set_editor_property('node', st)
        link(cur, pin(n, 'ComponentPose'))
        for p, v in (('EffectorLocation', 'Foot_' + side), ('JointTargetLocation', 'Knee_' + side)):
            vn = ag.place(ag.e.add_get_member_variable_node(v, ''), x, 220 if p == 'EffectorLocation' else 320)
            link(pin(vn, v, True), pin(n, p))
        cur = pin(n, 'Pose', True)
        x += 300
    idx = {tb: i for i, (tb, sb) in enumerate(MAP)}
    for b in FEET:
        modify(b, 'R%02d' % idx[b])
    chains = chains_of(list(tgt), kind) if OPTIONS.get('physics', True) else {}
    if OPTIONS.get('only_prefix'):
        chains = {k: v for k, v in chains.items() if k.startswith(OPTIONS['only_prefix'])}
    styles = {}
    nodes = 0
    for name, members in sorted(chains.items()):
        info = []
        for bone, txt, inf in anim_dynamics_nodes(kind, name, members, tgt, tgt_parents):
            n = ag.node('Animation|Dynamics|AnimDynamics', x, 0)
            st = n.get_editor_property('node')
            assert st.import_text(txt), (name, bone)
            n.set_editor_property('node', st)
            got = n.get_editor_property('node').export_text()
            assert bone in got and 'bChain=False' in got and 'AngularTarget=(X=' in got, (name, bone, got[:400])
            link(cur, pin(n, 'ComponentPose'))
            cur = pin(n, 'Pose', True)
            info.append(inf)
            nodes += 1
            x += 300
        styles[name] = info
    c2l = ag.node('Animation|ConvertSpaces|ComponentToLocal', x, 0)
    link(cur, pin(c2l, 'ComponentPose'))
    link(pin(c2l, 'Pose', True), pin(root, 'Result'))
    root.set_node_pos(u.IntPoint(x + 320, 0))
    compile_bp(abp, path)
    assert EAL.save_loaded_asset(abp, False)
    report.setdefault('anim_blueprints', {})[kind] = dict(path=abp.get_path_name(), bones=N, chains=styles, pelvis_scale=round(s, 4))
    log('anim blueprint %s: %d bones, %d physics chains (%d bodies)' % (kind, N, len(chains), nodes))
    return abp


# ------------------------------------------------------- the character
def wire_character(meshes, abps):
    project = Path(u.Paths.project_content_dir()).resolve()
    src = project / (CH.removeprefix('/Game/') + '.uasset')
    backup = ROOT / 'wizard-v5-before-assets'
    backup.mkdir(exist_ok=True)
    dest = backup / 'BP_WizardCharacter.uasset'
    if not dest.exists():
        shutil.copy2(src, dest)
    ch = load(CH)
    sub = u.get_engine_subsystem(u.SubobjectDataSubsystem)
    lib = u.SubobjectDataBlueprintFunctionLibrary

    def handles():
        hs = {}
        allh = sub.k2_gather_subobject_data_for_blueprint(ch)
        for h in allh:
            hs[str(lib.get_variable_name(sub.k2_find_subobject_data_from_handle(h)))] = h
        return hs, allh

    # 1. WizardMeshV5 under Quinn (the graph below needs its variable)
    hs, allh = handles()
    if 'WizardMeshV5' not in hs:
        params = u.AddNewSubobjectParams(parent_handle=hs['Mesh'], new_class=u.SkeletalMeshComponent, blueprint_context=ch)
        h, why = sub.add_new_subobject(params)
        assert lib.is_handle_valid(h), str(why)
        assert sub.rename_subobject(h, u.Text('WizardMeshV5'))
        hs['WizardMeshV5'] = h
    tmpl = lib.get_object(sub.k2_find_subobject_data_from_handle(hs['WizardMeshV5']))
    tmpl.set_editor_property('skeletal_mesh_asset', meshes['fire'])
    tmpl.set_editor_property('animation_mode', u.AnimationMode.ANIMATION_BLUEPRINT)
    tmpl.set_editor_property('anim_class', abps['fire'].generated_class())
    for prop, val in (('generate_overlap_events', False), ('can_ever_affect_navigation', False)):
        tmpl.set_editor_property(prop, val)
    tick = tmpl.get_editor_property('primary_component_tick')
    tick.set_editor_property('tick_group', u.TickingGroup.TG_POST_UPDATE_WORK)     # after Quinn is animated
    tmpl.set_editor_property('primary_component_tick', tick)
    tmpl.set_collision_profile_name('NoCollision')
    compile_bp(ch, CH)

    # 2. ApplyWizardAppearance: drop round 9's calls, switch mesh + anim blueprint per type
    g = Graph(ch, 'ApplyWizardAppearance')

    def inserted(node):
        """A call this script (or round 9) put into the branches."""
        if node.get_class().get_name() != 'K2Node_CallFunction':
            return False
        names = {str(p.get_pin_name()) for p in node.list_input_pins()}
        return bool(names & {'BodySource', 'NewClass'}) or ('NewMesh' in names and 'Material' not in names)
    done = []
    for n in list(g.e.list_all_nodes()):
        if n.get_class().get_name() != 'K2Node_IfThenElse':
            continue
        cond = n.find_condition_pin().list_connected_pins()
        eq = cond[0].get_owning_node() if cond else None
        if eq is None:
            continue
        bpin = eq.find_input_pin('B')
        kidx = int(float(str(bpin.get_pin_value()) or 0)) if bpin.is_valid() else 0
        tp = then(n)
        nxt = list(tp.list_connected_pins())
        # unwrap old inserted calls (round 9 ApplyWizardType, earlier runs of this step)
        while nxt and inserted(nxt[0].get_owning_node()):
            old = nxt[0].get_owning_node()
            after = list(then(old).list_connected_pins())
            feeders = [q.get_owning_node() for p in old.list_input_pins() for q in p.list_connected_pins()
                       if q.get_owning_node().get_class().get_name() == 'K2Node_VariableGet']
            g.e.remove_nodes([old] + feeders)
            nxt = after
        tp.break_pin_links()
        # the old wizard's anim blueprint must never run on the new wizard's
        # skeleton (its AnimDynamics chains would read bones that are not
        # there and assert): clear the class, then switch mesh, then class
        c0 = g.call('/Script/Engine.SkeletalMeshComponent.SetAnimInstanceClass', self=g.get('WizardMeshV5'))
        c1 = g.call('/Script/Engine.SkeletalMeshComponent.SetSkeletalMeshAsset', self=g.get('WizardMeshV5'),
                    NewMesh=meshes[KINDS[kidx]].get_path_name())
        c2 = g.call('/Script/Engine.SkeletalMeshComponent.SetAnimInstanceClass', self=g.get('WizardMeshV5'),
                    NewClass=abps[KINDS[kidx]].generated_class().get_path_name())
        pos = n.get_node_pos()
        c0.set_node_pos(u.IntPoint(pos.x + 300, pos.y + 260))
        c1.set_node_pos(u.IntPoint(pos.x + 620, pos.y + 260))
        c2.set_node_pos(u.IntPoint(pos.x + 940, pos.y + 260))
        link(tp, ex(c0))
        link(then(c0), ex(c1))
        link(then(c1), ex(c2))
        for q in nxt:
            link(then(c2), q)
        done.append(kidx)
    assert sorted(done) == [0, 1, 2, 3], done
    # leftovers of round 9 that were no longer in the chain
    stale = [n for n in g.e.list_all_nodes() if n.get_class().get_name() == 'K2Node_CallFunction'
             and 'BodySource' in {str(p.get_pin_name()) for p in n.list_input_pins()}]
    if stale:
        feeders = [q.get_owning_node() for n in stale for p in n.list_input_pins() for q in p.list_connected_pins()
                   if q.get_owning_node().get_class().get_name() == 'K2Node_VariableGet']
        g.e.remove_nodes(stale + feeders)
        log('removed %d stale round-9 calls' % len(stale))

    # round 9's body + retarget component go
    hs, allh = handles()
    for name in ('WizardBodyV5', 'WizardRetargetV5'):
        if name in hs:
            n = sub.delete_subobject(allh[0], hs[name], ch)
            log('removed component %s (%s)' % (name, n))
    hs, allh = handles()
    # 3. the spell point at the wizards' hand height
    fp = lib.get_object(sub.k2_find_subobject_data_from_handle(hs['FirePoint']))
    loc = fp.get_editor_property('relative_location')
    report['firepoint_before'] = [loc.x, loc.y, loc.z]
    fp.set_editor_property('relative_location', u.Vector(loc.x, loc.y, FIREPOINT_Z))
    compile_bp(ch, CH)
    # Quinn keeps animating every frame but is not drawn
    cdo = u.get_default_object(cls(CH))
    m = cdo.get_editor_property('mesh')
    for prop, val in (('visibility_based_anim_tick_option', u.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES),
                      ('render_in_main_pass', False), ('render_in_depth_pass', False), ('cast_shadow', False),
                      ('visible_in_ray_tracing', False), ('visible_in_reflection_captures', False)):
        m.set_editor_property(prop, val)
    assert EAL.save_loaded_asset(load(CH), False)
    if EAL.does_asset_exist(OLD_RETARGET):
        log('old retarget component asset deleted: %s' % EAL.delete_asset(OLD_RETARGET))
    report['character'] = dict(wizard_component='WizardMeshV5', branches=sorted(done), firepoint_z=FIREPOINT_Z, backup=str(dest))
    log('character wired')


def main():
    try:
        meshes = import_models()
        u.EditorLoadingAndSavingUtils.load_map('/Game/ThirdPerson/Lvl_ThirdPerson')
        src, _ = ref_pose(load(QUINN))
        assert 70 < src['pelvis'][0][2] < 110, src['pelvis']
        abps = {}
        for kind in KINDS:
            tgt, parents = ref_pose(meshes[kind])
            assert 50 < tgt['pelvis'][0][2] < 100, (kind, tgt['pelvis'])
            assert tgt['ball_l'][0][1] > tgt['foot_l'][0][1], (kind, 'the wizard must face +Y like Quinn')
            abps[kind] = build_abp(kind, meshes[kind], src, tgt, parents)
        wire_character(meshes, abps)
        report['passed'] = True
        log('done')
        print('WIZARD_V5_GAME_READY')
    except Exception:
        report['passed'] = False
        report['error'] = traceback.format_exc()
        REPORT.write_text(json.dumps(report, indent=1, default=str), encoding='utf-8')
        u.log_error(traceback.format_exc())


main()
