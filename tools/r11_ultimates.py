"""Round 11: ultimates = the CHARACTER's delivery x the MAGIC's payload.

Delivery (BP_UltimateCast.Delivery = caster's WizardType):
  0 fire boy       one big magic straight forward
  1 ice girl       staff charge, then a burst all around her
  2 wind boy       ninja move, then he dashes forward as a magic orb (knockback)
  3 lightning girl something falls from the sky onto the aimed spot
Payload: BP_UltimateCast.Element (the spell that was charged).

  fire boy   fire  big fireball (unchanged: 2x, hits people only, through walls)
             ice   big ice ball, 2x on a person; on anything it hits it bursts into
                   10 shards (25 % of the ball each); shards never split again
             wind  ricochet wind ball, 125 % per hit, 5 bounces
             light lightning ball every 0.4 s, 10 in all, follows his aim, 25 % each
  ice girl   fire  10 fireballs around, no split
             ice   unchanged: 10 ice balls, each splits into 4 on impact
             wind  10 wind balls, 3 bounces each, 30 % after the first bounce
             light 30 lightning balls, no bounce, no split
  wind boy   fire  dash, stops at a wall or person and explodes (1.5x, r 220)
             ice   dash, no bounce; hit 1.5x, then 10 ice crystals burst around
             wind  unchanged (10 wall bounces, 1.5x + knockback)
             light dash, hit 1.5x, then another 30 % to everyone within 300
  lightning  fire  meteor: 2x to everyone within 330 of the landing spot
  girl       ice   ice ball falls (1x), then splits into 10 shards along the ground
             wind  wind ball falls (1x within 220), then hops forward twice more
             light unchanged (3.2 s storm)
Repeat hits on the same person by one ultimate do 20 % where 'Penalize' is set
(bursts, shards, hops).  Server-side effects (bounces, dash ends, volley flashes)
are small replicated BP_CuteFX actors (this engine's Python cannot add inputs to
multicast events).

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r11_ultimates.py
"""
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
import r11_bp
importlib.reload(r11_bp)
from r11_bp import *          # noqa

RPT = 'r11-ultimates.json'
FX = '/Game/VFX/WizardMagic/Cute/BP_CuteFX'
ELS = ['Fire', 'Ice', 'Wind', 'Lightning']
# placeholder systems for BP_CuteFX until the cute ones exist (r11_vfx.py rewires them)
NS = {e: '/Game/VFX/WizardMagic/V4/Systems/NS_%s_Impact.NS_%s_Impact' % (e, e) for e in ['Fire', 'Ice', 'Wind']}
NS['Lightning'] = '/Game/VFX/WizardMagic/UltimatePolish/Systems/NS_Lightning_Contact.NS_Lightning_Contact'


def per_element(g, elem, make):
    """Branch ladder on an int pin (0..3); make(e) -> (first_node, last_exec_pin) or None.
    Returns (input exec pin, [last exec pins])."""
    sw = g.switch_int(elem, [0, 1, 2, 3])
    lasts = []
    for e in range(4):
        r = make(e)
        if r is None:
            lasts.append(sw[e])
            continue
        first, last = r
        link(sw[e], ex(first))
        lasts.append(last)
    return sw['in'], lasts


# ============================================================ effect actor
def fx_actor():
    """BP_CuteFX: replicated, plays one effect where it is spawned, then dies."""
    if not EAL.does_asset_exist(FX):
        b = L.create_blueprint_asset_with_parent(FX, u.Actor)
        assert b, FX
        ASSETS[FX] = b
        compile_bp(FX, False)
        add_component(FX, 'Root', u.SceneComponent)
        compile_bp(FX, False)
    cdo = u.get_default_object(cls(FX))
    for k, v in [('replicates', True), ('replicate_movement', False), ('always_relevant', False)]:
        cdo.set_editor_property(k, v)
    for n, t, d in [('FXElement', I, '0'), ('Kind', I, '0'), ('Size', R, '1')]:
        declare(FX, n, t, d, 'rep')
        L.set_blueprint_variable_instance_editable(load(FX), n, True)
        L.set_blueprint_variable_expose_on_spawn(load(FX), n, True)
    compile_bp(FX, False)
    g = Graph(FX)
    ev = g.native_event('ReceiveBeginPlay')
    for p in ev.list_output_pins():
        if is_exec(p):
            p.break_pin_links()
    g.e.remove_nodes([n for n in g.e.list_all_nodes() if n.get_class().get_name() not in ('K2Node_Event',)])
    ev = g.native_event('ReceiveBeginPlay')
    life = g.call('/Script/Engine.Actor.SetLifeSpan', InLifespan=3.0)
    chain(pin(ev, 'then', True), life)

    def mk(e):
        n = g.call('/Script/Niagara.NiagaraFunctionLibrary.SpawnSystemAtLocation', SystemTemplate=NS[ELS[e]], Location=g.loc(),
                   Rotation=result(g.call('/Script/Engine.Actor.K2_GetActorRotation')),
                   Scale=g.vec(g.get('Size'), g.get('Size'), g.get('Size')), bAutoDestroy=True, bAutoActivate=True, bPreCullCheck=False)
        return n, then(n)
    start, _ = per_element(g, g.get('FXElement'), mk)
    link(then(life), start)
    layout(g)
    compile_bp(FX, True)


def spawn_fx_fn(p):
    """<p>.SpawnFX(Location, FXElement, Kind, Size): server spawns a BP_CuteFX."""
    g = fresh(p, 'SpawnFX', [('Location', V), ('FXElement', I), ('Kind', I), ('Size', R)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    tr = g.math('MakeTransform', Location=g.inp('Location'), Rotation=(0, 0, 0), Scale=(1, 1, 1))
    be = g.call('/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass', ActorClass=cp(FX), SpawnTransform=tr,
                CollisionHandlingOverride='AlwaysSpawn', TransformScaleMethod='MultiplyWithRoot')
    ca, fx = g.cast(result(be), FX)
    s1 = g.set('FXElement', g.inp('FXElement'), FX, fx)
    s2 = g.set('Kind', g.inp('Kind'), FX, fx)
    s3 = g.set('Size', g.inp('Size'), FX, fx)
    fin = g.call('/Script/Engine.GameplayStatics.FinishSpawningActor', Actor=result(be), SpawnTransform=tr, TransformScaleMethod='MultiplyWithRoot')
    chain(pin(auth, 'then', True), be, ca, s1, s2, s3, fin)
    layout(g)
    compile_bp(p, False)


# ===================================================================== orb
def orb_vars():
    for n, t, d in [('PawnOnly', B, 'false'), ('WorldOnly', B, 'false'), ('Bounces', I, '0'), ('BounceScale', R, '1'), ('BouncesDone', I, '0'),
                    ('SplitMode', I, '0'), ('SplitScale', R, '0.5'), ('AreaRadius', R, '0'), ('AreaScale', R, '0'),
                    ('Hops', I, '0'), ('HopDir', V, '1,0,0'), ('Gravity', R, '0'), ('Penalize', B, 'false')]:
        declare(ORB, n, t, d)
    compile_bp(ORB, False)


def orb_functions():
    # ---- StartOrb: look, ignore the caster and the session, live 5 s (8 s if it bounces or hops)
    g = fresh(ORB, 'StartOrb')
    rv = g.fn('RefreshVisual')
    auth = g.branch(g.authority())
    chain(g.entry(), rv, auth)
    a1 = g.call('/Script/Engine.KismetArrayLibrary.Array_AddUnique', TargetArray=g.get('IgnoreActors'), NewItem=g.get('Caster'))
    a2 = g.call('/Script/Engine.KismetArrayLibrary.Array_AddUnique', TargetArray=g.get('IgnoreActors'), NewItem=g.get('Session'))
    bouncy = g.OR(g.math('Greater_IntInt', A=g.get('Bounces'), B=0), g.math('Greater_IntInt', A=g.get('Hops'), B=0))
    ls = g.call('/Script/Engine.Actor.SetLifeSpan', InLifespan=g.selectf(8.0, 5.0, bouncy))
    chain(pin(auth, 'then', True), a1, a2, ls)
    layout(g)

    # ---- MoveOrb: gravity, then a sphere sweep (people only / world only / everything)
    g = fresh(ORB, 'MoveOrb', [('Delta', R)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    live = g.branch(g.AND(g.valid(g.get('Session')), g.NOT(g.get('Resolved'))))
    link(pin(auth, 'then', True), ex(live))
    grav = g.set('Velocity', g.vsub(g.get('Velocity'), g.vec(0.0, 0.0, g.fmul(g.get('Gravity'), g.inp('Delta')))))
    nxt = g.set('NextLocation', g.vadd(g.loc(), g.vmul(g.get('Velocity'), g.inp('Delta'))))
    only = g.branch(g.get('PawnOnly'))
    chain(pin(live, 'then', True), grav, nxt, only)
    dest = g.call('/Script/Engine.Actor.K2_DestroyActor')
    link(pin(live, 'else', True), ex(dest))

    def trace(types):
        tr = g.call('/Script/Engine.KismetSystemLibrary.SphereTraceSingleForObjects', Start=g.loc(), End=g.get('NextLocation'),
                    Radius=g.get('Radius'), bTraceComplex=False, ActorsToIgnore=g.get('IgnoreActors'), DrawDebugType='None', bIgnoreSelf=True)
        mk = g.node('Utilities|Array|MakeArray')
        link(pin(mk, 'Array', True), pin(tr, 'ObjectTypes'))
        for _ in range(len(types) - 1):
            assert g.e.add_node_pin(mk)
        for k, t in enumerate(types):
            value(pin(mk, '[%d]' % k), t)
        hit = g.branch(result(tr))
        chain(then(tr), hit)
        res = g.fn('ResolveOrb', HitData=pin(tr, 'OutHit', True))
        mv = g.call('/Script/Engine.Actor.K2_SetActorLocation', NewLocation=g.get('NextLocation'), bSweep=False, bTeleport=True)
        link(pin(hit, 'then', True), ex(res))
        link(pin(hit, 'else', True), ex(mv))
        return tr
    t1 = trace(['ObjectTypeQuery3'])
    t2 = trace(['ObjectTypeQuery1', 'ObjectTypeQuery2', 'ObjectTypeQuery3'])
    t3 = trace(['ObjectTypeQuery1', 'ObjectTypeQuery2'])
    link(pin(only, 'then', True), ex(t1))
    world = g.branch(g.get('WorldOnly'))
    link(pin(only, 'else', True), ex(world))
    link(pin(world, 'then', True), ex(t3))
    link(pin(world, 'else', True), ex(t2))
    layout(g)

    # ---- ResolveOrb: damage, area damage, then bounce / hop / split / end
    g = fresh(ORB, 'ResolveOrb', [('HitData', HIT)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    bh = g.call('/Script/Engine.GameplayStatics.BreakHitResult', Hit=g.inp('HitData'))
    P = pin(bh, 'ImpactPoint', True)
    N = pin(bh, 'ImpactNormal', True)
    A = pin(bh, 'HitActor', True)
    S = lambda: g.get('Session')
    direct = g.branch(g.math('Greater_DoubleDouble', A=g.get('DamageScale'), B=0.0))
    link(pin(auth, 'then', True), ex(direct))
    dmg = g.call(cp(CAST) + '.DamageVictim', self=S(), Victim=A, Scale=g.get('DamageScale'), Penalize=g.get('Penalize'))
    link(pin(direct, 'then', True), ex(dmg))
    area = g.branch(g.math('Greater_DoubleDouble', A=g.get('AreaRadius'), B=0.0))
    link(then(dmg), ex(area))
    link(pin(direct, 'else', True), ex(area))
    ad = g.call(cp(CAST) + '.AreaDamage', self=S(), Center=P, Radius=g.get('AreaRadius'), Scale=g.get('AreaScale'), Penalize=g.get('Penalize'))
    link(pin(area, 'then', True), ex(ad))
    bounce = g.branch(g.math('Greater_IntInt', A=g.get('Bounces'), B=0))
    link(then(ad), ex(bounce))
    link(pin(area, 'else', True), ex(bounce))
    # bounce: reflect, step off the surface, weaker after the first bounce if BounceScale < 1
    b1 = g.set('Bounces', g.math('Subtract_IntInt', A=g.get('Bounces'), B=1))
    b2 = g.set('BouncesDone', g.math('Add_IntInt', A=g.get('BouncesDone'), B=1))
    first = g.ieq(g.get('BouncesDone'), 1)
    b3 = g.set('DamageScale', g.selectf(g.fmul(g.get('DamageScale'), g.get('BounceScale')), g.get('DamageScale'), first))
    b4 = g.set('Velocity', g.math('GetReflectionVector', Direction=g.get('Velocity'), SurfaceNormal=N))
    b5 = g.call('/Script/Engine.Actor.K2_SetActorLocation', NewLocation=g.vadd(P, g.vmul(N, g.fadd(g.get('Radius'), 4.0))),
                bSweep=False, bTeleport=True)
    b6 = g.call(cp(CAST) + '.SpawnFX', self=S(), Location=P, FXElement=g.get('Element'), Kind=0, Size=0.55)
    chain(pin(bounce, 'then', True), b1, b2, b3, b4, b5, b6)
    hop = g.branch(g.math('Greater_IntInt', A=g.get('Hops'), B=0))
    link(pin(bounce, 'else', True), ex(hop))
    h1 = g.set('Hops', g.math('Subtract_IntInt', A=g.get('Hops'), B=1))
    h2 = g.set('Velocity', g.vadd(g.vmul(g.get('HopDir'), 650.0), (0.0, 0.0, 720.0)))
    h3 = g.call('/Script/Engine.Actor.K2_SetActorLocation', NewLocation=g.vadd(P, g.vec(0.0, 0.0, g.fadd(g.get('Radius'), 6.0))),
                bSweep=False, bTeleport=True)
    h4 = g.call(cp(CAST) + '.SpawnFX', self=S(), Location=P, FXElement=g.get('Element'), Kind=1, Size=1.0)
    chain(pin(hop, 'then', True), h1, h2, h3, h4)
    e1 = g.set('Resolved', True)
    e2 = g.call('/Script/Engine.Actor.K2_SetActorLocation', NewLocation=P, bSweep=False, bTeleport=True)
    s1 = g.branch(g.ieq(g.get('SplitMode'), 1))
    chain(pin(hop, 'else', True), e1, e2, s1)
    sp1 = g.call(cp(CAST) + '.SplitOrb', self=S(), Position=P, IncomingVelocity=g.get('Velocity'))
    link(pin(s1, 'then', True), ex(sp1))
    s2 = g.branch(g.ieq(g.get('SplitMode'), 2))
    link(pin(s1, 'else', True), ex(s2))
    sp2 = g.call(cp(CAST) + '.RingShards', self=S(), Center=g.vadd(P, g.vmul(N, 30.0)), OrbElement=g.get('Element'), Count=10,
                 Scale=g.get('SplitScale'), Ignore=A)
    link(pin(s2, 'then', True), ex(sp2))
    dest = g.call('/Script/Engine.Actor.K2_DestroyActor')
    link(then(sp1), ex(dest))
    link(then(sp2), ex(dest))
    link(pin(s2, 'else', True), ex(dest))
    layout(g)
    compile_bp(ORB, False)


# ===================================================================== cast
def orb_call(g, pos, vel, el, scale, radius, visual, bounces=0, bscale=1.0, split=0, sscale=0.5, area=0.0, ascale=0.0, hops=0,
             hopdir=(1.0, 0.0, 0.0), grav=0.0, pen=False, pawn=False, world=False, ignore=None):
    kw = dict(Position=pos, Velocity=vel, OrbElement=el, Scale=scale, Radius=radius, Visual=visual, Bounces=bounces,
              BounceScale=bscale, SplitMode=split, SplitScale=sscale, AreaRadius=area, AreaScale=ascale, Hops=hops, HopDir=hopdir,
              Gravity=grav, Penalize=pen, PawnOnly=pawn, WorldOnly=world)
    if ignore is not None:
        kw['Ignore'] = ignore
    return g.fn('SpawnOrbEx', **kw)


def cast_helpers():
    for n, t, d, rep in [('Delivery', I, '0', 'rep'), ('VolleyLeft', I, '0', None), ('NextVolleyAt', R, '0', None)]:
        declare(CAST, n, t, d, rep)
    compile_bp(CAST, False)
    spawn_fx_fn(CAST)
    ACT = obj(u.Actor.static_class())

    # ---- SpawnOrbEx: one orb with every behaviour switch
    g = fresh(CAST, 'SpawnOrbEx', [('Position', V), ('Velocity', V), ('OrbElement', I), ('Scale', R), ('Radius', R), ('Visual', R),
                                   ('Bounces', I), ('BounceScale', R), ('SplitMode', I), ('SplitScale', R), ('AreaRadius', R),
                                   ('AreaScale', R), ('Hops', I), ('HopDir', V), ('Gravity', R), ('Penalize', B), ('PawnOnly', B),
                                   ('WorldOnly', B), ('Ignore', ACT)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    tr = g.math('MakeTransform', Location=g.inp('Position'), Rotation=(0, 0, 0), Scale=(1, 1, 1))
    be = g.call('/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass', ActorClass=cp(ORB), SpawnTransform=tr,
                CollisionHandlingOverride='AlwaysSpawn', Owner=g.get('Caster'), TransformScaleMethod='MultiplyWithRoot')
    ca, orb = g.cast(result(be), ORB)
    sets = [g.set('Session', g.selfref(), ORB, orb), g.set('Caster', g.get('Caster'), ORB, orb)]
    for var, src in [('Element', 'OrbElement'), ('Velocity', 'Velocity'), ('DamageScale', 'Scale'), ('Radius', 'Radius'),
                     ('VisualScale', 'Visual'), ('Bounces', 'Bounces'), ('BounceScale', 'BounceScale'), ('SplitMode', 'SplitMode'),
                     ('SplitScale', 'SplitScale'), ('AreaRadius', 'AreaRadius'), ('AreaScale', 'AreaScale'), ('Hops', 'Hops'),
                     ('HopDir', 'HopDir'), ('Gravity', 'Gravity'), ('Penalize', 'Penalize'), ('PawnOnly', 'PawnOnly'),
                     ('WorldOnly', 'WorldOnly')]:
        sets.append(g.set(var, g.inp(src), ORB, orb))
    # a shard does not hit the one its ball just hit
    ig = g.branch(g.valid(g.inp('Ignore')))
    add_ig = g.call('/Script/Engine.KismetArrayLibrary.Array_AddUnique', TargetArray=g.get('IgnoreActors', ORB, orb), NewItem=g.inp('Ignore'))
    fin = g.call('/Script/Engine.GameplayStatics.FinishSpawningActor', Actor=result(be), SpawnTransform=tr, TransformScaleMethod='MultiplyWithRoot')
    last = chain(pin(auth, 'then', True), be, ca, *sets, ig)
    link(pin(ig, 'then', True), ex(add_ig))
    link(then(add_ig), ex(fin))
    link(pin(ig, 'else', True), ex(fin))
    layout(g)
    compile_bp(CAST, False)

    # ---- DamageVictim(Victim, Scale, Penalize)
    g = fresh(CAST, 'DamageVictim', [('Victim', ACT), ('Scale', R), ('Penalize', B)])
    ok = g.fn('ValidCombat')
    auth = g.branch(g.AND(g.authority(), pin(ok, 'Allowed', True)))
    chain(g.entry(), ok, auth)
    ca, w = g.cast(g.inp('Victim'), CH)
    link(pin(auth, 'then', True), ex(ca))
    alive = g.branch(g.AND(g.math('NotEqual_ObjectObject', A=w, B=g.get('Caster')), g.NOT(g.get('bIsDead', CH, w))))
    link(then(ca), ex(alive))
    seen = result(g.call('/Script/Engine.KismetArrayLibrary.Array_Contains', TargetArray=g.get('Victims'), ItemToFind=w))
    fac = g.selectf(0.2, 1.0, g.AND(seen, g.inp('Penalize')))
    pd = g.set('PendingDamage', g.fmul(g.fmul(g.get('BaseDamage'), g.inp('Scale')), fac))
    add = g.call('/Script/Engine.KismetArrayLibrary.Array_AddUnique', TargetArray=g.get('Victims'), NewItem=w)
    ap = g.call('/Script/Engine.GameplayStatics.ApplyDamage', DamagedActor=w, BaseDamage=g.get('PendingDamage'),
                EventInstigator=result(g.call('/Script/Engine.Pawn.GetController', self=g.get('Caster'))), DamageCauser=g.get('Caster'))
    chain(pin(alive, 'then', True), pd, add, ap)
    layout(g)

    # ---- AreaDamage(Center, Radius, Scale, Penalize)
    g = fresh(CAST, 'AreaDamage', [('Center', V), ('Radius', R), ('Scale', R), ('Penalize', B)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    all_ = g.call('/Script/Engine.GameplayStatics.GetAllActorsOfClass', ActorClass=cp(CH))
    fe = g.foreach(pin(all_, 'OutActors', True))
    chain(pin(auth, 'then', True), all_, fe)
    el = pin(fe, 'Array Element', True)
    d = g.vsub(g.loc(el), g.inp('Center'))
    bv = g.call('/Script/Engine.KismetMathLibrary.BreakVector', InVec=d)
    near = g.AND(g.math('LessEqual_DoubleDouble', A=g.math('VSizeXY', A=d), B=g.inp('Radius')),
                 g.math('LessEqual_DoubleDouble', A=g.math('Abs', A=pin(bv, 'Z', True)), B=260.0))
    inr = g.branch(near)
    link(pin(fe, 'LoopBody', True), ex(inr))
    dv = g.fn('DamageVictim', Victim=el, Scale=g.inp('Scale'), Penalize=g.inp('Penalize'))
    link(pin(inr, 'then', True), ex(dv))
    layout(g)

    # ---- RingShards(Center, OrbElement, Count, Scale): a flat ring of small orbs, no further split
    g = fresh(CAST, 'RingShards', [('Center', V), ('OrbElement', I), ('Count', I), ('Scale', R), ('Ignore', ACT)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    fx = g.fn('SpawnFX', Location=g.inp('Center'), FXElement=g.inp('OrbElement'), Kind=1, Size=1.1)
    lp = g.forloop(0, g.math('Subtract_IntInt', A=g.inp('Count'), B=1))
    chain(pin(auth, 'then', True), fx, lp)
    ang = g.fmul(g.tofloat(pin(lp, 'Index', True)), g.math('Divide_DoubleDouble', A=360.0, B=g.tofloat(g.inp('Count'))))
    dirv = g.math('RotateAngleAxis', InVect=(1, 0, 0), AngleDeg=ang, Axis=(0, 0, 1))
    # start outside a body standing on the burst point
    o = orb_call(g, g.vadd(g.inp('Center'), g.vmul(dirv, 70.0)), g.vmul(dirv, 950.0), g.inp('OrbElement'), g.inp('Scale'), 18.0, 1.0, pen=True,
                 ignore=g.inp('Ignore'))
    link(pin(lp, 'LoopBody', True), ex(o))
    layout(g)

    # ---- RingBurst(...): the ice girl's burst around her
    g = fresh(CAST, 'RingBurst', [('OrbElement', I), ('Count', I), ('Scale', R), ('Radius', R), ('Visual', R), ('Bounces', I),
                                  ('BounceScale', R), ('SplitMode', I)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    lp = g.forloop(0, g.math('Subtract_IntInt', A=g.inp('Count'), B=1))
    link(pin(auth, 'then', True), ex(lp))
    ang = g.fmul(g.tofloat(pin(lp, 'Index', True)), g.math('Divide_DoubleDouble', A=360.0, B=g.tofloat(g.inp('Count'))))
    dirv = g.math('RotateAngleAxis', InVect=(1, 0, 0), AngleDeg=ang, Axis=(0, 0, 1))
    o = orb_call(g, g.vadd(g.loc(g.get('Caster')), g.vmul(dirv, 75.0)), g.vmul(dirv, 950.0), g.inp('OrbElement'), g.inp('Scale'),
                 g.inp('Radius'), g.inp('Visual'), bounces=g.inp('Bounces'), bscale=g.inp('BounceScale'), split=g.inp('SplitMode'), pen=True)
    link(pin(lp, 'LoopBody', True), ex(o))
    layout(g)

    # ---- SplitOrb: the original ice split (4 orbs back in a 120 degree fan, half damage)
    g = fresh(CAST, 'SplitOrb', [('Position', V), ('IncomingVelocity', V)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    lp = g.forloop(0, 3)
    link(pin(auth, 'then', True), ex(lp))
    back = g.vmul(g.math('Normal', A=g.inp('IncomingVelocity'), Tolerance=0.0001), -1.0)
    ang = g.fadd(-60.0, g.fmul(g.tofloat(pin(lp, 'Index', True)), 40.0))
    dirv = g.math('RotateAngleAxis', InVect=back, AngleDeg=ang, Axis=(0, 0, 1))
    o = orb_call(g, g.vadd(g.inp('Position'), g.vmul(dirv, 45.0)), g.vmul(dirv, 1100.0), g.get('Element'), 0.5, 18.0, 1.0, pen=True)
    link(pin(lp, 'LoopBody', True), ex(o))
    layout(g)
    compile_bp(CAST, False)

    # ---- the wind boy: payload where he stops, the end of his dash, his hit on a person
    g = fresh(CAST, 'DashPayload', [('Center', V), ('Ignore', ACT)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)

    def pay(e):
        if e == 0:
            n = g.fn('AreaDamage', Center=g.inp('Center'), Radius=220.0, Scale=1.5, Penalize=False)
        elif e == 1:
            n = g.fn('RingShards', Center=g.inp('Center'), OrbElement=1, Count=10, Scale=0.5, Ignore=g.inp('Ignore'))
        elif e == 3:
            n = g.fn('AreaDamage', Center=g.inp('Center'), Radius=300.0, Scale=0.3, Penalize=False)
        else:
            return None
        return n, then(n)
    start, lasts = per_element(g, g.get('Element'), pay)
    link(pin(auth, 'then', True), start)
    layout(g)

    g = fresh(CAST, 'FinishDash')
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    pop = g.fn('SpawnFX', Location=g.loc(g.get('Caster')), FXElement=g.get('Element'), Kind=1, Size=1.4)
    st = g.fn('StopCast')
    # the session stays a little while: crystals it just threw need it
    de = g.call('/Script/Engine.Actor.SetLifeSpan', InLifespan=4.0)
    chain(pin(auth, 'then', True), pop, st, de)
    layout(g)
    compile_bp(CAST, False)

    # ---- knockback: launch the person away (a teleport sweep was stopped by the dasher's own body)
    g = fresh(CAST, 'KnockbackVictim', [('Victim', obj(cls(CH)))])
    away = g.math('Normal', A=g.math('Multiply_VectorVector', A=g.vsub(g.loc(g.inp('Victim')), g.loc(g.get('Caster'))), B=(1, 1, 0)),
                  Tolerance=0.0001)
    lc = g.call('/Script/Engine.Character.LaunchCharacter', self=g.inp('Victim'), LaunchVelocity=g.vadd(g.vmul(away, 1100.0), (0.0, 0.0, 420.0)),
                bXYOverride=True, bZOverride=True)
    chain(g.entry(), lc)
    layout(g)
    compile_bp(CAST, False)

    g = fresh(CAST, 'DashHit', [('Victim', ACT)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    ca, w = g.cast(g.inp('Victim'), CH)
    link(pin(auth, 'then', True), ex(ca))
    seen = result(g.call('/Script/Engine.KismetArrayLibrary.Array_Contains', TargetArray=g.get('Victims'), ItemToFind=w))
    okv = g.branch(g.AND(g.NOT(seen), g.math('NotEqual_ObjectObject', A=w, B=g.get('Caster')), g.NOT(g.get('bIsDead', CH, w))))
    link(then(ca), ex(okv))
    fb = g.branch(g.ieq(g.get('Element'), 0))
    link(pin(okv, 'then', True), ex(fb))
    dv = g.fn('DamageVictim', Victim=w, Scale=1.5, Penalize=False)
    link(pin(fb, 'else', True), ex(dv))
    pl = g.fn('DashPayload', Center=g.loc(g.get('Caster')), Ignore=w)
    link(pin(fb, 'then', True), ex(pl))       # fire: the explosion is the hit
    link(then(dv), ex(pl))
    kb = g.fn('KnockbackVictim', Victim=w)
    link(then(pl), ex(kb))
    iswind = g.branch(g.ieq(g.get('Element'), 2))
    link(then(kb), ex(iswind))
    link(pin(iswind, 'then', True), ex(g.fn('StopCast')))
    link(pin(iswind, 'else', True), ex(g.fn('FinishDash')))
    layout(g)
    compile_bp(CAST, False)


def cast_flow():
    # ---- StartCast
    g = fresh(CAST, 'StartCast')
    au = g.fn('AudioUltimateStart')
    auth = g.branch(g.authority())
    s1 = g.set('StartedAt', g.now())
    s2 = g.call('/Script/Engine.KismetArrayLibrary.Array_AddUnique', TargetArray=g.get('IgnoreActors'), NewItem=g.get('Caster'))
    chain(g.entry(), au, auth)
    chain(pin(auth, 'then', True), s1, s2)
    sw = g.switch_int(g.get('Delivery'), [0, 1, 2, 3])
    link(then(s2), sw['in'])
    C = lambda: g.loc(g.get('Caster'))
    Dir = lambda: g.get('Direction')
    flat = lambda: g.math('Normal', A=g.math('Multiply_VectorVector', A=g.get('Direction'), B=(1, 1, 0)), Tolerance=0.0001)

    def life(n, t):
        ls = g.call('/Script/Engine.Actor.SetLifeSpan', InLifespan=t)
        chain(then(n), ls)
        return n, then(ls)

    # 0: fire boy, straight forward (the session lives as long as its longest orb)
    def d0(e):
        if e == 0:
            return life(orb_call(g, g.vadd(C(), g.vmul(Dir(), 150.0)), g.vmul(Dir(), 1050.0), 0, 2.0, 100.0, 5.0, pawn=True), 7.0)
        if e == 1:
            return life(orb_call(g, g.vadd(C(), g.vmul(Dir(), 150.0)), g.vmul(Dir(), 1050.0), 1, 2.0, 60.0, 3.6, split=2, sscale=0.5), 9.0)
        if e == 2:
            return life(orb_call(g, g.vadd(C(), g.vmul(flat(), 150.0)), g.vmul(flat(), 1100.0), 2, 1.25, 45.0, 2.6, bounces=5, bscale=1.0), 9.0)
        n = g.set('VolleyLeft', 10)
        n2 = g.set('NextVolleyAt', g.now())
        chain(then(n), n2)
        ls = g.call('/Script/Engine.Actor.SetLifeSpan', InLifespan=9.5)
        chain(then(n2), ls)
        return n, then(ls)
    st, _ = per_element(g, g.get('Element'), d0)
    link(sw[0], st)

    # 1: ice girl, burst all around
    def d1(e):
        cnt, rad, vis = {0: (10, 26.0, 1.6), 1: (10, 18.0, 1.0), 2: (10, 24.0, 1.4), 3: (30, 18.0, 1.1)}[e]
        n = g.fn('RingBurst', OrbElement=e, Count=cnt, Scale=1.0, Radius=rad, Visual=vis, Bounces=3 if e == 2 else 0,
                 BounceScale=0.3, SplitMode=1 if e == 1 else 0)
        return life(n, 9.0)
    st, _ = per_element(g, g.get('Element'), d1)
    link(sw[1], st)

    # 2: wind boy dash (the old wind start, for every magic): flat direction, height, orb form, flying
    flatn = g.set('Direction', flat())
    hgt = g.set('DashHeight', g.math('FClamp', Value=pin(g.call('/Script/Engine.KismetMathLibrary.BreakVector', InVec=C()), 'Z', True),
                                     Min=100.0, Max=700.0))
    de = g.set('DashElement', g.get('Element'), CH, g.get('Caster'))
    dash = g.set('UltimateDashing', True, CH, g.get('Caster'))
    wf = g.call(cp(CH) + '.UpdateWindForm', self=g.get('Caster'))
    cmv = g.place(g.e.add_get_member_variable_node('CharacterMovement', '/Script/Engine.Character'))
    value(cmv.find_self_pin(), g.get('Caster'))
    cmp = pin(cmv, 'CharacterMovement', True)
    fly = g.call('/Script/Engine.CharacterMovementComponent.SetMovementMode', self=cmp, NewMovementMode='MOVE_Flying', NewCustomMode=0)
    stop = g.call('/Script/Engine.MovementComponent.StopMovementImmediately', self=cmp)
    rdy = g.set('DashReady', True)
    lsp = g.call('/Script/Engine.Actor.SetLifeSpan', InLifespan=g.selectf(0.0, 3.5, g.ieq(g.get('Element'), 2)))
    chain(sw[2], flatn, hgt, de, dash, wf, fly, stop, rdy, lsp)

    # 3: lightning girl, from the sky onto the target (this actor stands on it)
    T = lambda: g.loc()

    def d3(e):
        if e == 3:
            n = g.call('/Script/Engine.Actor.SetLifeSpan', InLifespan=3.2)
            return n, then(n)
        # they fall onto the ground (people under them are caught by the landing)
        if e == 0:
            start = g.vsub(g.vadd(T(), (0.0, 0.0, 1150.0)), g.vmul(Dir(), 500.0))
            vel = g.vmul(g.math('Normal', A=g.vsub(T(), start), Tolerance=0.0001), 2600.0)
            return life(orb_call(g, start, vel, 0, 0.0, 70.0, 4.5, area=330.0, ascale=2.0, world=True), 8.0)
        if e == 1:
            return life(orb_call(g, g.vadd(T(), (0.0, 0.0, 1150.0)), (0.0, 0.0, -2500.0), 1, 0.0, 55.0, 3.0, split=2, sscale=0.5,
                                 area=150.0, ascale=1.0, pen=True, world=True), 8.0)
        return life(orb_call(g, g.vadd(T(), (0.0, 0.0, 1150.0)), (0.0, 0.0, -2300.0), 2, 0.0, 55.0, 3.0, area=220.0, ascale=1.0, hops=2,
                             hopdir=Dir(), grav=1700.0, pen=True, world=True), 8.0)
    st, _ = per_element(g, g.get('Element'), d3)
    flat3 = g.set('Direction', flat())
    chain(sw[3], flat3)
    link(then(flat3), st)
    layout(g)
    compile_bp(CAST, False)

    # ---- VolleyStep: the fire boy's lightning volley, aimed where he looks now
    g = fresh(CAST, 'VolleyStep')
    go = g.branch(g.AND(g.math('Greater_IntInt', A=g.get('VolleyLeft'), B=0),
                        g.math('GreaterEqual_DoubleDouble', A=g.now(), B=g.get('NextVolleyAt')), g.valid(g.get('Caster'))))
    chain(g.entry(), go)
    v1 = g.set('VolleyLeft', g.math('Subtract_IntInt', A=g.get('VolleyLeft'), B=1))
    v2 = g.set('NextVolleyAt', g.fadd(g.get('NextVolleyAt'), 0.4))
    aim = g.math('GetForwardVector', InRot=result(g.call('/Script/Engine.Pawn.GetBaseAimRotation', self=g.get('Caster'))))
    fp = g.get('FirePoint', CH, g.get('Caster'))
    start = result(g.call('/Script/Engine.SceneComponent.K2_GetComponentLocation', self=fp))
    o = orb_call(g, g.vadd(start, g.vmul(aim, 40.0)), g.vmul(aim, 1500.0), 3, 0.25, 30.0, 1.6)
    act = g.call(cp(CH) + '.QueueWizardAction', self=g.get('Caster'), ActionCode=3)
    pop = g.fn('SpawnFX', Location=start, FXElement=3, Kind=2, Size=0.6)
    chain(pin(go, 'then', True), v1, v2, o, act, pop)
    layout(g)

    # ---- TickCast
    g = fresh(CAST, 'TickCast', [('Delta', R)])
    aw = g.fn('AudioWallTick')
    auth = g.branch(g.authority())
    chain(g.entry(), aw, auth)
    ok = g.fn('ValidCombat')
    valid = g.branch(pin(ok, 'Allowed', True))
    chain(pin(auth, 'then', True), ok, valid)
    chain(pin(valid, 'else', True), g.fn('StopCast'), g.call('/Script/Engine.Actor.K2_DestroyActor'))
    go = g.branch(g.NOT(g.get('Stopped')))             # a stopped dash just waits for its lifespan
    link(pin(valid, 'then', True), ex(go))
    sw = g.switch_int(g.get('Delivery'), [0, 2, 3])
    link(pin(go, 'then', True), sw['in'])
    vb = g.branch(g.ieq(g.get('Element'), 3))
    link(sw[0], ex(vb))
    link(pin(vb, 'then', True), ex(g.fn('VolleyStep')))
    link(sw[2], ex(g.fn('DashStep', Delta=g.inp('Delta'))))
    sb = g.branch(g.ieq(g.get('Element'), 3))
    link(sw[3], ex(sb))
    # the storm: 15 pulses a second, 45 in all (as before)
    tt = g.set('TickTarget', g.math('Min', A=45, B=g.math('FTrunc', A=g.fmul(g.fsub(g.now(), g.get('StartedAt')), 15.0))))
    more = g.branch(g.math('Greater_IntInt', A=g.get('TickTarget'), B=g.get('PulseCount')))
    lp = g.forloop(g.get('PulseCount'), g.math('Subtract_IntInt', A=g.get('TickTarget'), B=1))
    chain(pin(sb, 'then', True), tt, more)
    link(pin(more, 'then', True), ex(lp))
    link(pin(lp, 'LoopBody', True), ex(g.fn('StormPulse')))
    layout(g)
    compile_bp(CAST, False)

    # ---- DashStep (the old one: move along Direction, walls, people) with the payload rules
    g = fresh(CAST, 'DashStep', [('Delta', R)])
    auth = g.branch(g.authority())
    chain(g.entry(), auth)
    s1 = g.set('PreviousLocation', g.loc(g.get('Caster')))
    s2 = g.set('NextLocation', g.vadd(g.get('PreviousLocation'), g.vmul(g.get('Direction'), g.fmul(g.get('DashSpeed'), g.inp('Delta')))))
    allw = g.call('/Script/Engine.GameplayStatics.GetAllActorsOfClass', ActorClass=cp(CH))
    tr = g.call('/Script/Engine.KismetSystemLibrary.SphereTraceSingle', Start=g.get('PreviousLocation'), End=g.get('NextLocation'),
                Radius=42.0, TraceChannel='TraceTypeQuery1', bTraceComplex=False, ActorsToIgnore=pin(allw, 'OutActors', True),
                DrawDebugType='None', bIgnoreSelf=True)
    s3 = g.set('WallHit', pin(tr, 'OutHit', True))
    hitb = g.branch(result(tr))
    chain(pin(auth, 'then', True), s1, s2, allw, tr, s3, hitb)
    bh = g.call('/Script/Engine.GameplayStatics.BreakHitResult', Hit=g.get('WallHit'))
    wallpos = g.vadd(g.math('Multiply_VectorVector', A=g.vadd(pin(bh, 'Location', True), g.vmul(pin(bh, 'ImpactNormal', True), 3.0)), B=(1, 1, 0)),
                     g.vec(0.0, 0.0, g.get('DashHeight')))
    mvw = g.call('/Script/Engine.Actor.K2_SetActorLocation', self=g.get('Caster'), NewLocation=wallpos, bSweep=False, bTeleport=True)
    link(pin(hitb, 'then', True), ex(mvw))
    windb = g.branch(g.ieq(g.get('Element'), 2))
    link(then(mvw), ex(windb))
    # wind: bounce off the wall (up to 10)
    w1 = g.set('WallBounces', g.math('Add_IntInt', A=g.get('WallBounces'), B=1))
    w2 = g.set('Direction', g.math('GetReflectionVector', Direction=g.get('Direction'), SurfaceNormal=pin(bh, 'ImpactNormal', True)))
    w3 = g.fn('SpawnFX', Location=pin(bh, 'ImpactPoint', True), FXElement=2, Kind=0, Size=0.8)
    enough = g.branch(g.math('GreaterEqual_IntInt', A=g.get('WallBounces'), B=10))
    chain(pin(windb, 'then', True), w1, w2, w3, enough)
    chain(pin(enough, 'then', True), g.fn('StopCast'), g.call('/Script/Engine.Actor.K2_DestroyActor'))
    # the others stop at the wall with their payload
    chain(pin(windb, 'else', True), g.fn('DashPayload', Center=g.loc(g.get('Caster'))), g.fn('FinishDash'))
    # (DashHit / DashPayload take an 'Ignore' actor: the person just hit)
    # no wall: move on
    mv = g.call('/Script/Engine.Actor.K2_SetActorLocation', self=g.get('Caster'),
                NewLocation=g.vadd(g.math('Multiply_VectorVector', A=g.get('NextLocation'), B=(1, 1, 0)), g.vec(0.0, 0.0, g.get('DashHeight'))),
                bSweep=False, bTeleport=True)
    link(pin(hitb, 'else', True), ex(mv))
    face = g.call('/Script/Engine.Actor.K2_SetActorRotation', self=g.get('Caster'), NewRotation=g.math('MakeRotFromX', X=g.get('Direction')),
                  bTeleportPhysics=True)
    df = g.set('DashFacing', g.math('Normal', A=g.math('Multiply_VectorVector', A=g.get('Direction'), B=(1, 1, 0)), Tolerance=0.0001), CH,
               g.get('Caster'))
    link(then(mv), ex(face))
    link(pin(enough, 'else', True), ex(face))
    chain(then(face), df)
    fe = g.foreach(pin(allw, 'OutActors', True))
    link(then(df), ex(fe))
    el = pin(fe, 'Array Element', True)
    seg = g.math('FindClosestPointOnSegment', Point=g.loc(el), SegmentStart=g.get('PreviousLocation'), SegmentEnd=g.loc(g.get('Caster')))
    near = g.branch(g.AND(g.math('LessEqual_DoubleDouble', A=g.math('Vector_Distance', V1=seg, V2=g.loc(el)), B=90.0),
                          g.math('NotEqual_ObjectObject', A=el, B=g.get('Caster')), g.NOT(g.get('Stopped'))))
    link(pin(fe, 'LoopBody', True), ex(near))
    link(pin(near, 'then', True), ex(g.fn('DashHit', Victim=el)))
    layout(g)
    compile_bp(CAST, False)

    # ---- StormPulse: same storm, new damage signature, visual bolts through SpawnOrbEx
    g = fresh(CAST, 'StormPulse')
    auth = g.branch(g.AND(g.authority(), g.math('Less_IntInt', A=g.get('PulseCount'), B=45)))
    chain(g.entry(), auth)
    s = g.set('PulseCount', g.math('Add_IntInt', A=g.get('PulseCount'), B=1))
    link(pin(auth, 'then', True), ex(s))
    ad = g.fn('AreaDamage', Center=g.loc(), Radius=g.get('StormRadius'), Scale=0.1, Penalize=False)
    link(then(s), ex(ad))
    ang = g.math('RandomFloatInRange', Min=0.0, Max=360.0)
    off = g.vmul(g.math('RotateAngleAxis', InVect=(1, 0, 0), AngleDeg=ang, Axis=(0, 0, 1)), g.math('RandomFloatInRange', Min=0.0, Max=280.0))
    o = orb_call(g, g.vadd(g.vadd(g.loc(), off), (0.0, 0.0, 240.0)), (0.0, 0.0, -2600.0), 3, 0.0, 18.0, 1.0)
    link(then(ad), ex(o))
    layout(g)

    # ---- StopCast / RefreshCastVisual / AudioUltimateStart: element checks -> delivery checks
    for gname in ['StopCast', 'RefreshCastVisual', 'AudioUltimateStart']:
        g = Graph(CAST, gname)
        for n in list(g.e.list_all_nodes()):
            if n.get_class().get_name() != 'K2Node_VariableGet' or str(n.get_node_title()) != 'Get Element':
                continue
            links = sum(len(list(p.list_connected_pins())) for p in n.list_output_pins())
            if gname != 'StopCast' and links != 1:
                continue            # the per-element sound ladder keeps its element checks
            for p in n.list_output_pins():
                for q in list(p.list_connected_pins()):
                    eq = q.get_owning_node()
                    bpin = eq.find_input_pin('B')
                    bval = str(bpin.get_pin_value()) if bpin.is_valid() else ''
                    if gname == 'StopCast' and bval == '2':
                        p.break_single_pin_link(q)          # the caster is restored when a DASH ends
                        link(g.get('Delivery'), q)
                    if gname in ('RefreshCastVisual', 'AudioUltimateStart') and bval == '3':
                        both = g.AND(g.ieq(g.get('Element'), 3), g.ieq(g.get('Delivery'), 3))
                        outp = result(eq)
                        for t in list(outp.list_connected_pins()):
                            outp.break_single_pin_link(t)
                            link(both, t)
        layout(g)
    # remove the old helpers nobody calls any more
    for old in ['SpawnOrb']:
        if old in [str(x) for x in L.list_graph_names(load(CAST))]:
            L.remove_function_graph(load(CAST), old)
    compile_bp(CAST, True)


# ============================================================ character side
def character():
    declare(CH, 'DashElement', I, '2', 'rep')
    compile_bp(CH, False)
    declare(TELE, 'Delivery', I, '0', 'rep')
    L.set_blueprint_variable_instance_editable(load(TELE), 'Delivery', True)
    L.set_blueprint_variable_expose_on_spawn(load(TELE), 'Delivery', True)
    compile_bp(TELE, False)

    # ---- LaunchElementUltimate: delivery = WizardType; the lightning girl's cast stands on the target
    g = fresh(CH, 'LaunchElementUltimate', [('ElementIndex', I)])
    s0 = g.set('UltimateWindupActive', False)
    ok = g.fn('CanActInMatch')                 # pure
    go = g.branch(g.AND(g.authority(), pin(ok, 'Allowed', True)))
    chain(g.entry(), s0, go)
    W = g.toint(g.get('WizardType'))
    where = g.selectv(g.get('LockedStormTarget'), g.loc(), g.ieq(W, 3))
    tr = g.math('MakeTransform', Location=where, Rotation=(0, 0, 0), Scale=(1, 1, 1))
    be = g.call('/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass', ActorClass=cp(CAST), SpawnTransform=tr,
                CollisionHandlingOverride='AlwaysSpawn', Owner=g.selfref(), TransformScaleMethod='MultiplyWithRoot')
    ca, c = g.cast(result(be), CAST)
    sets = [g.set('Caster', g.selfref(), CAST, c), g.set('Element', g.inp('ElementIndex'), CAST, c),
            g.set('Delivery', g.toint(g.get('WizardType')), CAST, c),
            g.set('BaseDamage', g.selectf(26.4, 22.4, g.ieq(g.inp('ElementIndex'), 0)), CAST, c),
            g.set('Direction', g.get('LockedUltimateDirection'), CAST, c)]
    fin = g.call('/Script/Engine.GameplayStatics.FinishSpawningActor', Actor=result(be), SpawnTransform=tr, TransformScaleMethod='MultiplyWithRoot')
    chain(pin(go, 'then', True), be, ca, *sets, fin)
    layout(g)

    # ---- BeginUltimateWindup: direction, target, stop, telegraph shaped by the character
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
    bh = g.call('/Script/Engine.GameplayStatics.BreakHitResult', Hit=pin(lt, 'OutHit', True))
    ground = g.selectv(g.vadd(pin(bh, 'ImpactPoint', True), (0.0, 0.0, 5.0)), g.vadd(g.loc(), (0.0, 0.0, -84.0)), result(lt))
    flat = g.math('Normal', A=g.math('Multiply_VectorVector', A=g.get('LockedUltimateDirection'), B=(1, 1, 0)), Tolerance=0.0001)
    lane0 = g.vadd(ground, g.vmul(flat, 2625.0))
    lane2 = g.vadd(ground, g.vmul(flat, 1250.0))
    where = g.selectv(g.get('LockedStormTarget'), g.selectv(lane0, g.selectv(lane2, ground, g.ieq(W(), 2)), g.ieq(W(), 0)), g.ieq(W(), 3))
    tr = g.math('MakeTransform', Location=where, Rotation=g.math('MakeRotFromX', X=flat), Scale=(1, 1, 1))
    be = g.call('/Script/Engine.GameplayStatics.BeginDeferredActorSpawnFromClass', ActorClass=cp(TELE), SpawnTransform=tr,
                CollisionHandlingOverride='AlwaysSpawn', Owner=g.selfref(), TransformScaleMethod='MultiplyWithRoot')
    ca, t = g.cast(result(be), TELE)
    e1 = g.set('Element', g.inp('ElementIndex'), TELE, t)
    e2 = g.set('Delivery', W(), TELE, t)
    fin = g.call('/Script/Engine.GameplayStatics.FinishSpawningActor', Actor=result(be), SpawnTransform=tr, TransformScaleMethod='MultiplyWithRoot')
    chain(then(lt), be, ca, e1, e2, fin)
    layout(g)
    compile_bp(CH, False)

    # ---- telegraph: shape by the character, colour by the magic
    g = fresh(TELE, 'ApplyWarningVisual')
    D = lambda: g.get('Delivery')
    el = lambda: g.get('Element')
    mats = ['/Game/BluePrint/Magic/Ultimates/Telegraphs/M_%s_Telegraph.M_%s_Telegraph' % (e, e) for e in ELS]

    def mk(e):
        n = g.call('/Script/Engine.PrimitiveComponent.SetMaterial', self=g.get('WarningSurface'), ElementIndex=0, Material=mats[e])
        return n, then(n)
    start, lasts = per_element(g, el(), mk)
    link(g.entry(), start)
    circle3 = g.selectf(6.9, g.selectf(6.383, 5.0, g.ieq(el(), 3)), g.ieq(el(), 0))
    sx = g.selectf(52.5, g.selectf(9.574, g.selectf(25.0, circle3, g.ieq(D(), 2)), g.ieq(D(), 1)), g.ieq(D(), 0))
    sy = g.selectf(2.4, g.selectf(9.574, g.selectf(1.8, circle3, g.ieq(D(), 2)), g.ieq(D(), 1)), g.ieq(D(), 0))
    sc = g.call('/Script/Engine.SceneComponent.SetRelativeScale3D', self=g.get('WarningSurface'), NewScale3D=g.vec(sx, sy, 1.0))
    for l in lasts:
        link(l, ex(sc))
    layout(g)
    compile_bp(TELE, True)

    # ---- the lightning girl sees her landing circle whenever the current spell is charged
    g = fresh(CH, 'CurrentSpellCharged', outputs=[('Charged', B)], pure=True)
    cur = lambda: g.toint(g.get('CurrentSpellType'))
    anyc = g.OR(g.AND(g.ieq(cur(), 0), g.ieq(g.get('FireSpellState'), 2)), g.AND(g.ieq(cur(), 1), g.ieq(g.get('IceSpellState'), 2)),
                g.AND(g.ieq(cur(), 2), g.ieq(g.get('WindSpellState'), 2)), g.AND(g.ieq(cur(), 3), g.ieq(g.get('LightningSpellState'), 2)))
    chain(g.entry(), g.ret(Charged=anyc))
    layout(g)
    compile_bp(CH, False)
    g = Graph(CH, 'UpdateStormAim')
    done = any('CurrentSpellCharged' in str(n.get_node_title()).replace(' ', '') for n in g.e.list_all_nodes())   # patched before
    for n in list(g.e.list_all_nodes()):
        if done or n.get_class().get_name() != 'K2Node_CommutativeAssociativeBinaryOperator':
            continue
        a, b = n.find_input_pin('A'), n.find_input_pin('B')
        srcs = [q.get_owning_node() for q in list(a.list_connected_pins()) + list(b.list_connected_pins())]
        if len(srcs) == 2 and all(s.get_class().get_name() == 'K2Node_PromotableOperator' for s in srcs):
            outp = result(n)
            tg = list(outp.list_connected_pins())
            ch_ = g.fn('CurrentSpellCharged')
            both = g.AND(g.ieq(g.toint(g.get('WizardType')), 3), pin(ch_, 'Charged', True))
            for t in tg:
                outp.break_single_pin_link(t)
                link(both, t)
            remove_tree(g, [n])
            done = True
    assert done, 'UpdateStormAim condition not found'
    layout(g)

    # ---- the wind boy's orb form: hide the wizard (and anything on him), orb colour by the magic
    g = Graph(CH, 'UpdateWindForm')
    for n in list(g.e.list_all_nodes()):
        if n.get_class().get_name() != 'K2Node_VariableGet' or str(n.get_node_title()) != 'Get Mesh':
            continue
        outp = pin(n, 'Mesh', True)
        for q in list(outp.list_connected_pins()):
            owner = q.get_owning_node()
            if str(q.get_pin_name()) == 'self' and 'Visib' in str(owner.get_node_title()):
                outp.break_single_pin_link(q)
                link(g.get('WizardMeshV5'), q)
                pp = owner.find_input_pin('bPropagateToChildren')
                if pp.is_valid():
                    value(pp, True)
    mats = ['/Game/BluePrint/Magic/Ultimates/M_UltimateOrb_%s.M_UltimateOrb_%s' % (e, e) for e in ELS]
    if not any(str(n.get_node_title()) == 'Set Material' for n in g.e.list_all_nodes()):
        act = next(n for n in g.e.list_all_nodes() if n.get_class().get_name() == 'K2Node_CallFunction' and str(n.get_node_title()) == 'Activate')
        inexec = list(ex(act).list_connected_pins())
        ex(act).break_pin_links()

        def mk(e):
            n = g.call('/Script/Engine.PrimitiveComponent.SetMaterial', self=g.get('WindFormMesh'), ElementIndex=0, Material=mats[e])
            return n, then(n)
        start, lasts = per_element(g, g.get('DashElement'), mk)
        for p in inexec:
            link(p, start)
        for l in lasts:
            link(l, ex(act))
    layout(g)
    compile_bp(CH, False)

    # ---- ultimate wind-up animations by character: codes 4..7 -> 4 + WizardType
    g = Graph(CH, 'PlayWizardAction')
    if any(str(n.get_node_title()) == 'Select Int' or 'SelectInt' in str(n.get_node_title()) for n in g.e.list_all_nodes()):
        compile_bp(CH, True)          # patched before
        return
    targets = []
    for n in list(g.e.list_all_nodes()):
        if n.get_class().get_name() != 'K2Node_PromotableOperator' or 'Equal' not in str(n.get_node_title()):
            continue
        a, b = n.find_input_pin('A'), n.find_input_pin('B')
        if not (a.is_valid() and b.is_valid()):
            continue
        srcs = list(a.list_connected_pins())
        if len(srcs) == 1 and srcs[0].get_owning_node().get_class().get_name() == 'K2Node_FunctionEntry' and str(b.get_pin_value()) in ('4', '5', '6', '7'):
            targets.append(a)
    assert len(targets) == 4, len(targets)
    code = g.inp('ActionCode')
    isult = g.AND(g.math('GreaterEqual_IntInt', A=code, B=4), g.math('LessEqual_IntInt', A=code, B=7))
    eff = g.math('SelectInt', A=g.math('Add_IntInt', A=4, B=g.toint(g.get('WizardType'))), B=code, bPickA=isult)
    for a in targets:
        a.break_pin_links()
        link(eff, a)
    layout(g)
    compile_bp(CH, True)


def main():
    try:
        for p in [CH, CAST, ORB, TELE]:
            backup(p)
        # empty the graphs that call functions whose signatures change (rewritten below)
        names = [str(x) for x in L.list_graph_names(load(CAST))]
        for p, name in [(CAST, 'StormPulse'), (CAST, 'DashStep'), (CAST, 'SplitOrb'), (CAST, 'StartCast'), (CAST, 'RingShards'),
                        (CAST, 'RingBurst'), (CAST, 'VolleyStep'), (CAST, 'DashHit'), (CAST, 'DashPayload'), (ORB, 'ResolveOrb')]:
            if p == CAST and name not in names:
                continue
            g = Graph(p, name)
            g.e.remove_nodes([n for n in g.e.list_all_nodes() if n.get_class().get_name() not in ('K2Node_FunctionEntry', 'K2Node_FunctionResult')])
        declare(CH, 'DashElement', I, '2', 'rep')      # the cast sets it on the caster
        compile_bp(CH, False)
        fx_actor()
        log('effect actor ready', RPT)
        orb_vars()
        cast_helpers()
        log('cast helpers ready', RPT)
        orb_functions()
        log('orb ready', RPT)
        cast_flow()
        log('cast flow ready', RPT)
        compile_bp(ORB, True)
        character()
        log('character wired', RPT)
        REPORT['passed'] = True
        log('done', RPT)
        print('R11_ULTIMATES_DONE')
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        (OUT / RPT).write_text(json.dumps(REPORT, indent=1, default=str), encoding='utf-8')
        u.log_error(traceback.format_exc())


main()
