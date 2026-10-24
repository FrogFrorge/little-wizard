"""PIE test (round 11): every character x every magic ultimate through the real
game flow (spell charged -> Server_Fire -> wind-up -> launch), on a test floor far
from the arena, with four dummy wizards (AI controllers with player states so they
take damage like players).  Records damage per dummy, orbs, effect pops, the
caster's path; screenshots at the wind-up and mid-flight.

UnrealEditor <uproject> -RenderOffscreen -ExecCmds="py r11_test_ultimates.py"
Options (env R11_ONLY="0:1,2:3" = delivery:element pairs) for reruns.
"""
import unreal as u
import json
import math
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/round11'
SHOTS = OUT / 'shots'
SHOTS.mkdir(parents=True, exist_ok=True)
RES = OUT / 'test-ultimates.json'
ls = u.get_editor_subsystem(u.LevelEditorSubsystem)
sysobj = u.get_default_object(u.SystemLibrary)
gs = u.get_default_object(u.GameplayStatics)
u.get_default_object(u.load_class(None, '/Script/UnrealEd.LevelEditorPlaySettings')).set_editor_property('PlayNumberOfClients', 1)
try:
    u.get_default_object(u.load_class(None, '/Script/UnrealEd.EditorPerformanceSettings')).set_editor_property('bThrottleCPUWhenNotForeground', False)
except Exception:
    pass
CH = '/Game/ThirdPerson/Blueprints/BP_WizardCharacter'
ORB = '/Game/BluePrint/Magic/Ultimates/BP_UltimateOrb'
CAST = '/Game/BluePrint/Magic/Ultimates/BP_UltimateCast'
FX = '/Game/VFX/WizardMagic/Cute/BP_CuteFX'
TELE = '/Game/BluePrint/Magic/Ultimates/Telegraphs/BP_UltimateTelegraph'
ELS = ['Fire', 'Ice', 'Wind', 'Lightning']
WHO = ['fireboy', 'icegirl', 'windboy', 'lightninggirl']
O = u.Vector(0.0, 40000.0, 130.0)       # floor top at z = 0 (the dash height is clamped to 100..700)
DUMMIES = [u.Vector(700, 0, 0), u.Vector(700, 250, 0), u.Vector(0, 520, 0), u.Vector(-420, -300, 0)]
COMBOS = [(d, e) for d in range(4) for e in range(4)]
if os.environ.get('R11_ONLY'):
    COMBOS = [tuple(int(x) for x in p.split(':')) for p in os.environ['R11_ONLY'].split(',')]
ctx = dict(stage='wait', at=time.monotonic(), i=0, log=[], start=time.monotonic(), results={}, made=[], dummies=[])


def note(s):
    ctx['log'].append('%.1f %s' % (time.monotonic() - ctx['start'], s))
    RES.write_text(json.dumps({k: v for k, v in ctx.items() if k in ('log', 'results', 'stage', 'i')}, indent=1, default=str), encoding='utf-8')


def finish():
    note('finish')
    try:
        u.unregister_slate_post_tick_callback(ctx['handle'])
    except Exception:
        pass
    ls.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def prop(o, n, v, k='Double'):
    sysobj.call_method('Set%sPropertyByName' % k, (o, n, v))


def spawn(w, klass, pos, props=None, rot=None):
    tr = u.Transform(location=pos, rotation=rot or u.Rotator(0, 0, 0))
    o = gs.call_method('BeginDeferredActorSpawnFromClass', (w, klass, tr, u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None,
                                                            u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    for n, (v, k) in (props or {}).items():
        prop(o, n, v, k)
    o = gs.call_method('FinishSpawningActor', (o, tr, u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    return o


def block(w, pos, scale):
    a = spawn(w, u.StaticMeshActor.static_class(), pos)
    m = a.get_component_by_class(u.StaticMeshComponent)
    m.set_mobility(u.ComponentMobility.MOVABLE)
    m.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
    m.set_collision_profile_name('BlockAll')
    a.set_actor_scale3d(scale)
    ctx['made'].append(a)
    return a


def build_site(w):
    block(w, O + u.Vector(0, 0, -150), u.Vector(60, 60, 0.4))            # floor, top at O.z - 130
    block(w, O + u.Vector(1500, 0, 150), u.Vector(0.4, 20, 6))            # front wall
    block(w, O + u.Vector(-760, 0, 150), u.Vector(0.4, 20, 6))            # back wall
    block(w, O + u.Vector(370, 1050, 150), u.Vector(23, 0.4, 6))           # side walls
    block(w, O + u.Vector(370, -1050, 150), u.Vector(23, 0.4, 6))
    chc = u.load_asset(CH).generated_class()
    for k, d in enumerate(DUMMIES):
        dm = spawn(w, chc, O + d, rot=u.Rotator(0, 0, 180))
        ai = spawn(w, u.AIController.static_class(), O + d, {'bWantsPlayerState': (True, 'Bool')})
        ai.possess(dm)
        ctx['dummies'].append(dm)
        ctx['made'].append(ai)
    note('site built, dummies %d' % len(ctx['dummies']))


def reset_dummies():
    for k, dm in enumerate(ctx['dummies']):
        prop(dm, 'MaxHealth', 1000.0)
        prop(dm, 'Health', 1000.0)
        prop(dm, 'bIsDead', False, 'Bool')
        dm.set_actor_location(O + DUMMIES[k], False, True)
        dm.set_actor_rotation(u.Rotator(0, 0, 180), True)


def health(dm):
    return dm.get_editor_property('Health')


def all_of(w, path):
    return list(u.GameplayStatics.get_all_actors_of_class(w, u.load_asset(path).generated_class()))


def shot(w, name):
    u.SystemLibrary.execute_console_command(w, 'HighResShot 1280x720 filename=%s' % (SHOTS / (name + '.png')).as_posix())


def tick(dt):
    try:
        if time.monotonic() - ctx['start'] > 1500:
            note('timeout')
            finish()
            return
        ws = u.EditorLevelLibrary.get_pie_worlds(True)
        if not ws:
            return
        w = ws[0]
        pc = u.GameplayStatics.get_player_controller(w, 0)
        pawn = u.GameplayStatics.get_player_pawn(w, 0)
        if not pc or not pawn:
            return
        el = time.monotonic() - ctx['at']
        st = ctx['stage']
        if st == 'wait':
            if el > 4:
                sysobj.call_method('K2_SetTimer', (pc, 'ExploreGeometric', .1, False, 0, 0))
                ctx.update(stage='enter', at=time.monotonic())
                note('explore requested')
            return
        if st == 'enter':
            if el > 7:
                state = u.GameplayStatics.get_game_state(w)
                note('match phase %s practice %s' % (state.get_editor_property('MatchPhase'), state.get_editor_property('PracticeMode')))
                build_site(w)
                ctx.update(stage='setup', at=time.monotonic())
            return
        if ctx['i'] >= len(COMBOS):
            finish()
            return
        d, e = COMBOS[ctx['i']]
        key = '%s_%s' % (WHO[d], ELS[e].lower())
        if st == 'setup':
            for path in (ORB, CAST, FX, TELE):
                for a in all_of(w, path):
                    a.destroy_actor()
            prop(pawn, 'UltimateDashing', False, 'Bool')
            prop(pawn, 'UltimateWindupActive', False, 'Bool')
            pawn.get_editor_property('character_movement').set_movement_mode(u.MovementMode.MOVE_WALKING)
            sysobj.call_method('SetBytePropertyByName', (pawn, 'WizardType', d))
            pawn.call_method('InitializeWizardTraits')
            sysobj.call_method('SetBytePropertyByName', (pawn, 'CurrentSpellType', e))
            for k, name in enumerate(ELS):
                prop(pawn, name + 'SpellState', 2 if k == e else 0, 'Int')
            pawn.set_actor_location(O, False, True)
            pawn.set_actor_rotation(u.Rotator(0, 0, 0), True)
            pc.set_control_rotation(u.Rotator(roll=0, pitch=-6, yaw=0))
            reset_dummies()
            ctx.update(stage='settle', at=time.monotonic(), orbs=set(), fx=0, fxkinds={}, path=[], h0=None, flags=set())
            return
        if st == 'settle':
            if el > 1.2:
                ctx['h0'] = [health(dm) for dm in ctx['dummies']]
                aim = O + DUMMIES[0]
                pawn.call_method('Server_Fire', (aim,))
                # the landing spot: under the first dummy
                if d == 3:
                    prop(pawn, 'LockedStormTarget', O + DUMMIES[0] + u.Vector(0, 0, -122), 'Vector') if False else \
                        sysobj.call_method('SetVectorPropertyByName', (pawn, 'LockedStormTarget', O + DUMMIES[0] + u.Vector(0, 0, -122)))
                ctx.update(stage='watch', at=time.monotonic(), seen_fx=set())
                note('%s fired, state now %s' % (key, pawn.get_editor_property(ELS[e] + 'SpellState')))
            return
        if st == 'watch':
            fl = ctx['flags']
            for a in all_of(w, ORB):
                if a.get_name() not in ctx['orbs'] and len(ctx['orbs']) < 3:
                    ctx.setdefault('trk', {})[a.get_name()] = []
                ctx['orbs'].add(a.get_name())
                if a.get_name() in ctx.get('trk', {}) and len(ctx['trk'][a.get_name()]) < 12 and int(el * 10) % 2 == 0:
                    p_ = a.get_actor_location() - O
                    v_ = a.get_editor_property('Velocity')
                    ctx['trk'][a.get_name()].append([round(el, 2), round(p_.x), round(p_.y), round(p_.z), round(v_.x), round(v_.y), round(v_.z),
                                                     a.get_editor_property('Resolved')])
            for a in all_of(w, CAST):
                if 'castdir' not in ctx:
                    dv = a.get_editor_property('Direction')
                    ctx['castdir'] = [round(dv.x, 3), round(dv.y, 3), round(dv.z, 3), a.get_editor_property('Delivery'), a.get_editor_property('Element'),
                                      [round(x) for x in ((a.get_actor_location() - O).x, (a.get_actor_location() - O).y, (a.get_actor_location() - O).z)]]
            for a in all_of(w, FX):
                n = a.get_name()
                if n not in ctx['seen_fx']:
                    ctx['seen_fx'].add(n)
                    kd = a.get_editor_property('Kind')
                    ctx['fxkinds'][str(kd)] = ctx['fxkinds'].get(str(kd), 0) + 1
            p = pawn.get_actor_location()
            ctx['path'].append([round(p.x - O.x), round(p.y - O.y), round(p.z - O.z)])
            if el > 0.45 and 'w' not in fl:
                shot(w, 'u_%s_a_windup' % key)
                fl.add('w')
            if el > 1.35 and 'm' not in fl:
                shot(w, 'u_%s_b_mid' % key)
                fl.add('m')
            if el > 2.2 and 'n' not in fl:
                shot(w, 'u_%s_c_late' % key)
                fl.add('n')
            if el > 7.5:
                dmg = [round(h0 - health(dm), 2) for h0, dm in zip(ctx['h0'], ctx['dummies'])]
                path = ctx['path']
                far = max(math.hypot(q[0], q[1]) for q in path) if path else 0
                ctx['results'][key] = dict(damage=dmg, total=round(sum(dmg), 2), orbs=len(ctx['orbs']), fx=ctx['fxkinds'],
                                           caster_max_travel=round(far), caster_end=path[-1] if path else None,
                                           track=ctx.pop('trk', {}), cast=ctx.pop('castdir', None), path_head=path[:6],
                                           dummy_end=[[round(x) for x in ((dm.get_actor_location() - O).x, (dm.get_actor_location() - O).y)]
                                                      for dm in ctx['dummies']])
                note('%s damage %s orbs %d fx %s travel %d' % (key, dmg, len(ctx['orbs']), ctx['fxkinds'], far))
                ctx['i'] += 1
                ctx.update(stage='setup', at=time.monotonic())
            return
    except Exception:
        import traceback
        note('ERROR ' + traceback.format_exc())
        finish()


ctx['handle'] = u.register_slate_post_tick_callback(tick)
note('begin play requested')
ls.editor_request_begin_play()
