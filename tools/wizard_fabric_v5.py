"""Round 10: fabric detail for the V5 wizards -- weave, fine wrinkles, small prints.

One tiling texture per wizard (16 cm square, sampled through 'DetailUV', the
parts' box projection at a fine scale):
  R  weave            G  small four-point stars (the prints)
  B  fine wrinkles    A  mottling (soft tone variation)
and its normal map (OpenGL green) for the game.  Per face corner the colour
attribute 'Detail' says how much of it a part gets: R cloth, G print, B
wrinkles -- 0 on skin, hair, metal, soles, piping and the big appliques.
Blender's cloth materials and the Unreal material (import_wizard_models_v5)
read the same three channels, so renders and game agree.
"""
import math
from math import pi

FABRIC_TILE = .16                     # metres per texture tile
FABRIC_CLOTH = ('Cream', 'Ivory', 'Dark', 'Red', 'Purple', 'Lavender', 'Green', 'Khaki', 'IcePants', 'Blue')
FABRIC_SKIP = ('sole', 'Sole', 'toe cap', 'Heel tab', 'heel counter', 'Eyelet', 'lug', 'uckle', 'snap', 'bead', 'Bead',
               'Pendant', 'charm', 'bolt', 'Lace', 'piping', 'Piping', 'thread', 'Tassel', 'snowflake', 'star', 'Star',
               'trim', 'Trim', 'rim', 'bow', 'knot loop')
FABRIC_FIRM = ('Shoe', 'Boot', 'cuff rib', 'Ankle cuff', 'Hat', 'hat', 'Collar', 'collar', 'Wrist wraps', 'belt')
# per wizard: (print materials, part name starts, star colour, more toward the hem)
FABRIC_PRINT = {
    'fire': (('Red',), ('Scarf tail', 'Long ivory coat', 'Robe sleeve'), (.86, .60, .20), True),
    'ice': (('Ivory',), ('Layered robe', 'Robe under layer'), (.56, .54, .84), True),
    'wind': (('Khaki', 'Green'), ('Athletic split wrap',), (.82, .62, .24), True),
    'lightning': (('Purple',), ('Hip strap', 'Hoodie strap', 'Robe sleeve'), (.95, .76, .30), False),
}


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def fabric_texture(kind, folder, size=1024, seed=10):
    """The tiling detail texture and its normal map as PNG images."""
    import numpy as np
    import bpy
    rng = np.random.default_rng(seed + sum(map(ord, kind)))
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    u, v = x / size, 1.0 - y / size                       # v up, as in Blender UVs
    tau = 2 * pi
    # weave: plain weave, ~1.2 mm threads, slightly irregular
    f = 128
    warp = .5 + .5 * np.sin(tau * f * u + .6 * np.sin(tau * 3 * v + 1.3))
    weft = .5 + .5 * np.sin(tau * f * v + .6 * np.sin(tau * 2 * u + .4))
    over = (np.sin(tau * f / 2 * u) * np.sin(tau * f / 2 * v)) > 0
    weave = np.where(over, warp ** .7, weft ** .7) * .85 + .15 * rng.random((size, size))
    # mottling: soft low-frequency tone variation
    mott = np.zeros_like(u)
    for _ in range(10):
        a, b = (int(c) for c in rng.integers(1, 6, 2))
        mott += np.sin(tau * (a * u + b * v) + rng.uniform(0, tau)) / (a + b)
    mott = (mott - mott.min()) / (mott.max() - mott.min())
    # fine wrinkles: soft folds mostly along v (hanging cloth), some diagonal
    wr = np.zeros_like(u)
    for k in range(14):
        a = int(rng.integers(2, 9))                       # folds across: 2..8 per tile
        b = int(rng.integers(-2, 3)) if k % 3 else 0
        env = .6 + .4 * np.sin(tau * (int(rng.integers(1, 3)) * v + int(rng.integers(-1, 2)) * u) + rng.uniform(0, tau))
        wr += env * np.sin(tau * (a * u + b * v) + rng.uniform(0, tau)) / a ** .6
    wr = (wr - wr.min()) / (wr.max() - wr.min())
    wr = np.clip(.5 + (wr - .5) * np.abs(wr - .5) * 2.4, 0, 1)    # rounded ridges, flat between
    # small four-point stars at jittered spots (about 1 cm, 7 per tile)
    stars = np.zeros_like(u)
    for cu, cv in rng.random((7, 2)):
        rad = rng.uniform(.030, .040)                     # tile units: 4.8 - 6.4 mm
        ang = rng.uniform(-.3, .3)
        du = (u - cu + .5) % 1 - .5
        dv = (v - cv + .5) % 1 - .5
        ca, sa = math.cos(ang), math.sin(ang)
        px, py = (du * ca - dv * sa) / rad, (du * sa + dv * ca) / rad
        d = np.abs(px) ** .5 + np.abs(py) ** .5            # astroid: a four-point star
        stars = np.maximum(stars, np.clip((1.0 - d) / .08, 0, 1))
    img = np.stack([weave, stars, wr, mott], -1).astype(np.float32)
    # normal map from the height (weave fine, wrinkles soft, prints a hair raised)
    h = weave * .25 + wr * 2.2 + stars * .4
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * .5
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * .5      # +v is up (the row index goes down)
    k = 1.6
    n = np.stack([-dx * k, -dy * k, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    nrm = np.concatenate([n * .5 + .5, np.ones_like(h)[..., None]], -1).astype(np.float32)
    out = {}
    for name, pix in (('T_%s_Detail' % kind.title(), img), ('T_%s_DetailN' % kind.title(), nrm)):
        old = bpy.data.images.get(name)
        if old is not None:
            bpy.data.images.remove(old)
        im = bpy.data.images.new(name, width=size, height=size, alpha=True)
        im.colorspace_settings.name = 'Non-Color'
        im.pixels.foreach_set(pix[::-1].ravel())          # Blender rows go bottom-up
        im.filepath_raw = str(folder / (name + '.png'))
        im.file_format = 'PNG'
        im.save()
        out[name] = im
    return out


def fabric_detail(G):
    """'Detail' corner colours and 'DetailUV' on every part; the cloth
    materials get the weave, the wrinkle bump and the prints."""
    kind = G['KIND']
    mats, parts = G['mats'], G['parts']
    pmats, pparts, pcol, hem = FABRIC_PRINT.get(kind, ((), (), (1, 1, 1), False))
    s = 1.0 / FABRIC_TILE
    stats = {}
    for ob in parts:
        me = ob.data
        if not me.polygons:
            continue
        name = ob.name
        uvl = me.uv_layers.get('DetailUV') or me.uv_layers.new(name='DetailUV')
        col = me.color_attributes.get('Detail') or me.color_attributes.new(name='Detail', type='BYTE_COLOR', domain='CORNER')
        zs = [v.co.z for v in me.vertices]
        z0, z1 = min(zs), max(zs)
        skip = any(k in name for k in FABRIC_SKIP)
        firm = any(k in name for k in FABRIC_FIRM)
        printed = any(name.startswith(p) for p in pparts)
        for poly in me.polygons:
            m = (me.materials[poly.material_index].name if me.materials else '').split('.')[0]
            cloth = (not skip) and m in FABRIC_CLOTH
            nrm = poly.normal
            axis = max(range(3), key=lambda k: abs(nrm[k]))
            axes = [k for k in range(3) if k != axis]
            pr = 1.0 if (cloth and printed and m in pmats) else 0.0
            for li in poly.loop_indices:
                p = me.vertices[me.loops[li].vertex_index].co
                uvl.data[li].uv = (p[axes[0]] * s, p[axes[1]] * s)
                hz = 1.0
                if pr and hem and z1 - z0 > .02:
                    hz = _smooth(((z1 - p.z) / (z1 - z0) - .45) / .45)     # more toward the hem
                col.data[li].color_srgb = (1.0 if cloth else 0.0, pr * hz, (.45 if firm else 1.0) if cloth else 0.0, 1.0)
            if cloth:
                stats[m] = stats.get(m, 0) + 1
    for ob in parts:
        ca = ob.data.color_attributes
        if 'Detail' in ca:
            ca.active_color = ca['Detail']
            ca.render_color_index = list(ca).index(ca['Detail'])
    folder = G['OUT'] / kind / 'Textures'
    folder.mkdir(parents=True, exist_ok=True)
    imgs = fabric_texture(kind, folder)
    tex = imgs['T_%s_Detail' % kind.title()]
    for mname in FABRIC_CLOTH:
        m = mats.get(mname)
        if m is not None and m.use_nodes:
            _fabric_shader(m, tex, pcol)
    G['FABRIC'] = dict(tile_m=FABRIC_TILE, cloth_faces=stats, print_colour=pcol, print_parts=list(pparts))
    return G['FABRIC']


def _fabric_shader(m, tex, pcol):
    """Cloth material: tone (weave + mottling), small stars in the print
    colour and a bump (weave + soft wrinkles), all scaled by 'Detail'."""
    nt = m.node_tree
    if nt.nodes.get('Fabric detail'):
        return
    n, L = nt.nodes, nt.links.new
    bsdf = n['Principled BSDF']
    base = tuple(bsdf.inputs['Base Color'].default_value)
    uv = n.new('ShaderNodeUVMap')
    uv.uv_map = 'DetailUV'
    uv.location = (-1300, 200)
    ti = n.new('ShaderNodeTexImage')
    ti.name = 'Fabric detail'
    ti.image = tex
    ti.location = (-1100, 200)
    L(uv.outputs['UV'], ti.inputs['Vector'])
    sep = n.new('ShaderNodeSeparateColor')
    sep.location = (-800, 250)
    L(ti.outputs['Color'], sep.inputs['Color'])
    at = n.new('ShaderNodeAttribute')
    at.attribute_name = 'Detail'
    at.location = (-1100, -150)
    msk = n.new('ShaderNodeSeparateColor')
    msk.location = (-800, -150)
    L(at.outputs['Color'], msk.inputs['Color'])

    def op(kind, a, b, loc):
        nd = n.new('ShaderNodeMath')
        nd.operation = kind
        nd.location = loc
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                nd.inputs[i].default_value = x
            else:
                L(x, nd.inputs[i])
        return nd.outputs[0]
    t1 = op('MULTIPLY', op('SUBTRACT', sep.outputs['Red'], .5, (-600, 300)), .16, (-450, 300))
    t2 = op('MULTIPLY', op('SUBTRACT', ti.outputs['Alpha'], .5, (-600, 200)), .14, (-450, 200))
    tone = op('ADD', 1.0, op('MULTIPLY', op('ADD', t1, t2, (-300, 250)), msk.outputs['Red'], (-150, 250)), (0, 250))
    cmb = n.new('ShaderNodeCombineColor')
    cmb.location = (0, 380)
    for ch in ('Red', 'Green', 'Blue'):
        L(tone, cmb.inputs[ch])
    mix = n.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = (150, 300)
    mix.inputs['Factor'].default_value = 1.0
    mix.inputs[6].default_value = base
    L(cmb.outputs['Color'], mix.inputs[7])
    star = op('MULTIPLY', sep.outputs['Green'], msk.outputs['Green'], (150, 80))
    mix2 = n.new('ShaderNodeMix')
    mix2.data_type = 'RGBA'
    mix2.location = (350, 250)
    L(star, mix2.inputs['Factor'])
    L(mix.outputs[2], mix2.inputs[6])
    mix2.inputs[7].default_value = (*pcol, 1)
    L(mix2.outputs[2], bsdf.inputs['Base Color'])
    h = op('ADD', op('MULTIPLY', sep.outputs['Red'], op('MULTIPLY', msk.outputs['Red'], .25, (-300, -350)), (-150, -350)),
           op('MULTIPLY', sep.outputs['Blue'], op('MULTIPLY', msk.outputs['Blue'], 1.6, (-300, -450)), (-150, -450)),
           (0, -400))
    bump = n.new('ShaderNodeBump')
    bump.location = (200, -300)
    bump.inputs['Strength'].default_value = .55
    bump.inputs['Distance'].default_value = .0012
    L(h, bump.inputs['Height'])
    L(bump.outputs['Normal'], bsdf.inputs['Normal'])
