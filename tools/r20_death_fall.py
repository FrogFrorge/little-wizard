"""Round 20: a wizard at 0 health falls over -- the way the killing blow pushed them -- and the
ultimate charge chance gets a tunable base.

Commandlet:  UnrealEditor-Cmd <uproject> -run=pythonscript -script="r20_death_fall.py"
             (env R20_SUPER_BASE = the chance base, default 50: 100/(supers+10) % -> 50/(...) %)

BP_WizardCharacter:
- RecordHitDirection(DamageCauser), first thing on Event AnyDamage (server): the direction the
  blow travelled -- a shot's / an orb's flight, or from the attacker for anything not moving --
  flat, in DeathFallDir (replicated, so every machine falls the same way).
- OnRep_bIsDead (every machine; the server too, as 'set with notify'): StartDeathFall when dead,
  StopDeathFall when alive again (a respawn or a new round puts the body back).
- StartDeathFall: the body ('Mesh', which carries WizardMeshV5) topples about the feet -- its
  origin -- toward DeathFallDir in the capsule's frame: the rotation axis is Up x dir.
- DeathFallStep (a 1/60 s timer): a rigid body falling over about its base,
      angle'' = (3 g / 2 L) sin(angle)       (g = 980 cm/s^2, L = 140 cm: 10.5 /s^2)
  starting from a small tilt and the push of the blow (1.7 rad/s), so it leans slowly, then
  drops fast; on the ground (86 degrees) it bounces back a little (restitution 0.25) and
  settles; the body slides 40 cm along the blow meanwhile.  Hair and cloth (AnimDynamics)
  swing with the motion; 0.8 s after settling the pose is frozen (DeathFreezePose).
  Knocked out in the air (a jump, a hover, a knock-up)?  The game stops the character's
  movement on death (DisableMovement), which left the body hanging in mid-air: the body now
  also drops to the floor under it (found by a trace at the start) with gravity, 980 cm/s^2,
  while it topples; the pose is frozen only once it is on the floor.
- CalculateSuperChance: the literal 100 of BaseChance = 100 / (supers + 10) is now the
  variable SuperChanceBase.
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
import r11_bp
importlib.reload(r11_bp)
from r11_bp import *          # noqa

OUT = ROOT / 'output' / 'round20'
OUT.mkdir(parents=True, exist_ok=True)
RES = OUT / 'r20-death-fall.json'
SUPER_BASE = float(os.environ.get('R20_SUPER_BASE', '50'))
K = 10.5                       # 3 g / 2 L
PUSH = 1.7                     # rad/s from the blow
MAX = 1.50                     # rad: lying (86 degrees; the big chibi head keeps it off flat)
BOUNCE = 0.25
SLIDE = 40.0
G = 980.0                      # cm/s^2: a body knocked out in the air falls to the floor
DT = 1.0 / 60.0
WIZ = cp(CH)
rep = {'steps': []}


def note(s):
    rep['steps'].append(s)
    RES.write_text(json.dumps(rep, indent=1), encoding='utf-8')
    print('R20 ' + s)


def km(name, **a):
    return '/Script/Engine.KismetMathLibrary.' + name, a


def call(g, path, **a):
    return g.call(path, **a)


def mathp(g, name, **a):
    return result(g.call('/Script/Engine.KismetMathLibrary.' + name, **a))


def variables():
    declare(CH, 'DeathFallDir', V, '', 'rep')
    for n in ('DeathFallAngle', 'DeathFallSpeed', 'DeathDrop', 'DeathDropSpeed', 'DeathDropMax'):
        declare(CH, n, R, '0')
    for n in ('DeathFallActive', 'DeathBaseSaved'):
        declare(CH, n, B, 'false')
    declare(CH, 'DeathFallAxis', V, '')
    declare(CH, 'DeathFallLocalDir', V, '')
    declare(CH, 'DeathMeshBaseLoc', V, '')
    declare(CH, 'DeathMeshBaseRot', ROT, '')
    declare(CH, 'SuperChanceBase', R, '%g' % SUPER_BASE)
    note('variables declared')


def record_hit_direction():
    g = fresh(CH, 'RecordHitDirection', [('DamageCauser', obj(u.Actor.static_class()))])
    causer = g.inp('DamageCauser')
    ok = g.branch(g.valid(causer))
    flat = g.vec((1.0, 1.0, 0.0))
    away = g.math('Multiply_VectorVector', A=g.vsub(g.loc(), g.loc(causer)), B=flat)
    vel = g.math('Multiply_VectorVector', A=result(g.call('/Script/Engine.Actor.GetVelocity', self=causer)), B=g.vec((1.0, 1.0, 0.0)))
    is_wizard = g.math('ClassIsChildOf', TestClass=result(g.call('/Script/Engine.GameplayStatics.GetObjectClass', Object=causer)),
                       ParentClass=WIZ)
    moving = g.math('Greater_DoubleDouble', A=g.math('VSize', A=vel), B=150.0)
    use_vel = g.AND(moving, g.NOT(is_wizard))
    d = g.math('Normal', A=g.selectv(vel, away, use_vel), Tolerance=0.0001)
    chain(g.entry(), ok)
    chain(then(ok), g.set('DeathFallDir', d))
    layout(g)
    note('RecordHitDirection')


def start_death_fall():
    g = fresh(CH, 'StartDeathFall')
    once = g.branch(g.get('DeathBaseSaved'))
    mesh = g.get('Mesh')
    xf = result(g.call('/Script/Engine.SceneComponent.GetRelativeTransform', self=mesh))
    brk = g.call('/Script/Engine.KismetMathLibrary.BreakTransform', InTransform=xf)
    local = g.math('LessLess_VectorRotator', A=g.get('DeathFallDir'), B=result(g.call('/Script/Engine.Actor.K2_GetActorRotation')))
    local_flat = g.math('Normal', A=g.math('Multiply_VectorVector', A=local, B=g.vec((1.0, 1.0, 0.0))), Tolerance=0.0001)
    have = g.math('Greater_DoubleDouble', A=g.math('VSize', A=local_flat), B=0.5)
    ldir = g.selectv(local_flat, g.vec((-1.0, 0.0, 0.0)), have)          # no direction: backwards
    axis = g.math('Cross_VectorVector', A=g.vec((0.0, 0.0, 1.0)), B=ldir)
    # the floor under the body (the feet: the mesh's origin): how far it has to drop
    me = g.loc()
    trace = g.call('/Script/Engine.KismetSystemLibrary.LineTraceSingle', Start=me, End=g.vsub(me, g.vec((0.0, 0.0, 3000.0))),
                   TraceChannel='TraceTypeQuery1', bTraceComplex=False, bIgnoreSelf=True)
    feet_z = g.fadd(pin(g.call('/Script/Engine.KismetMathLibrary.BreakVector', InVec=me), 'Z', True),
                    pin(g.call('/Script/Engine.KismetMathLibrary.BreakVector', InVec=pin(brk, 'Location', True)), 'Z', True))
    hit = g.call('/Script/Engine.GameplayStatics.BreakHitResult', Hit=pin(trace, 'OutHit', True))
    floor_z = g.selectf(pin(g.call('/Script/Engine.KismetMathLibrary.BreakVector', InVec=pin(hit, 'ImpactPoint', True)), 'Z', True),
                        g.fsub(feet_z, 3000.0), result(trace))
    drop = g.math('FMax', A=g.fsub(feet_z, floor_z), B=0.0)
    chain(g.entry(), once)
    chain(pin(once, 'else', True), trace,
          g.set('DeathMeshBaseLoc', pin(brk, 'Location', True)),
          g.set('DeathMeshBaseRot', pin(brk, 'Rotation', True)),
          g.set('DeathFallLocalDir', ldir),
          g.set('DeathFallAxis', axis),
          g.set('DeathFallAngle', 0.03),
          g.set('DeathFallSpeed', PUSH),
          g.set('DeathDropMax', drop),
          g.set('DeathDrop', 0.0),
          g.set('DeathDropSpeed', 0.0),
          g.set('DeathFallActive', True),
          g.set('DeathBaseSaved', True),
          g.call('/Script/Engine.KismetSystemLibrary.K2_SetTimer', Object=g.selfref(), FunctionName='DeathFallStep',
                 Time=DT, bLooping=True))
    layout(g)
    note('StartDeathFall')


def apply_pose(g, angle):
    """Mesh relative transform for the current angle (radians): rotate about the feet, slide."""
    frac = g.math('FClamp', Value=g.math('Divide_DoubleDouble', A=angle, B=MAX), Min=0.0, Max=1.0)
    slide = g.fmul(g.fmul(frac, frac), SLIDE)
    loc = g.vsub(g.vadd(g.get('DeathMeshBaseLoc'), g.vmul(g.get('DeathFallLocalDir'), slide)),
                 g.vec(0.0, 0.0, g.get('DeathDrop')))
    tilt = g.math('RotatorFromAxisAndAngle', Axis=g.get('DeathFallAxis'), Angle=g.fmul(angle, 57.29578))
    rot = g.math('ComposeRotators', A=g.get('DeathMeshBaseRot'), B=tilt)
    return g.call('/Script/Engine.SceneComponent.K2_SetRelativeLocationAndRotation', self=g.get('Mesh'),
                  NewLocation=loc, NewRotation=rot, bSweep=False, bTeleport=True)


def death_fall_step():
    g = fresh(CH, 'DeathFallStep')
    # semi-implicit Euler, through the variables (a pure node is re-evaluated at every use: an
    # expression for the new speed read again after the speed is set would add twice)
    speed = g.fadd(g.get('DeathFallSpeed'), g.fmul(g.math('Sin', A=g.get('DeathFallAngle')), K * DT))
    set_speed = g.set('DeathFallSpeed', speed)
    # the drop (knocked out in the air): gravity until the feet are on the floor
    set_dspeed = g.set('DeathDropSpeed', g.fadd(g.get('DeathDropSpeed'), G * DT))
    set_drop = g.set('DeathDrop', g.math('FMin', A=g.fadd(g.get('DeathDrop'), g.fmul(g.get('DeathDropSpeed'), DT)),
                                         B=g.get('DeathDropMax')))
    landed = g.branch(g.math('GreaterEqual_DoubleDouble', A=g.get('DeathDrop'), B=g.fsub(g.get('DeathDropMax'), 0.01)))
    nxt = g.fadd(g.get('DeathFallAngle'), g.fmul(g.get('DeathFallSpeed'), DT))
    down = g.branch(g.math('GreaterEqual_DoubleDouble', A=nxt, B=MAX))
    hard = g.branch(g.math('Greater_DoubleDouble', A=g.get('DeathFallSpeed'), B=0.5))
    chain(g.entry(), set_dspeed, set_drop, set_speed, down)
    # still falling (or rising after the bounce)
    chain(pin(down, 'else', True), g.set('DeathFallAngle', nxt), apply_pose(g, g.get('DeathFallAngle')))
    # on the ground: bounce back while fast, else lie still
    link(pin(down, 'then', True), ex(hard))
    chain(pin(hard, 'then', True), g.set('DeathFallSpeed', g.fmul(g.get('DeathFallSpeed'), -BOUNCE)), g.set('DeathFallAngle', MAX),
          apply_pose(g, g.get('DeathFallAngle')))
    chain(pin(hard, 'else', True), g.set('DeathFallSpeed', 0.0), g.set('DeathFallAngle', MAX), apply_pose(g, g.get('DeathFallAngle')),
          landed)
    chain(pin(landed, 'then', True), g.set('DeathFallActive', False),
          g.call('/Script/Engine.KismetSystemLibrary.K2_ClearTimer', Object=g.selfref(), FunctionName='DeathFallStep'),
          g.call('/Script/Engine.KismetSystemLibrary.K2_SetTimer', Object=g.selfref(), FunctionName='DeathFreezePose',
                 Time=0.8, bLooping=False))
    layout(g)
    note('DeathFallStep')


def death_freeze_pose():
    g = fresh(CH, 'DeathFreezePose')
    dead = g.branch(g.get('bIsDead'))
    chain(g.entry(), dead)
    chain(then(dead), g.call('/Script/Engine.ActorComponent.SetComponentTickEnabled', self=g.get('WizardMeshV5'), bEnabled=False))
    layout(g)
    note('DeathFreezePose')


def stop_death_fall():
    g = fresh(CH, 'StopDeathFall')
    had = g.branch(g.get('DeathBaseSaved'))
    chain(g.entry(), had)
    chain(then(had),
          g.call('/Script/Engine.KismetSystemLibrary.K2_ClearTimer', Object=g.selfref(), FunctionName='DeathFallStep'),
          g.call('/Script/Engine.KismetSystemLibrary.K2_ClearTimer', Object=g.selfref(), FunctionName='DeathFreezePose'),
          g.call('/Script/Engine.SceneComponent.K2_SetRelativeLocationAndRotation', self=g.get('Mesh'),
                 NewLocation=g.get('DeathMeshBaseLoc'), NewRotation=g.get('DeathMeshBaseRot'), bSweep=False, bTeleport=True),
          g.call('/Script/Engine.ActorComponent.SetComponentTickEnabled', self=g.get('WizardMeshV5'), bEnabled=True),
          g.set('DeathFallActive', False), g.set('DeathBaseSaved', False), g.set('DeathFallAngle', 0.0),
          g.set('DeathDrop', 0.0), g.set('DeathDropSpeed', 0.0))
    layout(g)
    note('StopDeathFall')


def title(n):
    return str(n.get_node_title()).split('\n')[0].strip().replace(' ', '')


def wire_on_rep():
    g = Graph(CH, 'OnRep_bIsDead')
    nodes = list(g.e.list_all_nodes())
    if any(title(n) == 'StartDeathFall' for n in nodes):
        note('OnRep_bIsDead already wired')
        return
    stop_j = next(n for n in nodes if title(n) == 'StopJumping')
    br0 = g.entry().list_connected_pins()[0].get_owning_node()        # Branch(bIsDead) right after the entry
    assert br0.get_class().get_name() == 'K2Node_IfThenElse', br0.get_class().get_name()
    tp = then(stop_j)
    old = list(tp.list_connected_pins())
    tp.break_pin_links()
    start = g.fn('StartDeathFall')
    link(tp, ex(start))
    for o in old:
        link(then(start), o)
    stop = g.fn('StopDeathFall')
    el = pin(br0, 'else', True)
    assert not el.list_connected_pins(), 'OnRep_bIsDead else already used'
    link(el, ex(stop))
    note('OnRep_bIsDead: StartDeathFall after Stop Jumping, StopDeathFall when alive')


def wire_any_damage():
    g = Graph(CH, 'EventGraph')
    nodes = list(g.e.list_all_nodes())
    ev = next(n for n in nodes if n.get_class().get_name() == 'K2Node_Event' and title(n) == 'EventAnyDamage')
    tp = then(ev)
    nxt = [q.get_owning_node() for q in tp.list_connected_pins()]
    if any(title(n) == 'RecordHitDirection' for n in nxt):
        note('AnyDamage already wired')
        return
    old = list(tp.list_connected_pins())
    tp.break_pin_links()
    rec = g.fn('RecordHitDirection', DamageCauser=pin(ev, 'DamageCauser', True))
    link(tp, ex(rec))
    for o in old:
        link(then(rec), o)
    note('AnyDamage: RecordHitDirection first')


def super_chance():
    g = Graph(CH, 'CalculateSuperChance')
    done = 0
    for n in list(g.e.list_all_nodes()):
        if title(n) in ('float/float', 'Divide(Float)'):
            a = n.find_input_pin('A')
            if a.is_valid() and not a.list_connected_pins() and str(a.get_pin_value()).startswith('100'):
                link(g.get('SuperChanceBase'), a)
                done += 1
    note('CalculateSuperChance: %d literal 100s now SuperChanceBase' % done)


def main():
    backup(CH)
    variables()
    record_hit_direction()
    start_death_fall()
    death_fall_step()
    death_freeze_pose()
    stop_death_fall()
    compile_bp(CH, save=False)              # the new functions exist before they are called
    wire_on_rep()
    wire_any_damage()
    super_chance()
    compile_bp(CH)
    # the base for this run: the class default object holds a Blueprint variable's default (a
    # re-run with another R20_SUPER_BASE changes it)
    b = load(CH)
    u.get_default_object(b.generated_class()).set_editor_property('SuperChanceBase', SUPER_BASE)
    compile_bp(CH)
    note('SuperChanceBase on the class default: %s' % u.get_default_object(load(CH).generated_class()).get_editor_property('SuperChanceBase'))
    rep['passed'] = True
    note('done')


try:
    main()
except Exception:
    import traceback
    rep['passed'] = False
    rep['error'] = traceback.format_exc()
    RES.write_text(json.dumps(rep, indent=1), encoding='utf-8')
    print(rep['error'])
