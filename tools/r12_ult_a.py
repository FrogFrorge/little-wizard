"""Round 12, part A: the ultimate actors (BP_UltimateCast / BP_UltimateOrb / BP_UltimateTelegraph).

- the fire boy's lightning volley: the balls fly out level (they used to follow the
  camera's downward pitch into the floor at his feet), a little bigger; he holds one
  pose for the whole volley (action 13) instead of replaying the throw ten times
- the wind boy's lightning dash: the 30% splash reaches 500 units (was 300), with a
  lightning pop as wide as the splash
- the lightning girl's wind ball: the two forward hops are twice as fast (same arc)
- the fire boy's lane warning: as wide as the orb really is (fire 2 m, ice 1.2 m,
  wind 0.9 m, lightning 0.6 m) and only as long as the way to the first wall
  (BP_UltimateTelegraph.LaneLength, set by BeginUltimateWindup -- part B).  Since
  round 11 both lanes (fire boy, wind boy) were drawn as squares, length x length
  (r11_bp's vec(sx, sy, 1) returned sx alone -- fixed there)

Only these graphs change; the character is edited in part B (r12_char_b.py), and
no Blueprint is compiled before all the edits of this run are made.

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r12_ult_a.py
"""
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
import r11_bp
importlib.reload(r11_bp)
from r11_bp import *          # noqa

RPT = 'r12-ult-a.json'
ELS = ['Fire', 'Ice', 'Wind', 'Lightning']


def orb_call(g, pos, vel, el, scale, radius, visual, **kw):
    args = dict(Position=pos, Velocity=vel, OrbElement=el, Scale=scale, Radius=radius, Visual=visual, Bounces=0,
                BounceScale=1.0, SplitMode=0, SplitScale=0.5, AreaRadius=0.0, AreaScale=0.0, Hops=0, HopDir=(1.0, 0.0, 0.0),
                Gravity=0.0, Penalize=False, PawnOnly=False, WorldOnly=False)
    args.update(kw)
    return g.fn('SpawnOrbEx', **args)


def literal(p_, graph, cls_name, title, match, pin_name, new):
    """Set pin_name to new on the one node of this graph whose literal pins match."""
    g = Graph(p_, graph)
    hits = []
    for n in g.e.list_all_nodes():
        if n.get_class().get_name() != cls_name or (title and str(n.get_node_title()) != title):
            continue
        ok = True
        for k, v in match.items():
            q = n.find_input_pin(k)
            if not q.is_valid() or q.list_connected_pins() or abs(float(str(q.get_pin_value()) or 'nan') - v) > 1e-3:
                ok = False
                break
        if ok:
            hits.append(n)
    if not hits:
        return 'already (no node with %s)' % match
    assert len(hits) == 1, (graph, match, len(hits))
    value(hits[0].find_input_pin(pin_name), new)
    return 'set %s=%s' % (pin_name, new)


def volley_step():
    g = fresh(CAST, 'VolleyStep')
    go = g.branch(g.AND(g.math('Greater_IntInt', A=g.get('VolleyLeft'), B=0),
                        g.math('GreaterEqual_DoubleDouble', A=g.now(), B=g.get('NextVolleyAt')), g.valid(g.get('Caster'))))
    chain(g.entry(), go)
    first = g.branch(g.ieq(g.get('VolleyLeft'), 10))
    link(pin(go, 'then', True), ex(first))
    hold = g.call(cp(CH) + '.QueueWizardAction', self=g.get('Caster'), ActionCode=13)
    link(pin(first, 'then', True), ex(hold))
    v1 = g.set('VolleyLeft', g.math('Subtract_IntInt', A=g.get('VolleyLeft'), B=1))
    link(then(hold), ex(v1))
    link(pin(first, 'else', True), ex(v1))
    v2 = g.set('NextVolleyAt', g.fadd(g.get('NextVolleyAt'), 0.4))
    # level, where he faces now (he can turn during the volley)
    fw = g.math('GetForwardVector', InRot=result(g.call('/Script/Engine.Pawn.GetBaseAimRotation', self=g.get('Caster'))))
    aim = g.math('Normal', A=g.math('Multiply_VectorVector', A=fw, B=(1, 1, 0)), Tolerance=0.0001)
    fp = g.get('FirePoint', CH, g.get('Caster'))
    start = result(g.call('/Script/Engine.SceneComponent.K2_GetComponentLocation', self=fp))
    o = orb_call(g, g.vadd(start, g.vmul(aim, 60.0)), g.vmul(aim, 1400.0), 3, 0.25, 30.0, 2.0)
    pop = g.fn('SpawnFX', Location=start, FXElement=3, Kind=2, Size=0.45)
    chain(then(v1), v2, o, pop)
    layout(g)


def dash_splash_fx():
    """The wind boy's lightning dash: the 500-unit splash had no picture of its own
    (only the dash's small finish pop) -- a big lightning pop as wide as the splash."""
    g = Graph(CAST, 'DashPayload')
    hits = []
    for n in g.e.list_all_nodes():
        if n.get_class().get_name() != 'K2Node_CallFunction' or 'AreaDamage' not in str(n.get_node_title()):
            continue
        r = n.find_input_pin('Radius')
        if r.is_valid() and not r.list_connected_pins() and abs(float(str(r.get_pin_value()) or 'nan') - 500.0) < 1e-3:
            hits.append(n)
    assert len(hits) == 1, len(hits)
    out = then(hits[0])
    if out.list_connected_pins():
        return 'already'
    # BP_CuteFX kind 1 (BigPop, x0.6): its ring sprite is 540 at scale 1 -> size 3 is ~10 m across
    fx = g.fn('SpawnFX', Location=g.inp('Center'), FXElement=3, Kind=1, Size=3.0)
    link(out, ex(fx))
    layout(g)
    return 'added'


def telegraph():
    declare(TELE, 'LaneLength', R, '0', 'rep')
    L.set_blueprint_variable_instance_editable(load(TELE), 'LaneLength', True)
    L.set_blueprint_variable_expose_on_spawn(load(TELE), 'LaneLength', True)
    g = fresh(TELE, 'ApplyWarningVisual')
    D = lambda: g.get('Delivery')
    el = lambda: g.get('Element')
    cute = '/Game/VFX/WizardMagic/Cute/Materials/%s.%s'
    lane = g.OR(g.ieq(D(), 0), g.ieq(D(), 2))
    # the cute warnings (r11_vfx_wire.py): lanes for the fire boy and the wind boy, circles for the girls
    lasts = []

    def mk(e):
        b = g.branch(lane)
        n1 = g.call('/Script/Engine.PrimitiveComponent.SetMaterial', self=g.get('WarningSurface'), ElementIndex=0,
                    Material=cute % (('M_Cute_Tele_Lane_' + ELS[e],) * 2))
        n2 = g.call('/Script/Engine.PrimitiveComponent.SetMaterial', self=g.get('WarningSurface'), ElementIndex=0,
                    Material=cute % (('M_Cute_Tele_Circle_' + ELS[e],) * 2))
        link(pin(b, 'then', True), ex(n1))
        link(pin(b, 'else', True), ex(n2))
        lasts.extend([then(n1), then(n2)])
        return b, None
    sw = g.switch_int(el(), [0, 1, 2, 3])
    link(g.entry(), sw['in'])
    for e in range(4):
        b, _ = mk(e)
        link(sw[e], ex(b))
    circle3 = g.selectf(6.9, g.selectf(6.383, 5.0, g.ieq(el(), 3)), g.ieq(el(), 0))
    # the fire boy's lane: the orb's own width, the way to the first wall
    w0 = g.selectf(2.0, g.selectf(1.2, g.selectf(0.9, 0.6, g.ieq(el(), 2)), g.ieq(el(), 1)), g.ieq(el(), 0))
    l0 = g.selectf(g.fmul(g.get('LaneLength'), 0.01), 52.5, g.math('Greater_DoubleDouble', A=g.get('LaneLength'), B=1.0))
    sx = g.selectf(l0, g.selectf(9.574, g.selectf(25.0, circle3, g.ieq(D(), 2)), g.ieq(D(), 1)), g.ieq(D(), 0))
    sy = g.selectf(w0, g.selectf(9.574, g.selectf(1.8, circle3, g.ieq(D(), 2)), g.ieq(D(), 1)), g.ieq(D(), 0))
    sc = g.call('/Script/Engine.SceneComponent.SetRelativeScale3D', self=g.get('WarningSurface'), NewScale3D=g.vec(sx, sy, 1.0))
    for l_ in lasts:
        link(l_, ex(sc))
    layout(g)


def main():
    try:
        for p_ in (CAST, ORB, TELE):
            backup(p_)
        log('wind hop speed: ' + literal(ORB, 'ResolveOrb', 'K2Node_CallFunction', None, {'X': 650.0, 'Y': 650.0, 'Z': 650.0},
                                         'X', '1300.0'), RPT)
        log(' ... ' + literal(ORB, 'ResolveOrb', 'K2Node_CallFunction', None, {'X': 1300.0, 'Y': 650.0, 'Z': 650.0}, 'Y', '1300.0'), RPT)
        log(' ... ' + literal(ORB, 'ResolveOrb', 'K2Node_CallFunction', None, {'X': 1300.0, 'Y': 1300.0, 'Z': 650.0}, 'Z', '1300.0'), RPT)
        log('wind hop rise: ' + literal(ORB, 'ResolveOrb', 'K2Node_CallFunction', None, {'X': 0.0, 'Y': 0.0, 'Z': 720.0},
                                        'Z', '1440.0'), RPT)
        log('wind hop gravity: ' + literal(CAST, 'StartCast', 'K2Node_CallFunction', None, {'Hops': 2, 'Gravity': 1700.0},
                                           'Gravity', '6800.0'), RPT)
        log('lightning dash splash: ' + literal(CAST, 'DashPayload', 'K2Node_CallFunction', None, {'Radius': 300.0, 'Scale': 0.3},
                                                'Radius', '500.0'), RPT)
        log('lightning dash splash picture: ' + dash_splash_fx(), RPT)
        volley_step()
        log('volley: level, one held pose', RPT)
        telegraph()
        log('fire boy lane: orb width, to the first wall', RPT)
        for p_ in (ORB, TELE, CAST):
            compile_bp(p_, True)
        REPORT['passed'] = True
        log('done', RPT)
        print('R12_ULT_A_DONE')
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        (OUT / RPT).write_text(json.dumps(REPORT, indent=1, default=str), encoding='utf-8')
        u.log_error(traceback.format_exc())


main()
