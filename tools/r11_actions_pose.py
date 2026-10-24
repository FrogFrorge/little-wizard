"""Round 11: the characters' own actions, as poses of Quinn's skeleton (the
wizards copy Quinn's pose).  Pure Python (no Unreal): r11_actions.py keys these
into AnimSequences; r11_actions_preview.py draws stick figures.

Quinn's component space: +Y forward, +X the left side, +Z up, centimetres.
Each action is a list of keys (time 0..1, spec); a spec says where the pelvis,
spine, hands, feet, head go, and -- for the ice girl -- where her staff points
(the staff is rigid in her right hand: a fixed vector in Quinn's hand frame,
from output/round11/staff-frame.json).
"""
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
exec((ROOT / 'wizard_pose_math.py').read_text())          # va vs vm dot cross length norm qm qi qr axis between fk worldrot rotate ik smooth mix
BASE = json.loads((ROOT / 'wizard-skeleton-pose.json').read_text())
_SF = ROOT / 'output/round11/staff-frame.json'
STAFF = json.loads(_SF.read_text()) if _SF.exists() else None
REST = fk(BASE)
HAND0 = {s: REST['hand_' + s][0][:] for s in 'lr'}
FOOT0 = {s: REST['foot_' + s][0][:] for s in 'lr'}
POLE_ARM = {'r': [-60, -10, 120], 'l': [60, -10, 120]}
POLE_LEG = {'r': [-14, 70, 55], 'l': [14, 70, 55]}

# ------------------------------------------------------------ small maths
def ease(t):
    return smooth(t)


def lerp(a, b, t):
    if isinstance(a, (int, float)):
        return a + (b - a) * t
    return [x + (y - x) * t for x, y in zip(a, b)]


def qslerp(a, b, t):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b = [-x for x in b]
        d = -d
    if d > .9995:
        r = [x + (y - x) * t for x, y in zip(a, b)]
    else:
        th = math.acos(d)
        s = math.sin(th)
        r = [(math.sin((1 - t) * th) * x + math.sin(t * th) * y) / s for x, y in zip(a, b)]
    n = math.sqrt(sum(x * x for x in r))
    return [x / n for x in r]


def mat_to_q(m):
    """3x3 rotation matrix (rows) -> quaternion (x, y, z, w)."""
    (m00, m01, m02), (m10, m11, m12), (m20, m21, m22) = m
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return [(m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, .25 * s]
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        return [.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s]
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        return [(m01 + m10) / s, .25 * s, (m12 + m21) / s, (m02 - m20) / s]
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2
    return [(m02 + m20) / s, (m12 + m21) / s, .25 * s, (m10 - m01) / s]


def frame_q(a, b):
    """Rotation whose matrix columns are a, b, a x b (orthonormalised)."""
    a = norm(a)
    b = norm(vs(b, vm(a, dot(a, b))))
    c = cross(a, b)
    return mat_to_q([[a[0], b[0], c[0]], [a[1], b[1], c[1]], [a[2], b[2], c[2]]])


def staff_hand_q(d, front):
    """Quinn's right-hand component rotation that points the staff along d with
    the crystal facing 'front'."""
    v, f = STAFF['staff_axis_in_quinn_hand'], STAFF['crystal_front_in_quinn_hand']
    ql = frame_q(v, f)            # local frame -> axes
    qw = frame_q(d, front)        # wanted world frame
    return qm(qw, qi(ql))


# ------------------------------------------------------------ the pose
NEUTRAL = dict(pelvis=[0, 0, 0], lean=0.0, twist=0.0, side=0.0, nod=0.0, hand_r=None, hand_l=None,
               foot_r=[0, 0, 0], foot_l=[0, 0, 0], staff=None, staff_w=0.0, fist=0.0, tremble=0.0)


def spec_at(keys, t):
    """Interpolate the specs of the keys (eased between neighbours)."""
    keys = sorted(keys, key=lambda k: k[0])
    if t <= keys[0][0]:
        k0, k1, u = keys[0], keys[0], 0.0
    elif t >= keys[-1][0]:
        k0, k1, u = keys[-1], keys[-1], 0.0
    else:
        for a, b in zip(keys[:-1], keys[1:]):
            if a[0] <= t <= b[0]:
                k0, k1, u = a, b, ease((t - a[0]) / max(b[0] - a[0], 1e-6))
                break
    s0 = dict(NEUTRAL, **k0[1])
    s1 = dict(NEUTRAL, **k1[1])
    out = {}
    for k in NEUTRAL:
        a, b = s0[k], s1[k]
        if k in ('hand_r', 'hand_l'):
            a = a if a is not None else HAND0[k[-1]]
            b = b if b is not None else HAND0[k[-1]]
            out[k] = lerp(a, b, u)
        elif k == 'staff':
            if a is None and b is None:
                out[k] = None
            else:
                aa = a or b
                bb = b or a
                out[k] = (norm(lerp(aa[0], bb[0], u)), norm(lerp(aa[1], bb[1], u)))
        else:
            out[k] = lerp(a, b, u)
    return out


def build_pose(spec, t_abs=0.0):
    p = copy.deepcopy(BASE)
    tr = spec['tremble'] * math.sin(t_abs * 2 * math.pi * 18.0)
    pel = va(spec['pelvis'], [tr * .6, 0, tr])
    p['pelvis']['p'] = va(p['pelvis']['p'], pel)
    # body: twist (about up), lean (forward is negative about +X), side bend
    if spec['twist']:
        rotate(p, 'spine_02', [0, 0, 1], spec['twist'] * .4)
        rotate(p, 'spine_04', [0, 0, 1], spec['twist'] * .6)
    if spec['lean']:
        rotate(p, 'spine_02', [1, 0, 0], -spec['lean'] * .45)
        rotate(p, 'spine_04', [1, 0, 0], -spec['lean'] * .55)
    if spec['side']:
        rotate(p, 'spine_03', [0, 1, 0], spec['side'])
    if spec['nod']:
        rotate(p, 'neck_01', [1, 0, 0], -spec['nod'] * .5)
        rotate(p, 'head', [1, 0, 0], -spec['nod'] * .5)
    # legs stay planted (offsets move the feet)
    for s in 'lr':
        ik(p, 'thigh_' + s, 'calf_' + s, 'foot_' + s, va(FOOT0[s], spec['foot_' + s]), POLE_LEG[s])
    # arms
    for s in 'lr':
        ik(p, 'upperarm_' + s, 'lowerarm_' + s, 'hand_' + s, spec['hand_' + s], POLE_ARM[s])
    # the staff (right hand orientation)
    if spec['staff'] is not None and spec['staff_w'] > 1e-3 and STAFF:
        w = fk(p)
        q_ik = w['hand_r'][1]
        q_st = staff_hand_q(*spec['staff'])
        worldrot(p, 'hand_r', qslerp(q_ik, q_st, min(1.0, spec['staff_w'])))
    # keep the IK markers on the hands and feet (the mannequin's rig reads them)
    world = fk(p)
    for ikn, src in [('ik_hand_l', 'hand_l'), ('ik_hand_r', 'hand_r'), ('ik_foot_l', 'foot_l'), ('ik_foot_r', 'foot_r')]:
        if ikn not in p:
            continue
        parent = p[ikn]['parent']
        pw, pq = world[parent]
        p[ikn]['p'] = qr(qi(pq), vs(world[src][0], pw))
        p[ikn]['q'] = qm(qi(pq), world[src][1])
    return p


def staff_tip(p, length=95.0):
    """Where the staff points (for previews/tests): the hand plus the staff axis."""
    w = fk(p)
    q = w['hand_r'][1]
    d = qr(q, STAFF['staff_axis_in_quinn_hand'])
    return w['hand_r'][0], va(w['hand_r'][0], vm(d, length))


# ------------------------------------------------------------ the actions
H = lambda x, y, z: [x, y, z]
UP, FWD = [0, 0, 1], [0, 1, 0]
ACTIONS = {
    # the fire boy: the spell leaves at once, so he snaps straight into a big lunging
    # throw (arm flung out, off hand thrown back), shakes with it, then springs up
    # into a fist pump -- brash and loud
    'FireCast': (0.72, [
        (0.00, {}),
        (0.08, dict(pelvis=[0, 12, -16], twist=-40, lean=24, side=-4, hand_r=H(-2, 70, 146), hand_l=H(30, -30, 108),
                    foot_r=[-8, -16, 0], foot_l=[4, 14, 0], nod=4)),
        (0.26, dict(pelvis=[0, 14, -18], twist=-44, lean=26, side=-5, hand_r=H(0, 74, 150), hand_l=H(32, -32, 106),
                    foot_r=[-8, -16, 0], foot_l=[4, 14, 0], nod=4, tremble=1.0)),
        (0.46, dict(pelvis=[0, 4, 7], twist=-10, lean=-8, side=8, hand_r=H(-16, 14, 196), hand_l=H(26, 4, 96), nod=-16)),
        (0.58, dict(pelvis=[0, 4, 2], twist=-8, lean=-6, side=6, hand_r=H(-16, 16, 184), hand_l=H(26, 4, 98), nod=-12)),
        (0.70, dict(pelvis=[0, 4, 5], twist=-8, lean=-7, side=7, hand_r=H(-16, 14, 192), hand_l=H(26, 4, 97), nod=-14)),
        (1.00, {}),
    ]),
    # the ice girl: the staff thrusts at the target at once (the spell leaves its
    # crystal), holds, twirls back upright, settles
    'IceCast': (0.62, [
        (0.00, dict(staff=(UP, FWD), staff_w=0.0)),
        (0.10, dict(pelvis=[0, 6, -4], twist=-14, lean=8, hand_r=H(-12, 46, 128), hand_l=H(32, 6, 116),
                    staff=([.04, 1, .32], UP), staff_w=1.0)),
        (0.40, dict(pelvis=[0, 5, -3], twist=-10, lean=6, hand_r=H(-13, 44, 126), hand_l=H(31, 7, 114),
                    staff=([.04, 1, .36], UP), staff_w=1.0)),
        (0.66, dict(pelvis=[0, 0, 1], twist=4, hand_r=H(-22, 18, 126), hand_l=H(26, 12, 108),
                    staff=([.08, .30, 1], FWD), staff_w=1.0, nod=-4)),
        (1.00, dict(staff=(UP, FWD), staff_w=0.0)),
    ]),
    # the fire boy's ultimate: wide stance, charge at the hip (shaking), thrust both palms
    'FireUlt': (1.25, [
        (0.00, {}),
        (0.12, dict(pelvis=[0, -4, -14], twist=32, lean=4, hand_r=H(-30, -6, 104), hand_l=H(-14, 4, 106),
                    foot_r=[-14, -4, 0], foot_l=[10, 4, 0], tremble=0.6)),
        (0.58, dict(pelvis=[0, -6, -16], twist=36, lean=6, hand_r=H(-30, -8, 102), hand_l=H(-14, 2, 104),
                    foot_r=[-14, -4, 0], foot_l=[10, 4, 0], tremble=1.6, nod=8)),
        (0.68, dict(pelvis=[0, 14, -12], twist=-8, lean=16, hand_r=H(-8, 62, 128), hand_l=H(8, 62, 128),
                    foot_r=[-14, -4, 0], foot_l=[10, 4, 0])),
        (0.86, dict(pelvis=[0, 12, -10], twist=-6, lean=14, hand_r=H(-8, 60, 128), hand_l=H(8, 60, 128),
                    foot_r=[-14, -4, 0], foot_l=[10, 4, 0], tremble=0.8)),
        (1.00, {}),
    ]),
    # round 12: the fire boy's lightning volley -- one pose held for the whole volley
    # (palms pushed forward in a wide stance, a slight shake), not a throw per ball
    'FireVolley': (4.2, [
        (0.00, dict(pelvis=[0, 12, -12], twist=-8, lean=16, hand_r=H(-8, 62, 128), hand_l=H(8, 62, 128),
                    foot_r=[-14, -4, 0], foot_l=[10, 4, 0])),
        (0.05, dict(pelvis=[0, 12, -12], twist=-8, lean=16, hand_r=H(-8, 62, 128), hand_l=H(8, 62, 128),
                    foot_r=[-14, -4, 0], foot_l=[10, 4, 0], tremble=0.5)),
        (0.95, dict(pelvis=[0, 12, -12], twist=-8, lean=16, hand_r=H(-8, 62, 128), hand_l=H(8, 62, 128),
                    foot_r=[-14, -4, 0], foot_l=[10, 4, 0], tremble=0.5)),
        (1.00, dict(pelvis=[0, 12, -12], twist=-8, lean=16, hand_r=H(-8, 62, 128), hand_l=H(8, 62, 128),
                    foot_r=[-14, -4, 0], foot_l=[10, 4, 0])),
    ]),
    # the ice girl's ultimate: staff overhead, twirl and charge, slam it down -> burst
    'IceUlt': (1.20, [
        (0.00, dict(staff=(UP, FWD), staff_w=0.0)),
        (0.13, dict(pelvis=[0, 0, 4], hand_r=H(-8, 14, 182), hand_l=H(10, 14, 170), staff=([0, 0, 1], FWD), staff_w=1.0, nod=-10)),
        (0.30, dict(pelvis=[0, 0, 6], hand_r=H(-6, 12, 186), hand_l=H(12, 12, 172), staff=([.35, .1, .93], FWD), staff_w=1.0, nod=-12,
                    side=-6)),
        (0.45, dict(pelvis=[0, 0, 6], hand_r=H(-10, 16, 186), hand_l=H(14, 10, 172), staff=([-.3, -.25, .92], FWD), staff_w=1.0, nod=-12,
                    side=6)),
        (0.60, dict(pelvis=[0, 0, 7], hand_r=H(-8, 14, 188), hand_l=H(12, 14, 174), staff=([0, .1, 1], FWD), staff_w=1.0, nod=-14)),
        (0.68, dict(pelvis=[0, 6, -22], lean=18, hand_r=H(-12, 42, 104), hand_l=H(44, 2, 128), staff=([0, .3, -1], FWD), staff_w=1.0,
                    foot_r=[-8, 0, 0], foot_l=[8, 0, 0])),
        (0.86, dict(pelvis=[0, 5, -20], lean=16, hand_r=H(-12, 40, 104), hand_l=H(44, 2, 130), staff=([0, .3, -1], FWD), staff_w=1.0,
                    foot_r=[-8, 0, 0], foot_l=[8, 0, 0])),
        (1.00, dict(staff=(UP, FWD), staff_w=0.0)),
    ]),
    # the wind boy's ultimate: ninja hand seal in a low stance, then the dash pose
    'WindUlt': (1.00, [
        (0.00, {}),
        (0.14, dict(pelvis=[0, -2, -22], lean=10, hand_r=H(-3, 24, 128), hand_l=H(3, 24, 128), foot_r=[-12, -6, 0], foot_l=[12, 4, 0],
                    nod=10)),
        (0.52, dict(pelvis=[0, -2, -24], lean=12, hand_r=H(-3, 26, 130), hand_l=H(3, 26, 130), foot_r=[-12, -6, 0], foot_l=[12, 4, 0],
                    nod=12, tremble=0.4)),
        (0.70, dict(pelvis=[0, 14, -26], lean=38, hand_r=H(-24, -40, 100), hand_l=H(24, -40, 100), foot_r=[-10, -18, 0],
                    foot_l=[10, 14, 0], nod=-6)),
        (1.00, dict(pelvis=[0, 14, -26], lean=38, hand_r=H(-24, -40, 100), hand_l=H(24, -40, 100), foot_r=[-10, -18, 0],
                    foot_l=[10, 14, 0], nod=-6)),
    ]),
    # the wind boy coming out of the orb dash: a ninja landing (crouched, one hand to
    # the ground, the other arm swept back), then he stands up with his arms crossed
    'WindLand': (0.80, [
        (0.00, dict(pelvis=[0, 6, -30], lean=28, twist=10, hand_r=H(-14, 36, 22), hand_l=H(36, -34, 118),
                    foot_r=[-10, -16, 0], foot_l=[10, 14, 0], nod=-14)),
        (0.32, dict(pelvis=[0, 4, -24], lean=22, twist=8, hand_r=H(-14, 34, 30), hand_l=H(36, -30, 120),
                    foot_r=[-10, -16, 0], foot_l=[10, 14, 0], nod=-12)),
        (0.62, dict(pelvis=[0, 0, 1], lean=-4, hand_r=H(10, 18, 118), hand_l=H(-10, 18, 115), nod=-6)),
        (0.84, dict(pelvis=[0, 0, 0], lean=-3, hand_r=H(10, 18, 118), hand_l=H(-10, 18, 115), nod=-5)),
        (1.00, {}),
    ]),
    # the lightning girl's ultimate: arms up to the sky, then point down at the spot
    'LightningUlt': (1.10, [
        (0.00, {}),
        (0.14, dict(pelvis=[0, 0, 3], lean=-10, hand_r=H(-34, 6, 196), hand_l=H(34, 6, 196), nod=-16)),
        (0.56, dict(pelvis=[0, 0, 4], lean=-12, side=4, hand_r=H(-36, 4, 198), hand_l=H(36, 4, 198), nod=-18, tremble=0.3)),
        (0.68, dict(pelvis=[0, 6, -6], lean=12, twist=-10, hand_r=H(-10, 58, 118), hand_l=H(22, -6, 102), nod=6)),
        (0.88, dict(pelvis=[0, 6, -5], lean=10, twist=-8, hand_r=H(-10, 56, 120), hand_l=H(22, -6, 102), nod=6)),
        (1.00, {}),
    ]),
    # the lightning girl arriving from a blink: a crouched landing, then a cute V
    'LightningBlink': (0.50, [
        (0.00, dict(pelvis=[0, 6, -20], lean=22, hand_r=H(-26, 34, 66), hand_l=H(30, -26, 118), foot_r=[-6, -8, 0], foot_l=[8, 6, 0])),
        (0.16, dict(pelvis=[0, 4, -18], lean=18, hand_r=H(-26, 32, 70), hand_l=H(30, -24, 118), foot_r=[-6, -8, 0], foot_l=[8, 6, 0])),
        (0.42, dict(pelvis=[0, 0, 3], side=-8, hand_r=H(-14, 22, 160), hand_l=H(24, -4, 100), nod=-4)),
        (0.62, dict(pelvis=[0, 0, 2], side=-6, hand_r=H(-14, 22, 158), hand_l=H(24, -4, 100), nod=-4)),
        (1.00, {}),
    ]),
    # the ice girl hovering: held up by her staff, raised over her head; legs dangle
    'IceHover': (1.60, [
        (0.00, dict(pelvis=[0, 0, 0], hand_r=H(-8, 8, 192), hand_l=H(36, 6, 124), foot_r=[0, -8, 16], foot_l=[0, 4, 12],
                    staff=([0, .06, 1], FWD), staff_w=1.0, nod=-6)),
        (0.50, dict(pelvis=[0, 0, 3], hand_r=H(-8, 8, 194), hand_l=H(36, 8, 128), foot_r=[0, -6, 18], foot_l=[0, 6, 10],
                    staff=([0, .06, 1], FWD), staff_w=1.0, nod=-6)),
        (1.00, dict(pelvis=[0, 0, 0], hand_r=H(-8, 8, 192), hand_l=H(36, 6, 124), foot_r=[0, -8, 16], foot_l=[0, 4, 12],
                    staff=([0, .06, 1], FWD), staff_w=1.0, nod=-6)),
    ]),
}


def action_frames(name, fps=30):
    dur, keys = ACTIONS[name]
    n = max(2, int(round(dur * fps)) + 1)
    frames = []
    for i in range(n):
        t = i / (n - 1)
        frames.append(build_pose(spec_at(keys, t), t * dur))
    return dur, frames
