"""Round 20: a simulated 1v1v1v1 battle -- all four wizards, every one driven by a simple bot,
last wizard standing -- seen the way a player sees the game: the game's own third-person
camera behind one of them (default: Volta).  Also a statistics mode for tuning the ultimate
charge chance (no pictures).

UnrealEditor <uproject> -RenderOffscreen -UseFixedTimeStep -FPS=30 -DeterministicAudio
  -ini:EditorPerProjectUserSettings:[/Script/UnrealEd.LevelEditorPlaySettings]:bUseNonRealtimeAudioDevice=True
  -ExecCmds="py r20_battle.py"
env R11_VIDEO_DIR=<frames root>  R11_VIDEO_JSON=<log json>  R13_AUDIO=1
    R20_POV=0-3 (whose camera, default 3)  R20_MAP=FrostGarden  R20_TRIAL=1 (20 s, for a look)  R20_SEED=<int>
    R20_STATS=10,5,2.5  R20_ROUNDS=5: matches without pictures, each a chance in percent in turn
        (SuperChanceBase = 10 x the percent on every wizard), the ultimates timed -> the json

The fight happens in the map reference ("explore") world, so the arena, its spawn points and
every rule are the game's own: spells and their cooldowns, the random ultimate charges, guard,
blink, hover, damage, and (round 20) the fall when a wizard is knocked out.  Only the decisions
are scripted here, one small bot per wizard (see act()).  Every knockout is seen up close for
1.5 s (a camera beside the fall, at normal speed), then the picture goes back to the player's
camera -- the wizard who did it, if the one we follow was the one who fell.  At the end a camera circles
the winner.  Every frame: a HighResShot (1280x720) and each wizard's state in the log json --
r20_battle_post.py draws the health bars and the kill feed from it.
"""
import unreal as u
import json
import math
import os
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/round20/battle'
OUT.mkdir(parents=True, exist_ok=True)
FRAMES = Path(os.environ.get('R11_VIDEO_DIR', str(OUT / 'frames')))
RES = Path(os.environ.get('R11_VIDEO_JSON', str(OUT / 'battle.json')))
RES.parent.mkdir(parents=True, exist_ok=True)
POV0 = int(os.environ.get('R20_POV', '3'))
MAP = os.environ.get('R20_MAP', 'FrostGarden')
TRIAL = os.environ.get('R20_TRIAL') == '1'
STATS = [float(x) for x in os.environ.get('R20_STATS', '').split(',') if x]
ROUNDS = int(os.environ.get('R20_ROUNDS', '5'))
SEED = int(os.environ.get('R20_SEED', '19'))
LANG = 0                                  # English (the user: the battle video in English only)
FPS = 30
CLOSE, OVERVIEW, OUTRO = 26, 36, 105     # frames: each wizard at the start, the arena, the winner
KO_SECS = 1.5                             # a knockout seen up close (the fall itself takes ~0.6 s)
INTRO = 4 * CLOSE + OVERVIEW
FIGHT_MAX = (20 if TRIAL else 150) * FPS
ls = u.get_editor_subsystem(u.LevelEditorSubsystem)
sysobj = u.get_default_object(u.SystemLibrary)
gs = u.get_default_object(u.GameplayStatics)
u.get_default_object(u.load_class(None, '/Script/UnrealEd.LevelEditorPlaySettings')).set_editor_property('PlayNumberOfClients', 1)
try:
    u.get_default_object(u.load_class(None, '/Script/UnrealEd.EditorPerformanceSettings')).set_editor_property('bThrottleCPUWhenNotForeground', False)
except Exception:
    pass
AUDIO = os.environ.get('R13_AUDIO') == '1'
ATTS = {}
if AUDIO:
    # as r11_video.py / r18_demo.py (round 13): background audio, no auto-disabled submixes,
    # and for the capture only the attenuation without the left/right pan
    try:
        u.get_default_object(u.load_class(None, '/Script/UnrealEd.LevelEditorMiscSettings')).set_editor_property('bAllowBackgroundAudio', True)
    except Exception:
        pass
    for _cmd in ('au.DisableAppVolume 1', 'au.NeverMuteNonRealtimeAudioDevices 1', 'au.NeverDisableSubmixes 1'):
        u.SystemLibrary.execute_console_command(None, _cmd)
    for _n in ('ATT_Magic', 'ATT_Movement', 'ATT_Ultimate'):
        _a = u.load_asset('/Game/Audio/Wizard/Mix/' + _n)
        _s = _a.get_editor_property('attenuation')
        ATTS[_n] = (_a, bool(_s.get_editor_property('spatialize')))
        _s.set_editor_property('spatialize', False)
        _a.set_editor_property('attenuation', _s)
    try:
        u.get_default_object(u.load_class(None, '/Script/UnrealEd.EditorLoadingSavingSettings')).set_editor_property('bAutoSaveEnable', False)
    except Exception:
        pass

CH = '/Game/ThirdPerson/Blueprints/BP_WizardCharacter'
ORB = '/Game/BluePrint/Magic/Ultimates/BP_UltimateOrb'
CAST = '/Game/BluePrint/Magic/Ultimates/BP_UltimateCast'
TELE = '/Game/BluePrint/Magic/Ultimates/Telegraphs/BP_UltimateTelegraph'
ELS = ['Fire', 'Ice', 'Wind', 'Lightning']
WHO = ['fireboy', 'icegirl', 'windboy', 'lightninggirl']
WHO_ZH = ['布萊茲', '妮芙', '蓋爾', '沃爾妲']
SPELLS = ['/Game/BluePrint/Magic/%sball/BP_%sball' % (e, e) for e in ELS]
SHOT_SPEED = 960.0                        # cm/s: a fireball in flight (round 19 probe)
HEAD = 'head'
ctx = dict(stage='wait', at=time.monotonic(), start=time.monotonic(), log=[], n=0, f=0, frames=[], events=[],
           bots=[], req=0, last_cast={}, pending_stop=[], cover=[], stats=[])
CLASSES = {}


def cls(path):
    if path not in CLASSES:
        CLASSES[path] = u.load_asset(path).generated_class()
    return CLASSES[path]


def note(s):
    ctx['log'].append('%.1f %s' % (time.monotonic() - ctx['start'], s))
    save()


def save():
    RES.write_text(json.dumps({'log': ctx['log'], 'pov0': POV0, 'map': MAP, 'fps': FPS, 'intro': INTRO,
                               'events': ctx['events'], 'frames': ctx['frames'], 'stats': ctx['stats']}, ensure_ascii=False),
                   encoding='utf-8')


def finish():
    note('finish')
    if AUDIO and ctx.get('rec') and ctx.get('world'):
        try:
            u.AudioMixerLibrary.stop_recording_output(ctx['world'], u.AudioRecordingExportType.WAV_FILE, 'game_audio',
                                                      FRAMES.as_posix(), None, None)
            note('game audio written: %d ticks recorded' % ctx['tick'])
        except Exception:
            import traceback
            note('audio stop ERROR ' + traceback.format_exc())
        ctx['rec'] = False
    for _a, _sp in ATTS.values():
        _s = _a.get_editor_property('attenuation')
        _s.set_editor_property('spatialize', _sp)
        _a.set_editor_property('attenuation', _s)
    try:
        u.unregister_slate_post_tick_callback(ctx['handle'])
    except Exception:
        pass
    ls.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def prop(o, n, v, k='Double'):
    sysobj.call_method('Set%sPropertyByName' % k, (o, n, v))


def get(o, n, default=None):
    try:
        return o.get_editor_property(n)
    except Exception:
        return default


def spawn(w, klass, pos, props=None, rot=None):
    tr = u.Transform(location=pos, rotation=rot or u.Rotator(roll=0, pitch=0, yaw=0))
    o = gs.call_method('BeginDeferredActorSpawnFromClass', (w, klass, tr, u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None,
                                                            u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    for n, (v, k) in (props or {}).items():
        prop(o, n, v, k)
    return gs.call_method('FinishSpawningActor', (o, tr, u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))


def all_of(w, path):
    return list(u.GameplayStatics.get_all_actors_of_class(w, cls(path)))


def look_at(a, b):
    return u.MathLibrary.find_look_at_rotation(a, b)


def flat(v):
    return u.Vector(v.x, v.y, 0.0)


def unit(v):
    n = v.length()
    return v * (1.0 / n) if n > 1e-3 else u.Vector(0, 0, 0)


def capture(w, path):
    u.SystemLibrary.execute_console_command(w, 'HighResShot 1280x720 filename=%s' % path.as_posix())
    ctx['req'] += 1


def state(pawn, e):
    v = get(pawn, ELS[e] + 'SpellState', 0)
    return int(v.value) if hasattr(v, 'value') else int(v)


def is_dead(pawn):
    return bool(get(pawn, 'bIsDead', False))


def owner_pawn(actor):
    """The wizard behind a shot or an orb (an orb's owner may be the ultimate's cast actor)."""
    o = actor.get_owner() or actor.get_instigator()
    for _ in range(3):
        if o is None:
            return None
        if o.get_class().get_name().startswith('BP_WizardCharacter'):
            return o
        o = o.get_owner() or o.get_instigator()
    return None


def wizard_meshes(pawn):
    out = [c for c in pawn.get_components_by_class(u.SkeletalMeshComponent)]
    out += [c for c in pawn.get_components_by_class(u.StaticMeshComponent)]
    return out


# ------------------------------------------------------------------ the bots
class Bot:
    def __init__(self, d, pawn, ctrl, rng, sharp):
        self.d, self.pawn, self.ctrl, self.rng = d, pawn, ctrl, rng
        self.sharp = sharp                       # the first-person wizard aims a little better
        self.alive = True
        self.target = None
        self.retarget = 0.0
        self.strafe = rng.choice((-1.0, 1.0))
        self.strafe_until = 0.0
        self.pref = 480.0 + rng.random() * 300.0
        self.next_cast = 1.2 + rng.random() * 1.2
        self.guard_until = None
        self.guard_ready = 0.0
        self.watch = None                        # (cast time, element, press-at-time or None)
        self.next_jump = 3.0 + rng.random() * 5.0
        self.hover_until = None
        self.stuck = 0
        self.last_hp = None
        self.last_hit_by = None                  # (wizard index, fight time)
        self.dead_t = None
        self.aim_pt = None
        self.los = True
        self.los_lost = -9.0

    # where the wizard is
    def loc(self):
        return self.pawn.get_actor_location()

    def hp(self):
        return float(get(self.pawn, 'Health', 0.0))

    def maxhp(self):
        return float(get(self.pawn, 'MaxHealth', 100.0))


def blocked(w, a, b, ignore):
    """Where the straight line from a to b is cut by the arena (the crystals, the walls), or
    None.  (Python returns the hit result, or None when nothing blocks.)"""
    try:
        r = u.SystemLibrary.line_trace_single(w, a, b, u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore,
                                              u.DrawDebugTrace.NONE, True)
    except Exception:
        return None
    if r is None or r is False:
        return None
    hit = r
    if isinstance(r, tuple):
        if len(r) == 2 and isinstance(r[0], bool):
            if not r[0]:
                return None
            hit = r[1]
        else:
            hit = r[0]
    try:
        br = u.GameplayStatics.break_hit_result(hit)
        return br[4] if br[0] else None
    except Exception:
        ctx['trace_odd'] = ctx.get('trace_odd', 0) + 1
        return (a + b) * 0.5


def sees(w, b, o):
    eye = u.Vector(0, 0, 60)
    return blocked(w, b.loc() + eye, o.loc() + eye, [b.pawn, o.pawn]) is None


def enemies(b):
    return [o for o in ctx['bots'] if o is not b and o.alive]


def choose_target(w, b, t):
    foes = enemies(b)
    if not foes:
        b.target = None
        return
    if b.target in foes and t < b.retarget and (b.los or t - b.los_lost < 1.2):
        return
    # the nearest one in sight (crystals hide the others), then the nearest
    foes.sort(key=lambda o: (0 if sees(w, b, o) else 1, (o.loc() - b.loc()).length()))
    # mostly the nearest; sometimes whoever hit me last, sometimes another one (free for all)
    pick = foes[0]
    if b.last_hit_by and t - b.last_hit_by[1] < 2.0:
        hitter = next((o for o in foes if o.d == b.last_hit_by[0]), None)
        if hitter and b.rng.random() < 0.6:
            pick = hitter
    elif len(foes) > 1 and b.rng.random() < 0.3:
        pick = foes[1]
    b.target = pick
    b.retarget = t + 1.5 + b.rng.random() * 1.8


def lead(b, tgt, z=40.0):
    """Where to aim so the shot meets the target (with a bot's error)."""
    p = tgt.loc()
    v = tgt.pawn.get_velocity()
    dist = (p - b.loc()).length()
    tt = dist / SHOT_SPEED
    err = (40.0 if b.sharp else 75.0) * (0.5 + dist / 1200.0)
    return u.Vector(p.x + v.x * tt + b.rng.uniform(-err, err), p.y + v.y * tt + b.rng.uniform(-err, err), p.z + z)


def threats(w, b):
    """Enemy shots and orbs coming at this wizard: (actor, distance, velocity)."""
    me = b.loc()
    out = []
    for path in SPELLS + [ORB]:
        for a in all_of(w, path):
            op = owner_pawn(a)
            if op is None or op == b.pawn:
                continue
            p = a.get_actor_location()
            rel = me - p
            dist = rel.length()
            if dist > 420:
                continue
            v = a.get_velocity()
            sp = v.length()
            if sp < 100:
                continue
            # closing in, and its path passes within ~130 cm
            along = (rel.x * v.x + rel.y * v.y + rel.z * v.z) / sp
            if along <= 0:
                continue
            miss = math.sqrt(max(0.0, dist * dist - along * along))
            if miss < 130:
                out.append((a, dist, v))
    return out


def clear_of_cover(me):
    """Stay 2+ m off the crystals: up against one, a first-person view is only crystal (the
    round 19 trials), and a wizard there just shoots into it."""
    push = u.Vector(0, 0, 0)
    for origin, r in ctx['cover']:
        off = flat(me - origin)
        d = off.length()
        if d < r + 230.0:
            push = push + unit(off) * (1.6 * (r + 230.0 - d) / 230.0)
    return push


def keep_inside(me, center, radius):
    """A push back toward the middle near the arena's edge.  Frost Garden is a diamond with
    its corners on the axes (the spawn points sit in them): |x| + |y| measures it; other maps
    are taken as round."""
    off = flat(me - center)
    if MAP == 'FrostGarden':
        r = abs(off.x) + abs(off.y)
        edge = radius * 0.78
        if r <= edge:
            return u.Vector(0, 0, 0)
        sx = 1.0 if off.x > 0 else -1.0
        sy = 1.0 if off.y > 0 else -1.0
        return unit(u.Vector(-sx, -sy, 0.0)) * (0.6 + 2.5 * (r - edge) / (radius * 0.22))
    r = off.length()
    if r <= radius * 0.82:
        return u.Vector(0, 0, 0)
    return unit(off) * (-0.6 - 2.5 * (r - radius * 0.82) / (radius * 0.18))


def act(w, b, t, center, radius):
    """One bot's decisions for this frame (fight time t, seconds)."""
    pawn = b.pawn
    choose_target(w, b, t)
    me = b.loc()
    if b.target is not None and (ctx['f'] + b.d) % 4 == 0:
        was = b.los
        b.los = sees(w, b, b.target)
        if was and not b.los:
            b.los_lost = t
    cm = pawn.get_editor_property('character_movement')
    # ---- guard / dodge
    if b.guard_until is not None:
        if t >= b.guard_until:
            pawn.call_method('Server_SetBlocking', (False,))
            b.guard_until = None
        else:
            return
    th = threats(w, b)
    if th:
        a, dist, v = min(th, key=lambda x: x[1])
        if b.d == 3 and bool(get(pawn, 'bBlinkReady', False)) and b.rng.random() < 0.5:
            side = unit(u.Vector(-v.y, v.x, 0.0)) * b.rng.choice((-1.0, 1.0))
            pawn.call_method('Server_Blink', (side,))
            ctx['events'].append(dict(t=t, kind='blink', who=b.d))
        elif t >= b.guard_ready and b.rng.random() < (0.85 if b.sharp else 0.6):
            p = a.get_actor_location()
            pawn.set_actor_rotation(u.Rotator(roll=0, pitch=0, yaw=math.degrees(math.atan2(p.y - me.y, p.x - me.x))), True)
            pawn.call_method('Server_SetBlocking', (True,))
            b.guard_until = t + 0.5
            b.guard_ready = t + 0.5 + 3.2
            return
    if b.target is None:
        return
    tp = b.target.loc()
    to = flat(tp - me)
    dist = max(to.length(), 1.0)
    dirv = to * (1.0 / dist)
    # ---- the aim (the head looks there; the first-person camera follows it)
    b.aim_pt = tp + u.Vector(0, 0, 40)
    try:
        b.ctrl.set_control_rotation(look_at(me + u.Vector(0, 0, 60), b.aim_pt))
    except Exception:
        pass
    # ---- move: circle the target at the preferred range, stay on the floor
    if t >= b.strafe_until and b.los:
        b.strafe = -b.strafe if b.rng.random() < 0.6 else b.strafe
        b.strafe_until = t + 0.8 + b.rng.random() * 1.4
    # hurt: keep further away (the fight lasts and moves around more)
    pref = b.pref + (350.0 if b.hp() < 0.35 * b.maxhp() else 0.0)
    radial = 1.0 if dist > pref + 150 else (-0.8 if dist < pref - 150 else 0.0)
    perp = u.Vector(-dirv.y, dirv.x, 0.0) * b.strafe
    if not b.los:
        radial, perp = 0.45, perp * 1.4         # round the crystal to see the target again
    mv = dirv * radial + perp
    mv = mv + keep_inside(me, center, radius) + clear_of_cover(me)
    speed = flat(pawn.get_velocity()).length()
    b.stuck = b.stuck + 1 if speed < 60 and mv.length() > 0.5 else 0
    if b.stuck > 12:
        b.strafe = -b.strafe
        b.strafe_until = t + 1.0
        b.stuck = 0
    if b.hover_until is None or t >= b.hover_until:
        pawn.add_movement_input(unit(mv), 1.0, False)
    # ---- jumps; Neve hovers now and then
    if b.hover_until is not None and t >= b.hover_until:
        pawn.call_method('Server_SetJumpHeld', (False,))
        pawn.stop_jumping()
        b.hover_until = None
    if t >= b.next_jump and not cm.is_falling():
        if b.d == 1 and b.rng.random() < 0.6:
            pawn.call_method('Server_SetJumpHeld', (True,))
            pawn.jump()
            b.hover_until = t + 1.7
        else:
            pawn.jump()
            ctx['pending_stop'].append(pawn)
        b.next_jump = t + 4.0 + b.rng.random() * 6.0
    # ---- second press: when the shot is near an enemy (the wind shot homes: press early)
    if b.watch is not None:
        t0, e, press_at = b.watch
        pr = get(pawn, 'ActiveSecondaryProjectile')
        if pr is None or t - t0 > 1.6:
            b.watch = None
        elif press_at is not None and t >= press_at:
            pawn.call_method('Server_UseSecondary')
            ctx['events'].append(dict(t=t, kind='second', who=b.d, element=e))
            b.watch = None
        elif press_at is None:
            pp = pr.get_actor_location()
            near = min(((o.loc() - pp).length() for o in enemies(b)), default=9e9)
            if near < 230:
                pawn.call_method('Server_UseSecondary')
                ctx['events'].append(dict(t=t, kind='second', who=b.d, element=e))
                b.watch = None
    # ---- cast
    if t < b.next_cast or bool(get(pawn, 'UltimateWindupActive', False)) or bool(get(pawn, 'UltimateDashing', False)):
        return
    charged = [e for e in range(4) if state(pawn, e) == 2]
    ready = [e for e in range(4) if state(pawn, e) == 0]
    ult_ok = {0: dist < 1500 and b.los, 1: dist < 650, 2: 250 < dist < 1300 and b.los, 3: dist < 1900}[b.d]
    if not b.los and not (charged and ult_ok):
        b.next_cast = t + 0.25
        return
    if charged and ult_ok:
        e, ult = charged[0], True
    elif ready:
        e, ult = b.rng.choice(ready), False
    else:
        b.next_cast = t + 0.25
        return
    sysobj.call_method('SetBytePropertyByName', (pawn, 'CurrentSpellType', e))
    aim = lead(b, b.target)
    if ult and b.d == 3:
        aim = u.Vector(aim.x, aim.y, tp.z - 88.0)       # the storm: on the floor at the target
    teles = set(x.get_name() for x in all_of(w, TELE))
    pawn.call_method('Server_Fire', (aim,))
    ctx['last_cast'][b.target.d] = (b.d, t)
    if ult:
        ctx['events'].append(dict(t=t, kind='ult', who=b.d, element=e, target=b.target.d))
        if b.d == 3:
            # the storm lands on the target, not where the view's centre happened to be
            for n_ in ('StormTarget', 'LockedStormTarget'):
                sysobj.call_method('SetVectorPropertyByName', (pawn, n_, aim))
            pawn.set_actor_rotation(u.Rotator(roll=0, pitch=0, yaw=math.degrees(math.atan2(aim.y - me.y, aim.x - me.x))), True)
            for x in all_of(w, TELE):
                if x.get_name() not in teles:
                    x.set_actor_location(aim, False, True)
        b.next_cast = t + 1.6 + b.rng.random() * 0.6
    else:
        press = None
        if b.rng.random() < 0.65:
            press = t + 0.25 if e == 2 else None       # the wind shot turns to the nearest enemy
            b.watch = (t, e, press)
        b.next_cast = t + 1.0 + b.rng.random() * 0.8


# ------------------------------------------------------------------ eliminations
def knock_out(w, b, t):
    b.alive = False
    b.dead_t = t
    pawn = b.pawn
    try:
        pawn.call_method('Server_SetBlocking', (False,))
        pawn.call_method('Server_SetJumpHeld', (False,))
    except Exception:
        pass
    killer = b.last_hit_by[0] if (b.last_hit_by and t - b.last_hit_by[1] < 3.0) else None
    ctx['events'].append(dict(t=t, kind='out', who=b.d, by=killer))
    note('%s knocked out at %.1f s by %s' % (WHO[b.d], t, WHO[killer] if killer is not None else '?'))


def credit_hits(w, t):
    """Who hurt whom: a wizard who lost health this frame is credited to the nearest enemy shot
    or orb (or, failing that, the enemy who cast at them last)."""
    shots = []
    for path in SPELLS + [ORB]:
        for a in all_of(w, path):
            op = owner_pawn(a)
            if op is not None:
                shots.append((a.get_actor_location(), op))
    for b in ctx['bots']:
        if not b.alive:
            continue
        hp = b.hp()
        if b.last_hp is not None and hp < b.last_hp - 0.01:
            me = b.loc()
            best = None
            for p, op in shots + ctx.get('prev_shots', []):
                if op == b.pawn:
                    continue
                dd = (p - me).length()
                if best is None or dd < best[0]:
                    best = (dd, op)
            src = None
            if best and best[0] < 600:
                src = next((o.d for o in ctx['bots'] if o.pawn == best[1]), None)
            if src is None:
                lc = ctx['last_cast'].get(b.d)
                src = lc[0] if lc and t - lc[1] < 2.5 else None
            if src is not None:
                b.last_hit_by = (src, t)
        b.last_hp = hp
    ctx['prev_shots'] = shots


# ------------------------------------------------------------------ cameras
def watch(pc, b, blend):
    """The wizard we watch, through the game's own camera (the pawn's spring arm, which follows
    its controller's rotation): what a player sees."""
    pc.set_view_target_with_blend(b.pawn, blend)
    ctx['aim_rot'] = None


def smooth_aim(b):
    """The watched wizard's aim is the camera: turn it smoothly (a bot would snap)."""
    if b.aim_pt is None:
        return
    want = look_at(b.loc() + u.Vector(0, 0, 60), b.aim_pt)
    cur = ctx.get('aim_rot') or want
    dy = (want.yaw - cur.yaw + 180.0) % 360.0 - 180.0
    dp = want.pitch - cur.pitch
    step = 9.0                                    # at most 270 degrees a second
    dy = max(-step, min(step, dy * 0.3))
    dp = max(-step, min(step, dp * 0.3))
    rot = u.Rotator(roll=0, pitch=max(-30.0, min(15.0, cur.pitch + dp)), yaw=cur.yaw + dy)
    ctx['aim_rot'] = rot
    b.ctrl.set_control_rotation(rot)


def orbit_camera(center, k, n, radius, height, yaw0, sweep):
    a = math.radians(yaw0 + sweep * k / max(1, n - 1))
    loc = center + u.Vector(math.cos(a) * radius, math.sin(a) * radius, height)
    return loc, look_at(loc, center)


# ------------------------------------------------------------------ the frame loop
def record(w, phase, pov):
    ws = []
    for b in ctx['bots']:
        p = b.loc()
        ws.append([1 if b.alive else 0, round(b.hp(), 1), round(b.maxhp(), 1), round(p.x), round(p.y)])
    ctx['frames'].append(dict(p=phase, v=pov, w=ws, tick=ctx.get('tick', 0)))
    if ctx.get('ko'):
        ctx['frames'][-1]['ko'] = ctx['ko']['b'].d


def ko_view(w, pc, b, t):
    """A knockout seen up close: a camera beside the fall (at right angles to it, a little above,
    clear of the crystals), the fall direction being the game's own (DeathFallDir)."""
    body = b.loc()
    fd = get(b.pawn, 'DeathFallDir')
    fdir = unit(flat(fd)) if fd is not None else u.Vector(0, 0, 0)
    if fdir.length() < 0.5:
        killer = next((o for o in ctx['bots'] if b.last_hit_by and o.d == b.last_hit_by[0]), None)
        fdir = unit(flat(body - killer.loc())) if killer else u.Vector(1, 0, 0)
    try:
        half = b.pawn.get_component_by_class(u.CapsuleComponent).get_scaled_capsule_half_height()
    except Exception:
        half = 90.0
    # the middle of the body once it is down; knocked out in the air, it first drops to the floor
    # (DeathDropMax: the game's floor trace at the start of the fall)
    dmax = min(float(get(b.pawn, 'DeathDropMax', 0.0) or 0.0), 1500.0)
    mid = body + fdir * 55.0 + u.Vector(0, 0, 45.0 - half - dmax)
    side = u.Vector(-fdir.y, fdir.x, 0.0)
    ignore = [o.pawn for o in ctx['bots']]
    others = [flat(o.loc()) for o in ctx['bots'] if o.alive and o is not b]
    killer = next((o for o in ctx['bots'] if b.last_hit_by and o.d == b.last_hit_by[0] and o.alive), None)
    ends = [mid + u.Vector(0, 0, 30.0), mid + fdir * 65.0 + u.Vector(0, 0, 15.0), mid - fdir * 65.0 + u.Vector(0, 0, 15.0)]
    picks = [(mid + unit(side * s + fdir * back) * dist + u.Vector(0, 0, h), h)
             for s in (1.0, -1.0) for back in (0.25, -0.25, 0.0, 0.5, -0.5) for dist in (360.0, 300.0, 440.0, 520.0)
             for h in (95.0, 170.0)]

    def score(pick):
        p_, h = pick
        # the whole body in sight (its middle and both ends), no crystal right beside the camera
        # (it would fill half the picture), nobody standing between the camera and the body (they
        # would walk into the picture), the camera on the far side from the one who did it
        if any(blocked(w, e, p_, ignore) is not None for e in ends):
            return -1e9
        a, c = flat(p_), flat(mid)
        for co, rad in ctx.get('cover', []):
            if (flat(co) - a).length() < rad + 130.0:
                return -1e9
        ab = c - a
        room = 400.0
        for q in others:
            k = max(0.0, min(1.0, (q - a).dot(ab) / max(ab.dot(ab), 1.0)))
            room = min(room, (a + ab * k - q).length())
        away = 0.0
        if killer is not None:
            away = 150.0 * max(0.0, unit(a - c).dot(unit(flat(killer.loc()) - c)))
        return room - away - abs((p_ - mid).length() - 375.0) * 0.1 - (40.0 if h > 100.0 else 0.0)

    best = max(picks, key=score)
    if score(best) < -1e8:
        # nothing clear around the body: look down at it from high above one side
        loc = mid + side * 220.0 + u.Vector(0, 0, 380.0)
    else:
        loc = best[0]
    ctx['ko'] = dict(b=b, t=t, loc=loc, mid=mid, dmax=dmax)
    cam = ctx['cam']
    try:
        cam.get_component_by_class(u.CameraComponent).set_field_of_view(70.0)
    except Exception:
        pass
    cam.set_actor_location_and_rotation(loc, look_at(loc, mid + u.Vector(0, 0, 20.0 + dmax)), False, True)
    pc.set_view_target_with_blend(cam, 0.0)
    prop(pc, 'bShowMouseCursor', True, 'Bool')                        # no crosshair on this camera
    ctx['events'].append(dict(t=t, kind='kocam', who=b.d))
    note('close-up of %s falling (direction %.2f %.2f, drop %.0f cm)' % (WHO[b.d], fdir.x, fdir.y, dmax))


def ko_follow(ko, t):
    """The close-up drifts in a little while the body falls."""
    j = min(1.0, (t - ko['t']) / KO_SECS)
    loc = ko['loc'] + (ko['mid'] - ko['loc']) * (0.12 * j * (2.0 - j))
    up = ko['dmax'] - float(get(ko['b'].pawn, 'DeathDrop', ko['dmax']) or 0.0)      # follows a body dropping from the air
    ctx['cam'].set_actor_location_and_rotation(loc, look_at(loc, ko['mid'] + u.Vector(0, 0, 20.0 + max(0.0, up))), False, True)


def tick(dt):
    try:
        if time.monotonic() - ctx['start'] > 3300:
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
        if ctx.get('rec'):
            ctx['tick'] += 1
        for p_ in ctx.get('pending_stop', []):
            try:
                p_.stop_jumping()
            except Exception:
                pass
        ctx['pending_stop'] = []
        if st == 'wait':
            if el > 4:
                sysobj.call_method('K2_SetTimer', (pc, 'Explore' + MAP, .1, False, 0, 0))
                ctx.update(stage='enter', at=time.monotonic())
            return
        if st == 'enter':
            if el > 8:
                setup(w, pc, pawn)
            return
        if st == 'settle':
            ctx['f'] += 1
            for b in ctx['bots']:
                b.pawn.set_actor_rotation(u.Rotator(roll=0, pitch=0, yaw=math.degrees(math.atan2(
                    ctx['center'].y - b.loc().y, ctx['center'].x - b.loc().x))), True)
            if ctx['f'] >= 30:
                ctx.update(stage='intro', f=0)
                if AUDIO:
                    u.AudioMixerLibrary.start_recording_output(w, 1200.0, None)
                    ctx.update(rec=True, tick=0, world=w)
                note('recording (audio %s)' % AUDIO)
            return
        cam = ctx.get('cam')
        if st == 'intro':
            k = ctx['f']
            if k < 4 * CLOSE:
                # each wizard at the start, face on (they face the middle), the camera easing in
                b = ctx['bots'][k // CLOSE]
                j = (k % CLOSE) / float(CLOSE - 1)
                yaw = b.pawn.get_actor_rotation().yaw
                a = math.radians(yaw + 18.0 - 10.0 * j)
                dist = 300.0 - 50.0 * j
                head = b.loc() + u.Vector(0, 0, 45)
                loc = head + u.Vector(math.cos(a) * dist, math.sin(a) * dist, 15.0)
                rot = look_at(loc, head)
                b.ctrl.set_control_rotation(look_at(head, loc))
            else:
                j = (k - 4 * CLOSE) / float(OVERVIEW - 1)
                loc, rot = orbit_camera(ctx['center'] + u.Vector(0, 0, 60), int(j * 99), 100, ctx['radius'] * 0.95,
                                        ctx['radius'] * 0.42, ctx['yaw0'], 25.0)
            cam.set_actor_location_and_rotation(loc, rot, False, True)
            record(w, 'intro', -1)
            capture(w, FRAMES / 'battle' / ('f_%05d.png' % ctx['n']))
            ctx['n'] += 1
            ctx['f'] += 1
            if ctx['f'] >= INTRO:
                ctx.update(stage='fight', f=0, pov=POV0)
                ctx['events'].append(dict(t=0.0, kind='pov', who=POV0))
                watch(pc, ctx['bots'][POV0], 0.0)
                prop(pc, 'bShowMouseCursor', False, 'Bool')          # the game's crosshair
                note('fight starts, the camera behind %s' % WHO[POV0])
            return
        if st == 'fight':
            k = ctx['f']
            t = k / float(FPS)
            for b in ctx['bots']:
                if b.alive:
                    act(w, b, t, ctx['center'], ctx['radius'])
            credit_hits(w, t)
            for b in ctx['bots']:
                if b.alive and (is_dead(b.pawn) or b.hp() <= 0.0):
                    knock_out(w, b, t)
                    if not STATS:
                        ko_view(w, pc, b, t)
            alive = [b for b in ctx['bots'] if b.alive]
            pov = ctx['bots'][ctx['pov']]
            ko = ctx.get('ko')
            if ko and len(alive) > 1 and t - ko['t'] >= KO_SECS:
                # back to the player's camera -- if the wizard we follow is the one who fell, the
                # camera moves to the wizard who knocked them out (a cut: no flying through crystals)
                ctx['ko'] = ko = None
                if not pov.alive:
                    nxt = next((b for b in alive if pov.last_hit_by and b.d == pov.last_hit_by[0]), alive[0])
                    ctx['pov'] = nxt.d
                    ctx['events'].append(dict(t=t, kind='pov', who=nxt.d))
                    note('the camera moves to %s' % WHO[nxt.d])
                    pov = nxt
                watch(pc, pov, 0.0)
                prop(pc, 'bShowMouseCursor', False, 'Bool')
            if ko and not STATS:
                ko_follow(ko, t)
            if pov.alive and not STATS:
                smooth_aim(pov)
            if not STATS:
                record(w, 'fight', ctx['pov'])
                capture(w, FRAMES / 'battle' / ('f_%05d.png' % ctx['n']))
                ctx['n'] += 1
            ctx['f'] += 1
            done = len(alive) <= 1 and all(b.alive or t - b.dead_t > 1.9 for b in ctx['bots'])
            if done or k + 1 >= FIGHT_MAX:
                win = alive[0] if len(alive) == 1 else max(alive, key=lambda b: b.hp()) if alive else ctx['bots'][ctx['pov']]
                ctx['events'].append(dict(t=t, kind='win', who=win.d))
                note('winner %s at %.1f s (%d alive)' % (WHO[win.d], t, len(alive)))
                if STATS:
                    next_match(w, pc, pawn, t, win)
                    return
                prop(pc, 'bShowMouseCursor', True, 'Bool')
                try:
                    cam.get_component_by_class(u.CameraComponent).set_field_of_view(100.0)
                except Exception:
                    pass
                pc.set_view_target_with_blend(cam, 0.0)
                ctx.update(stage='outro', f=0, winner=win, ko=None)
            for b in ctx['bots']:
                if b.alive and not b.los:
                    ctx['no_los'] = ctx.get('no_los', 0) + 1
            if k % 150 == 0 and not STATS:
                note('t %.0f s: %s | frames out of sight %d' % (
                    t, ', '.join('%s %.0f' % (WHO[b.d], b.hp()) for b in ctx['bots'] if b.alive), ctx.get('no_los', 0)))
            return
        if st == 'outro':
            k = ctx['f']
            win = ctx['winner']
            if k == 0:
                win.pawn.call_method('Server_SetBlocking', (False,))
                ctx['win_yaw'] = win.pawn.get_actor_rotation().yaw
            # the winner turns to the camera, which circles in front of her / him
            yaw = ctx['win_yaw']
            loc, rot = orbit_camera(win.loc() + u.Vector(0, 0, 40), k, OUTRO, 330.0, 40.0, yaw - 35.0, 70.0)
            win.pawn.set_actor_rotation(u.Rotator(roll=0, pitch=0, yaw=math.degrees(math.atan2(loc.y - win.loc().y,
                                                                                                loc.x - win.loc().x))), True)
            win.ctrl.set_control_rotation(look_at(win.loc() + u.Vector(0, 0, 60), loc))
            cam.set_actor_location_and_rotation(loc, rot, False, True)
            record(w, 'outro', win.d)
            capture(w, FRAMES / 'battle' / ('f_%05d.png' % ctx['n']))
            ctx['n'] += 1
            ctx['f'] += 1
            if ctx['f'] >= OUTRO:
                note('done: %d frames, %d shot requests' % (ctx['n'], ctx['req']))
                finish()
            return
    except Exception:
        import traceback
        note('ERROR ' + traceback.format_exc())
        finish()


def clear_field(w):
    for path in [ORB, CAST, TELE] + SPELLS:
        for a in all_of(w, path):
            a.destroy_actor()


def next_match(w, pc, pawn, t, win):
    """Statistics: keep this match's numbers, clear the arena, start the next one."""
    ults = [e for e in ctx['events'] if e['kind'] == 'ult']
    ctx['stats'].append(dict(rate=ctx['rate'], secs=round(t, 1), winner=win.d, ults=[[round(e['t'], 1), e['who']] for e in ults],
                             outs=[[round(e['t'], 1), e['who'], e.get('by')] for e in ctx['events'] if e['kind'] == 'out']))
    note('match %d at %g%%: %.0f s, %d ultimates' % (len(ctx['stats']), ctx['rate'], t, len(ults)))
    for b in ctx['bots']:
        for a in (b.pawn, b.ctrl):
            try:
                a.destroy_actor()
            except Exception:
                pass
    clear_field(w)
    ctx['events'] = []
    ctx['last_cast'] = {}
    if len(ctx['stats']) >= ROUNDS * len(STATS):
        save()
        finish()
        return
    setup(w, pc, pawn)


def setup(w, pc, pawn):
    rng = random.Random(SEED + 101 * len(ctx['stats']))
    starts = list(u.GameplayStatics.get_all_actors_of_class(w, u.PlayerStart.static_class()))
    pts = [s.get_actor_location() for s in starts]
    if len(pts) < 4:
        note('only %d player starts -- using a square around the player' % len(pts))
        c = pawn.get_actor_location()
        pts = [c + u.Vector(math.cos(a) * 900, math.sin(a) * 900, 0) for a in (0.5, 2.07, 3.64, 5.21)]
    center = u.Vector(sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts), sum(p.z for p in pts) / len(pts))
    pts.sort(key=lambda p: math.atan2(p.y - center.y, p.x - center.x))
    radius = sum(flat(p - center).length() for p in pts) / len(pts)
    ctx.update(center=center, radius=radius, yaw0=math.degrees(math.atan2(pts[0].y - center.y, pts[0].x - center.x)) + 20.0)
    note('arena centre %s, spawn radius %.0f, %d starts' % ([round(center.x), round(center.y), round(center.z)], radius, len(starts)))
    sysobj.call_method('SetIntPropertyByName', (pc, 'Language', LANG))
    prop(pc, 'bShowMouseCursor', True, 'Bool')
    chc = cls(CH)
    order = list(range(4))
    rng.shuffle(order)                         # who starts where
    bots = [None] * 4
    if STATS:
        ctx['rate'] = STATS[len(ctx['stats']) % len(STATS)]
        if not ctx.get('parked'):
            # the player's own wizard sits the matches out: up in the air, still, untouchable
            pawn.get_editor_property('character_movement').disable_movement()
            pawn.set_actor_location(center + u.Vector(0, 0, 3000), False, True)
            pawn.set_actor_hidden_in_game(True)
            pawn.set_actor_enable_collision(False)
            ctx['parked'] = True
    for d in range(4):
        spot = pts[order[d]] + u.Vector(0, 0, 40)
        if d == POV0 and not STATS:
            p, ctrl = pawn, pc
            ps = pawn.get_editor_property('player_state')
            p.set_actor_location(spot, False, True)
        else:
            p = spawn(w, chc, spot)
            ctrl = spawn(w, u.AIController.static_class(), spot, {'bWantsPlayerState': (True, 'Bool')})
            ctrl.possess(p)
            ps = p.get_editor_property('player_state')
        if ps:
            sysobj.call_method('SetBytePropertyByName', (ps, 'SelectedWizardType', d))
        prop(p, 'PracticePawn', False, 'Bool')
        sysobj.call_method('SetBytePropertyByName', (p, 'WizardType', d))
        p.call_method('InitializeWizardTraits')
        cm = p.get_editor_property('character_movement')
        prop(p, 'bUseControllerRotationYaw', False, 'Bool')
        prop(cm, 'bUseControllerDesiredRotation', False, 'Bool')
        prop(cm, 'bOrientRotationToMovement', True, 'Bool')
        # a trial: low health, so knock-outs come within its 20 s
        prop(p, 'Health', 22.0 if TRIAL else float(get(p, 'MaxHealth', 100.0)))
        prop(p, 'bBlinkReady', True, 'Bool')
        for k, name in enumerate(ELS):
            sysobj.call_method('K2_ClearTimer', (p, 'Refresh%sSpell' % name))
            prop(p, name + 'SpellState', 0, 'Int')
        if STATS:
            prop(p, 'SuperChanceBase', ctx['rate'] * 10.0)      # 100 / (supers + 10) % at 10 %
        bots[d] = Bot(d, p, ctrl, random.Random(SEED * 7 + d + 101 * len(ctx['stats'])), sharp=(d == POV0 and not STATS))
    ctx['bots'] = bots
    cover = []
    for a in u.GameplayStatics.get_all_actors_of_class(w, cls('/Game/Maps/WizardWorlds/BP_ArenaProp')):
        o, e = a.get_actor_bounds(False)
        if e.z > 60:                               # the crystals (not floor marks)
            cover.append((o, max(e.x, e.y)))
    ctx['cover'] = cover
    note('%d crystals to keep clear of' % len(cover))
    if STATS:
        ctx.update(stage='fight', f=0, pov=POV0)
        return
    (FRAMES / 'battle').mkdir(parents=True, exist_ok=True)
    cam = spawn(w, u.CameraActor.static_class(), center + u.Vector(0, 0, 800))
    try:
        cam.get_component_by_class(u.CameraComponent).set_field_of_view(100.0)
    except Exception:
        pass
    pc.set_view_target_with_blend(cam, 0.0)
    ctx.update(cam=cam, stage='settle', f=0)
    for b in bots:
        note('%s at %s, health %.0f / %.0f' % (WHO[b.d], [round(b.loc().x), round(b.loc().y)], b.hp(), b.maxhp()))


if __name__ == '__main__':
    ctx['handle'] = u.register_slate_post_tick_callback(tick)
    note('begin play requested (pov %s, map %s, trial %s, seed %d, stats %s x %d)' % (WHO[POV0], MAP, TRIAL, SEED, STATS, ROUNDS))
    ls.editor_request_begin_play()
