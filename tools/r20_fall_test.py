"""Round 20 test: does a wizard knocked out fall the way the blow pushed them?

PIE (full editor, -UseFixedTimeStep -FPS=30), Frost Garden.  Three cases, one after another:
a target wizard at the arena middle facing +X with 5 health, and a shooter 7 m away --
  'back'   shooter at -X: the fireball hits her back, travelling +X -> she falls forward (+X)
  'side'   shooter at -Y: travelling +Y -> she falls to her right (+Y)
  'front'  shooter at +X: travelling -X -> she falls backwards (-X)
  'air'    (round 20, second pass) she floats 1.6 m up (flying, as in a jump or a hover), the
           shot from -X: she falls forward AND drops to the floor (the game's DisableMovement
           on death used to leave a body knocked out in the air hanging there)
A camera at right angles to the fall shoots 54 frames from the cast; the log has the angle
(DeathFallAngle) and the mesh's world tilt every frame.  -> output/round20/fall_test/
"""
import json
import math
import time
from pathlib import Path
import unreal as u

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'round20' / 'fall_test'
OUT.mkdir(parents=True, exist_ok=True)
RES = OUT / 'fall_test.json'
ls = u.get_editor_subsystem(u.LevelEditorSubsystem)
sysobj = u.get_default_object(u.SystemLibrary)
gs = u.get_default_object(u.GameplayStatics)
u.get_default_object(u.load_class(None, '/Script/UnrealEd.LevelEditorPlaySettings')).set_editor_property('PlayNumberOfClients', 1)
CH = '/Game/ThirdPerson/Blueprints/BP_WizardCharacter'
CASES = [('back', (-700, 0), (1, 0)), ('side', (0, -700), (0, 1)), ('front', (700, 0), (-1, 0)), ('air', (-700, 0), (1, 0))]
ONLY = [x for x in __import__('os').environ.get('R20_CASES', '').split(',') if x]
if ONLY:
    CASES = [c for c in CASES if c[0] in ONLY]
FRAMES = 54
ctx = dict(stage='wait', at=time.monotonic(), start=time.monotonic(), log=[], cases={}, ci=0, f=0)


def note(s):
    ctx['log'].append('%.1f %s' % (time.monotonic() - ctx['start'], s))
    RES.write_text(json.dumps({'log': ctx['log'], 'cases': ctx['cases']}, indent=1), encoding='utf-8')


def finish():
    note('finish')
    try:
        u.unregister_slate_post_tick_callback(ctx['h'])
    except Exception:
        pass
    ls.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def prop(o, n, v, k='Double'):
    sysobj.call_method('Set%sPropertyByName' % k, (o, n, v))


def spawn(w, klass, pos, props=None, rot=None):
    tr = u.Transform(location=pos, rotation=rot or u.Rotator(roll=0, pitch=0, yaw=0))
    o = gs.call_method('BeginDeferredActorSpawnFromClass', (w, klass, tr, u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None,
                                                            u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    for n, (v, k) in (props or {}).items():
        prop(o, n, v, k)
    return gs.call_method('FinishSpawningActor', (o, tr, u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))


def wizard(w, d, pos, yaw):
    chc = u.load_asset(CH).generated_class()
    p = spawn(w, chc, pos, rot=u.Rotator(roll=0, pitch=0, yaw=yaw))
    ai = spawn(w, u.AIController.static_class(), pos, {'bWantsPlayerState': (True, 'Bool')})
    ai.possess(p)
    ps = p.get_editor_property('player_state')
    if ps:
        sysobj.call_method('SetBytePropertyByName', (ps, 'SelectedWizardType', d))
    prop(p, 'PracticePawn', False, 'Bool')
    sysobj.call_method('SetBytePropertyByName', (p, 'WizardType', d))
    p.call_method('InitializeWizardTraits')
    return p


def tick(dt):
    try:
        if time.monotonic() - ctx['start'] > 400:
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
        if st == 'wait' and el > 4:
            sysobj.call_method('K2_SetTimer', (pc, 'ExploreFrostGarden', .1, False, 0, 0))
            ctx.update(stage='enter', at=time.monotonic())
            return
        if st == 'enter' and el > 8:
            pawn.set_actor_location(u.Vector(0, -1800, 200), False, True)          # out of the way
            prop(pc, 'bShowMouseCursor', True, 'Bool')
            ctx['cam'] = spawn(w, u.CameraActor.static_class(), u.Vector(0, 0, 400))
            pc.set_view_target_with_blend(ctx['cam'], 0.0)
            ctx.update(stage='case', f=0)
            return
        if st == 'case':
            name, shooter_at, fall = CASES[ctx['ci']]
            f = ctx['f']
            base = u.Vector(0, 0, 120) + u.Vector(ctx['ci'] * 0.0, 0, 0)
            if f == 0:
                # a fresh target each case (Neve: the hat shows the tilt well), and a shooter
                for k in ('target', 'shooter'):
                    if ctx.get(k):
                        ctx[k].destroy_actor()
                ctx['target'] = wizard(w, 1, base + u.Vector(0, 0, 160 if name == 'air' else 0), 0.0)
                if name == 'air':
                    ctx['target'].get_editor_property('character_movement').set_movement_mode(u.MovementMode.MOVE_FLYING)
                sx, sy = shooter_at
                yaw = math.degrees(math.atan2(-sy, -sx))
                ctx['shooter'] = wizard(w, 0, base + u.Vector(sx, sy, 0), yaw)
                # the camera at right angles to the fall, 6 m away, chest high
                fx, fy = fall
                side = u.Vector(-fy, fx, 0) * 600.0
                up = 70.0 if name == 'air' else 0.0          # the air case: frame the drop too
                side = side * (1.25 if name == 'air' else 1.0)
                loc = base + side + u.Vector(fall[0] * 80, fall[1] * 80, 10 + up)
                ctx['cam'].set_actor_location_and_rotation(loc, u.MathLibrary.find_look_at_rotation(loc, base + u.Vector(fall[0] * 80, fall[1] * 80, -20 + up)), False, True)
                ctx['cases'][name] = []
            if f == 12:
                t = ctx['target']
                prop(t, 'Health', 5.0)
                s = ctx['shooter']
                for e in ('Fire', 'Ice', 'Wind', 'Lightning'):
                    sysobj.call_method('K2_ClearTimer', (s, 'Refresh%sSpell' % e))
                    prop(s, e + 'SpellState', 0, 'Int')
                sysobj.call_method('SetBytePropertyByName', (s, 'CurrentSpellType', 0))
                s.call_method('Server_Fire', (t.get_actor_location() + u.Vector(0, 0, 20),))
            if f >= 12:
                t = ctx['target']
                mesh = t.get_editor_property('mesh')
                r = mesh.get_world_rotation() if hasattr(mesh, 'get_world_rotation') else mesh.k2_get_component_rotation()
                up = r.get_up_vector() if hasattr(r, 'get_up_vector') else None
                feet = mesh.get_world_location() if hasattr(mesh, 'get_world_location') else mesh.k2_get_component_location()
                ctx['cases'][name].append(dict(f=f - 12, dead=bool(t.get_editor_property('bIsDead')), feet=round(feet.z, 1),
                                               drop=round(float(t.get_editor_property('DeathDrop')), 1),
                                               angle=round(float(t.get_editor_property('DeathFallAngle')), 3),
                                               up=[round(up.x, 2), round(up.y, 2), round(up.z, 2)] if up else None,
                                               dir=str(t.get_editor_property('DeathFallDir'))[:60] if f == 12 + FRAMES - 1 else None))
                u.SystemLibrary.execute_console_command(w, 'HighResShot 960x540 filename=%s' % (OUT / ('%s_%02d.png' % (name, f - 12))).as_posix())
            ctx['f'] += 1
            if ctx['f'] >= 12 + FRAMES:
                last = ctx['cases'][name][-1]
                note('%s: dead %s, angle %.2f, up %s, dir %s' % (name, last['dead'], last['angle'], last['up'], last['dir']))
                ctx['ci'] += 1
                ctx['f'] = 0
                if ctx['ci'] >= len(CASES):
                    finish()
            return
    except Exception:
        import traceback
        note('ERROR ' + traceback.format_exc())
        finish()


ctx['h'] = u.register_slate_post_tick_callback(tick)
ls.editor_request_begin_play()
