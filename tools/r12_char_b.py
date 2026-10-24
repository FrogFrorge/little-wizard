"""Round 12, part B: the character (BP_WizardCharacter).  Run after r12_ult_a.py.

- wind boy: moves and shoots 1.15x (round 11 had made it 1.2 / 1.3; it was 1.1 / 1.1)
- ice girl's hover: holding the jump key in the air keeps her at that height (the
  rise she had when the hover began is stopped -- she used to keep floating up)
- BeginUltimateWindup: the fire boy's lane warning gets its real length (the way
  to the first wall, at most 52.5 m); the lightning girl turns to face her circle

No compile before the end (compiling this Blueprint mid-run and then adding an
operator node crashes this editor).

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r12_char_b.py
"""
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
import r11_bp
importlib.reload(r11_bp)
from r11_bp import *          # noqa

RPT = 'r12-char-b.json'
WIND = 1.15


def wind_traits():
    g = Graph(CH, 'InitializeWizardTraits')
    changed = []
    for n in g.e.list_all_nodes():
        if n.get_class().get_name() != 'K2Node_VariableSet':
            continue
        for var in ('MoveSpeedMultiplier', 'ProjectileSpeedMultiplier'):
            p_ = n.find_input_pin(var)
            if not p_.is_valid() or p_.list_connected_pins():
                continue
            v = float(p_.get_pin_value() or 0)
            if abs(v - 1.0) > 1e-4:            # the wind branch (the others set 1.0)
                value(p_, '%.6f' % WIND)
                changed.append((var, v, WIND))
    assert len(changed) == 2, changed
    return changed


def hover_holds():
    g = Graph(CH, 'ApplyHoverState')
    if any(n.get_class().get_name() == 'K2Node_VariableSet' and n.find_input_pin('Velocity').is_valid() for n in g.e.list_all_nodes()):
        return 'already'
    # the last node of the flow (UpdateWizardPose)
    tail = next(n for n in g.e.list_all_nodes() if 'UpdateWizardPose' in str(n.get_node_title()).replace(' ', ''))
    assert not list(then(tail).list_connected_pins())
    hov = g.branch(g.get('bIsHovering'))
    link(then(tail), ex(hov))
    cmv = g.place(g.e.add_get_member_variable_node('CharacterMovement', '/Script/Engine.Character'))
    cm = pin(cmv, 'CharacterMovement', True)
    vg = g.place(g.e.add_get_member_variable_node('Velocity', '/Script/Engine.MovementComponent'))
    value(vg.find_self_pin(), cm)
    bv = g.call('/Script/Engine.KismetMathLibrary.BreakVector', InVec=pin(vg, 'Velocity', True))
    vs = g.place(g.e.add_set_member_variable_node('Velocity', '/Script/Engine.MovementComponent'))
    value(vs.find_self_pin(), cm)
    value(pin(vs, 'Velocity'), result(g.call('/Script/Engine.KismetMathLibrary.MakeVector', X=pin(bv, 'X', True), Y=pin(bv, 'Y', True), Z=0.0)))
    link(pin(hov, 'then', True), ex(vs))
    layout(g)
    return 'hover keeps the height'


def windup():
    """BeginUltimateWindup (as round 11's, plus the lane length and the facing)."""
    g = fresh(CH, 'BeginUltimateWindup', [('ElementIndex', I)])
    go = g.branch(g.authority())
    chain(g.entry(), go)
    W = lambda: g.toint(g.get('WizardType'))
    aim = g.math('Normal', A=g.vsub(g.get('LastAcceptedAimPoint'), g.loc()), Tolerance=0.0001)
    fwd = result(g.call('/Script/Engine.Actor.GetActorForwardVector'))
    s1 = g.set('UltimateWindupActive', True)
    s2 = g.set('LockedUltimateDirection', g.selectv(fwd, aim, g.ieq(W(), 2)))
    s3 = g.set('LockedStormTarget', g.get('StormTarget'))
    cmv = g.place(g.e.add_get_member_variable_node('CharacterMovement', '/Script/Engine.Character'))
    stop = g.call('/Script/Engine.MovementComponent.StopMovementImmediately', self=pin(cmv, 'CharacterMovement', True))
    lt = g.call('/Script/Engine.KismetSystemLibrary.LineTraceSingle', Start=g.vadd(g.loc(), (0.0, 0.0, 80.0)),
                End=g.vadd(g.loc(), (0.0, 0.0, -3000.0)), TraceChannel='TraceTypeQuery1', bTraceComplex=False,
                ActorsToIgnore=g.get('UltimateTraceIgnore'), DrawDebugType='None', bIgnoreSelf=True)
    chain(pin(go, 'then', True), s1, s2, s3, stop, lt)
    # the lightning girl turns to face the circle she calls down
    face = g.branch(g.ieq(W(), 3))
    link(then(lt), ex(face))
    tgt = g.math('Normal', A=g.math('Multiply_VectorVector', A=g.vsub(g.get('LockedStormTarget'), g.loc()), B=(1, 1, 0)), Tolerance=0.0001)
    turn = g.call('/Script/Engine.Actor.K2_SetActorRotation', NewRotation=g.math('MakeRotFromX', X=tgt), bTeleportPhysics=False)
    link(pin(face, 'then', True), ex(turn))
    bh = g.call('/Script/Engine.GameplayStatics.BreakHitResult', Hit=pin(lt, 'OutHit', True))
    ground = g.selectv(g.vadd(pin(bh, 'ImpactPoint', True), (0.0, 0.0, 5.0)), g.vadd(g.loc(), (0.0, 0.0, -84.0)), result(lt))
    flat = g.math('Normal', A=g.math('Multiply_VectorVector', A=g.get('LockedUltimateDirection'), B=(1, 1, 0)), Tolerance=0.0001)
    # the fire boy's lane runs to the first wall (people do not stop it), at most 52.5 m
    allw = g.call('/Script/Engine.GameplayStatics.GetAllActorsOfClass', ActorClass=cp(CH))
    link(then(turn), ex(allw))
    link(pin(face, 'else', True), ex(allw))
    ls = g.vadd(ground, (0.0, 0.0, 60.0))
    wt = g.call('/Script/Engine.KismetSystemLibrary.LineTraceSingle', Start=ls, End=g.vadd(ls, g.vmul(flat, 5250.0)),
                TraceChannel='TraceTypeQuery1', bTraceComplex=False, ActorsToIgnore=pin(allw, 'OutActors', True),
                DrawDebugType='None', bIgnoreSelf=True)
    link(then(allw), ex(wt))
    wb = g.call('/Script/Engine.GameplayStatics.BreakHitResult', Hit=pin(wt, 'OutHit', True))
    dist = g.selectf(g.math('FMax', A=g.math('Vector_Distance', V1=pin(wb, 'Location', True), V2=ls), B=200.0), 5250.0, result(wt))
    lane0 = g.vadd(ground, g.vmul(flat, g.fmul(dist, 0.5)))
    lane2 = g.vadd(ground, g.vmul(flat, 1250.0))
    where = g.selectv(g.get('LockedStormTarget'), g.selectv(lane0, g.selectv(lane2, ground, g.ieq(W(), 2)), g.ieq(W(), 0)), g.ieq(W(), 3))
    tr = g.math('MakeTransform', Location=where, Rotation=g.math('MakeRotFromX', X=flat), Scale=(1, 1, 1))
    be = g.call('/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass', ActorClass=cp(TELE), SpawnTransform=tr,
                CollisionHandlingOverride='AlwaysSpawn', Owner=g.selfref(), TransformScaleMethod='MultiplyWithRoot')
    ca, t = g.cast(result(be), TELE)
    e1 = g.set('Element', g.inp('ElementIndex'), TELE, t)
    e2 = g.set('Delivery', W(), TELE, t)
    e3 = g.set('LaneLength', g.selectf(dist, 0.0, g.ieq(W(), 0)), TELE, t)
    fin = g.call('/Script/Engine.GameplayStatics.FinishSpawningActor', Actor=result(be), SpawnTransform=tr, TransformScaleMethod='MultiplyWithRoot')
    chain(then(wt), be, ca, e1, e2, e3, fin)
    layout(g)


def main():
    try:
        backup(CH)
        log('wind traits %s' % wind_traits(), RPT)
        log('hover: %s' % hover_holds(), RPT)
        windup()
        log('windup: lane length, the lightning girl faces her circle', RPT)
        compile_bp(CH, True)
        REPORT['passed'] = True
        log('done', RPT)
        print('R12_CHAR_B_DONE')
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        (OUT / RPT).write_text(json.dumps(REPORT, indent=1, default=str), encoding='utf-8')
        u.log_error(traceback.format_exc())


main()
