"""Little Wizards V5 outfits (round 8): shoes, trousers, sleeves and the larger
clothing pieces, rebuilt to match the 3d-v2 turnaround sheets more closely.

Called from build_wizard_models_v5.py with its globals() (mesh / tube / ell /
star helpers, materials, weights).  Coordinates are the build's body space
(before apply_proportions): feet on z = 0, front is -Y.
"""
import math
from math import sin, cos, pi, radians
from mathutils import Vector


def _sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def outline(cx, cy, A, B, n=48, p=2.4, toe=.10, heel=.20, t0=0.0, t1=2 * pi, closed=True):
    """Foot-shaped ring in the x-y plane: a superellipse (power p) around
    (cx, cy), half-width A, half-length B, a little narrower at the toe (front,
    -y) and more at the heel."""
    pts = []
    m = n if closed else n + 1
    for k in range(m):
        t = t0 + (t1 - t0) * k / n
        u, v = _sgnpow(cos(t), 2 / p), _sgnpow(sin(t), 2 / p)
        taper = 1 - (toe if v < 0 else heel) * v * v
        pts.append((cx + A * u * taper, cy + B * v))
    return pts


def loft_rings(G, name, rings, material, w, cap_bottom=False, cap_top=False, closed=True, sub=1):
    """Mesh through rings of equal length (lists of 3D points)."""
    vs, fs = [], []
    n = len(rings[0])
    for r in rings:
        vs.extend(tuple(p) for p in r)
    m = n if closed else n - 1
    for i in range(len(rings) - 1):
        for j in range(m):
            a = i * n + j
            b = i * n + (j + 1) % n
            fs.append((a, b, b + n, a + n))
    if cap_bottom:
        fs.append(tuple(range(n - 1, -1, -1)))
    if cap_top:
        fs.append(tuple((len(rings) - 1) * n + j for j in range(n)))
    return G['mesh'](name, vs, fs, material, w, sub)


def star(G, name, x, y, z, size, material, w, points=4, normal=(0, -1, 0)):
    """Flat embossed star facing -Y (the build's star() is defined after the limbs)."""
    import bpy
    vs = [(x, y - .002, z)]
    for i in range(points * 2):
        a = pi / 2 + i * pi / points
        r = size if i % 2 == 0 else size * .31
        vs.append((x + r * cos(a), y, z + r * sin(a)))
    fs = [(0, i + 1, (i + 1) % (points * 2) + 1) for i in range(points * 2)]
    ob = G['mesh'](name, vs, fs, material, w)
    sol = ob.modifiers.new('Emboss', 'SOLIDIFY')
    sol.thickness = .002
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=sol.name)
    return ob


# ---------------------------------------------------------------------- shoes
SHOES = {
    # upper, toe cap, midsole, outsole, collar, laces, tongue, accent, collar top z
    'wind': dict(upper='Green', toe='Cream', mid='Cream', out='Green', collar='Green', laces='Cream',
                 tongue='Green', accent='Cream', top=.215, star='Gold', patch='Cream',
                 scale=(.88, .86, .86)),             # round 9: wind's shoes were too big
    'fire': dict(upper='Brown', toe='Brown', mid='Sole', out='Sole', collar='Brown', laces='RedLight',
                 tongue='Brown', accent='Brown', top=.275, eyelets='Gold', lugs=True, boot=True),
    'lightning': dict(upper='Ivory', toe='Ivory', mid='Ivory', out='Purple', collar='Ivory', laces='Purple',
                      tongue='Ivory', accent='Purple', top=.205, star='Purple', zigzag=True),
    'ice': dict(upper='Ivory', toe='Ivory', mid='Ivory', out='Lavender', collar='Lavender', laces='Cream',
                tongue='Ivory', accent='Lavender', top=.215, strap=True, heel_panel=True),
}

# (z, half width, half length, centre y) of the upper's sections, from the sole up
UPPER = [(.040, .086, .146, -.065), (.058, .087, .145, -.064), (.075, .085, .138, -.058),
         (.092, .081, .122, -.047), (.108, .075, .101, -.033), (.122, .069, .081, -.020),
         (.136, .064, .067, -.010), (.150, .062, .062, -.004)]


def build_shoe(G, kind, s, sg):
    S = SHOES[kind]
    n0 = len(G['parts'])
    x0 = sg * .14
    fw = 'foot_' + s
    lw = G['legweight'](s)
    # sole: coloured outsole + midsole, rounded edges
    sole = [(.000, .955), (.004, .985), (.009, 1.0), (.016, 1.0)]
    mid = [(.016, 1.0), (.030, 1.006), (.038, 1.0), (.043, .975)]
    if S.get('lugs'):
        sole = [(.000, .955), (.005, .985), (.012, 1.0), (.024, 1.0)]
        mid = [(.024, 1.0), (.034, 1.004), (.040, 1.0), (.045, .975)]

    def ring(z, k):
        return [(x, y, z) for x, y in outline(x0 + 0, -.064, .092 * k, .156 * k)]
    loft_rings(G, 'Shoe outsole ' + s, [ring(z, k) for z, k in sole], S['out'], fw, cap_bottom=True)
    loft_rings(G, 'Shoe midsole ' + s, [ring(z, k) for z, k in mid], S['mid'], fw, cap_top=True)
    if S.get('lugs'):
        # chunky boot tread: blocks around the outsole edge
        for j in range(14):
            t = 2 * pi * (j + .5) / 14
            (x, y), = outline(x0, -.064, .094, .158, n=1, t0=t, t1=t + 1e-6, closed=False)[:1]
            G['box']('Boot lug', (x, y, .010), (.020, .020, .020), S['out'], fw, .004)
    # upper: sections from the sole up to the ankle, then the high collar
    rings = [[(x, y, z) for x, y in outline(x0, cy, A, B)] for z, A, B, cy in UPPER]
    top = S['top']
    for z in (.168, .190, top):
        r = .062 + .004 * (z - .150) / max(.001, top - .150)
        rings.append([(x, y, z) for x, y in outline(x0, -.004, r, r, p=2.0, toe=0, heel=0)])
    loft_rings(G, 'Shoe upper ' + s, rings[:len(UPPER)], S['upper'], fw)
    loft_rings(G, 'Shoe collar ' + s, rings[len(UPPER) - 1:], S['collar'], lw if S.get('boot') else fw)
    # padded collar rim
    rim = [(x, y, top + .004) for x, y in outline(x0, -.004, .066, .066, p=2.0, toe=0, heel=0, n=40)]
    G['tube']('Shoe collar rim ' + s, rim + [rim[0]], .009, S['collar'], lw if S.get('boot') else fw, 10)
    # toe cap: the front of the lower sections, a hair outside the upper
    if S['toe'] != S['upper'] or kind == 'lightning':
        caps = []
        for z, A, B, cy in UPPER[:4]:
            caps.append([(x, y, z + .001) for x, y in outline(x0, cy, A + .0025, B + .0025, t0=1.10 * pi, t1=1.90 * pi,
                                                              closed=False, n=24)])
        loft_rings(G, 'Shoe toe cap ' + s, caps, S['toe'], fw, closed=False)
    # heel counter
    heel = []
    for z, A, B, cy in UPPER[:7]:
        heel.append([(x, y, z + .001) for x, y in outline(x0, cy, A + .0022, B + .0022, t0=.18 * pi, t1=.82 * pi,
                                                          closed=False, n=24)])
    loft_rings(G, 'Shoe heel counter ' + s, heel, S['accent'] if S.get('heel_panel') else S['upper'], fw, closed=False)
    # tongue, rising out of the collar at the front
    tongue = [(x0, -.088, .112), (x0, -.075, .150), (x0, -.062, .190), (x0, -.054, top + .030)]
    strip(G, 'Shoe tongue ' + s, tongue, .056, .004, S['tongue'], fw)
    if S.get('star'):
        star(G, 'Shoe tongue star', x0, -.060, top + .005, .016, S['star'], fw)
    # laces across the instep, crossing
    front = []                                           # front of the upper by height
    for z, A, B, cy in UPPER[3:] + [(top, .064, .064, -.004)]:
        front.append((z, cy - B))
    def fy(z):
        for (za, ya), (zb, yb) in zip(front, front[1:]):
            if z <= zb:
                t = (z - za) / max(1e-6, zb - za)
                return ya + (yb - ya) * t
        return front[-1][1]
    for j in range(6):
        z = .100 + j * .019
        y = fy(z) - .007
        y2 = fy(z + .012) - .007
        for side in (1, -1):
            G['tube']('Laces', [(x0 - side * .030, y, z), (x0 + side * .030, y2, z + .012)], .0036, S['laces'], fw, 6)
        if S.get('eyelets'):
            for side in (1, -1):
                G['ell']('Eyelet', (x0 + side * .033, y - .001, z), (.006, .003, .006), S['eyelets'], fw, 10, 6)
    # bow on top for sneakers
    if not S.get('boot'):
        zb = .100 + 5 * .019 + .012
        yb = fy(zb) - .010
        for side in (1, -1):
            G['tube']('Lace bow', [(x0, yb, zb), (x0 + side * .020, yb - .006, zb + .010), (x0 + side * .030, yb + .004, zb + .002),
                                   (x0, yb, zb)], .0034, S['laces'], fw, 6)
            G['tube']('Lace end', [(x0, yb, zb), (x0 + side * .012, yb - .010, zb - .022)], .0030, S['laces'], fw, 6)
    # accents
    if S.get('zigzag'):
        # purple lightning panel along the outer side
        for side in (1, -1):
            xs = x0 + side * .088
            path = [(xs, .040, .060), (xs, .010, .108), (xs, -.020, .072), (xs, -.055, .112), (xs, -.090, .078), (xs, -.125, .095)]
            G['tube']('Shoe zigzag', path, .0075, S['accent'], fw, 8)
    if S.get('strap'):
        # strap across the ankle with a square buckle patch
        strap = [(x, y, .172) for x, y in outline(x0, -.010, .070, .074, p=2.0, toe=0, heel=0, n=36)]
        G['tube']('Shoe ankle strap ' + s, strap + [strap[0]], .010, S['accent'], fw, 10)
        G['box']('Strap patch', (x0, -.084, .172), (.040, .010, .026), S['accent'], fw, .004)
    if kind == 'wind':
        G['box']('Heel tab', (x0, .062, .150), (.030, .010, .050), 'Cream', fw, .004)
    sc = S.get('scale')
    if sc:
        # smaller shoe: scaled about the ankle (the collar stays on the leg)
        for ob in G['parts'][n0:]:
            for v in ob.data.vertices:
                v.co = Vector((x0 + (v.co.x - x0) * sc[0], -.004 + (v.co.y + .004) * sc[1], v.co.z * sc[2]))
            ob.data.update()


# ----------------------------------------------------------------- trousers
def balloon(G, name, s, sg, ring_list, material, w, n=32, folds=.05, fold_k=7):
    """Trouser leg along the leg line: (z, half width x, half depth y, centre x,
    centre y).  Above the gathered cuff the cloth falls in soft folds."""
    rings = []
    z_c = ring_list[-1][0]
    ph = .4 if sg > 0 else 1.3
    for z, rx, ry, cx, cy in ring_list:
        f = folds * math.exp(-((z - z_c - .035) / .05) ** 2)
        rings.append([(sg * cx + rx * (1 + f * sin(fold_k * 2 * pi * j / n + ph)) * cos(2 * pi * j / n),
                       cy + ry * (1 + f * sin(fold_k * 2 * pi * j / n + ph)) * sin(2 * pi * j / n), z) for j in range(n)])
    return loft_rings(G, name, rings, material, w)


JOGGERS = {
    # (z, rx, ry, centre x, centre y): wide thighs, very full below the knee,
    # gathered into a cuff just above the shoe
    'lightning': [(.75, .080, .077, .090, 0), (.70, .102, .088, .102, 0), (.60, .108, .092, .118, -.004),
                  (.50, .112, .095, .126, -.010), (.42, .118, .098, .130, -.012), (.34, .121, .100, .134, -.010),
                  (.30, .114, .095, .136, -.008), (.27, .098, .086, .138, -.004), (.248, .074, .068, .139, -.002),
                  (.234, .060, .057, .140, 0)],
    'ice': [(.75, .080, .077, .090, 0), (.70, .100, .087, .102, 0), (.60, .106, .090, .118, -.004),
            (.50, .110, .093, .126, -.010), (.42, .114, .096, .130, -.012), (.34, .115, .097, .134, -.010),
            (.30, .110, .093, .136, -.008), (.275, .096, .084, .138, -.004), (.252, .072, .066, .139, -.002),
            (.240, .060, .057, .140, 0)],
    'fire': [(.75, .080, .077, .090, 0), (.70, .100, .087, .102, 0), (.60, .104, .088, .118, -.004),
             (.50, .106, .090, .126, -.010), (.42, .110, .093, .130, -.012), (.36, .113, .095, .134, -.010),
             (.33, .108, .092, .136, -.008), (.305, .094, .084, .138, -.004), (.287, .074, .068, .139, -.002),
             (.274, .060, .057, .140, 0)],
}


def build_trousers(G, kind, s, sg):
    lw = G['legweight'](s)
    mat = {'lightning': 'Purple', 'ice': 'IcePants', 'fire': 'Dark'}[kind]
    rl = JOGGERS[kind]
    balloon(G, 'Trousers ' + s, s, sg, rl, mat, lw)
    z_c = rl[-1][0]
    # ribbed ankle cuff
    for k in range(3):
        z = z_c - .006 - k * .010
        ring = [(sg * .140 + .061 * cos(2 * pi * j / 32), .059 * sin(2 * pi * j / 32), z) for j in range(32)]
        G['tube']('Ankle cuff rib ' + s, ring + [ring[0]], .0055, mat, lw, 8)
    G['tube']('Ankle cuff ' + s, [(sg * .14, 0, z_c - .002), (sg * .14, 0, z_c - .034)], .060, mat, lw, 28)
    if kind == 'lightning':
        # big cargo pocket with a flap on the outer thigh
        G['box']('Cargo pocket ' + s, (sg * .232, -.012, .555), (.040, .118, .150), 'Purple', lw, .014)
        G['box']('Pocket flap ' + s, (sg * .240, -.014, .628), (.040, .124, .040), 'Purple', lw, .010)
        G['ell']('Pocket snap', (sg * .262, -.014, .618), (.006, .010, .006), 'PurpleLight', lw, 10, 6)


# ------------------------------------------------------------------ helpers
def _ev(f, *args):
    return f(*args) if callable(f) else f


def _angdiff(a, b):
    """Signed angle a - b in (-pi, pi]."""
    return (a - b + pi) % (2 * pi) - pi


def table_z(knots, z):
    """Linear interpolation of the values in knots (z, v1, v2, ...) at z."""
    ks = sorted(knots)
    if z <= ks[0][0]:
        return ks[0][1:]
    if z >= ks[-1][0]:
        return ks[-1][1:]
    for k0, k1 in zip(ks, ks[1:]):
        if z <= k1[0]:
            u = (z - k0[0]) / (k1[0] - k0[0])
            return tuple(a + (b - a) * u for a, b in zip(k0[1:], k1[1:]))


def acc_chain(G, name, pts, parent, n=3):
    """Round 9: physics chain for a hanging accessory (strap, cord, sash end):
    n bones of equal length along pts (top -> tip), parented to parent.
    Returns the weight function (by height: the parent at the very top, then
    the chain bones down to the tip).  Listed in G['ACC_CHAINS']: HairCheck
    swings them, in Unreal they are physics chains like the hair."""
    P = [Vector(p) for p in pts]
    L = [0.0]
    for a, b in zip(P, P[1:]):
        L.append(L[-1] + (b - a).length)
    J = []
    for k in range(n + 1):
        d = L[-1] * k / n
        i = next((q for q in range(len(P) - 1) if L[q + 1] >= d - 1e-9), len(P) - 2)
        t = (d - L[i]) / max(1e-9, L[i + 1] - L[i])
        J.append(P[i].lerp(P[i + 1], max(0.0, min(1.0, t))))
    names, par = [], parent
    for k in range(n):
        nm = 'acc_%s_%02d' % (name, k + 1)
        G['bones'][nm] = (J[k].copy(), J[k + 1].copy(), par)
        names.append(nm)
        par = nm
    G.setdefault('ACC_CHAINS', []).append(dict(name=name, bone_names=names))
    knots = sorted([((J[k].z + J[k + 1].z) / 2, names[k]) for k in range(n)] + [(J[0].z + .004, parent)],
                   key=lambda kv: kv[0])
    return lambda p: G['chainweight'](p, knots)


def _materials(G, ob, names):
    """Per-face materials (names in face order)."""
    me = ob.data
    order = list(dict.fromkeys(names))
    me.materials.clear()
    for nm in order:
        me.materials.append(G['mats'][nm])
    for p, nm in zip(me.polygons, names):
        p.material_index = order.index(nm)
    return order


def _solidify(G, ob, thick, w, lining=None, n_outer=1):
    import bpy
    me = ob.data
    if lining:
        for _ in range(n_outer):
            me.materials.append(G['mats'][lining])
    bpy.context.view_layer.objects.active = ob
    sol = ob.modifiers.new('Fabric thickness', 'SOLIDIFY')
    sol.thickness = thick
    if lining:
        sol.material_offset = n_outer
    bpy.ops.object.modifier_apply(modifier=sol.name)
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    G['weights'](ob, w)
    for p in me.polygons:
        p.use_smooth = True


def garment(G, name, a0, a1, top, hem, shape, w, mat_fn, lining=None, nu=48, nv=20, thick=.004,
            folds=(0.0, 7, 0.0), piping=None, piping_r=.0035, closed=False, piping_sides=True, side_from=(0.0, 0.0)):
    """Cloth around the body: rows from the top edge (t = 0) to the hem (t = 1).
    a0, a1: angle range (0 = +x, -pi/2 = front, pi/2 = back), numbers or functions of t.
    top(a), hem(a): z of the top edge and of the hem at angle a.
    shape(z, t, a) -> (rx, ry, cy): the section ellipse.
    mat_fn(t, a, z) -> outside material; lining: inside material.
    side_from: t where the piping of the a0 / a1 edge starts (a vent).
    folds: (amplitude, count, phase): soft waves growing toward the hem.
    Returns (object, at) with at(a, t) -> (surface point, outward direction)."""
    nr = nu if closed else nu + 1

    def at(a, t):
        zt, zh = top(a), hem(a)
        z = zt + (zh - zt) * t
        rx, ry, cy = shape(z, t, a)
        f = 1 + folds[0] * t ** 1.3 * sin(folds[1] * a + folds[2])
        p = Vector((rx * f * cos(a), cy + ry * f * sin(a), z))
        n = Vector((cos(a) / max(rx, 1e-6), sin(a) / max(ry, 1e-6), 0)).normalized()
        return p, n
    vs, ang = [], []
    for i in range(nv + 1):
        t = i / nv
        A0, A1 = _ev(a0, t), _ev(a1, t)
        for j in range(nr):
            a = A0 + (A1 - A0) * j / nu
            vs.append(at(a, t)[0])
            ang.append(a)
    fs, fm = [], []
    for i in range(nv):
        for j in range(nu):
            p, q = i * nr + j, i * nr + (j + 1) % nr
            fs.append((p, p + nr, q + nr, q))
            a = ang[p] + _angdiff(ang[q], ang[p]) / 2
            zc = (vs[p].z + vs[q].z + vs[p + nr].z + vs[q + nr].z) / 4
            fm.append(mat_fn((i + .5) / nv, a, zc))
    ob = G['mesh'](name, [tuple(v) for v in vs], fs, fm[0], w)
    order = _materials(G, ob, fm)
    _solidify(G, ob, thick, w, lining, len(order))
    if piping:
        def out(k):
            return tuple(vs[k] + Vector((cos(ang[k]), sin(ang[k]), 0)) * .0025)
        hem_pts = [out(nv * nr + j) for j in range(nr)]
        if closed:
            hem_pts.append(hem_pts[0])
        G['tube'](name + ' hem piping', hem_pts, piping_r, piping, w, 6)
        if not closed and piping_sides:
            for j, t0 in ((0, side_from[0]), (nr - 1, side_from[1])):
                i0 = min(nv - 1, int(round(t0 * nv)))
                G['tube'](name + ' edge piping', [out(i * nr + j) for i in range(i0, nv + 1)], piping_r, piping, w, 6)
    return ob, at


def _catmull(P, R, s):
    """Point and radius at s (0..1) on a Catmull-Rom spline through P (radii R)."""
    n = len(P) - 1
    x = max(0.0, min(.999999, s)) * n
    k = int(x)
    u = x - k
    p0, p1, p2, p3 = P[max(k - 1, 0)], P[k], P[k + 1], P[min(k + 2, n)]
    r0, r1, r2, r3 = R[max(k - 1, 0)], R[k], R[k + 1], R[min(k + 2, n)]

    def cr(a, b, c, d):
        return .5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3)
    return cr(p0, p1, p2, p3), cr(r0, r1, r2, r3)


def fine_tube(G, name, path, radii, w, mat_fn, nl=56, na=56):
    """Open tube along a smooth spline through path; mat_fn(s, th) -> material
    (s 0..1 along the tube, th 0..2pi around).  Returns its rings."""
    # arc-length table of the spline (the segments have different lengths)
    S = [k / 400 for k in range(401)]
    Lc = [0.0]
    prev = _catmull(path, radii, 0.0)[0]
    for sk in S[1:]:
        q = _catmull(path, radii, sk)[0]
        Lc.append(Lc[-1] + (q - prev).length)
        prev = q
    tot = Lc[-1]

    def s_at(frac):
        d = frac * tot
        for k in range(400):
            if Lc[k + 1] >= d:
                return S[k] + (S[k + 1] - S[k]) * (d - Lc[k]) / max(1e-12, Lc[k + 1] - Lc[k])
        return 1.0
    rings = []
    for i in range(nl + 1):
        s = s_at(i / nl)
        p, r = _catmull(path, radii, s)
        p2, _ = _catmull(path, radii, min(1.0, s + 1e-3))
        p1, _ = _catmull(path, radii, max(0.0, s - 1e-3))
        t = (p2 - p1).normalized()
        ref = Vector((0, 1, 0)) if abs(t.y) < .9 else Vector((1, 0, 0))
        a = t.cross(ref).normalized()
        b = t.cross(a).normalized()
        rings.append([p + a * (r * cos(2 * pi * j / na)) + b * (r * sin(2 * pi * j / na)) for j in range(na)])
    vs = [tuple(q) for ring in rings for q in ring]
    fs, fm = [], []
    for i in range(nl):
        for j in range(na):
            a_, b_ = i * na + j, i * na + (j + 1) % na
            fs.append((a_, b_, b_ + na, a_ + na))
            fm.append(mat_fn((i + .5) / nl, 2 * pi * (j + .5) / na, tot))
    ob = G['mesh'](name, vs, fs, fm[0], w)
    _materials(G, ob, fm)
    return rings


def surface_bvh(G, include=None, exclude=()):
    """BVH of the current parts (names starting with one of include)."""
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for ob in G['parts']:
        if include and not ob.name.startswith(include):
            continue
        if exclude and ob.name.startswith(exclude):
            continue
        off = len(verts)
        verts.extend(v.co.copy() for v in ob.data.vertices)
        polys.extend([off + i for i in p.vertices] for p in ob.data.polygons)
    return BVHTree.FromPolygons(verts, polys)


def project(bvh, side, u, z, lift):
    """Surface point seen from a side: front / back (u = x) or left / right (u = y)."""
    o, d = {'front': (Vector((u, -2.0, z)), Vector((0, 1, 0))), 'back': (Vector((u, 2.0, z)), Vector((0, -1, 0))),
            'left': (Vector((2.0, u, z)), Vector((-1, 0, 0))), 'right': (Vector((-2.0, u, z)), Vector((1, 0, 0)))}[side]
    loc, nrm, idx, dist = bvh.ray_cast(o, d, 5.0)
    if loc is None:
        return None, None
    if nrm.dot(d) > 0:
        nrm = -nrm
    return loc + nrm * lift, nrm


def _orient(fs, vs, want):
    """Reverse the faces if their normals point away from want."""
    n = Vector()
    for f in fs[:20]:
        a, b, c = (Vector(vs[f[0]]), Vector(vs[f[1]]), Vector(vs[f[2]]))
        n += (b - a).cross(c - a)
    if n.dot(want) < 0:
        return [tuple(reversed(f)) for f in fs]
    return fs


def decal(G, name, poly, bvh, side, material, w, lift=.0025, thick=.0015, cuts=4, outline=None, outline_r=.0026):
    """Flat shape (poly: (u, z) points) laid on a surface seen from a side."""
    import bpy
    import bmesh
    bm = bmesh.new()
    vv = [bm.verts.new((u, 0.0, z)) for u, z in poly]
    bm.faces.new(vv)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    vs, keep = [], {}
    for v in bm.verts:
        p, n = project(bvh, side, v.co.x, v.co.z, lift)
        keep[v.index] = len(vs)
        vs.append(tuple(p) if p is not None else (v.co.x, 0.0, v.co.z))
    fs = [tuple(keep[v.index] for v in f.verts) for f in bm.faces]
    bm.free()
    want = {'front': Vector((0, -1, 0)), 'back': Vector((0, 1, 0)), 'left': Vector((1, 0, 0)), 'right': Vector((-1, 0, 0))}[side]
    fs = _orient(fs, vs, want)
    ob = G['mesh'](name, vs, fs, material, w)
    bpy.context.view_layer.objects.active = ob
    sol = ob.modifiers.new('Emboss', 'SOLIDIFY')
    sol.thickness = thick
    bpy.ops.object.modifier_apply(modifier=sol.name)
    if outline:
        pts = []
        for (u0, z0), (u1, z1) in zip(poly, poly[1:] + poly[:1]):
            for k in range(8):
                u, z = u0 + (u1 - u0) * k / 8, z0 + (z1 - z0) * k / 8
                p, n = project(bvh, side, u, z, lift + .0012)
                if p is not None:
                    pts.append(tuple(p))
        pts.append(pts[0])
        G['tube'](name + ' piping', pts, outline_r, outline, w, 6)
    return ob


def surface_band(G, name, pts, bvh, side, width, material, w, lift=.003, thick=.003, n=24):
    """Band (strap, trim) along (u, z) points laid on a surface seen from a side."""
    import bpy
    poly = []
    for (u0, z0), (u1, z1) in zip(pts, pts[1:]):
        for k in range(n):
            poly.append((u0 + (u1 - u0) * k / n, z0 + (z1 - z0) * k / n))
    poly.append(pts[-1])
    P, N = [], []
    for u, z in poly:
        p, nr = project(bvh, side, u, z, lift)
        if p is not None:
            P.append(p)
            N.append(nr)
    vs = []
    for k in range(len(P)):
        t = (P[min(k + 1, len(P) - 1)] - P[max(k - 1, 0)]).normalized()
        sd = N[k].cross(t).normalized()
        wk = width(k / max(1, len(P) - 1)) if callable(width) else width
        vs += [tuple(P[k] - sd * wk / 2), tuple(P[k] + sd * wk / 2)]
    fs = [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(len(P) - 1)]
    want = {'front': Vector((0, -1, 0)), 'back': Vector((0, 1, 0)), 'left': Vector((1, 0, 0)), 'right': Vector((-1, 0, 0))}[side]
    fs = _orient(fs, vs, want)
    ob = G['mesh'](name, vs, fs, material, w)
    bpy.context.view_layer.objects.active = ob
    sol = ob.modifiers.new('Emboss', 'SOLIDIFY')
    sol.thickness = thick
    bpy.ops.object.modifier_apply(modifier=sol.name)
    return ob, P, N


def star3(G, name, c, nrm, size, material, w, points=4, up=(0, 0, 1), thick=.002):
    """Embossed star at c facing nrm."""
    import bpy
    n = Vector(nrm).normalized()
    u = Vector(up) - n * n.dot(Vector(up))
    if u.length < 1e-6:
        u = Vector((1, 0, 0)) - n * n.x
    u.normalize()
    v = n.cross(u)
    c = Vector(c)
    vs = [c + n * .0012]
    for i in range(points * 2):
        a = i * pi / points
        r = size if i % 2 == 0 else size * .31
        vs.append(c + u * (r * cos(a)) + v * (r * sin(a)))
    fs = [(0, i + 1, (i + 1) % (points * 2) + 1) for i in range(points * 2)]
    vs = [tuple(p) for p in vs]
    fs = _orient(fs, vs, n)
    ob = G['mesh'](name, vs, fs, material, w)
    bpy.context.view_layer.objects.active = ob
    sol = ob.modifiers.new('Emboss', 'SOLIDIFY')
    sol.thickness = thick
    bpy.ops.object.modifier_apply(modifier=sol.name)
    return ob


def strip(G, name, centre, width, thick, material, w, normal=(0, -1, 0)):
    """Flat band with some thickness along a centre line; width across x (a
    number or a list per point)."""
    nrm = Vector(normal).normalized()
    vs, fs = [], []
    for i, p in enumerate(centre):
        p = Vector(p)
        wd = width[i] if isinstance(width, (list, tuple)) else width
        for dx, dn in ((-wd / 2, 0), (wd / 2, 0), (wd / 2, thick), (-wd / 2, thick)):
            vs.append(tuple(p + Vector((dx, 0, 0)) - nrm * dn))
    for i in range(len(centre) - 1):
        a = 4 * i
        for k in range(4):
            fs.append((a + k, a + (k + 1) % 4, a + 4 + (k + 1) % 4, a + 4 + k))
    fs.append((3, 2, 1, 0))
    last = 4 * (len(centre) - 1)
    fs.append((last, last + 1, last + 2, last + 3))
    return G['mesh'](name, vs, fs, material, w)


# --------------------------------------------------------------------- arms
# Round 9: the bare arms are built after apply_proportions, in the final space,
# along the re-posed bones (G['ARM_FINAL'][s] = shoulder joint, elbow, wrist).
# (s, radius across, radius front-back): s = 0 shoulder joint, 1 elbow, 2 wrist,
# beyond 2 inside the palm; above the joint the arm ends in a round cap.
# Radii measured on the 3d-v2 wind sheet (deltoid, slim upper arm, narrow
# elbow, forearm swelling below it, thin wrist under the wrap).
ARM_PROFILE = [(0.00, .046, .043), (.15, .044, .041), (.30, .039, .037), (.50, .035, .033), (.70, .032, .031),
               (.90, .029, .028), (1.00, .0285, .027), (1.12, .033, .030), (1.25, .037, .032), (1.40, .036, .030),
               (1.60, .031, .026), (1.80, .027, .023), (2.00, .025, .021), (2.12, .023, .019)]
ARM_SCALE = {'wind': (1.0, 1.0), 'fire': (.95, .5), 'lightning': (.88, .3), 'ice': (.88, .3)}   # size, muscle


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def arm_weight_final(G, s):
    """Weights for final-space arm geometry: projection on the re-posed bones,
    soft elbow (s .75 - 1.25) and wrist (s 1.85 - 2.10)."""
    J2, E2, W2 = G['ARM_FINAL'][s]

    def f(p):
        p = Vector(p)
        best = None
        for k, (A, B) in enumerate(((J2, E2), (E2, W2))):
            ab = B - A
            u = (p - A).dot(ab) / ab.length_squared
            u = min(1.0, u) if k == 0 else max(0.0, u)
            d = (p - (A + ab * u)).length
            if best is None or d < best[0]:
                best = (d, k + u)
        sv = best[1]
        lo, hd = _smooth((sv - .75) / .5), _smooth((sv - 1.85) / .25)
        return {nm + s: w for nm, w in (('upperarm_', 1 - lo), ('lowerarm_', lo * (1 - hd)), ('hand_', hd)) if w > 1e-4}
    return f


def _arm_axes(G, s, sg):
    J2, E2, W2 = G['ARM_FINAL'][s]

    def centre(sv):
        if sv <= 1.0:
            return J2 + (E2 - J2) * sv
        return E2 + (W2 - E2) * (sv - 1.0)

    def frame(sv):
        t = (centre(sv + .02) - centre(sv - .02)).normalized()
        a = t.cross(Vector((0, 1, 0))).normalized()          # outward (away from the body)
        if a.dot(Vector((sg, 0, 1))) < 0:
            a = -a
        b = t.cross(a).normalized()                           # front (-y)
        if b.y > 0:
            b = -b
        return t, a, b
    return centre, frame


def _tube_mesh(G, name, rings, material, w):
    """Closed mesh through rings (lists of points) with a pole at each end."""
    import bmesh
    na = len(rings[0])
    vs = [tuple(p) for r in rings for p in r]
    fs = []
    for i in range(len(rings) - 1):
        for j in range(na):
            p, q = i * na + j, i * na + (j + 1) % na
            fs.append((p, q, q + na, p + na))
    for end, sgn in ((0, -1), (len(rings) - 1, 1)):
        c = sum((Vector(v) for v in rings[end]), Vector()) / na
        nb = rings[end - sgn] if 0 <= end - sgn < len(rings) else rings[end]
        t = (c - sum((Vector(v) for v in nb), Vector()) / na)
        vs.append(tuple(c + (t.normalized() * .002 if t.length > 1e-9 else Vector())))
        k = len(vs) - 1
        for j in range(na):
            p, q = end * na + j, end * na + (j + 1) % na
            fs.append((p, q, k))
    ob = G['mesh'](name, vs, fs, material, w)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def build_arms_final(G):
    """One continuous bare arm per side: round shoulder cap (part of a sphere
    around the joint), deltoid, biceps, narrow elbow, forearm, wrist running
    into the palm.  Wind also gets the banded wrist wraps of the sheet."""
    kind = G['KIND']
    size, mus = ARM_SCALE.get(kind, (1.0, 1.0))
    NA = 32
    for s, sg in (('l', 1), ('r', -1)):
        centre, frame = _arm_axes(G, s, sg)
        w = arm_weight_final(G, s)
        rx0, ry0 = ARM_PROFILE[0][1] * size, ARM_PROFILE[0][2] * size
        rings = []
        t0, a0, b0 = frame(0.0)
        for i in range(1, 9):                                  # shoulder cap
            ph = (pi / 2) * i / 8
            c = centre(0.0) - t0 * (rx0 * cos(ph))
            rings.append([c + a0 * (rx0 * sin(ph) * cos(2 * pi * j / NA)) + b0 * (ry0 * sin(ph) * sin(2 * pi * j / NA))
                          for j in range(NA)])
        NS = 54
        s1 = ARM_PROFILE[-1][0]
        for i in range(1, NS + 1):
            sv = s1 * i / NS
            c = centre(sv)
            t, a, b = frame(sv)
            rx, ry = table_z(ARM_PROFILE, sv)
            rx, ry = rx * size, ry * size
            delt = .10 * mus * sin(pi * min(1.0, sv / .45)) ** 2        # deltoid: outer side (0 at the cap)
            bic = .08 * mus * math.exp(-((sv - .55) / .18) ** 2)        # biceps: front
            fore = .07 * mus * math.exp(-((sv - 1.25) / .16) ** 2)      # forearm: outer front
            ring = []
            for j in range(NA):
                th = 2 * pi * j / NA
                ca, sa = cos(th), sin(th)
                kx = 1 + delt * max(0.0, ca) ** 1.5 + fore * max(0.0, cos(th - pi / 4)) ** 2
                ky = 1 + bic * max(0.0, sa) ** 1.5 + fore * max(0.0, cos(th - pi / 4)) ** 2
                ring.append(c + a * (rx * kx * ca) + b * (ry * ky * sa))
            rings.append(ring)
        _tube_mesh(G, 'Arm ' + s, rings, 'Skin', w)
        if kind == 'wind':
            # banded wrist wrap (3d-v2): from mid-forearm to the wrist, four
            # wraps, a small lip at both ends
            rings = []
            NR = 30
            sa_, sb_ = 1.56, 2.03
            for i in range(NR + 1):
                u = i / NR
                sv = sa_ + (sb_ - sa_) * u
                c = centre(sv)
                t, a, b = frame(sv)
                R = .0372 - .0030 * u
                R -= .0020 * sum(math.exp(-((u - g) / .022) ** 2) for g in (.25, .50, .75))
                R += .0010 * (math.exp(-(u / .035) ** 2) + math.exp(-((1 - u) / .035) ** 2))
                rings.append([c + a * (R * cos(2 * pi * j / NA)) + b * (R * .93 * sin(2 * pi * j / NA)) for j in range(NA)])
            _tube_mesh(G, 'Wrist wraps ' + s, rings, 'Dark', w)
        else:
            build_sleeve(G, kind, s, sg)
    if kind == 'wind':
        stand_collar(G)


def stand_collar(G):
    """Wind's tall stand collar (3d-v2), fitted around the final neck: it
    follows the neck centre at every height, at least the sheet's width; two
    gold studs at the front."""
    neck = next(o for o in G['parts'] if o.name == 'Neck')
    ps = [v.co.copy() for v in neck.data.vertices]
    NA = 40
    rings = []
    for z, rxt, ryt, gp in ((1.212, .068, .058, .012), (1.232, .066, .057, .010), (1.250, .063, .055, .008),
                            (1.264, .060, .053, .007), (1.274, .058, .052, .006), (1.279, .058, .052, .006)):
        band = [p for p in ps if abs(p.z - z) < .006] or ps
        x0, x1 = min(p.x for p in band), max(p.x for p in band)
        y0, y1 = min(p.y for p in band), max(p.y for p in band)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = max(rxt, (x1 - x0) / 2 + gp), max(ryt, (y1 - y0) / 2 + gp)
        rings.append([Vector((cx + rx * cos(2 * pi * j / NA), cy + ry * sin(2 * pi * j / NA), z)) for j in range(NA)])
    ob = loft_rings(G, 'Stand collar', rings, 'Green', 'neck_01', sub=1)
    _solidify(G, ob, .0045, 'neck_01')
    c = rings[3]
    cen = sum(c, Vector()) / NA
    for sg in (1, -1):
        # front studs: on the ring, 30 degrees off the front centre
        a = -pi / 2 + sg * radians(30)
        p = Vector((cen.x + (c[0].x - cen.x) * cos(a), cen.y + (c[NA // 4].y - cen.y) * sin(a), c[0].z))
        n = Vector((p.x - cen.x, p.y - cen.y, 0)).normalized()
        G['ell']('Collar stud', tuple(p + n * .004), (.0055, .0055, .0055), 'Gold', 'neck_01', 12, 8)


# ------------------------------------------------------------------ sleeves
SLEEVES = {
    # round 9, final space: the sleeve starts inside the shoulder and hangs to
    # a cuff centre near the wrist (offset from the wrist: out, up in m), so
    # it no longer sticks out like a wing; radii from the shoulder (inside the
    # top) to the cuff; band: (width, colour); lining colour
    'lightning': dict(cuff=(.000, .010), r=[.040, .058, .070, .084, .100], band=(.030, 'Purple'), teeth=(5, .090),
                      lining='Purple', mat='Ivory', stars=3),
    'ice': dict(cuff=(-.030, -.012), r=[.040, .060, .078, .098, .120], band=(.100, 'Lavender'), lining='Lavender',
                mat='Ivory', motifs='Ivory'),
    'fire': dict(cuff=(-.036, .034), r=[.038, .056, .062, .068, .076], band=(.058, 'Red'), lining='Red',
                 mat='Cream', trim='Gold', inner='Dark', diamond=True),
}


def build_sleeve(G, kind, s, sg):
    """Final space (after apply_proportions): from inside the shoulder, round
    the joint, straight down to the cuff; the arm stays inside."""
    S = SLEEVES[kind]
    aw = arm_weight_final(G, s)
    J2, E2, Wr = G['ARM_FINAL'][s]
    du = (E2 - J2).normalized()
    C = Wr + Vector((sg * S['cuff'][0], 0.0, S['cuff'][1]))
    path = [J2 + Vector((-sg * .040, 0.0, .002)), J2 + du * .045, J2.lerp(C, .48), J2.lerp(C, .74), C]
    rr = list(S['r'])
    cw, cmat = S['band']
    teeth = S.get('teeth')

    def mat(sv, th, tot):
        d = (1 - sv) * tot                      # distance from the opening (m)
        return cmat if d < cw and not teeth else S['mat']
    NL, NA = 48, 64
    rings = fine_tube(G, 'Robe sleeve ' + s, path, rr, aw, mat, nl=NL, na=NA)
    if teeth:
        # purple band with triangles pointing up the sleeve: its own mesh, laid
        # 1 mm over the sleeve, so the zigzag edge is crisp
        k, amp = teeth
        tot = sum((Vector(rings[i + 1][0]) - Vector(rings[i][0])).length for i in range(NL))  # rough
        cen = [sum(r, Vector()) / len(r) for r in rings]
        Ls = [0.0]
        for i in range(NL):
            Ls.append(Ls[-1] + (cen[i + 1] - cen[i]).length)
        tot = Ls[-1]

        def on_sleeve(d, th):
            """Point on the sleeve at distance d from the opening, angle th."""
            L = tot - d
            i = max(0, min(NL - 1, next((q for q in range(NL) if Ls[q + 1] >= L), NL - 1)))
            u = (L - Ls[i]) / max(1e-9, Ls[i + 1] - Ls[i])
            x = th / (2 * pi) * NA
            j = int(x) % NA
            fx = x - int(x)
            j2 = (j + 1) % NA

            def ring_pt(r):
                return Vector(rings[r][j]).lerp(Vector(rings[r][j2]), fx)
            p = ring_pt(i).lerp(ring_pt(i + 1), u)
            c = cen[i].lerp(cen[i + 1], u)
            return p + (p - c).normalized() * .0012
        NT = k * 16
        vs, fs = [], []
        ROWS = 6
        for j in range(NT + 1):
            th = 2 * pi * j / NT
            x = (th * k / (2 * pi)) % 1.0
            lim = cw + amp * (1 - abs(2 * x - 1))
            for r in range(ROWS + 1):
                vs.append(tuple(on_sleeve(lim * r / ROWS, th)))
        for j in range(NT):
            for r in range(ROWS):
                a_, b_ = j * (ROWS + 1) + r, (j + 1) * (ROWS + 1) + r
                fs.append((a_, b_, b_ + 1, a_ + 1))
        c_end = cen[-1]
        fs = _orient(fs, vs, (Vector(vs[1]) - c_end))
        band = G['mesh']('Sleeve band ' + s, vs, fs, cmat, aw)
        _solidify(G, band, .0012, aw)
    e = path[-1]
    v = (path[-2] - e).normalized()
    R = rr[-1]
    G['tube']('Sleeve lining ' + s, [tuple(e - v * .004), tuple(e + v * .060)], [R * .97, R * .90], S['lining'], aw, 32)
    # round 10: the sleeve's own centre / radius at distance d from the opening
    # (trims and appliques sat on the opening's radius along a straight line
    # and floated off the narrower, curving sleeve)
    cs = [sum((Vector(q) for q in r), Vector()) / len(r) for r in rings]
    rs = [sum((Vector(q) - c).length for q in r) / len(r) for r, c in zip(rings, cs)]
    Ls = [0.0]
    for i in range(len(cs) - 1):
        Ls.append(Ls[-1] + (cs[i + 1] - cs[i]).length)

    def sleeve_at(d):
        Lq = max(0.0, Ls[-1] - d)
        i = next((q for q in range(len(cs) - 1) if Ls[q + 1] >= Lq), len(cs) - 2)
        t = (Lq - Ls[i]) / max(1e-9, Ls[i + 1] - Ls[i])
        return cs[i].lerp(cs[i + 1], t), (cs[i + 1] - cs[i]).normalized(), rs[i] + (rs[i + 1] - rs[i]) * t
    if S.get('trim'):
        for d in (cw, 0.0):
            c, axd, Rd = sleeve_at(d)
            G['tube']('Cuff piping ' + s, [tuple(c - axd * .003), tuple(c + axd * .003)], [Rd + .0035, Rd + .0035],
                      S['trim'], aw, 32)
    if S.get('inner'):
        # shirt sleeve showing at the wrist
        G['tube']('Inner sleeve ' + s, [tuple(e + v * .03), tuple(Wr - (Wr - e).normalized() * .006)], [.050, .042],
                  S['inner'], aw, 20)
    ax = v.cross(Vector((0, 1, 0)))
    if ax.length < 1e-6:
        ax = v.cross(Vector((1, 0, 0)))
    ax.normalize()
    ay = v.cross(ax).normalized()
    if S.get('motifs'):
        # big snowflakes around the lavender band, small stars between (3d-v2)
        for j in range(6):
            a = 2 * pi * (j + .5) / 6
            nrm = ax * cos(a) + ay * sin(a)
            c, _, Rd = sleeve_at(cw * .50)
            star3(G, 'Sleeve snowflake ' + s, c + nrm * (Rd + .0015), nrm, .030, S['motifs'], aw,
                  points=6, up=tuple(v))
            a2 = 2 * pi * (j + 1.0) / 6
            nrm2 = ax * cos(a2) + ay * sin(a2)
            c, _, Rd = sleeve_at(cw * .78)
            star3(G, 'Sleeve snowflake ' + s, c + nrm2 * (Rd + .0015), nrm2, .012, S['motifs'], aw,
                  up=tuple(v))
    if S.get('diamond'):
        # gold diamond on the outer side of the red cuff
        o = Vector((sg, 0.0, 0.0)) - v * (v.x * sg)
        o.normalize()
        c, _, Rd = sleeve_at(cw * .5)
        star3(G, 'Cuff diamond ' + s, c + o * (Rd + .0045), o, .024, 'Gold', aw, up=tuple(v))
    for j in range(S.get('stars', 0)):
        a = -pi / 2 + (j - .5) * .9
        nrm = ax * cos(a) + ay * sin(a)
        c, _, Rd = sleeve_at(cw + teeth[1] * .45 if teeth else cw * 1.5)
        star3(G, 'Sleeve star ' + s, c + nrm * (Rd + .002), nrm, .015, 'Gold', aw, up=tuple(v))
    return e, v, R


# --------------------------------------------------------------- garments
def fire_coat(G):
    """Open long coat: cream with a red lining, wide red facings down the front
    edges that turn into pointed red tails, gold piping; a red V on the back."""
    cw = G['coatweight']

    def edge(t):                                # half angle of the front opening
        return .28 + .50 * t ** 1.4
    KN = [(1.172, .110, .084, .000), (1.155, .146, .098, .000), (1.135, .180, .108, .000), (1.11, .194, .114, .000),
          (1.05, .192, .118, .000),
          (.94, .170, .124, .004), (.85, .180, .136, .006),
          (.78, .206, .152, .006), (.60, .262, .195, .010), (.45, .310, .232, .014), (.30, .360, .268, .018),
          (.22, .385, .285, .020)]

    def hem(a):
        d = abs(_angdiff(a, -pi / 2))           # angle from the front centre
        db = abs(_angdiff(a, pi / 2))           # angle from the back centre
        # pointed front tails, pointed red panels at the back sides, the cream
        # back panel a little shorter
        return (.345 - .060 * math.exp(-((d - .80) / .30) ** 2) - .050 * math.exp(-((db - .95) / .22) ** 2)
                + .022 * math.exp(-(db / .38) ** 2))

    def mat(t, a, z):
        d = abs(_angdiff(a, -pi / 2))
        if d < edge(t) + .15 + .24 * t ** 1.6:
            return 'Red'
        db = abs(_angdiff(a, pi / 2))
        return 'Red' if z < .86 and .60 < db < 1.30 else 'Cream'
    # round 9: two halves, a vent up the centre back from below the waist to
    # the hem (3d-v2 back view); above it they meet along a seam
    vt = .47

    def vgap(t):
        return .085 * _smooth((t - vt) / (1 - vt)) ** 1.3
    shape = lambda z, t, a: table_z(KN, z)
    kw = dict(lining='Red', nu=70, nv=48, folds=(.030, 9, .3), piping='Gold', piping_r=.0034)     # nu 100 -> 70 (round 10)
    ob, at = garment(G, 'Long ivory coat', lambda t: -pi / 2 + edge(t), lambda t: pi / 2 - vgap(t),
                     lambda a: 1.172, hem, shape, cw, mat, side_from=(0.0, vt), **kw)
    garment(G, 'Long ivory coat right', lambda t: pi / 2 + vgap(t), lambda t: 3 * pi / 2 - edge(t),
            lambda a: 1.172, hem, shape, cw, mat, side_from=(vt, 0.0), **kw)
    # gold trim along the inner edge of the red facings
    for sg in (1, -1):
        pts = []
        for k in range(41):
            t = k / 40
            a = -pi / 2 + sg * (edge(t) + .15 + .24 * t ** 1.6)
            p, n = at(a, t)
            pts.append(tuple(p + n * .003))
        G['tube']('Coat facing piping', pts, .0028, 'Gold', cw, 6)
    bvh = surface_bvh(G, include=('Long ivory coat',))
    # red V on the upper back with a gold star
    decal(G, 'Coat back V', [(-.110, 1.075), (.110, 1.075), (0.0, .900)], bvh, 'back', 'Red', G['torso'], outline='Gold')
    p, n = project(bvh, 'back', 0.0, 1.005, .004)
    if p is not None:
        star3(G, 'Coat back star', p, n, .030, 'Gold', G['torso'])
    # gold stars on the red tails, front and back
    for sg in (1, -1):
        p, n = project(bvh, 'front', sg * .245, .420, .003)
        if p is not None:
            star3(G, 'Coat tail star', p, n, .030, 'Gold', cw)
        q, n2 = at(pi / 2 + sg * .95, .90)
        star3(G, 'Coat tail star', q + n2 * .004, n2, .030, 'Gold', cw)
    # gold seams between the red back panels and the cream back
    for sg in (1, -1):
        for db in (.60, 1.30):
            a = pi / 2 + sg * db
            pts = []
            for k in range(21):
                z = .86 - (.86 - hem(a)) * k / 20
                t = (1.172 - z) / (1.172 - hem(a))
                p, n = at(a, t)
                pts.append(tuple(p + n * .003))
            G['tube']('Coat panel piping', pts, .0028, 'Gold', cw, 6)

    # gold lines set in from the vent, the hem and the red panels on the two
    # cream back flaps (3d-v2)
    def on_coat(a, z, lift=.0032):
        t = max(0.0, min(1.0, (1.172 - z) / (1.172 - hem(a))))
        p, n = at(a, t)
        return tuple(p + n * lift)
    z_top, ins, up = .80, .060, .045
    for sg in (1, -1):
        pts = []
        zb = hem(pi / 2) + up
        for k in range(15):
            z = z_top - (z_top - zb) * k / 14
            pts.append(on_coat(pi / 2 + sg * (vgap((1.172 - z) / (1.172 - hem(pi / 2))) + ins), z))
        a_in, a_out = vgap(1.0) + ins, .60 - ins
        for k in range(1, 11):
            a = pi / 2 + sg * (a_in + (a_out - a_in) * k / 10)
            pts.append(on_coat(a, hem(a) + up))
        a = pi / 2 + sg * a_out
        for k in range(1, 15):
            pts.append(on_coat(a, hem(a) + up + (z_top - hem(a) - up) * k / 14))
        G['tube']('Coat back trim', pts, .0022, 'Gold', cw, 6)
    return ob


def fire_pauldrons(G):
    """Red shoulder caps with gold piping, pointed over the upper arm, gold star."""
    for s, sg in (('l', 1), ('r', -1)):
        aw = G['armweight'](s)
        c = Vector((sg * .196, .004, 1.104))
        rx, ry, rz = .094, .092, .096
        th_out = 0.0 if sg > 0 else pi
        NU, NV = 48, 14

        def phimax(th):
            return 1.00 + .62 * max(0.0, cos(th - th_out)) ** 5

        def pt(th, phi, k=1.0):
            return c + Vector((rx * k * sin(phi) * cos(th), ry * k * sin(phi) * sin(th), rz * k * cos(phi)))
        vs = [tuple(c + Vector((0, 0, rz)))]
        for i in range(1, NV + 1):
            for j in range(NU):
                th = 2 * pi * j / NU
                vs.append(tuple(pt(th, phimax(th) * i / NV)))
        fs = []
        for j in range(NU):
            fs.append((0, 1 + (j + 1) % NU, 1 + j))
        for i in range(NV - 1):
            for j in range(NU):
                a = 1 + i * NU + j
                b = 1 + i * NU + (j + 1) % NU
                fs.append((a, b, b + NU, a + NU))
        fs = _orient(fs, vs, Vector((0, 0, 1)))
        ob = G['mesh']('Crimson shoulder ' + s, vs, fs, 'Red', aw)
        _solidify(G, ob, .004, aw)
        edge_pts = [vs[1 + (NV - 1) * NU + j] for j in range(NU)]
        edge_pts = [tuple(Vector(p) + (Vector(p) - c).normalized() * .002) for p in edge_pts]
        G['tube']('Shoulder piping ' + s, edge_pts + [edge_pts[0]], .0034, 'Gold', aw, 6)
        ph = phimax(th_out) * .62
        star3(G, 'Shoulder star', pt(th_out, ph, 1.03), (pt(th_out, ph) - c).normalized(), .030, 'Gold', aw)


def fire_scarf(G):
    """Scarf tails: a long one on her left side with gold stars and a tassel,
    a short one on the right (the neck wrap is built in the main script)."""
    sw = lambda p: G['chainweight'](p, [(.54, 'scarf_02'), (.91, 'scarf_01'), (1.12, 'spine_03')])
    long_ = [(.058, -.112, 1.125), (.074, -.140, 1.03), (.087, -.160, .90), (.097, -.170, .76), (.103, -.175, .64),
             (.106, -.177, .585)]
    strip(G, 'Scarf tail long', long_, [.078, .082, .086, .088, .088, .010], .006, 'Red', sw)
    short = [(-.052, -.118, 1.12), (-.066, -.140, 1.03), (-.078, -.152, .955), (-.082, -.155, .925)]
    strip(G, 'Scarf tail short', short, [.070, .072, .072, .010], .006, 'Red', sw)
    for z in (.70, .655):
        star3(G, 'Scarf star', (.103 + (.012 if z > .68 else -.012), -.182, z), (0, -1, 0), .016, 'Gold', sw)
    G['tassel'](.106, -.176, .575, 'Red', 'scarf_02')


def ice_robe(G):
    """Robe skirt with a handkerchief hem (points at the front, back and sides),
    lavender border with snowflakes, tassels at the points."""
    cw = G['coatweight']
    KN = [(.83, .205, .150, 0), (.70, .240, .176, 0), (.55, .272, .200, 0), (.40, .298, .221, 0), (.28, .312, .232, 0)]

    def hem(a):
        th = a + pi / 2
        pts = ((1 + cos(4 * th)) / 2) ** 3
        front = math.exp(-(_angdiff(a, -pi / 2) / .45) ** 2)
        return .44 - .090 * pts - .040 * front * pts
    band = .056

    def mat(t, a, z):
        return 'Lavender' if z - hem(a) < band else 'Ivory'
    ob, at = garment(G, 'Layered robe', 0.0, 2 * pi, lambda a: .83, hem, lambda z, t, a: table_z(KN, z), cw, mat,
                     lining='Ivory', nu=88, nv=34, closed=True, folds=(.028, 8, .4), piping='Cream', piping_r=.0032)   # nu 128 -> 88 (round 10)
    # trim line on top of the border
    pts = []
    for j in range(129):
        a = 2 * pi * j / 128
        t = (.83 - (hem(a) + band)) / (.83 - hem(a))
        p, n = at(a, t)
        pts.append(tuple(p + n * .0035))
    G['tube']('Robe band piping', pts, .0028, 'Cream', cw, 6)
    # snowflakes / stars on the border, tassels at the points
    for k in range(8):
        a = -pi / 2 + k * pi / 4
        t = (.83 - (hem(a) + band * .5)) / (.83 - hem(a))
        p, n = at(a, t)
        star3(G, 'Robe snowflake', p + n * .0035, n, .022 if k % 2 == 0 else .015, 'Ivory', cw, points=6 if k % 2 == 0 else 4)
        if k % 2 == 0:
            q, n2 = at(a, 1.0)
            G['tassel'](q.x + n2.x * .01, q.y + n2.y * .01, q.z - .006, 'IcePants', cw)

    # round 9: under layer (the 3d-v2 robe is layered): its points at the
    # diagonals hang below the outer layer between the outer points
    def hem2(a):
        th = a + pi / 2 + pi / 4
        return .395 - .075 * ((1 + cos(4 * th)) / 2) ** 3
    KN2 = [(z, rx * .955, ry * .955, c) for z, rx, ry, c in KN]
    garment(G, 'Robe under layer', 0.0, 2 * pi, lambda a: .80, hem2, lambda z, t, a: table_z(KN2, z), cw,
            lambda t, a, z: 'Lavender' if z - hem2(a) < .045 else 'Ivory', lining='Ivory', nu=88, nv=30,
            closed=True, folds=(.018, 8, .4), piping='Cream', piping_r=.0030)
    # lavender panel down the centre back with a big snowflake (3d-v2)
    bvh = surface_bvh(G, include=('Layered robe',))
    decal(G, 'Robe back panel', [(-.130, .745), (.130, .745), (0.0, .415)], bvh, 'back', 'Lavender', cw,
          outline='Cream')
    p, n = project(bvh, 'back', 0.0, .610, .0045)
    if p is not None:
        star3(G, 'Robe back snowflake', p, n, .048, 'Ivory', cw, points=6)
    return ob, at


def ice_sash_and_cords(G, robe_at):
    """Blue sash knotted at the front with long ends; cords with beads and
    tassels hanging at the sides; blue scarf at the neck."""
    cw = G['coatweight']
    G['ell']('Sash knot', (.050, -.172, .800), (.030, .020, .024), 'IcePants', 'pelvis', 20, 14)
    bvh = surface_bvh(G, include=('Layered robe',))
    for k, (x0, x1, wd) in enumerate(((.040, .030, .052), (.070, .110, .048))):
        ctrl = [(x0, .790), (x0 + (x1 - x0) * .4, .66), (x1, .50)]
        cp = [project(bvh, 'front', u, z, .004)[0] for u, z in ctrl]
        sw = acc_chain(G, 'sash_%d' % (k + 1), cp, 'pelvis') if all(p is not None for p in cp) else cw
        surface_band(G, 'Sash end', ctrl, bvh, 'front',
                     lambda u, wd=wd: wd * (1 - .7 * max(0.0, (u - .9) / .1)), 'IcePants', sw, lift=.004, thick=.003)
    for sg in (1, -1):
        for a_off, z1 in ((.72, .56), (1.30, .48)):
            a = -pi / 2 + sg * a_off
            pts = []
            for k in range(13):
                z = .805 - (.805 - z1) * k / 12
                t = (.83 - z) / (.83 - .40)
                p, n = robe_at(a, max(0.0, min(1.0, t)))
                pts.append(tuple(p + n * .010))
            e = Vector(pts[-1])
            kw_ = acc_chain(G, 'cord_%s%d' % ('l' if sg > 0 else 'r', 1 if a_off < 1 else 2),
                            pts + [tuple(e + Vector((0, 0, -.095)))], 'pelvis')
            G['tube']('Robe cord', pts, .0030, 'IcePants', kw_, 6)
            G['ell']('Cord bead', tuple(e + Vector((0, 0, -.008))), (.010, .010, .011), 'Gold', kw_, 12, 8)
            G['tassel'](e.x, e.y, e.z - .018, 'IcePants', kw_)
    # blue scarf around the cowl, knotted at the front
    G['loft']('Neck scarf', [(1.118, .121, .112, -.010), (1.136, .127, .118, -.012), (1.154, .121, .112, -.010)],
              'IcePants', 'neck_01', 40, .03, False)
    G['ell']('Neck scarf knot', (.018, -.128, 1.128), (.026, .018, .022), 'IcePants', 'neck_01', 16, 12)
    strip(G, 'Neck scarf end', [(.012, -.134, 1.12), (.004, -.142, 1.06), (-.004, -.146, 1.01)], [.040, .040, .010],
          .004, 'IcePants', 'spine_03')
    strip(G, 'Neck scarf end', [(.030, -.134, 1.12), (.044, -.140, 1.07), (.054, -.142, 1.035)], [.034, .034, .010],
          .004, 'IcePants', 'spine_03')


def ice_hat_band(G):
    """Round 9: wide soft scarf band round the crown base (3d-v2), fitted to the
    crown and folded, a big knot at the front on her right with a gold ring."""
    crown = next(o for o in reversed(G['parts']) if o.name.startswith('Bent hat crown'))
    ps = [v.co.copy() for v in crown.data.vertices]
    NA = 96
    prof = [(1.626, .003), (1.638, .011), (1.651, .017), (1.664, .018), (1.677, .012), (1.688, .003)]
    rings, mid = [], None
    for k, (z, o) in enumerate(prof):
        band = [p for p in ps if abs(p.z - z) < .008] or ps
        x0, x1 = min(p.x for p in band), max(p.x for p in band)
        y0, y1 = min(p.y for p in band), max(p.y for p in band)
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        ring = []
        for j in range(NA):
            a = 2 * pi * j / NA
            f = 1 + .55 * sin(3 * a + 1.2 * k) * sin(pi * k / (len(prof) - 1))     # twisted folds
            ring.append(Vector((cx + (rx + o * f) * cos(a), cy + (ry + o * f) * sin(a), z + .003 * sin(3 * a + 1.2 * k))))
        rings.append(ring)
        if k == 3:
            mid = (cx, cy, rx + o, ry + o, z)
    loft_rings(G, 'Hat scarf band', rings, 'Lavender', 'head', sub=1)
    cx, cy, rx, ry, z = mid
    a = radians(-118)
    p = Vector((cx + rx * cos(a), cy + ry * sin(a), z))
    n = Vector((cos(a) / rx, sin(a) / ry, 0)).normalized()
    G['ell']('Hat scarf knot', tuple(p + n * .012), (.034, .034, .030), 'Lavender', 'head', 24, 16)
    for sgn in (1, -1):                                   # two small loops of the knot
        t = Vector((-n.y, n.x, 0)) * sgn
        G['ell']('Hat scarf knot loop', tuple(p + n * .010 + t * .036 + Vector((0, 0, -.004))), (.022, .022, .018),
                 'Lavender', 'head', 16, 12)
    c = p + n * .044
    u, w = Vector((-n.y, n.x, 0)), Vector((0, 0, 1))
    ring = [tuple(c + (u * cos(2 * pi * j / 32) + w * sin(2 * pi * j / 32)) * .017) for j in range(33)]
    G['tube']('Hat clasp ring', ring, .0036, 'Gold', 'head', 8)


def ice_wrap_lines(G):
    """Kimono-like overlap: two lavender trims crossing the chest."""
    bvh = surface_bvh(G, include=('Tunic body',))
    surface_band(G, 'Robe collar trim', [(-.070, 1.150), (-.010, 1.030), (.060, .920), (.105, .845)], bvh, 'front',
                 .016, 'Lavender', G['torso'], lift=.002, thick=.003)
    surface_band(G, 'Robe collar trim', [(.070, 1.150), (.035, 1.080), (.000, 1.040)], bvh, 'front',
                 .014, 'Lavender', G['torso'], lift=.002, thick=.003)


def lightning_hoodie(G):
    """Oversized hoodie from the shoulders: hem lower at the back on her right,
    purple straps down the front, a big purple bolt with a gold edge, a purple
    triangle on the back."""
    torso = G['torso']
    KN = [(1.178, .118, .082, .000), (1.166, .160, .098, .000), (1.150, .200, .110, .000), (1.128, .226, .118, .000),
          (1.100, .236, .122, .000), (1.058, .230, .125, .000), (1.000, .216, .128, .000), (.950, .204, .132, .002),
          (.850, .203, .147, .004), (.780, .209, .154, .004), (.700, .214, .159, .004), (.640, .216, .161, .004)]

    def hem(a):
        return .742 - .060 * math.exp(-(_angdiff(a, 2.55) / .55) ** 2) + .005 * sin(3 * a)
    ob, at = garment(G, 'Hoodie body', 0.0, 2 * pi, lambda a: 1.178, hem, lambda z, t, a: table_z(KN, z), torso,
                     lambda t, a, z: 'Ivory', lining='Ivory', nu=72, nv=34, closed=True, folds=(.018, 6, .2))   # nu 96 -> 72 (round 10)
    bvh = surface_bvh(G, include=('Hoodie body',))
    bolt = [(-.060, 1.080), (-.132, .938), (-.062, .948), (-.106, .796), (.052, .990), (-.016, .978), (.022, 1.080)]
    decal(G, 'Hoodie bolt', bolt, bvh, 'front', 'Purple', torso, outline='Gold', cuts=5)
    decal(G, 'Hoodie back triangle', [(-.112, 1.030), (.112, 1.030), (0.0, .875)], bvh, 'back', 'Purple', torso,
          outline='Gold')
    p, n = project(bvh, 'back', 0.0, .955, .004)
    if p is not None:
        star3(G, 'Hoodie back star', p, n, .026, 'Gold', torso)
    for sg in (1, -1):
        band, P, N = surface_band(G, 'Hoodie strap', [(sg * .118, 1.150), (sg * .120, .960), (sg * .126, .760)], bvh,
                                  'front', .032, 'Purple', torso, lift=.003, thick=.003)
        for z in (1.07, .93):
            q, n = project(bvh, 'front', sg * .120, z, .0075)
            if q is not None:
                G['ell']('Strap rivet', tuple(q), (.0045, .0030, .0045), 'Gold', torso, 10, 6)
    return ob


def plate(G, name, c, nrm, up, w, h, t, material, wgt):
    """Small box (buckle, tag) at c facing nrm: w across, h along up, t thick."""
    import bpy
    import bmesh
    n = Vector(nrm).normalized()
    u = Vector(up) - n * n.dot(Vector(up))
    u.normalize()
    v = n.cross(u)
    c = Vector(c)
    vs = []
    for dn in (0.0, t):
        for du, dv in ((-h / 2, -w / 2), (-h / 2, w / 2), (h / 2, w / 2), (h / 2, -w / 2)):
            vs.append(tuple(c + n * dn + u * du + v * dv))
    fs = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    ob = G['mesh'](name, vs, fs, material, wgt)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def leg_point(kind, sg, z, phi, lift):
    """Point on the trouser leg (JOGGERS ring at z) at angle phi around the leg
    (0 = outward, -90 deg = front), lifted off the cloth; outward normal and
    horizontal side direction."""
    rows = [(r[0], r[1], r[2], r[3], r[4]) for r in JOGGERS[kind]]
    rx, ry, cx, cy = table_z([(r[0], r[1], r[2], r[3], r[4]) for r in rows], z)
    c, sp = cos(phi), sin(phi)
    p = Vector((sg * (cx + rx * c), cy + ry * sp, z))
    n = Vector((sg * c / rx, sp / ry, 0)).normalized()
    side = Vector((-sg * rx * sp, ry * c, 0)).normalized()
    return p + n * lift, n, side


def trouser_seat(G, material):
    """Short piece joining the trouser legs under a top (no gap at the crotch)."""
    G['loft']('Trouser seat', [(.660, .150, .100, -.004), (.700, .170, .110, -.004), (.760, .168, .112, 0.0),
                               (.800, .160, .108, 0.0)], material, G['torso'], 40, 0, True)


def lightning_hip_straps(G):
    """Two straps per side hanging from under the hoodie hem over the
    front-outer thigh: purple, and ivory with gold stars; silver buckles."""
    for s_, sg in (('l', 1), ('r', -1)):
        lw = G['legweight'](s_)
        for phi, z1, mat, nm in ((radians(-62), .445, 'Purple', 'Hip strap '), (radians(-28), .490, 'Ivory', 'Hip strap light ')):
            P, N, D = [], [], []
            for k in range(25):
                z = .760 - (.760 - z1) * k / 24
                p, n, d = leg_point('lightning', sg, z, phi, .010)
                P.append(p)
                N.append(n)
                D.append(d)
            wd = .030
            vs = []
            for p, d in zip(P, D):
                vs += [tuple(p - d * wd / 2), tuple(p + d * wd / 2)]
            fs = [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(len(P) - 1)]
            fs = _orient(fs, vs, N[len(N) // 2])
            # round 9: each strap hangs on its own physics chain from the thigh
            lw = acc_chain(G, 'strap_%s%d' % (s_, 1 if mat == 'Purple' else 2), P, 'thigh_' + s_)
            ob = G['mesh'](nm + s_, vs, fs, mat, lw)
            _solidify(G, ob, .003, lw)
            k = min(range(len(P)), key=lambda i: abs(P[i].z - .700))
            plate(G, 'Strap buckle', P[k] + N[k] * .002, N[k], (0, 0, 1), .040, .026, .005, 'Silver', lw)
            plate(G, 'Strap buckle bar', P[k] + N[k] * .007, N[k], (0, 0, 1), .028, .006, .002, 'PurpleLight', lw)
            if mat == 'Ivory':
                for zz in (.630, .565):
                    k = min(range(len(P)), key=lambda i: abs(P[i].z - zz))
                    star3(G, 'Strap star', P[k] + N[k] * .0025, N[k], .013, 'Gold', lw)
                plate(G, 'Strap tip', P[-1] + N[-1] * .0015 + Vector((0, 0, .014)), N[-1], (0, 0, 1), .031, .028, .003, 'Purple', lw)
            else:
                plate(G, 'Strap tip', P[-1] + N[-1] * .0015 + Vector((0, 0, .014)), N[-1], (0, 0, 1), .031, .028, .003, 'Ivory', lw)


def wind_wrap(G):
    """Wrap skirt: khaki and green halves with cream borders down the split
    edges and along the hem; gold stars near the hem corners."""
    cw = G['coatweight']
    out = []
    for j, (a0, span, col) in enumerate(((-1.40, 1.62, 'Green'), (.14, 1.62, 'Khaki'), (1.71, 1.62, 'Green'),
                                         (3.30, 1.55, 'Khaki'))):
        a1 = a0 + span

        def shape(z, t, a):
            k = 1 - (1 - t) ** 2
            return (.165 + .105 * k, .122 + .072 * k, 0.0)

        def hem(a, a0=a0, a1=a1):
            u = (a - a0) / (a1 - a0)
            return .52 - .030 * sin(pi * u) - .020 * u

        def mat(t, a, z, a0=a0, a1=a1, col=col):
            near_edge = min(a - a0, a1 - a) < .085
            return 'Cream' if (z - hem(a) < .042 or near_edge) and t > .10 else col
        ob, at = garment(G, 'Athletic split wrap %d' % j, a0, a1, lambda a: .80, hem, shape, cw, mat, lining=col,
                         nu=40, nv=18, folds=(.020, 6, .3 * j))
        out.append(at)
        if j in (0, 3):
            u = .80 if j == 0 else .20
            p, n = at(a0 + (a1 - a0) * u, .82)
            star3(G, 'Wrap star', p + n * .003, n, .022, 'Gold', cw)
    # folded fabric roll at the waist under the belt
    ring = [(.182 * cos(2 * pi * j / 48), .140 * sin(2 * pi * j / 48), .785) for j in range(48)]
    G['tube']('Wrap waist roll', ring + [ring[0]], .011, 'Khaki', 'pelvis', 10)
    # gold ring on the belt
    c = Vector((-.105, -.150, .772))
    ring = [tuple(c + Vector((.017 * cos(2 * pi * j / 24), 0, .017 * sin(2 * pi * j / 24)))) for j in range(24)]
    G['tube']('Belt ring', ring + [ring[0]], .0035, 'Gold', 'pelvis', 8)
    return out


def ice_staff(G):
    """Round 11: the ice girl's magic staff, in her right hand (she casts with it).
    Rigid on a new bone 'staff' (child of hand_r); 'staff_tip' marks the crystal so
    the game can put effects there.  Cream shaft, lavender grip, gold fittings, a
    gold ring holding a pale blue snowflake crystal, a little bow and a tassel like
    the ones on her robe."""
    mats = G['mats']
    if 'Crystal' not in mats:
        G['mat']('Crystal', (.52, .72, .95), .16)
    h, t, _ = G['bones']['hand_r']
    h, t = Vector(h), Vector(t)
    grip = h + (t - h) * .62 + Vector((.012, -.012, 0))       # in the fist (right hand: +x is inward)
    up = Vector((0.0, -.10, 1.0)).normalized()                 # upright, leaning a little forward
    side = Vector((1.0, 0.0, 0.0))
    front = side.cross(up).normalized()                        # about -y: the side the crystal faces
    bot = grip - up * .38
    top = grip + up * .60                                       # the ring stays under the hat brim
    ring_c = top + up * .092
    G['bones']['staff'] = (grip.copy(), grip + up * .30, 'hand_r')
    G['bones']['staff_tip'] = (ring_c.copy(), ring_c + up * .06, 'staff')
    w = 'staff'
    n = 9
    pts = [tuple(bot + (top - bot) * (k / (n - 1))) for k in range(n)]
    G['tube']('Staff shaft', pts, [.0115, .0125, .0135, .0145, .0135, .0125, .012, .0115, .011], 'Ivory', w, 12)
    G['tube']('Staff grip', [tuple(grip - up * .065), tuple(grip + up * .065)], .0165, 'Lavender', w, 12)
    G['ell']('Staff foot', tuple(bot - up * .008), (.019, .019, .024), 'Gold', w, 14, 10)
    G['tube']('Staff collar', [tuple(top - up * .022), tuple(top + up * .012)], .0185, 'Gold', w, 14)
    # the ring, in the plane facing the front, round the crystal
    R_ = .072
    ring = [tuple(ring_c + side * (R_ * cos(a)) + up * (R_ * sin(a)))
            for a in [-pi / 2 + 2 * pi * k / 28 for k in range(29)]]
    G['tube']('Staff ring', ring, .0085, 'Gold', w, 10)
    # the snowflake crystal and its bright middle
    star3(G, 'Staff crystal', tuple(ring_c), tuple(front), .060, 'Crystal', w, points=6, up=tuple(up), thick=.016)
    G['ell']('Staff gem', tuple(ring_c + front * .010), (.020, .016, .020), 'Crystal', w, 16, 12)
    # two little gold twinkles riding the ring
    for a in (0.0, pi):
        c = ring_c + side * ((R_ + .002) * cos(a)) + up * ((R_ + .002) * sin(a))
        star3(G, 'Staff twinkle', tuple(c + front * .006), tuple(front), .020, 'Gold', w, points=4, up=tuple(up), thick=.004)
    # a bow under the ring and a tassel hanging from it
    bow = top - up * .045 + front * .016
    for sg in (1, -1):
        G['ell']('Staff bow', tuple(bow + side * (sg * .024) + up * .004), (.022, .009, .015), 'Lavender', w, 14, 10)
    G['ell']('Staff bow knot', tuple(bow), (.010, .010, .010), 'Lavender', w, 12, 8)
    cord_end = bow + Vector((0, 0, -.045))
    G['tube']('Staff tassel cord', [tuple(bow), tuple(cord_end)], .0022, 'IcePants', w, 6)
    G['tassel'](cord_end.x, cord_end.y, cord_end.z - .010, 'IcePants', w)
    return grip, ring_c
