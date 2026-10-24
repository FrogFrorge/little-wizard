"""Round 20: the footage for the character introduction videos -- each wizard in their own
arena, every action once at normal speed, with the other three wizards as opponents.

Built on r18_demo.py (round 18: the actions, the cameras, the face-on special and ultimates,
the FreeCam trick, the storm target), with what makes it an introduction instead of a test:
- the wizard's own arena (the map reference worlds -- Blaise Ember Ruins, Neve Frost Garden,
  Gale Sky Grove, Volta Neon Foundry) instead of the grey test site.  Each visit makes a fresh
  layout; the arena props within 13 m of the middle are taken away so nothing stands between
  the camera and the action, the ones further out stay as the backdrop
- the other three wizards are the opponents (no training dummies).  Neve's slowing aura
  (5 m) is kept off the shots' path: when she is an opponent she stands furthest away
- an opening reveal (the camera sweeps in to the wizard's face) and a closing pose
- the HUD is hidden and its ultimate timing (CutInStart, the game time the card starts) is
  logged for every frame: r20_intro_post.py draws the cut-in card itself, in each video's
  language -- one capture serves all four languages

PIE with a fixed time step (every frame is 1/30 s of game time), a HighResShot per frame,
the game's own sound recorded in step (round 13), one recording per wizard (each arena is a
new world): <frames>/<who>/game_audio.wav.

UnrealEditor <uproject> -RenderOffscreen -UseFixedTimeStep -FPS=30 -DeterministicAudio
  -ini:EditorPerProjectUserSettings:[/Script/UnrealEd.LevelEditorPlaySettings]:bUseNonRealtimeAudioDevice=True
  -ExecCmds="py r20_intro.py"
env R11_VIDEO_DIR=<frames root>  R11_VIDEO_WHO=0,1,2,3  R11_VIDEO_JSON=<timeline json>  R13_AUDIO=1
    R20_ONLY=<segment ids> for a short trial (intro run jump spell0-3 second0-3 block special ult0-3 pose)
    R20_HUD=1 keeps the HUD (the game's own English card in the frames: checks the post's timing)
"""
import unreal as u
import json
import math
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/round20/intro'
OUT.mkdir(parents=True, exist_ok=True)
FRAMES = Path(os.environ.get('R11_VIDEO_DIR', str(OUT / 'frames')))
WHOLIST = [int(x) for x in os.environ.get('R11_VIDEO_WHO', '0,1,2,3').split(',')]
ONLY = [x for x in os.environ.get('R20_ONLY', '').split(',') if x]
HUD_ON = os.environ.get('R20_HUD') == '1'
FPS = 30
PRE = 20               # unrecorded frames before each segment
TAIL = 15              # frames kept after the last shot / orb is gone (its pop fades)
RES = Path(os.environ.get('R11_VIDEO_JSON', str(OUT / ('intro-trial.json' if ONLY else 'intro.json'))))
RES.parent.mkdir(parents=True, exist_ok=True)
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
    # see r11_video.py (round 13): background audio, never-disabled submixes, and for the
    # capture only (in memory, put back at the end) attenuation without the left/right pan
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
FX = '/Game/VFX/WizardMagic/Cute/BP_CuteFX'
TELE = '/Game/BluePrint/Magic/Ultimates/Telegraphs/BP_UltimateTelegraph'
FIELD = '/Game/BluePrint/Magic/Lightningball/BP_LightiningField'
PROP = '/Game/Maps/WizardWorlds/BP_ArenaProp'
ELS = ['Fire', 'Ice', 'Wind', 'Lightning']
WHO = ['fireboy', 'icegirl', 'windboy', 'lightninggirl']
ARENA = ['EmberRuins', 'FrostGarden', 'SkyGrove', 'NeonFoundry']
SPELLS = ['/Game/BluePrint/Magic/%sball/BP_%sball' % (e, e) for e in ELS]
O = u.Vector(0.0, 0.0, 130.0)        # the arena's middle, 130 cm above its floor (set on arrival)
FLOOR = -122.0                       # the floor (+8 cm) relative to O
CLEAR = 1300.0                       # props closer than this to the middle are taken away
# the opponents, in the order of their spots: the first is the main target (and the one who
# shoots at the guard); Neve, when she is one, stands furthest from the shots' path
OPPS = {0: [2, 3, 1], 1: [0, 3, 2], 2: [3, 0, 1], 3: [0, 2, 1]}
SPOTS = [(560, 0), (660, -280), (-220, -560)]
LANE = (-420, 300)
AIM = (560, 0)
# round 14: how far the shot flies before the second press (cm), and where it is aimed (the
# wind shot goes off to the side on purpose, so its turn toward the nearest opponent shows)
SECOND_AT = [330.0, 260.0, 240.0, 300.0]
SECOND_AIM = [AIM, AIM, (520, 420), AIM]


def cam(yaw, pitch, dist, off=(0, 0, 0), **kw):
    """A camera placed like a spring arm: rotation (yaw, pitch), `dist` back from a pivot =
    the wizard + off (+60 cm, the chest).  z: a fixed pivot height above the wizard's start;
    at: a fixed world pivot (offset from O)."""
    d = dict(yaw=yaw, pitch=pitch, dist=dist, off=off)
    d.update(kw)
    return d


def orbit(rel, dist, h=10.0, pan=0.0, z=None, off=(0, 0, 0)):
    """A camera `dist` cm from the wizard's chest (+off), at `rel` degrees from where the
    wizard faces (0 = straight in front of the face), `h` cm higher, looking at the chest;
    `pan` then turns it sideways (negative: the wizard sits right of centre -- the cut-in card
    covers the left half).  z: a fixed pivot height above the wizard's start."""
    return dict(orbit=rel, dist=dist, h=h, pan=pan, z=z, off=off)


def shot(spec, start=0, blend=0, face=False):
    """One camera set-up of a segment from frame `start`; `blend` frames of smooth move from
    the previous one (0 = a cut); face: the wizard looks into the camera."""
    return dict(spec=spec, start=start, blend=blend, face=face)


def ring(a, r=450.0):
    return (round(r * math.cos(math.radians(a))), round(r * math.sin(math.radians(a))))


# Every ultimate winds up for 0.8 s: cast at frame 3, the launch shows from frame 26 (round 18).
CUT = 26
STORM_V = (600, 160)                  # Volta's drop point: ahead, a little to her right
ULT = {
    0: dict(face=0, aim=AIM, dummies=SPOTS, a=orbit(15, 400, pan=-24),
            c=[cam(281, -14, 760, (280, 0, 0)), cam(281, -14, 760, (300, 0, 0)),
               cam(286, -30, 1150, (380, -120, 0)), cam(281, -12, 820, (320, 0, 0))],
            secs=[(2.4, 4.0), (2.6, 4.6), (3.0, 5.6), (5.4, 6.4)]),
    1: dict(face=0, aim=AIM, dummies=[ring(a) for a in (105, 180, 255)],
            a=orbit(0, 480, h=20, pan=-24), c=[orbit(0, 900, h=560)] * 4, blend=(12, 18),
            secs=[(2.6, 4.4), (2.6, 4.6), (2.6, 5.0), (2.6, 4.4)]),
    2: dict(face=0, aim=AIM, dummies=[(560, 0), (900, 180), (480, -560)], a=orbit(15, 380, pan=-24),
            c=[cam(283, -12, 720, (220, 0, 0))] * 4, secs=[(2.6, 5.0)] * 4),
    3: dict(face=math.degrees(math.atan2(STORM_V[1], STORM_V[0])), aim=STORM_V,
            dummies=[(660, 210), (540, 40), (1250, 340)], a=orbit(10, 400, pan=-24),
            c=[cam(278, -22, 820, at=(400, 110, 20))] * 4, secs=[(2.6, 5.4)] * 4),
}


def segments(d):
    """dicts: id, kind, secs (min, max: the segment ends when the magic is gone), e (element),
    at (start), face (yaw), dummies (the opponents' spots, in OPPS order; the rest sit out),
    target (aim point, offset from O), shots"""
    side = cam(281, -12, 700, (250, 0, 0))          # the basic shots and second presses
    s = [dict(id='intro', kind='intro', secs=(3.0, 3.0), e=0, at=(0, 0), face=-20, dummies=[], target=None,
              shots=[shot(orbit(38, 860, h=230), face=True), shot(orbit(0, 300, h=0), start=1, blend=70, face=True)]),
         dict(id='run', kind='run', secs=(2.2, 2.2), e=0, at=LANE, face=0, dummies=[], target=None,
              shots=[shot(cam(285, -8, 470))]),
         dict(id='jump', kind='jump', secs=(1.6, 1.6), e=0, at=(0, 0), face=-30, dummies=[], target=None,
              shots=[shot(orbit(0, 380, h=0, z=70), face=True)])]
    for e in range(4):
        s.append(dict(id='spell%d' % e, kind='spell', secs=(1.2, 2.0), e=e, at=(0, 0), face=0,
                      dummies=SPOTS, target=AIM, shots=[shot(side)]))
        s.append(dict(id='second%d' % e, kind='second', secs=(1.5, 3.0), e=e, at=(0, 0), face=0,
                      dummies=SPOTS, target=SECOND_AIM[e], shots=[shot(side)]))
    s.append(dict(id='block', kind='block', secs=(1.4, 2.4), e=0, at=(0, 0), face=0,
                  dummies=SPOTS, target=AIM, shots=[shot(cam(262, -8, 540, (210, 0, 0)))]))
    if d == 1:
        s.append(dict(id='special', kind='hover', secs=(2.8, 2.8), e=0, at=(0, 0), face=20,
                      dummies=[], target=None, shots=[shot(orbit(0, 440, h=0, z=100), face=True)]))
    if d == 3:
        s.append(dict(id='special', kind='blink', secs=(1.7, 1.7), e=0, at=(0, -175), face=0,
                      dummies=[], target=None, shots=[shot(cam(180, -4, 430, at=(0, 0, 70)), face=True)]))
    st = ULT[d]
    for e in range(4):
        b0, bl = st.get('blend', (CUT, 0))
        s.append(dict(id='ult%d' % e, kind='ult', secs=st['secs'][e], e=e, at=(0, 0), face=st['face'],
                      dummies=st['dummies'], target=st['aim'],
                      shots=[shot(st['a'], face=True), shot(st['c'][e], start=b0, blend=bl)]))
    s.append(dict(id='pose', kind='pose', secs=(2.0, 2.0), e=0, at=(0, 0), face=-15, dummies=[], target=None,
                  shots=[shot(orbit(0, 290, h=0), face=True), shot(orbit(-26, 520, h=50), start=1, blend=58, face=True)]))
    if ONLY:
        s = [x for x in s if x['id'] in ONLY]
    return s


ctx = dict(stage='wait', at=time.monotonic(), start=time.monotonic(), log=[], opps=[], ci=0, si=0, f=0, n=0,
           timeline={}, req=0, cam=None)


def note(s):
    ctx['log'].append('%.1f %s' % (time.monotonic() - ctx['start'], s))
    RES.write_text(json.dumps({'log': ctx['log'], 'timeline': ctx['timeline'], 'hud_on': HUD_ON}, indent=1,
                              ensure_ascii=False), encoding='utf-8')


def stop_audio(w, d):
    if AUDIO and ctx.get('rec'):
        try:
            u.AudioMixerLibrary.stop_recording_output(w, u.AudioRecordingExportType.WAV_FILE, 'game_audio',
                                                      (FRAMES / WHO[d]).as_posix(), None, None)
            note('%s: game audio written, %d ticks recorded' % (WHO[d], ctx['tick']))
        except Exception:
            import traceback
            note('audio stop ERROR ' + traceback.format_exc())
        ctx['rec'] = False


def finish():
    note('finish')
    if ctx.get('rec') and ctx.get('world'):
        stop_audio(ctx['world'], ctx.get('d', 0))
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


def quiet_music(pc):
    """The music is added afterwards as one continuous track: stop the arena's here."""
    try:
        m = pc.get_editor_property('AudioMusicRef')
        if m and m.is_playing():
            m.stop()
    except Exception:
        pass


# NOTE: never set_editor_property() on the pawn or its components during PIE -- the editor
# change notification re-initialises the Blueprint actor.  Set properties by name instead.
def prop(o, n, v, k='Double'):
    sysobj.call_method('Set%sPropertyByName' % k, (o, n, v))


def get(o, n, default=None):
    try:
        return o.get_editor_property(n)
    except Exception:
        return default


def V(xy, z=0.0):
    """A floor-plan point (offset from O) as a world vector."""
    return O + u.Vector(float(xy[0]), float(xy[1]), float(z))


def spawn(w, klass, pos, props=None, rot=None):
    tr = u.Transform(location=pos, rotation=rot or u.Rotator(roll=0, pitch=0, yaw=0))
    o = gs.call_method('BeginDeferredActorSpawnFromClass', (w, klass, tr, u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None,
                                                            u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    for n, (v, k) in (props or {}).items():
        prop(o, n, v, k)
    return gs.call_method('FinishSpawningActor', (o, tr, u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))


def all_of(w, path):
    return list(u.GameplayStatics.get_all_actors_of_class(w, u.load_asset(path).generated_class()))


def look_at(a, b):
    return u.MathLibrary.find_look_at_rotation(a, b)


# ------------------------------------------------------------------ the arena and the opponents
def clear_props(w):
    """The props near the middle go (each visit makes a fresh layout); floor marks stay."""
    n = 0
    for a in all_of(w, PROP):
        o, e = a.get_actor_bounds(False)
        if e.z > 60 and math.hypot(o.x - O.x, o.y - O.y) < CLEAR:
            a.destroy_actor()
            n += 1
    return n


def calm(p):
    """An opponent never charges an ultimate: a cast's Refresh timer could roll one."""
    for name in ELS:
        sysobj.call_method('K2_ClearTimer', (p, 'Refresh%sSpell' % name))
        prop(p, name + 'SpellState', 0, 'Int')


def park(p, k):
    """Sitting a segment out: hidden, still and untouchable, high above a corner."""
    cm = p.get_editor_property('character_movement')
    cm.stop_movement_immediately()
    cm.disable_movement()
    p.set_actor_location(V((-1800 - 220 * k, 1800), 3000.0), False, True)
    p.set_actor_hidden_in_game(True)
    p.set_actor_enable_collision(False)


def make_opponent(w, od, k):
    chc = u.load_asset(CH).generated_class()
    pos = V((-1800 - 220 * k, 1800), 3000.0)
    p = spawn(w, chc, pos)
    ai = spawn(w, u.AIController.static_class(), pos, {'bWantsPlayerState': (True, 'Bool')})
    ai.possess(p)
    ps = p.get_editor_property('player_state')
    if ps:
        sysobj.call_method('SetBytePropertyByName', (ps, 'SelectedWizardType', od))
    prop(p, 'PracticePawn', False, 'Bool')
    sysobj.call_method('SetBytePropertyByName', (p, 'WizardType', od))
    p.call_method('InitializeWizardTraits')
    cm = p.get_editor_property('character_movement')
    prop(p, 'bUseControllerRotationYaw', False, 'Bool')
    prop(cm, 'bUseControllerDesiredRotation', False, 'Bool')
    prop(cm, 'bOrientRotationToMovement', False, 'Bool')
    park(p, k)
    return dict(pawn=p, ai=ai, d=od, k=k, out=True)


def ensure_opponents(w, d):
    """A knocked-away opponent could have left the arena (Sky Grove has no floor beyond the
    bridge): a missing or knocked-out one is made again."""
    for i, o in enumerate(ctx['opps']):
        ok = u.SystemLibrary.is_valid(o['pawn'])
        if ok and not bool(get(o['pawn'], 'bIsDead', False)):
            continue
        note('%s: opponent %s %s -- made again' % (WHO[d], WHO[o['d']], 'dead' if ok else 'gone'))
        for a in (o['pawn'], o['ai']):
            try:
                a.destroy_actor()
            except Exception:
                pass
        ctx['opps'][i] = make_opponent(w, o['d'], o['k'])


def place_opponents(where, at):
    hero = V(at, 60)
    for o in ctx['opps']:
        p = o['pawn']
        calm(p)
        prop(p, 'MaxHealth', 1000.0)
        prop(p, 'Health', 1000.0)
        if o['k'] >= len(where):
            park(p, o['k'])
            o['out'] = True
            continue
        p.set_actor_hidden_in_game(False)
        p.set_actor_enable_collision(True)
        cm = p.get_editor_property('character_movement')
        cm.set_movement_mode(u.MovementMode.MOVE_WALKING)
        cm.stop_movement_immediately()
        pos = V(where[o['k']])
        p.set_actor_location(pos, False, True)
        p.set_actor_rotation(u.Rotator(roll=0, pitch=0, yaw=math.degrees(math.atan2(hero.y - pos.y, hero.x - pos.x))), True)
        o['out'] = False
        o['ai'].set_control_rotation(look_at(pos + u.Vector(0, 0, 60), hero))


def opponents_look(pawn):
    """The opponents' heads follow the wizard (the head look-at uses the control rotation)."""
    hero = pawn.get_actor_location() + u.Vector(0, 0, 60)
    for o in ctx['opps']:
        if not o['out']:
            o['ai'].set_control_rotation(look_at(o['pawn'].get_actor_location() + u.Vector(0, 0, 60), hero))


# what keeps a segment going: shots, orbs, the lightning field.  Not the ultimate's cast
# actor (it outlives its payload by seconds) nor the cute effects (some linger ~3 s).
LIVE = [ORB, FIELD] + SPELLS


def live_magic(w):
    return sum(len(all_of(w, p)) for p in LIVE)


def clear_magic(w):
    for path in [ORB, CAST, FX, TELE, FIELD] + SPELLS:
        for a in all_of(w, path):
            a.destroy_actor()


def reset_pawn(pawn, where, yaw):
    cm = pawn.get_editor_property('character_movement')
    try:
        pawn.call_method('Server_SetBlocking', (False,))
        pawn.call_method('Server_SetJumpHeld', (False,))
        pawn.stop_jumping()
    except Exception:
        pass
    prop(pawn, 'UltimateDashing', False, 'Bool')
    prop(pawn, 'UltimateWindupActive', False, 'Bool')
    prop(pawn, 'bBlinkReady', True, 'Bool')
    prop(pawn, 'BlockReadyAt', 0.0)
    prop(pawn, 'bUseControllerRotationYaw', False, 'Bool')
    prop(cm, 'bUseControllerDesiredRotation', False, 'Bool')
    prop(cm, 'bOrientRotationToMovement', False, 'Bool')
    cm.stop_movement_immediately()
    cm.set_movement_mode(u.MovementMode.MOVE_WALKING)
    pawn.set_actor_location(V(where), False, True)
    pawn.set_actor_rotation(u.Rotator(roll=0, pitch=0, yaw=yaw), True)
    prop(pawn, 'Health', 1000.0)


def arm(pawn, e, charged):
    """Spell states: 0 ready, 1 cooling down, 2 charged (the next cast is the ultimate).
    A cast leaves a Refresh<El>Spell timer that later sets the state back -- clear them so a
    segment gets exactly the cast it asks for."""
    for k, name in enumerate(ELS):
        sysobj.call_method('K2_ClearTimer', (pawn, 'Refresh%sSpell' % name))
        prop(pawn, name + 'SpellState', 2 if (charged and k == e) else 0, 'Int')
    sysobj.call_method('SetBytePropertyByName', (pawn, 'CurrentSpellType', e))


def capture(w, path):
    u.SystemLibrary.execute_console_command(w, 'HighResShot 1280x720 filename=%s' % path.as_posix())
    ctx['req'] += 1


def wizard_type(pawn):
    try:
        v = pawn.get_editor_property('WizardType')
        return int(v.value) if hasattr(v, 'value') else int(v)
    except Exception:
        return -1


def set_wizard(pc, pawn, d, full=True):
    """The character: the player state's choice too (practice mode syncs the pawn from it)."""
    ps = pawn.get_editor_property('player_state') or pc.get_editor_property('player_state')
    if ps:
        sysobj.call_method('SetBytePropertyByName', (ps, 'SelectedWizardType', d))
    sysobj.call_method('SetBytePropertyByName', (pawn, 'WizardType', d))
    if full:
        pawn.call_method('InitializeWizardTraits')


def hide_hud(pc):
    hud = pc.get_hud()
    if hud and not HUD_ON:
        prop(hud, 'bShowHUD', False, 'Bool')
    return hud


def arena_ready(w, pc, pawn, d):
    """The wizard has stood in the middle for a moment: the floor height, then the stage."""
    global O
    half = pawn.get_component_by_class(u.CapsuleComponent).get_scaled_capsule_half_height()
    floor = pawn.get_actor_location().z - half
    O = u.Vector(0.0, 0.0, floor + 130.0)
    gone = clear_props(w)
    ctx['opps'] = [make_opponent(w, od, k) for k, od in enumerate(OPPS[d])]
    hide_hud(pc)
    # the cut-in cards come from the post; the in-game one (R20_HUD) in English, not saved
    prop(pc, 'bShowMouseCursor', True, 'Bool')
    sysobj.call_method('SetIntPropertyByName', (pc, 'Language', 0))
    if AUDIO:
        quiet_music(pc)
        u.AudioMixerLibrary.start_recording_output(w, 1200.0, None)
        ctx.update(rec=True, tick=0, world=w)
    ctx.update(stage='char', at=time.monotonic(), floor=floor)
    note('%s in %s: floor z %.1f, %d props taken away, opponents %s (audio %s, hud %s, only %s)' % (
        WHO[d], ARENA[d], floor, gone, [WHO[od] for od in OPPS[d]], AUDIO, HUD_ON, ONLY))


# ------------------------------------------------------------------ camera
def pose(spec, pawn_loc):
    if spec.get('orbit') is not None:
        off = spec['off']
        pivot = pawn_loc + u.Vector(off[0], off[1], 60 + off[2])
        if spec.get('z') is not None:
            pivot = u.Vector(pivot.x, pivot.y, ctx['z0'] + spec['z'])
        th = math.radians(ctx['seg']['face'] + spec['orbit'])
        loc = pivot + u.Vector(math.cos(th) * spec['dist'], math.sin(th) * spec['dist'], spec['h'])
        r = look_at(loc, pivot)
        return loc, u.Rotator(roll=0, pitch=r.pitch, yaw=r.yaw + spec['pan'])
    rot = u.Rotator(roll=0, pitch=spec['pitch'], yaw=spec['yaw'])
    if spec.get('at') is not None:
        a = spec['at']
        pivot = V(a[:2], a[2])
    else:
        off = spec['off']
        pivot = pawn_loc + u.Vector(off[0], off[1], 60 + off[2])
        if spec.get('z') is not None:
            pivot = u.Vector(pivot.x, pivot.y, ctx['z0'] + spec['z'])
    return pivot - rot.get_forward_vector() * spec['dist'], rot


def update_camera(pawn, k):
    """The segment's current camera set-up (cuts and smooth moves); returns it."""
    shots = ctx['seg']['shots']
    while ctx['sh'] + 1 < len(shots) and k >= shots[ctx['sh'] + 1]['start']:
        ctx['sh'] += 1
        ctx['sh_k'] = k
    sh = shots[ctx['sh']]
    here = pawn.get_actor_location()
    loc, rot = pose(sh['spec'], here)
    if sh['blend'] and ctx['sh'] > 0 and k - ctx['sh_k'] < sh['blend']:
        t = (k - ctx['sh_k'] + 1) / float(sh['blend'])
        t = t * t * (3 - 2 * t)
        ploc, prot = pose(shots[ctx['sh'] - 1]['spec'], here)
        loc = ploc + (loc - ploc) * t
        dy = (rot.yaw - prot.yaw + 180.0) % 360.0 - 180.0
        rot = u.Rotator(roll=0, pitch=prot.pitch + (rot.pitch - prot.pitch) * t, yaw=prot.yaw + dy * t)
    ctx['cam'].set_actor_location_and_rotation(loc, rot, False, True)
    return sh


def aim_head(pc, pawn, sh):
    """The controller's rotation is the aim; the head looks there: into the camera for
    face-on shots, else at the segment's target."""
    head = pawn.get_actor_location() + u.Vector(0, 0, 60)
    seg = ctx['seg']
    if sh['face'] or seg['target'] is None:
        if sh['face']:
            r = look_at(head, ctx['cam'].get_actor_location())
        else:
            r = u.Rotator(roll=0, pitch=-5, yaw=seg['face'])
    else:
        r = look_at(head, V(seg['target'], 30))
    pc.set_control_rotation(r)


def free_cam(pc):
    """GetBaseAimRotation -> the pawn's own rotation (round 18: else the fire volley and the
    storm target would follow the camera, which often looks at the wizard's face)."""
    u.SystemLibrary.execute_console_command(pc.get_world(), 'camera freecam', pc)


# ------------------------------------------------------------------ segments
def setup_segment(w, pc, pawn, d, seg):
    if wizard_type(pawn) != d:
        note('%s: WizardType was %s before %s -- set back' % (WHO[d], wizard_type(pawn), seg['id']))
        set_wizard(pc, pawn, d)
    clear_magic(w)
    ensure_opponents(w, d)
    place_opponents(seg['dummies'], seg['at'])
    reset_pawn(pawn, seg['at'], seg['face'])
    arm(pawn, seg['e'], False)
    if seg['kind'] == 'hover':
        prop(pawn, 'HoverDuration', 1.0)
    hide_hud(pc)
    ctx.update(seg=seg, sh=0, sh_k=0, events={}, wound=False, z0=pawn.get_actor_location().z, hp0=None, quiet=0)
    if ctx.get('cam') is None:
        ctx['cam'] = spawn(w, u.CameraActor.static_class(), pawn.get_actor_location())
        pc.set_view_target_with_blend(ctx['cam'], 0.0)
        free_cam(pc)
    sh = update_camera(pawn, 0)
    aim_head(pc, pawn, sh)


def volta_target(w, pawn, target):
    """The storm lands on `target`: her facing and the warning circle follow (the cast took
    them from the crosshair, i.e. from wherever the face-on camera looked)."""
    for n_ in ('StormTarget', 'LockedStormTarget', 'ResolvedStormAimPoint'):
        sysobj.call_method('SetVectorPropertyByName', (pawn, n_, target))
    here = pawn.get_actor_location()
    yaw = math.degrees(math.atan2(target.y - here.y, target.x - here.x))
    pawn.set_actor_rotation(u.Rotator(roll=0, pitch=0, yaw=yaw), True)
    for t in all_of(w, TELE):
        t.set_actor_location(target, False, True)


def act(w, pc, pawn, d, seg, k):
    """Things that happen k recorded frames into the segment."""
    kind, e = seg['kind'], seg['e']
    if kind in ('spell', 'second', 'ult') and k > 3:
        for name in ELS:             # no random charge after the cast (see arm)
            sysobj.call_method('K2_ClearTimer', (pawn, 'Refresh%sSpell' % name))
    if kind == 'run' and 3 <= k < 3 + int(1.7 * FPS):
        pawn.add_movement_input(u.Vector(1, 0, 0), 1.0, False)
    if kind == 'jump':
        if k == 4:
            pawn.jump()
        if k == 10:
            pawn.stop_jumping()
    if kind in ('spell', 'ult') and k == 3:
        if wizard_type(pawn) != d:
            note('%s: WizardType was %s at the cast -- set back' % (WHO[d], wizard_type(pawn)))
            sysobj.call_method('SetBytePropertyByName', (pawn, 'WizardType', d))
        arm(pawn, e, kind == 'ult')
        tgt = V(seg['target'], FLOOR if (kind == 'ult' and d == 3) else 30)
        pawn.call_method('Server_Fire', (tgt,))
        if kind == 'ult' and d == 3:
            volta_target(w, pawn, tgt)
    if kind == 'ult':
        wind = bool(get(pawn, 'UltimateWindupActive', False))
        if wind:
            ctx['wound'] = True
        elif ctx['wound'] and 'launch' not in ctx['events']:
            ctx['events']['launch'] = k
            note('%s %s: launch at frame %d' % (WHO[d], seg['id'], k))
        if k == 3 + int(1.6 * FPS) and 'launch' not in ctx['events']:
            note('%s %s: no launch seen by frame %d (wound %s)' % (WHO[d], seg['id'], k, ctx['wound']))
    if kind == 'second':
        if k == 3:
            arm(pawn, e, False)
            ctx['second_done'] = False
            pawn.call_method('Server_Fire', (V(seg['target'], 30),))
            ctx['second_from'] = pawn.get_actor_location()
        elif k > 3 and not ctx.get('second_done'):
            # once the shot is SECOND_AT cm out (a destroyed shot reads as the world origin)
            pr = get(pawn, 'ActiveSecondaryProjectile')
            dist = (pr.get_actor_location() - ctx['second_from']).length() if pr else -1.0
            if SECOND_AT[e] <= dist < 2000.0:
                pawn.call_method('Server_UseSecondary')
                ctx['second_done'] = True
                note('%s: second press %s at frame %d (%.0f cm)' % (WHO[d], ELS[e], k, dist))
            elif dist >= 2000.0 or k > 3 + 2 * FPS:
                ctx['second_done'] = True
                note('%s: the %s shot was gone before the second press (frame %d)' % (WHO[d], ELS[e], k))
    if kind == 'block':
        dm = ctx['opps'][0]['pawn']
        if k == 0:
            # health is clamped to MaxHealth on a hit: start from full to see the 40% damage
            prop(pawn, 'Health', float(get(pawn, 'MaxHealth', 100.0)))
            ctx['hp0'] = float(get(pawn, 'MaxHealth', 100.0))
        if k == 2:
            pawn.call_method('Server_SetBlocking', (True,))
        if k == 5:
            calm(dm)
            sysobj.call_method('SetBytePropertyByName', (dm, 'CurrentSpellType', 0))
            dm.call_method('Server_Fire', (pawn.get_actor_location() + u.Vector(0, 0, 20),))
            for name in ELS:
                sysobj.call_method('K2_ClearTimer', (dm, 'Refresh%sSpell' % name))
        if k == 36:
            pawn.call_method('Server_SetBlocking', (False,))
        if k == 50:
            note('%s block: health %.1f -> %.1f' % (WHO[d], ctx['hp0'], float(get(pawn, 'Health', 0.0))))
    if kind == 'hover':
        if k == 3:
            pawn.call_method('Server_SetJumpHeld', (True,))
            pawn.jump()
        if k == 3 + int(2.3 * FPS):
            pawn.call_method('Server_SetJumpHeld', (False,))
            pawn.stop_jumping()
    if kind == 'blink' and k == 8:
        pawn.call_method('Server_Blink', (u.Vector(0, 1, 0),))
        note('%s blink: now at y %+.0f' % (WHO[d], pawn.get_actor_location().y - O.y))


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
            ctx['tick'] += 1                # one engine tick = 1/30 s of recorded sound
        if st == 'wait':
            if el > 4:
                ctx.update(stage='travel')
            return
        if st == 'travel':
            if ctx['ci'] >= len(WHOLIST):
                finish()
                return
            d = WHOLIST[ctx['ci']]
            sysobj.call_method('K2_SetTimer', (pc, 'Explore' + ARENA[d], .1, False, 0, 0))
            ctx.update(stage='enter', at=time.monotonic(), cam=None, opps=[])
            note('to %s for %s' % (ARENA[d], WHO[d]))
            return
        d = WHOLIST[ctx['ci']]
        ctx['d'] = d
        if st == 'enter':
            if el > 8:
                # stand in the middle for a moment: the floor height comes from there
                set_wizard(pc, pawn, d)
                pawn.get_editor_property('character_movement').stop_movement_immediately()
                pawn.set_actor_location(u.Vector(0.0, 0.0, pawn.get_actor_location().z + 20.0), False, True)
                ctx.update(stage='measure', f=0)
            return
        if st == 'measure':
            ctx['f'] += 1
            if ctx['f'] >= 30:
                arena_ready(w, pc, pawn, d)
            return
        if AUDIO and ctx.get('tick', 0) % 15 == 0:
            quiet_music(pc)
        if ctx.get('tick', 0) % 30 == 0:
            prop(pc, 'bShowMouseCursor', True, 'Bool')
        segs = segments(d)
        if st == 'char':
            set_wizard(pc, pawn, d)
            clear_magic(w)
            place_opponents([], (0, 0))
            reset_pawn(pawn, (0, 0), 0)
            (FRAMES / WHO[d]).mkdir(parents=True, exist_ok=True)
            ctx.update(stage='settle', at=time.monotonic(), si=0, f=0, n=0, settle=0, tex=None)
            ctx['timeline'][WHO[d]] = {'segments': [], 'fps': FPS, 'arena': ARENA[d], 'floor': ctx['floor'],
                                       'opponents': [WHO[od] for od in OPPS[d]], 'audio': 'game_audio.wav'}
            return
        if st == 'settle':
            ctx['settle'] += 1
            if ctx['settle'] > 40:
                ctx.update(stage='seg', f=0)
            return
        if st == 'seg':
            if ctx['si'] >= len(segs):
                note('done %s: %d frames, %d shot requests' % (WHO[d], ctx['n'], ctx['req']))
                stop_audio(w, d)
                ctx['ci'] += 1
                ctx.update(stage='travel', at=time.monotonic())
                return
            seg = segs[ctx['si']]
            nmin, nframes = int(round(seg['secs'][0] * FPS)), int(round(seg['secs'][1] * FPS))
            f = ctx['f']
            if f == 0:
                setup_segment(w, pc, pawn, d, seg)
                ctx['f'] = 1
                return
            if f < PRE:                     # positions and camera settle, cleared magic fades (not recorded)
                aim_head(pc, pawn, update_camera(pawn, 0))
                opponents_look(pawn)
                ctx['f'] += 1
                return
            k = f - PRE
            tl = ctx['timeline'][WHO[d]]
            if k == 0:
                ctx['z0'] = pawn.get_actor_location().z          # settled on the floor
                tl['segments'].append(dict(id=seg['id'], kind=seg['kind'], e=seg['e'], start=ctx['n'], frames=nframes,
                                           ticks=[], hud=[]))
                ctx['gt0'] = u.GameplayStatics.get_time_seconds(w)
            act(w, pc, pawn, d, seg, k)
            # a segment with magic ends once all of it is gone (+ TAIL frames), within its bounds
            if nmin < nframes and k > 5:
                ctx['quiet'] = ctx.get('quiet', 0) + 1 if live_magic(w) == 0 else 0
            sh = update_camera(pawn, k)
            aim_head(pc, pawn, sh)
            opponents_look(pawn)
            # the HUD's cut-in timing for this frame (the post draws the card from it)
            hud = hide_hud(pc) if k % 30 == 0 else pc.get_hud()
            cs = float(get(hud, 'CutInStart', -100.0)) if hud else -100.0
            tex = get(hud, 'CutInTex') if hud else None
            name = tex.get_name() if tex else ''
            if name != ctx.get('tex'):
                ctx['tex'] = name
                note('%s %s: cut-in card %s from %.3f' % (WHO[d], seg['id'], name or '-', cs))
            rec = tl['segments'][-1]
            rec['hud'].append([round(u.GameplayStatics.get_time_seconds(w), 4), round(cs, 4)])
            if AUDIO:
                rec['ticks'].append(ctx['tick'])
            capture(w, FRAMES / WHO[d] / ('f_%05d.png' % ctx['n']))
            ctx['n'] += 1
            ctx['f'] += 1
            if k + 1 >= nframes or (k + 1 >= nmin and ctx.get('quiet', 0) >= TAIL):
                gt = u.GameplayStatics.get_time_seconds(w) - ctx['gt0']
                rec['frames'] = k + 1
                note('%s %s: %d frames (%d-%d), game time %.3f s (expected %.3f)' % (
                    WHO[d], seg['id'], k + 1, nmin, nframes, gt, k / FPS))
                ctx['quiet'] = 0
                ctx['si'] += 1
                ctx['f'] = 0
            return
    except Exception:
        import traceback
        note('ERROR ' + traceback.format_exc())
        finish()


if __name__ == '__main__':
    ctx['handle'] = u.register_slate_post_tick_callback(tick)
    note('begin play requested (who=%s, only=%s, hud %s)' % (WHOLIST, ONLY, HUD_ON))
    ls.editor_request_begin_play()
