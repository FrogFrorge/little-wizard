"""Round 13: wire the ultimate presentation into the game.

BP_WizardMatchHUD
  StartUltCutIn(Wizard)   picks the wizard's card (T_UltCutIn_<Wizard>) and notes the time
  DrawUltCutIn(SizeX, SizeY), called first thing in ReceiveDrawHUD: the card slides in
  from the left (0.16 s, ease-out), holds, then slides out and fades (1.15 -> 1.45 s);
  a faint white flash under the slide-in.  Game time (so it also slows in slow motion).
BP_WizardCharacter
  UltPresentation: the wizard's own wind-up sound (UltStart_<Wizard>, at the wizard),
  the cut-in swish (UltCutIn, 2D) and the local HUD's StartUltCutIn.  Called at the top
  of AudioAction for the ultimate codes 4-7 -- AudioAction runs from PlayWizardAction on
  every machine (the action token is a RepNotify set with notify on the server), so
  every player sees and hears whose ultimate is coming.

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r13_wire.py
"""
import os
import sys
import json
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
import r11_bp
importlib.reload(r11_bp)
from r11_bp import *          # noqa

HUD = '/Game/BluePrint/Gamemode/BP_WizardMatchHUD'
KEYS = ['Blaise', 'Neve', 'Gale', 'Volta']          # WizardType 0..3
OUT13 = Path(__file__).resolve().parent / 'output' / 'round13'
RPT = Path('..') / 'round13' / 'r13-wire.json'      # relative to r11_bp.OUT (output/round11)
SLIDE_IN, HOLD, SLIDE_OUT = 0.16, 1.15, 0.30
CARD_H, CARD_Y, CARD_ASPECT = 0.36, 0.26, 2.5        # of the screen height; the card is 1400 x 560


def hud_functions():
    declare(HUD, 'CutInTex', obj(u.Texture2D.static_class()), '')
    declare(HUD, 'CutInStart', R, '-100.0')
    # StartUltCutIn(Wizard)
    g = fresh(HUD, 'StartUltCutIn', [('Wizard', I)])
    sw = g.switch_int(g.inp('Wizard'), [0, 1, 2, 3])
    link(g.entry(), sw['in'])
    for d, key in enumerate(KEYS):
        s = g.set('CutInTex', '/Game/UI/UltCutIn/T_UltCutIn_%s.T_UltCutIn_%s' % (key, key))
        link(sw[d], ex(s))
        t = g.set('CutInStart', g.now())
        link(then(s), ex(t))
    layout(g)
    # DrawUltCutIn(SizeX, SizeY)
    g = fresh(HUD, 'DrawUltCutIn', [('SizeX', I), ('SizeY', I)])
    t = g.fsub(g.now(), g.get('CutInStart'))
    show = g.branch(g.AND(g.valid(g.get('CutInTex')), g.math('GreaterEqual_DoubleDouble', A=t, B=0.0),
                          g.math('Less_DoubleDouble', A=t, B=HOLD + SLIDE_OUT)))
    link(g.entry(), ex(show))
    sy = g.tofloat(g.inp('SizeY'))
    sx = g.tofloat(g.inp('SizeX'))
    h = g.fmul(sy, CARD_H)
    w = g.fmul(h, CARD_ASPECT)
    p = g.math('FClamp', Value=g.math('Divide_DoubleDouble', A=t, B=SLIDE_IN), Min=0.0, Max=1.0)
    ease = g.fsub(1.0, g.math('MultiplyMultiply_FloatFloat', Base=g.fsub(1.0, p), Exp=3.0))
    q = g.math('FClamp', Value=g.math('Divide_DoubleDouble', A=g.fsub(t, HOLD), B=SLIDE_OUT), Min=0.0, Max=1.0)
    out = g.fmul(q, q)
    x = g.fsub(g.fmul(g.fsub(ease, 1.0), w), g.fmul(out, w))
    # a faint flash under the slide-in
    flash = g.call('/Script/Engine.HUD.DrawRect', RectColor=g.math('MakeColor', R=1.0, G=1.0, B=1.0, A=g.fmul(g.fsub(1.0, p), 0.14)),
                   ScreenX=0.0, ScreenY=0.0, ScreenW=sx, ScreenH=sy)
    card = g.call('/Script/Engine.HUD.DrawTexture', Texture=g.get('CutInTex'), ScreenX=x, ScreenY=g.fmul(sy, CARD_Y),
                  ScreenW=w, ScreenH=h, TextureU=0.0, TextureV=0.0, TextureUWidth=1.0, TextureVHeight=1.0,
                  TintColor=g.math('MakeColor', R=1.0, G=1.0, B=1.0, A=g.fsub(1.0, q)))
    chain(pin(show, 'then', True), flash, card)
    layout(g)
    compile_bp(HUD, True)


def hud_draw_hook():
    g = Graph(HUD, 'EventGraph')
    nodes = g.e.list_all_nodes()
    if any('DrawUltCutIn' in str(n.get_node_title()) for n in nodes):
        return 'already'
    ev = next(n for n in nodes if n.get_class().get_name() == 'K2Node_Event' and 'DrawHUD' in str(n.get_node_title()).replace(' ', ''))
    out = pin(ev, 'then', True)
    targets = list(out.list_connected_pins())
    call = g.fn('DrawUltCutIn', SizeX=pin(ev, 'SizeX', True), SizeY=pin(ev, 'SizeY', True))
    out.break_pin_links()
    link(out, ex(call))
    for tp in targets:
        link(then(call), tp)
    compile_bp(HUD, True)
    return 'hooked (%d downstream)' % len(targets)


def character_presentation():
    g = fresh(CH, 'UltPresentation')
    wt = g.toint(g.get('WizardType'))
    sw = g.switch_int(wt, [0, 1, 2, 3])
    link(g.entry(), sw['in'])
    lasts = []
    for d, key in enumerate(KEYS):
        s = g.call('/Script/Engine.GameplayStatics.PlaySoundAtLocation', Sound='/Game/Audio/Wizard/SFX/UltStart_%s.UltStart_%s' % (key, key),
                   Location=g.loc(), VolumeMultiplier=1.0, PitchMultiplier=1.0, OwningActor=g.selfref())
        link(sw[d], ex(s))
        lasts.append(then(s))
    cut = g.call('/Script/Engine.GameplayStatics.PlaySound2D', Sound='/Game/Audio/Wizard/UI/UltCutIn.UltCutIn', VolumeMultiplier=1.0,
                 PitchMultiplier=1.0)
    for l_ in lasts + [sw['default']]:
        link(l_, ex(cut))
    pc = result(g.call('/Script/Engine.GameplayStatics.GetPlayerController', PlayerIndex=0))
    hud = result(g.call('/Script/Engine.PlayerController.GetHUD', self=pc))
    castn, as_hud = g.cast(hud, HUD, u.HUD)
    link(then(cut), ex(castn))
    start = g.call(cp(HUD) + '.StartUltCutIn', self=as_hud, Wizard=wt)
    link(pin(castn, 'then', True), ex(start))
    layout(g)


def audio_action_hook():
    g = Graph(CH, 'AudioAction')
    nodes = g.e.list_all_nodes()
    if any('UltPresentation' in str(n.get_node_title()) for n in nodes):
        return 'already'
    entry = g.entry()
    targets = list(entry.list_connected_pins())
    code = g.inp('Code')
    is_ult = g.branch(g.AND(g.math('GreaterEqual_IntInt', A=code, B=4), g.math('LessEqual_IntInt', A=code, B=7)))
    call = g.fn('UltPresentation')
    entry.break_pin_links()
    link(entry, ex(is_ult))
    link(pin(is_ult, 'then', True), ex(call))
    for tp in targets:
        link(then(call), tp)
        link(pin(is_ult, 'else', True), tp)
    return 'hooked'


def main():
    # two runs (R13_STAGE=hud, then char): no Blueprint is compiled before the operator
    # nodes of the next one are made (the mid-session compile crash, see r12)
    stage = os.environ.get('R13_STAGE', 'hud')
    try:
        for p_ in (HUD, CH):
            backup(p_)
        if stage == 'hud':
            hud_functions()
            log('HUD: StartUltCutIn / DrawUltCutIn', RPT)
            log('HUD draw hook: ' + hud_draw_hook(), RPT)
        else:
            character_presentation()
            log('character: UltPresentation', RPT)
            log('AudioAction hook: ' + audio_action_hook(), RPT)
            compile_bp(CH, True)
        REPORT['passed'] = True
        log('done', RPT)
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        (OUT13 / 'r13-wire.json').write_text(json.dumps(REPORT, indent=1, default=str), encoding='utf-8')
        u.log_error(traceback.format_exc())


main()
