"""Round 11: cute magic effects (materials + Niagara systems).

Sprites are drawn by Custom material nodes with the shapes of r11_cute_shapes.py
(sticker style: coloured outline, two-tone fill, gloss dot, soft glow; pop in
with an overshoot, shrink + fade out over the particle's life).

/Game/VFX/WizardMagic/Cute/Materials   M_Cute_<El>_{Orb,Bit,Burst,Puff}, M_Cute_{Twinkle,Ring,Glow},
                                       M_Cute_Tele_{Lane,Circle}_<El>, M_Cute_IceHalo (decal), M_Cute_AimCircle
/Game/VFX/WizardMagic/Cute/Systems     NS_Cute_<El>_{Bullet,Cast,Pop,BigPop,Charge,UltCore,DashOrb},
                                       NS_Cute_WindAura, NS_Cute_WindBulletAura, NS_Cute_IceStaff, NS_Cute_IceHover,
                                       NS_Cute_FireHype

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r11_vfx.py
"""
import unreal as u
import json
import os
import sys
import traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.append('C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/FX/CascadeToNiagaraConverter/Content/Python')
import Paths as P

F = getattr(u, 'FXConverterUtilitiesLibrary', None)      # from the CascadeToNiagaraConverter plugin
A = u.AssetToolsHelpers.get_asset_tools()
M = u.MaterialEditingLibrary
EAL = u.EditorAssetLibrary
BASE = '/Game/VFX/WizardMagic/Cute'
OUT = ROOT / 'output/round11'
OUT.mkdir(parents=True, exist_ok=True)
REPORT = {'materials': [], 'systems': [], 'warnings': []}
ELS = ['Fire', 'Ice', 'Wind', 'Lightning']
# outline, base, light, core, glow  (linear-ish; sprites are unlit emissive)
PAL = {
    # outline, base, light, core, glow -- saturated fills, darker outlines: the arenas are bright
    # (v3: ice / wind / lightning fills were washing out to white in game -> deeper bases)
    'Fire': ((0.62, 0.10, 0.05), (1.00, 0.38, 0.06), (1.00, 0.66, 0.12), (1.00, 0.90, 0.45), (1.00, 0.45, 0.10)),
    'Ice': ((0.20, 0.22, 0.85), (0.12, 0.42, 1.00), (0.36, 0.70, 1.00), (0.88, 0.96, 1.00), (0.40, 0.66, 1.00)),
    'Wind': ((0.02, 0.40, 0.26), (0.06, 0.62, 0.32), (0.30, 0.88, 0.52), (0.82, 1.00, 0.86), (0.30, 0.90, 0.55)),
    'Lightning': ((0.36, 0.12, 0.78), (0.95, 0.62, 0.02), (1.00, 0.84, 0.18), (1.00, 0.98, 0.66), (0.70, 0.55, 1.00)),
}
MOTIF = {'Fire': 'flame', 'Ice': 'snowflake', 'Wind': 'curl', 'Lightning': 'bolt'}
GAIN = 1.5           # emissive gain of the sticker colours


def f3(c, k=1.0):
    return 'float3(%.3f,%.3f,%.3f)' % tuple(x * k for x in c)


# ===================================================================== HLSL
FN = r'''
struct CuteFn {
  float pmod(float x, float m) { return x - m * floor(x / m); }
  float2 rot(float2 p, float a) { float c = cos(a), s = sin(a); return float2(c * p.x - s * p.y, s * p.x + c * p.y); }
  float sdCircle(float2 p, float r) { return length(p) - r; }
  float sdSeg(float2 p, float2 a, float2 b, float r) {
    float2 pa = p - a, ba = b - a; float h = saturate(dot(pa, ba) / max(dot(ba, ba), 1e-6)); return length(pa - ba * h) - r; }
  float smin(float a, float b, float k) { float h = saturate(0.5 + 0.5 * (b - a) / k); return lerp(b, a, h) - k * h * (1 - h); }
  float sdStar(float2 p, float r, float n, float m) {
    float an = 3.141593 / n; float en = 3.141593 / m;
    float2 acs = float2(cos(an), sin(an)); float2 ecs = float2(cos(en), sin(en));
    float bn = pmod(atan2(p.x, p.y), 2.0 * an) - an;
    p = length(p) * float2(cos(bn), abs(sin(bn)));
    p -= r * acs;
    p += ecs * clamp(-dot(p, ecs), 0.0, r * acs.y / ecs.y);
    return length(p) * sign(p.x); }
  float sdUCap(float2 p, float r1, float r2, float h) {
    p.x = abs(p.x); float b = (r1 - r2) / h; float a = sqrt(1.0 - b * b); float k = dot(p, float2(-b, a));
    if (k < 0.0) return length(p) - r1;
    if (k > a * h) return length(p - float2(0.0, h)) - r2;
    return dot(p, float2(a, b)) - r1; }
  float2 flame(float2 p, float t, float rnd) {
    float w = 0.07 * sin(p.y * 4.0 + t * 9.0 + rnd * 6.28) * saturate(p.y + 0.3);
    return float2(sdUCap(float2(p.x - w, p.y + 0.42), 0.50, 0.06, 1.25), sdUCap(float2(p.x - w * 1.4, p.y + 0.40), 0.27, 0.03, 0.80)); }
  float2 snowflake(float2 p, float t, float rnd) {
    float a = atan2(p.y, p.x) + rnd * 6.28; float r = length(p);
    a = pmod(a + 0.5236, 1.0472) - 0.5236;
    float2 q = float2(r * cos(a), abs(r * sin(a)));
    float d = sdSeg(q, float2(0, 0), float2(0.74, 0), 0.085);
    d = min(d, sdSeg(q, float2(0.40, 0), float2(0.53, 0.225), 0.07));
    d = min(d, sdSeg(q, float2(0.60, 0), float2(0.675, 0.13), 0.06));
    d = min(d, sdCircle(q - float2(0.80, 0), 0.11));
    d = smin(d, sdCircle(p, 0.22), 0.08);
    return float2(d, sdCircle(p, 0.10)); }
  float2 curl(float2 p, float t, float rnd) {
    float d = sdSeg(p, float2(-0.88, -0.30), float2(0.10, -0.30), 0.085);
    float2 c = p - float2(0.12, 0.06); float th = atan2(c.y, c.x); float best = 9.0;
    [unroll] for (int k = -1; k < 3; k++) {
      float tt = th + 6.283185 * k;
      float rr = 0.36 - 0.05 * (tt + 1.570796);
      float dd = abs(length(c) - rr) - 0.085 * clamp(rr / 0.36 + 0.25, 0.3, 1.0);
      if (tt >= -1.570796 && tt <= 8.168) best = min(best, dd); }
    d = min(d, best);
    d = min(d, sdCircle(p + float2(0.88, 0.30), 0.09));
    return float2(d, d + 0.05); }
  float2 bolt(float2 p, float t, float rnd) {
    float2 a = float2(0.30, 0.92), b = float2(-0.22, 0.10), c = float2(0.20, 0.06), e = float2(-0.30, -0.92);
    float d = min(min(sdSeg(p, a, b, 0.19), sdSeg(p, b, c, 0.19)), sdSeg(p, c, e, 0.19));
    float i = min(min(sdSeg(p, a, b, 0.065), sdSeg(p, b, c, 0.065)), sdSeg(p, c, e, 0.065));
    return float2(d, i); }
  float2 twinkle(float2 p) {
    float2 q = abs(p); float d = pow(pow(q.x + 1e-4, 0.62) + pow(q.y + 1e-4, 0.62), 1.0 / 0.62) - 0.92;
    return float2(d * 0.55, sdCircle(p, 0.13)); }
  float2 puff(float2 p, float rnd) {
    float d = sdCircle(p, 0.52);
    [unroll] for (int k = 0; k < 6; k++) { float a = k * 1.047198 + rnd * 1.5; d = smin(d, sdCircle(p - 0.42 * float2(cos(a), sin(a)), 0.30), 0.10); }
    return float2(d, sdCircle(p + float2(0.12, -0.10), 0.30)); }
  float2 motif(int m, float2 p, float t, float rnd) {
    if (m == 0) return flame(p, t, rnd);
    if (m == 1) return snowflake(p, t, rnd);
    if (m == 2) return curl(p, t, rnd);
    return bolt(p, t, rnd); }
  float2 burst(int m, float2 p, float t, float rnd) {
    if (m == 0) return float2(sdStar(p, 0.92, 8.0, 3.0) - 0.07, sdCircle(p, 0.36));
    if (m == 1) { float2 s = snowflake(p / 0.55, t, rnd); return float2(sdStar(p, 0.95, 6.0, 2.6) - 0.08, s.x * 0.55 + 0.02); }
    if (m == 2) { float a = atan2(p.y, p.x); float r = length(p);
      return float2((r - (0.66 + 0.24 * sin(4.0 * (a + 2.4 * r) + rnd * 6.28))) * 0.8, r - (0.30 + 0.06 * sin(4.0 * (a + 2.4 * r)))); }
    return float2(sdStar(p, 0.96, 10.0, 2.25) - 0.05, sdCircle(p, 0.34)); }
  float4 sticker(float2 dd, float2 p, float3 o, float3 b, float3 l, float3 c, float3 g, float glow, float gloss, float gw) {
    float aa = 0.03; float d = dd.x;
    float fill = saturate(0.5 - d / aa);
    float edge = saturate(0.5 - (d + 0.075) / aa);
    float grad = saturate(0.5 + 0.385 * (p.y - p.x));
    float3 col = lerp(o, lerp(b, l, grad), edge);
    col = lerp(col, c, saturate(0.5 - dd.y / aa));
    float gd = length(float2((p.x + 0.30) / 1.3, (p.y - 0.34) / 0.85)) - 0.11;
    col = lerp(col, float3(1, 1, 1), saturate(0.5 - gd / aa) * edge * gloss);
    float ga = glow * exp(-max(d, 0.0) * 7.0) * (1 - fill) * gw;
    float alpha = saturate(fill + ga);
    col = col * fill + g * ga / max(alpha, 1e-4) * (1 - fill);
    return float4(col, alpha); }
  float pop(float age) {
    float grow = saturate(age / 0.16); float over = 1 + 0.28 * sin(saturate(age / 0.30) * 3.141593);
    float late = 1 - 0.35 * saturate((age - 0.65) / 0.35); return max(grow * over * late, 0.03); }
  float fade(float age) { return 1 - saturate((age - 0.70) / 0.30); }
  // fades everything out before the sprite square's edge (no straight cut lines)
  float win(float2 p) { return 1 - smoothstep(0.86, 1.0, max(abs(p.x), abs(p.y))); }
  // the glow around a shape: round, gone before the square's edge (else it shows as a square halo)
  float gwin(float2 p) { return 1 - smoothstep(0.62, 0.95, length(p)); }
};
CuteFn f;
float2 p = (UV - 0.5) * float2(2.0, -2.0);
float age = saturate(Age);
'''


def palette_args(el, light=False):
    o, b, l, c, g = PAL[el]
    if light:                                   # puffs: one step lighter
        o, b, l = b, l, c
    return '%s, %s, %s, %s, %s' % (f3(o, GAIN), f3(b, GAIN), f3(l, GAIN), f3(c, GAIN), f3(g, GAIN))


def code_for(kind, el=None):
    m = ELS.index(el) if el else 0
    # (v3: shapes are scaled so the pop-in overshoot (x1.28) stays inside the sprite's
    #  square -- it used to be cut off in straight lines; emitter() makes the sprites
    #  bigger by FIT to keep the size)
    if kind == 'Bit':          # trail bits / confetti: pop, spin, fade
        return FN + '''
float k = f.pop(age) * (0.75 + 0.25 * Rand) * 0.80;
float2 q = f.rot(p / k, -(Rand * 6.28 + age * (Rand - 0.5) * 6.0));
float4 s = f.sticker(f.motif(%d, q, T, Rand), q, %s, 0.30, 1.0, f.gwin(p));
return float4(s.rgb, s.a * f.fade(age) * PA * f.win(p));''' % (m, palette_args(el))
    if kind == 'Orb':          # bullet core: breathes, the motif turns / flickers
        return FN + '''
float k = 1.0 + 0.045 * sin(T * 9.0 + Rand * 6.28);
float2 q = p / k;
float2 o = float2(f.sdCircle(q, 0.80), 9.0);
float2 mq = f.rot(q, %s) / 0.5;
float2 mm = f.motif(%d, mq, T, 0.0) * 0.5;
o.y = mm.x;
float4 s = f.sticker(o, q, %s, 0.45, 1.0, f.gwin(p));
return float4(s.rgb, s.a * PA * f.win(p));''' % ('T * 2.5' if el == 'Wind' else ('sin(T * 3.0) * 0.25' if el != 'Ice' else 'T * 0.8'), m, palette_args(el))
    if kind == 'Burst':        # impact / cast flash: fast pop, fade
        return FN + '''
float a2 = saturate(age * 1.25);
float k = f.pop(a2) * 0.765;
float2 q = f.rot(p / k, Rand * 1.5 + age * 0.8);
float4 s = f.sticker(f.burst(%d, q, T, Rand), q, %s, 0.40, 1.0, f.gwin(p));
return float4(s.rgb, s.a * f.fade(age) * PA * f.win(p));''' % (m, palette_args(el))
    if kind == 'Puff':
        return FN + '''
float k = f.pop(age) * (0.8 + 0.2 * Rand);
float2 q = p / k;
float4 s = f.sticker(f.puff(q, Rand), q, %s, 0.20, 1.0, f.gwin(p));
return float4(s.rgb, s.a * f.fade(age) * PA * f.win(p));''' % palette_args(el, light=True)
    if kind == 'Twinkle':      # tinted by the particle colour
        return FN + '''
float k = f.pop(age) * (0.7 + 0.3 * Rand) * 0.80;
float2 q = f.rot(p / k, Rand * 0.6 + age * 2.0 * (Rand - 0.5));
float3 b = PCol.rgb * 1.25;
float4 s = f.sticker(f.twinkle(q), q, b * 0.55, b, lerp(b, float3(1.25, 1.25, 1.25), 0.55), float3(1.3, 1.3, 1.3), b, 0.45, 0.0, f.gwin(p));
return float4(s.rgb, s.a * f.fade(age) * PA * f.win(p));'''
    if kind == 'Ring':         # expanding shock ring, tinted
        return FN + '''
float r = 0.23 + 0.62 * (1 - pow(1 - age, 3.0));
float w = 0.10 * (1 - age) + 0.02;
float d = abs(length(p) - r) - w;
float3 b = PCol.rgb * 1.25;
float4 s = f.sticker(float2(d, d + w * 0.5), p, b * 0.6, b, lerp(b, float3(1.2, 1.2, 1.2), 0.5), float3(1.2, 1.2, 1.2), b, 0.5, 0.0, f.gwin(p));
return float4(s.rgb, s.a * (1 - age) * PA * f.win(p));'''
    if kind == 'Glow':         # soft round glow, tinted (auras, charge, orb halos)
        return FN + '''
float r = length(p);
float a = exp(-r * r * 4.5) * (1 - smoothstep(0.85, 1.0, r));
float pulse = 0.85 + 0.15 * sin(T * 6.0 + Rand * 6.28);
return float4(PCol.rgb * 1.4, a * pulse * PA * (age < 0.999 ? (1 - saturate((age - 0.7) / 0.3)) : 1));'''
    raise ValueError(kind)


TELE_LANE = FN + r'''
// the plane is long along U (x): chevrons running forward, dashed edges, a soft fill
float2 uv = UV;
float across = abs(uv.y - 0.5) * 2.0;
float fill = 0.10 * (1 - across * across);
float edge = smoothstep(0.80, 0.86, across) * (1 - smoothstep(0.94, 0.99, across));
float dash = step(0.35, frac(uv.x * 26.0 - T * 1.6));
float chevx = frac(uv.x * 13.0 - T * 1.2);
float chev = abs(chevx - 0.5 - 0.30 * (1 - across)) ;
float chevm = (1 - smoothstep(0.05, 0.09, chev)) * (1 - smoothstep(0.55, 0.62, across));
float pulse = 0.75 + 0.25 * sin(T * 7.0);
float a = saturate(fill + edge * dash * 0.85 + chevm * 0.55) * pulse;
float3 col = lerp(%s, %s, edge * dash + chevm * 0.6);
return float4(col, a);'''

TELE_CIRCLE = FN + r'''
float r = length(p);
float ang = atan2(p.y, p.x);
float ringo = 1 - smoothstep(0.035, 0.05, abs(r - 0.92));
float dash = step(0.4, frac((ang + T * 0.9) / 6.283185 * 24.0));
float ringi = (1 - smoothstep(0.02, 0.035, abs(r - 0.70))) * 0.5;
float fill = 0.12 * (1 - smoothstep(0.80, 0.95, r)) * (0.6 + 0.4 * sin(r * 18.0 - T * 6.0));
float2 icon = f.motif(%d, f.rot(p, T * 0.6) / 0.28, T, 0.0) * 0.28;
float im = saturate(0.5 - icon.x / 0.02) * 0.65;
float pulse = 0.8 + 0.2 * sin(T * 7.0);
float a = saturate(ringo * dash + ringi + fill + im) * pulse * (1 - smoothstep(0.97, 1.0, r));
float3 col = lerp(%s, %s, saturate(ringo * dash + im));
return float4(col, a);'''

ICE_HALO = FN + r'''
// decal UV: the slow-down zone -- a faint snowy ring with little flakes riding round
float2 q = p;
float r = length(q);
float ring = (1 - smoothstep(0.012, 0.03, abs(r - 0.94))) * 0.45;
float inner = 0.05 * smoothstep(0.45, 0.94, r) * (1 - smoothstep(0.94, 0.99, r));
float ang = atan2(q.y, q.x) + T * 0.25;
float seg = f.pmod(ang, 0.5236) - 0.2618;
float2 fq = float2(r - 0.82, seg * r) / 0.06;
float2 fl = f.snowflake(fq, T, 0.0) * 0.06;
float flake = saturate(0.5 - fl.x / 0.008) * 0.35;
float a = saturate(ring + inner + flake) * (1 - smoothstep(0.985, 1.0, r));
return float4(float3(0.80, 0.90, 1.30), a * 0.32);'''

AIM_CIRCLE = FN + r'''
float r = length(p);
float ang = atan2(p.y, p.x);
float ring = (1 - smoothstep(0.03, 0.05, abs(r - 0.90))) * step(0.3, frac((ang - T * 1.2) / 6.283185 * 16.0));
float2 st = f.twinkle(f.rot(p, T) / 0.35) * 0.35;
float star = saturate(0.5 - st.x / 0.02);
float fill = 0.10 * (1 - smoothstep(0.75, 0.92, r));
float a = saturate(ring + star * 0.8 + fill) * (0.8 + 0.2 * sin(T * 8.0));
return float4(lerp(float3(0.95, 0.85, 1.3), float3(1.3, 1.2, 0.6), star), a);'''


# ===================================================================== materials
def asset(name, klass, factory, folder):
    p = '%s/%s/%s' % (BASE, folder, name)
    if EAL.does_asset_exist(p):
        return u.load_asset(p)
    return A.create_asset(name, '%s/%s' % (BASE, folder), klass, factory)


def material(name, code, domain='sprite', nodepth=False, soft=0.0):
    """Unlit translucent: Custom node (UV, T, Age, Rand, PCol) -> emissive + opacity.
    nodepth: drawn over the scene (big pops would otherwise be cut off in a straight line by the floor);
    soft: depth fade distance (cm) -- sprites touching the floor or a wall fade there instead of a hard line."""
    m = asset(name, u.Material, u.MaterialFactoryNew(), 'Materials')
    M.delete_all_material_expressions(m)
    props = {'blend_mode': u.BlendMode.BLEND_TRANSLUCENT, 'shading_model': u.MaterialShadingModel.MSM_UNLIT, 'two_sided': True}
    if domain == 'sprite':
        props['used_with_niagara_sprites'] = True
    if domain == 'decal':
        props['material_domain'] = u.MaterialDomain.MD_DEFERRED_DECAL
        props.pop('two_sided')
    props['disable_depth_test'] = bool(nodepth)
    m.set_editor_properties(props)
    c = M.create_material_expression(m, u.MaterialExpressionCustom, -320, 0)
    c.set_editor_property('output_type', u.CustomMaterialOutputType.CMOT_FLOAT4)
    ins = []
    srcs = [('UV', u.MaterialExpressionTextureCoordinate), ('T', u.MaterialExpressionTime), ('Age', u.MaterialExpressionParticleRelativeTime),
            ('Rand', u.MaterialExpressionParticleRandom), ('PCol', u.MaterialExpressionParticleColor)]
    for nm in [s[0] for s in srcs] + ['PA']:
        ci = u.CustomInput()
        ci.set_editor_property('input_name', nm)
        ins.append(ci)
    c.set_editor_property('inputs', ins)
    c.set_editor_property('code', code)
    for i, (nm, ty) in enumerate(srcs):
        a = M.create_material_expression(m, ty, -640, i * 150)
        M.connect_material_expressions(a, '', c, nm)
        if nm == 'PCol':                       # the colour's alpha comes from its own output
            assert M.connect_material_expressions(a, 'A', c, 'PA'), 'particle alpha'
    for chans, prop, y in [((True, True, True, False), u.MaterialProperty.MP_EMISSIVE_COLOR, 0),
                           ((False, False, False, True), u.MaterialProperty.MP_OPACITY, 200)]:
        mk = M.create_material_expression(m, u.MaterialExpressionComponentMask, -40, y)
        mk.set_editor_properties(dict(zip(['r', 'g', 'b', 'a'], chans)))
        M.connect_material_expressions(c, '', mk, '')
        if prop == u.MaterialProperty.MP_OPACITY and soft > 0:
            df = M.create_material_expression(m, u.MaterialExpressionDepthFade, 160, y)
            df.set_editor_property('fade_distance_default', float(soft))
            assert (M.connect_material_expressions(mk, '', df, 'Opacity') or
                    M.connect_material_expressions(mk, '', df, 'InOpacity')), 'depth fade input'
            M.connect_material_property(df, '', prop)
        else:
            M.connect_material_property(mk, '', prop)
    M.recompile_material(m)
    EAL.save_loaded_asset(m, False)
    REPORT['materials'].append(name)
    return m


# big pops and shock rings are drawn over the scene; everything else fades softly into the floor / walls
DEPTH = {'Burst': dict(nodepth=True), 'Ring': dict(nodepth=True), 'Glow': dict(soft=60.0), 'Puff': dict(soft=30.0),
         'Orb': dict(soft=20.0), 'Bit': dict(soft=20.0), 'Twinkle': dict(soft=20.0)}


def build_materials():
    mats = {}
    for el in ELS:
        for kind in ['Orb', 'Bit', 'Burst', 'Puff']:
            mats[(el, kind)] = material('M_Cute_%s_%s' % (el, kind), code_for(kind, el), **DEPTH[kind])
        o, b, l, c, g = PAL[el]
        mats[(el, 'Lane')] = material('M_Cute_Tele_Lane_%s' % el, TELE_LANE % (f3(b, 1.2), f3(l, 1.35)), domain='surface')
        mats[(el, 'Circle')] = material('M_Cute_Tele_Circle_%s' % el, TELE_CIRCLE % (ELS.index(el), f3(b, 1.2), f3(l, 1.35)), domain='surface')
    for kind in ['Twinkle', 'Ring', 'Glow']:
        mats[kind] = material('M_Cute_%s' % kind, code_for(kind), **DEPTH[kind])
    mats['IceHalo'] = material('M_Cute_IceHalo', ICE_HALO, domain='decal')
    mats['AimCircle'] = material('M_Cute_AimCircle', AIM_CIRCLE, domain='surface')
    return mats


# ===================================================================== niagara
CAT = u.ScriptExecutionCategory


def module(e, name, path, cat, version=None):
    args = u.CreateScriptContextArgs(F.create_asset_data(path)) if version is None else u.CreateScriptContextArgs(F.create_asset_data(path), version)
    return e.find_or_add_module_script(name, args, cat)


def put(script, name, val, what=''):
    if not script.set_parameter(name, val):
        REPORT['warnings'].append('input rejected %s %s' % (what, name))
        return False
    return True


def enum(path, val):
    return F.create_script_input_enum(path, val)


def dyn(path, inputs, typ, version=None):
    c = F.create_script_context(u.CreateScriptContextArgs(F.create_asset_data(path)) if version is None
                                else u.CreateScriptContextArgs(F.create_asset_data(path), version))
    for k, v in inputs.items():
        put(c, k, v, path)
    return F.create_script_input_dynamic(c, typ)


def rnd_vec(lo, hi):
    return dyn(P.di_random_range_vector, {'Minimum': F.create_script_input_vector(u.Vector(*lo)),
                                          'Maximum': F.create_script_input_vector(u.Vector(*hi))}, u.NiagaraScriptInputType.VEC3)


def rnd_float(lo, hi):
    return dyn(P.di_random_range_float, {'Minimum': F.create_script_input_float(lo), 'Maximum': F.create_script_input_float(hi)},
               u.NiagaraScriptInputType.FLOAT)


def owner_scaled(e, size):
    """Sprite size = size x the component's scale (projectile size class, pop scale)."""
    s = dyn(P.di_float_from_vector, {'Vector': F.create_script_input_linked_parameter('Engine.Owner.Scale', u.NiagaraScriptInputType.VEC3),
                                     'Channel': enum(P.enum_vec3_channel, 'X')}, u.NiagaraScriptInputType.FLOAT)
    s = dyn(P.di_multiply_float, {'A': s, 'B': F.create_script_input_float(size)}, u.NiagaraScriptInputType.FLOAT)
    v = dyn(P.di_vec2_from_float, {'Value': s}, u.NiagaraScriptInputType.VEC2, [1, 0])
    e.set_parameter_directly('Particles.SpriteSize', v, CAT.PARTICLE_UPDATE)


FIT = {'_Burst': 1.3, '_Bit': 1.2, 'M_Cute_Twinkle': 1.25, 'M_Cute_Ring': 1.1}     # see code_for(): shapes shrunk to fit the square


def emitter(ctx, name, mat, size, life, rate=0.0, count=0, local=True, loop=None, color=(1, 1, 1, 1), vel=None, accel=None,
            drag=0.0, pos=None, life_rand=None, align_velocity=False, sort=0):
    size = size * next((v for k, v in FIT.items() if k in mat.get_name()), 1.0)
    e = ctx.add_empty_emitter(name)
    e.set_local_space(local)
    e.set_sim_target(u.NiagaraSimTarget.CPU_SIM)
    st = module(e, 'EmitterState', '/Niagara/Modules/Emitter/EmitterState.EmitterState', CAT.EMITTER_UPDATE, [1, 0])
    burst = count > 0 and not rate
    put(st, 'Life Cycle Mode', enum(P.enum_niagara_emitter_life_cycle_mode, 'Self'), name)
    put(st, 'Loop Behavior', enum(P.enum_niagara_emitter_state_options, 'Once' if (burst or loop) else 'Infinite'), name)
    put(st, 'Loop Duration', F.create_script_input_float(0.1 if burst else (loop or 10000.0)), name)
    put(st, 'Inactive Response', enum(P.enum_niagara_inactive_mode, 'Complete (Let Particles Finish then Kill Emitter)'), name)
    if rate:
        sp = module(e, 'Spawn', P.script_spawnrate, CAT.EMITTER_UPDATE, [1, 0])
        put(sp, 'SpawnRate', F.create_script_input_float(rate), name)
    else:
        sp = module(e, 'Spawn', P.script_spawnburst, CAT.EMITTER_UPDATE, [1, 1])
        put(sp, 'Spawn Count', F.create_script_input_int(max(1, count)), name)
    init = module(e, 'InitializeParticle', P.script_initialize_particle, CAT.PARTICLE_SPAWN, [1, 0])
    put(init, 'Lifetime', rnd_float(*life_rand) if life_rand else F.create_script_input_float(life), name)
    e.set_parameter_directly('Particles.SpriteSize', F.create_script_input_vec2(u.Vector2D(size, size)), CAT.PARTICLE_SPAWN)
    e.set_parameter_directly('Particles.Color', F.create_script_input_linear_color(u.LinearColor(*color)), CAT.PARTICLE_SPAWN)
    if pos is not None:
        e.set_parameter_directly('Particles.Position', rnd_vec(*pos), CAT.PARTICLE_SPAWN)
    if vel is not None:
        e.set_parameter_directly('Particles.Velocity', rnd_vec(*vel), CAT.PARTICLE_SPAWN)
    module(e, 'ParticleState', P.script_particle_state, CAT.PARTICLE_UPDATE, [1, 1])
    if vel is not None or accel is not None:
        if drag:
            dm = module(e, 'Drag', P.script_drag, CAT.PARTICLE_UPDATE)
            put(dm, 'Drag', F.create_script_input_float(drag), name)
        if accel is not None:
            am = module(e, 'AccelerationForce', P.script_acceleration_force, CAT.PARTICLE_UPDATE)
            put(am, 'Acceleration', F.create_script_input_vector(u.Vector(*accel)), name)
        module(e, 'SolveForcesAndVelocity', P.script_solve_forces_and_velocity, CAT.PARTICLE_UPDATE)
    r = u.NiagaraSpriteRendererProperties()
    r.set_editor_property('material', mat)
    r.set_editor_property('sort_order_hint', sort)          # glows behind, cores in front
    if align_velocity:
        r.set_editor_property('alignment', u.NiagaraSpriteAlignment.VELOCITY_ALIGNED)
    e.add_renderer('SpriteRenderer', r)
    owner_scaled(e, size)
    return e


def system(name, build):
    p = '%s/Systems/%s' % (BASE, name)
    ns = A.create_asset(name, BASE + '/Systems', u.NiagaraSystem, u.NiagaraSystemFactoryNew())
    assert ns, 'could not create %s (old systems are deleted at the start)' % name
    ctx = F.create_system_conversion_context(ns)
    build(ctx)
    ctx.finalize()
    EAL.save_loaded_asset(ns, False)
    ctx.cleanup()
    REPORT['systems'].append(name)
    return ns


def rgba(c, a=1.0, k=1.0):
    return (c[0] * k, c[1] * k, c[2] * k, a)


# per element: how the little bits move
BIT_MOTION = {
    'Fire': dict(accel=(0, 0, 140), drag=2.0),          # embers rise
    'Ice': dict(accel=(0, 0, -90), drag=2.5),           # snow drifts down
    'Wind': dict(accel=(0, 0, 30), drag=3.0),           # curls float
    'Lightning': dict(accel=(0, 0, 0), drag=4.0),       # sparks stop fast
}


def build_systems(mats):
    for el in ELS:
        o, b, l, c, g = PAL[el]
        mo = BIT_MOTION[el]

        def bullet(ctx, el=el, g=g, l=l, mo=mo):
            emitter(ctx, 'Glow', mats['Glow'], 130, 10000, count=1, local=True, color=rgba(g, 0.30), sort=-2)
            emitter(ctx, 'Core', mats[(el, 'Orb')], 82, 10000, count=1, local=True, sort=2)
            emitter(ctx, 'Bits', mats[(el, 'Bit')], 34, 0.5, rate=36, local=False, life_rand=(0.35, 0.6),
                    vel=((-40, -40, -30), (40, 40, 40)), **mo)
            emitter(ctx, 'Twinkles', mats['Twinkle'], 26, 0.4, rate=14, local=False, color=rgba(l, 1.0), life_rand=(0.3, 0.5),
                    vel=((-70, -70, -40), (70, 70, 70)), drag=3.0)
        system('NS_Cute_%s_Bullet' % el, bullet)

        def cast(ctx, el=el, g=g, l=l, mo=mo):
            emitter(ctx, 'Flash', mats[(el, 'Burst')], 95, 0.24, count=1, local=True, sort=2)
            emitter(ctx, 'Ring', mats['Ring'], 125, 0.28, count=1, local=True, color=rgba(g, 1.0), sort=-1)
            emitter(ctx, 'Twinkles', mats['Twinkle'], 28, 0.42, count=7, local=False, color=rgba(l), life_rand=(0.3, 0.5),
                    vel=((-230, -230, -120), (230, 230, 230)), drag=4.0)
            emitter(ctx, 'Bits', mats[(el, 'Bit')], 32, 0.45, count=6, local=False, life_rand=(0.35, 0.55),
                    vel=((-170, -170, -80), (170, 170, 170)), **mo)
        system('NS_Cute_%s_Cast' % el, cast)

        def pop(ctx, el=el, g=g, l=l, b=b, mo=mo, k=1.0, n=1.0):
            emitter(ctx, 'Burst', mats[(el, 'Burst')], 190 * k, 0.32, count=1, local=True, sort=3)
            emitter(ctx, 'Glow', mats['Glow'], 240 * k, 0.28, count=1, local=True, color=rgba(g, 0.35), sort=-2)
            emitter(ctx, 'Ring', mats['Ring'], 270 * k, 0.36, count=1, local=True, color=rgba(g, 1.0), sort=-1)
            emitter(ctx, 'Puffs', mats[(el, 'Puff')], 66 * k, 0.55, count=int(8 * n), local=False, life_rand=(0.45, 0.65),
                    vel=((-210 * k, -210 * k, -80 * k), (210 * k, 210 * k, 200 * k)), drag=5.0)
            emitter(ctx, 'Bits', mats[(el, 'Bit')], 40 * k, 0.6, count=int(10 * n), local=False, life_rand=(0.45, 0.75),
                    vel=((-330 * k, -330 * k, -150 * k), (330 * k, 330 * k, 330 * k)), drag=mo['drag'], accel=mo['accel'])
            emitter(ctx, 'Twinkles', mats['Twinkle'], 30 * k, 0.5, count=int(10 * n), local=False, color=rgba(l), life_rand=(0.35, 0.6),
                    vel=((-290 * k, -290 * k, -150 * k), (290 * k, 290 * k, 290 * k)), drag=3.0)
        system('NS_Cute_%s_Pop' % el, pop)
        system('NS_Cute_%s_BigPop' % el, lambda ctx, pop=pop: pop(ctx, k=2.0, n=1.8))

        def charge(ctx, el=el, g=g, l=l, mo=mo):
            emitter(ctx, 'Glow', mats['Glow'], 150, 0.85, count=1, local=True, color=rgba(g, 0.8))
            emitter(ctx, 'Twinkles', mats['Twinkle'], 22, 0.45, rate=36, loop=0.7, local=True, color=rgba(l), life_rand=(0.3, 0.5),
                    pos=((-70, -70, -50), (70, 70, 80)), vel=((-30, -30, -10), (30, 30, 60)), drag=2.0)
            emitter(ctx, 'Bits', mats[(el, 'Bit')], 24, 0.5, rate=18, loop=0.7, local=True, life_rand=(0.35, 0.55),
                    pos=((-60, -60, -40), (60, 60, 70)), vel=((-40, -40, -20), (40, 40, 60)), drag=2.0)
        system('NS_Cute_%s_Charge' % el, charge)

        def ultcore(ctx, el=el, g=g, l=l, mo=mo, trail=1.0):
            emitter(ctx, 'Glow', mats['Glow'], 140, 10000, count=1, local=True, color=rgba(g, 0.35), sort=-2)
            emitter(ctx, 'Core', mats[(el, 'Orb')], 80, 10000, count=1, local=True, sort=2)
            emitter(ctx, 'Bits', mats[(el, 'Bit')], 30, 0.6, rate=60 * trail, local=False, life_rand=(0.4, 0.75),
                    vel=((-60, -60, -40), (60, 60, 60)), **mo)
            emitter(ctx, 'Twinkles', mats['Twinkle'], 24, 0.5, rate=24 * trail, local=False, color=rgba(l), life_rand=(0.35, 0.6),
                    vel=((-90, -90, -50), (90, 90, 90)), drag=3.0)
            emitter(ctx, 'Puffs', mats[(el, 'Puff')], 40, 0.5, rate=12 * trail, local=False, life_rand=(0.35, 0.55),
                    vel=((-30, -30, -20), (30, 30, 40)), drag=3.0)
        system('NS_Cute_%s_UltCore' % el, ultcore)
        system('NS_Cute_%s_DashOrb' % el, lambda ctx, ultcore=ultcore: ultcore(ctx, trail=2.2))

    lw = PAL['Wind'][2]
    # the wind boy: a faint breeze swirling round him, and round his spells
    system('NS_Cute_WindAura', lambda ctx: (
        emitter(ctx, 'Curls', mats[('Wind', 'Bit')], 34, 1.0, rate=7, local=True, color=(1, 1, 1, 0.30), life_rand=(0.8, 1.2),
                pos=((-55, -55, -70), (55, 55, 60)), vel=((-60, -60, 10), (60, 60, 50)), drag=1.0),
        emitter(ctx, 'Glints', mats['Twinkle'], 12, 0.6, rate=6, local=True, color=rgba(lw, 0.5), life_rand=(0.4, 0.7),
                pos=((-60, -60, -80), (60, 60, 70)), vel=((-30, -30, 0), (30, 30, 50)), drag=1.0)))
    system('NS_Cute_WindBulletAura', lambda ctx: (
        emitter(ctx, 'Swirl', mats[('Wind', 'Bit')], 44, 0.5, rate=10, local=True, color=(1, 1, 1, 0.42), life_rand=(0.4, 0.6),
                pos=((-25, -25, -25), (25, 25, 25))),
        emitter(ctx, 'Wake', mats[('Wind', 'Bit')], 22, 0.45, rate=16, local=False, color=(1, 1, 1, 0.35), life_rand=(0.3, 0.5),
                vel=((-30, -30, -20), (30, 30, 30)), drag=2.0)))
    li = PAL['Ice'][2]
    # the ice girl: sparkles from her staff, snow falling while she hovers
    system('NS_Cute_IceStaff', lambda ctx: (
        emitter(ctx, 'Glow', mats['Glow'], 60, 10000, count=1, local=True, color=rgba(PAL['Ice'][4], 0.6)),
        emitter(ctx, 'Flakes', mats[('Ice', 'Bit')], 14, 0.8, rate=10, local=False, life_rand=(0.6, 1.0),
                vel=((-20, -20, -40), (20, 20, 10)), accel=(0, 0, -40), drag=1.5),
        emitter(ctx, 'Glints', mats['Twinkle'], 12, 0.4, rate=8, local=False, color=rgba(li), life_rand=(0.3, 0.5),
                vel=((-30, -30, -20), (30, 30, 30)), drag=2.0)))
    system('NS_Cute_IceHover', lambda ctx: (
        emitter(ctx, 'Snow', mats[('Ice', 'Bit')], 16, 1.0, rate=22, local=False, life_rand=(0.7, 1.2),
                vel=((-35, -35, -80), (35, 35, -20)), accel=(0, 0, -60), drag=1.0),
        emitter(ctx, 'Glints', mats['Twinkle'], 14, 0.5, rate=14, local=False, color=rgba(li), life_rand=(0.35, 0.6),
                vel=((-40, -40, -60), (40, 40, 0)), drag=2.0),
        emitter(ctx, 'Breath', mats['Glow'], 60, 0.9, rate=3, local=True, color=rgba(PAL['Ice'][4], 0.20), pos=((-10, -10, -10), (10, 10, 10)))))
    lf = PAL['Fire'][2]
    # the fire boy: a hot little puff at his feet when he casts
    system('NS_Cute_FireHype', lambda ctx: (
        emitter(ctx, 'Flames', mats[('Fire', 'Bit')], 34, 0.5, count=7, local=False, life_rand=(0.4, 0.6),
                vel=((-160, -160, 60), (160, 160, 260)), accel=(0, 0, 160), drag=3.0),
        emitter(ctx, 'Puffs', mats[('Fire', 'Puff')], 40, 0.45, count=5, local=False, life_rand=(0.35, 0.5),
                vel=((-170, -170, 0), (170, 170, 60)), drag=5.0),
        emitter(ctx, 'Glints', mats['Twinkle'], 20, 0.4, count=6, local=False, color=rgba(lf), life_rand=(0.3, 0.45),
                vel=((-150, -150, 40), (150, 150, 240)), drag=3.0)))


def main():
    try:
        # R11_VFX_ONLY=materials: rebuild the sprite materials in place (colours, shapes)
        # and keep the systems (their particle tints stay as they were built)
        only_mats = os.environ.get('R11_VFX_ONLY', '') == 'materials'
        assert only_mats or F is not None, 'start the editor with -EnablePlugins=CascadeToNiagaraConverter'
        # systems are generated only by this script; r11_vfx_clean.py (a commandlet run
        # just before) deletes the old ones -- a package deleted and re-created in one
        # editor session is still in memory
        mats = build_materials()
        if not only_mats:
            build_systems(mats)
        REPORT['passed'] = True
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        u.log_error(traceback.format_exc())
    (OUT / 'r11-vfx.json').write_text(json.dumps(REPORT, indent=1), encoding='utf-8')
    print('R11_VFX_DONE', REPORT.get('passed'))


try:
    main()
finally:
    # run in the full editor with -EnablePlugins=CascadeToNiagaraConverter -ExecutePythonScript=...
    u.SystemLibrary.quit_editor()
