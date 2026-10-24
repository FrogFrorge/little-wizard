"""Cute sprite shapes for round 11's magic effects, in two forms that match line
for line: numpy (this file renders preview sheets) and HLSL (r11_vfx.py puts the
same formulas into Unreal Custom material nodes).

Each sprite: p in [-1, 1]^2 (y up), age 0..1 (particle life), rnd 0..1, t (s).
Style: sticker / toy -- chunky rounded shapes, coloured outline, two-tone fill,
a white gloss dot, a soft glow; pop in with a little overshoot, shrink + fade out.
"""
import numpy as np

PAL = {
    # outline, base, light, core, glow -- saturated fills, darker outlines: the arenas are bright
    'Fire': ((0.62, 0.10, 0.05), (1.00, 0.38, 0.06), (1.00, 0.66, 0.12), (1.00, 0.90, 0.45), (1.00, 0.45, 0.10)),
    'Ice': ((0.25, 0.25, 0.80), (0.35, 0.65, 1.00), (0.62, 0.86, 1.00), (0.92, 0.97, 1.00), (0.45, 0.72, 1.00)),
    'Wind': ((0.04, 0.45, 0.32), (0.20, 0.82, 0.52), (0.55, 0.98, 0.72), (0.88, 1.00, 0.90), (0.35, 0.95, 0.62)),
    'Lightning': ((0.38, 0.16, 0.80), (1.00, 0.78, 0.05), (1.00, 0.92, 0.35), (1.00, 1.00, 0.75), (0.70, 0.55, 1.00)),
}


# ---------------------------------------------------------------- numpy SDFs
def length(x, y):
    return np.sqrt(x * x + y * y)


def sd_circle(x, y, r):
    return length(x, y) - r


def sd_segment(x, y, ax, ay, bx, by, r):
    px, py = x - ax, y - ay
    vx, vy = bx - ax, by - ay
    h = np.clip((px * vx + py * vy) / (vx * vx + vy * vy + 1e-9), 0, 1)
    return length(px - vx * h, py - vy * h) - r


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def sd_star(x, y, r, n, m):
    """iq's star: n points, m in [2, n] (sharpness)."""
    an = np.pi / n
    en = np.pi / m
    acx, acy = np.cos(an), np.sin(an)
    ecx, ecy = np.cos(en), np.sin(en)
    bn = np.mod(np.arctan2(x, y), 2 * an) - an
    l = length(x, y)
    px, py = l * np.cos(bn), l * np.abs(np.sin(bn))
    px, py = px - r * acx, py - r * acy
    c = np.clip(-(px * ecx + py * ecy), 0, r * acy / ecy)
    px, py = px + ecx * c, py + ecy * c
    return length(px, py) * np.sign(px)


def sd_uneven_capsule(x, y, r1, r2, h):
    x = np.abs(x)
    b = (r1 - r2) / h
    a = np.sqrt(1 - b * b)
    k = -b * x + a * y
    d1 = length(x, y) - r1
    d2 = length(x, y - h) - r2
    d3 = x * a + y * b - r1
    return np.where(k < 0, d1, np.where(k > a * h, d2, d3))


def rot(x, y, ang):
    c, s = np.cos(ang), np.sin(ang)
    return c * x - s * y, s * x + c * y


# ---------------------------------------------------------------- shapes
def shape_flame(x, y, t, rnd):
    """A plump flame drop pointing up, gently licking."""
    w = 0.07 * np.sin(y * 4.0 + t * 9.0 + rnd * 6.28) * np.clip(y + 0.3, 0, 1)
    d = sd_uneven_capsule(x - w, y + 0.42, 0.50, 0.06, 1.25)
    inner = sd_uneven_capsule(x - w * 1.4, y + 0.40, 0.27, 0.03, 0.80)
    return d, inner


def shape_snowflake(x, y, t, rnd):
    a = np.arctan2(y, x) + rnd * 6.28
    r = length(x, y)
    a = np.mod(a + np.pi / 6, np.pi / 3) - np.pi / 6
    qx, qy = r * np.cos(a), np.abs(r * np.sin(a))
    d = sd_segment(qx, qy, 0, 0, 0.74, 0, 0.085)
    c60, s60 = 0.5, 0.866
    d = np.minimum(d, sd_segment(qx, qy, 0.40, 0, 0.40 + 0.26 * c60, 0.26 * s60, 0.07))
    d = np.minimum(d, sd_segment(qx, qy, 0.60, 0, 0.60 + 0.15 * c60, 0.15 * s60, 0.06))
    d = np.minimum(d, sd_circle(qx - 0.80, qy, 0.11))
    d = smin(d, sd_circle(x, y, 0.22), 0.08)
    inner = sd_circle(x, y, 0.10)
    return d, inner


def shape_curl(x, y, t, rnd):
    """Cartoon wind: a stroke that runs in and rolls up into a curl."""
    d = sd_segment(x, y, -0.88, -0.30, 0.10, -0.30, 0.085)
    # spiral around (0.18, 0.05): r = 0.35 - 0.045 * theta, theta from -pi/2 (joins the stroke) up to 2.2 pi
    cx, cy = x - 0.12, y - 0.06
    th = np.arctan2(cy, cx)                 # -pi..pi
    best = np.full_like(x, 9.0)
    for k in range(-1, 3):
        tt = th + 2 * np.pi * k
        ok = (tt >= -np.pi / 2) & (tt <= 2.6 * np.pi)
        rr = 0.36 - 0.05 * (tt + np.pi / 2)
        dd = np.abs(length(cx, cy) - rr) - 0.085 * np.clip(rr / 0.36 + 0.25, 0.3, 1.0)
        best = np.where(ok, np.minimum(best, dd), best)
    d = np.minimum(d, best)
    d = np.minimum(d, sd_circle(x + 0.88, y + 0.30, 0.09))
    return d, d + 0.05


def shape_bolt(x, y, t, rnd):
    """A chunky zigzag bolt icon."""
    pts = [(0.30, 0.92), (-0.22, 0.10), (0.20, 0.06), (-0.30, -0.92)]
    d = np.full_like(x, 9.0)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        d = np.minimum(d, sd_segment(x, y, ax, ay, bx, by, 0.15))
    inner = np.full_like(x, 9.0)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        inner = np.minimum(inner, sd_segment(x, y, ax, ay, bx, by, 0.05))
    return d, inner


def shape_twinkle(x, y, t, rnd):
    """Slim four-point sparkle (concave sides)."""
    ax, ay = np.abs(x), np.abs(y)
    d = (np.power(ax, 0.62) + np.power(ay, 0.62)) ** (1 / 0.62) - 0.92
    d = d * 0.55
    inner = sd_circle(x, y, 0.13)
    return d, inner


def shape_puff(x, y, t, rnd):
    """A round fluffy cloud ball: a centre plus six bumps."""
    d = sd_circle(x, y, 0.52)
    for k in range(6):
        a = k * np.pi / 3 + rnd * 1.5
        d = smin(d, sd_circle(x - 0.42 * np.cos(a), y - 0.42 * np.sin(a), 0.30), 0.10)
    inner = sd_circle(x + 0.12, y - 0.10, 0.30)
    return d, inner


def burst_fire(x, y, t, rnd):
    d = sd_star(x, y, 0.92, 8, 3.0) - 0.07
    return d, sd_circle(x, y, 0.36)


def burst_ice(x, y, t, rnd):
    d = sd_star(x, y, 0.95, 6, 2.6) - 0.08
    s, _ = shape_snowflake(x / 0.55, y / 0.55, t, rnd)
    return d, s * 0.55 + 0.02


def burst_wind(x, y, t, rnd):
    """A swirl flower: four plump blades curving round a core."""
    a = np.arctan2(y, x)
    r = length(x, y)
    edge = 0.66 + 0.24 * np.sin(4.0 * (a + 2.4 * r) + rnd * 6.28)
    d = (r - edge) * 0.8
    inner = r - (0.30 + 0.06 * np.sin(4.0 * (a + 2.4 * r)))
    return d, inner


def burst_lightning(x, y, t, rnd):
    """A spiky electric star (ten points) with a round core."""
    d = sd_star(x, y, 0.96, 10, 2.5) - 0.05
    return d, sd_circle(x, y, 0.34)


BURST = {'Fire': burst_fire, 'Ice': burst_ice, 'Wind': burst_wind, 'Lightning': burst_lightning}


def shape_burst(x, y, t, rnd):
    return burst_fire(x, y, t, rnd)


def orb_with(motif):
    def f(x, y, t, rnd):
        d = sd_circle(x, y, 0.80)
        m, _ = SHAPES[motif](x / 0.5, y / 0.5, t, rnd)
        return d, m * 0.5
    return f


def shape_orb(x, y, t, rnd):
    d = sd_circle(x, y, 0.80)
    inner = sd_circle(x + 0.10, y + 0.10, 0.48)
    return d, inner


def shape_ring(x, y, t, rnd):
    d = np.abs(length(x, y) - 0.80) - 0.07
    return d, d + 0.04


SHAPES = {'flame': shape_flame, 'snowflake': shape_snowflake, 'curl': shape_curl, 'bolt': shape_bolt,
          'twinkle': shape_twinkle, 'puff': shape_puff, 'burst': shape_burst, 'orb': shape_orb, 'ring': shape_ring}
MOTIF = {'Fire': 'flame', 'Ice': 'snowflake', 'Wind': 'curl', 'Lightning': 'bolt'}
for _e, _m in list(MOTIF.items()):
    SHAPES['orb_' + _e] = orb_with(_m)
    SHAPES['burst_' + _e] = BURST[_e]


def sticker(d, inner, x, y, pal, gloss=True, glow=0.35, aa=0.03):
    """Coloured outline, two-tone fill (light top-left), bright inner core, gloss dot, glow."""
    out, base, light, core, glw = [np.array(c)[None, None, :] for c in pal]
    fill = np.clip(0.5 - d / aa, 0, 1)
    edge = np.clip(0.5 - (d + 0.075) / aa, 0, 1)       # inside the outline band
    grad = np.clip(0.5 + 0.55 * (y - x) * 0.7, 0, 1)
    col = out * (1 - edge[..., None]) + (base * (1 - grad[..., None]) + light * grad[..., None]) * edge[..., None]
    cmask = np.clip(0.5 - inner / aa, 0, 1)
    col = col * (1 - cmask[..., None]) + core * cmask[..., None]
    if gloss:
        gd = length((x + 0.30) / 1.3, (y - 0.34) / 0.85) - 0.11
        gm = np.clip(0.5 - gd / aa, 0, 1) * edge
        col = col * (1 - gm[..., None]) + np.array([1, 1, 1])[None, None, :] * gm[..., None]
    ga = glow * np.exp(-np.maximum(d, 0) * 7.0) * (1 - fill)
    alpha = np.clip(fill + ga, 0, 1)
    col = col * fill[..., None] + glw * (ga[..., None]) / np.maximum(alpha[..., None], 1e-4) * (1 - fill[..., None])
    return col, alpha


def pop_scale(age):
    """Pop in with an overshoot, settle, shrink a little at the end."""
    grow = np.clip(age / 0.16, 0, 1)
    over = 1 + 0.28 * np.sin(np.clip(age / 0.30, 0, 1) * np.pi)
    late = 1 - 0.35 * np.clip((age - 0.65) / 0.35, 0, 1)
    return max(grow * over * late, 0.03)


def fade(age):
    return 1 - np.clip((age - 0.70) / 0.30, 0, 1)


def render(shape, pal, age=0.4, t=0.0, rnd=0.3, n=192, spin=0.0, gloss=True, glow=0.35):
    s = np.linspace(-1, 1, n)
    x, y = np.meshgrid(s, -s)
    k = pop_scale(age)
    x, y = rot(x / k, y / k, -(rnd * 6.28 * spin))
    d, inner = SHAPES[shape](x, y, t, rnd)
    col, a = sticker(d, inner, x, y, pal, gloss, glow)
    return col, a * fade(age)
