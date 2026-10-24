"""Round 14: the second press of every basic shot gets its own sound and effect; the result
screen shows your wizard.

Second press (二段), until now the same sound and pop as an ordinary hit:
- fire (detonate in the air, 2x radius), ice (split into shards), lightning (drop a field):
  their TriggerSecondary calls Multicast_HitFX (a multicast, so it runs on every machine).
  The fire one already passes FXScaleInput 2.0; ice and lightning now pass 1.3 (ordinary
  hits pass 1.0).  Inside Multicast_HitFX a branch on FXScaleInput > 1.05 plays
  Secondary_<Element> (instead of Impact_<Element>), a BigPop and a Cast ring flash, then
  the usual pop (at the larger scale)
- wind (turn and home in on the nearest enemy): OnRep_BounceCount -> Multicast_WindRedirectFX
  now plays Secondary_Wind (was the bounce's Ricochet), a bigger Cast flash and a Pop puff
Result screen (WBP_WizardResult.RefreshView): ResultPortrait shows the local player's wizard
(their PlayerState's SelectedWizardType), and the title is coloured by the result (victory
gold, defeat slate blue, draw purple).

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r14_wire.py
"""
import json
import shutil
import sys
import traceback
from pathlib import Path

import unreal as u

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r11_bp as B  # noqa: E402
from r11_bp import Graph, pin, link, then, ex, result, value

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'round14'
BACKUP = ROOT / 'round14-before-assets'
RESULT = '/Game/UI/Flow/WBP_WizardResult'
PS = '/Game/BluePrint/Character/BP_WizardPlayerState'
NS = '/Game/VFX/WizardMagic/Cute/Systems/NS_Cute_%s_%s.NS_Cute_%s_%s'
SFX = '/Game/Audio/Wizard/SFX/%s.%s'
KEYS = ['Blaise', 'Neve', 'Gale', 'Volta']
REPORT = {'steps': []}
# FXScaleInput of each element's second press; BigPop and Cast scale = FXScaleInput x these
SECOND = {'Fire': (None, 0.55, 1.0), 'Ice': (1.3, 0.55, 1.0), 'Lightning': (1.3, 0.55, 1.0)}


def log(s):
    print('R14 ' + s)
    REPORT['steps'].append(s)
    (OUT / 'r14-wire.json').write_text(json.dumps(REPORT, indent=1, ensure_ascii=False), encoding='utf-8')


def backup(path):
    src = Path(u.Paths.project_content_dir()).resolve() / (path.removeprefix('/Game/') + '.uasset')
    dst = BACKUP / src.relative_to(Path(u.Paths.project_content_dir()).resolve())
    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def title(n):
    return str(n.get_node_title()).split('\n')[0].strip()


def find(g, pred):
    hits = [n for n in g.e.list_all_nodes() if pred(n)]
    assert len(hits) == 1, (g.p, g.name, [title(h) for h in hits])
    return hits[0]


def next_of(n):
    """The node an exec 'then' pin leads to."""
    t = then(n)
    nxt = t.list_connected_pins()
    assert len(nxt) == 1, title(n)
    return nxt[0].get_owning_node()


def pin_value(n, name):
    p = n.find_input_pin(name)
    return str(p.get_pin_value()) if p.is_valid() else ''


def is_event(n, name):
    return n.get_class().get_name() == 'K2Node_CustomEvent' and title(n) == name


def is_call(n, fname):
    return n.get_class().get_name() == 'K2Node_CallFunction' and title(n) == fname


# ------------------------------------------------------------------ second press
def secondary_hit(el):
    p = B.SPELLS[el]
    g = Graph(p)
    ev = find(g, lambda n: is_event(n, 'Multicast_HitFX'))
    if any('Secondary_' in pin_value(n, 'Sound') for n in g.e.list_all_nodes()):
        log('%s: Multicast_HitFX already has the second-press branch' % el)
        return
    impact = next_of(ev)
    assert 'Impact_' in pin_value(impact, 'Sound'), (el, title(impact))
    pop = next_of(impact)
    loc = pin(ev, 'HitLocation', True)
    scale = pin(ev, 'FXScaleInput', True)
    _, k_big, k_cast = SECOND[el]
    # the branch: FXScaleInput > 1.05 -> second press
    then(ev).break_pin_links()
    br = g.branch(g.math('Greater_DoubleDouble', A=scale, B=1.05))
    link(then(ev), ex(br))
    link(pin(br, 'else', True), ex(impact))
    snd = g.call('/Script/Engine.GameplayStatics.PlaySoundAtLocation', Sound=SFX % ('Secondary_' + el, 'Secondary_' + el),
                 Location=loc, Rotation=(0, 0, 0), VolumeMultiplier=1.0,
                 PitchMultiplier=g.math('RandomFloatInRange', Min=0.97, Max=1.03), OwningActor=g.selfref())
    big_s = g.fmul(scale, k_big)
    big = g.call('/Script/Niagara.NiagaraFunctionLibrary.SpawnSystemAtLocation', SystemTemplate=NS % (el, 'BigPop', el, 'BigPop'),
                 Location=loc, Rotation=(0, 0, 0), Scale=g.math('MakeVector', X=big_s, Y=big_s, Z=big_s),
                 bAutoDestroy=True, bAutoActivate=True, bPreCullCheck=False)
    cast_s = g.fmul(scale, k_cast)
    ring = g.call('/Script/Niagara.NiagaraFunctionLibrary.SpawnSystemAtLocation', SystemTemplate=NS % (el, 'Cast', el, 'Cast'),
                  Location=loc, Rotation=(0, 0, 0), Scale=g.math('MakeVector', X=cast_s, Y=cast_s, Z=cast_s),
                  bAutoDestroy=True, bAutoActivate=True, bPreCullCheck=False)
    B.chain(pin(br, 'then', True), snd, big, ring)
    link(then(ring), ex(pop))
    log('%s: Multicast_HitFX -> second press plays Secondary_%s + BigPop x%.2f + Cast x%.2f' % (el, el, k_big, k_cast))


def secondary_scale(el):
    """Ice / lightning: their second press calls Multicast_HitFX with a scale of its own."""
    s = SECOND[el][0]
    if s is None:
        return
    g = Graph(B.SPELLS[el], 'TriggerSecondary')
    n = find(g, lambda n: is_call(n, 'Multicast_HitFX'))
    value(pin(n, 'FXScaleInput'), s)
    log('%s: TriggerSecondary -> Multicast_HitFX FXScaleInput %.2f' % (el, s))


def wind_redirect():
    g = Graph(B.SPELLS['Wind'])
    ev = find(g, lambda n: is_event(n, 'Multicast_WindRedirectFX'))
    snd = next_of(ev)
    value(pin(snd, 'Sound'), SFX % ('Secondary_Wind', 'Secondary_Wind'))
    flash = next_of(snd)
    assert 'Wind_Cast' in pin_value(flash, 'SystemTemplate'), title(flash)
    value(pin(flash, 'Scale'), (0.9, 0.9, 0.9))
    after = next_of(flash)
    if 'Wind_Pop' in pin_value(after, 'SystemTemplate'):
        log('Wind: redirect already has the puff')
        return
    then(flash).break_pin_links()
    puff = g.call('/Script/Niagara.NiagaraFunctionLibrary.SpawnSystemAtLocation', SystemTemplate=NS % ('Wind', 'Pop', 'Wind', 'Pop'),
                  Location=pin(flash, 'Location').list_connected_pins()[0], Rotation=(0, 0, 0), Scale=(0.6, 0.6, 0.6),
                  bAutoDestroy=True, bAutoActivate=True, bPreCullCheck=False)
    link(then(flash), ex(puff))
    link(then(puff), ex(after))
    log('Wind: Multicast_WindRedirectFX -> Secondary_Wind, Cast flash x0.9, Pop puff x0.6')


# ------------------------------------------------------------------ result screen
def slate(c):
    f = lambda v: (v / 255.0) / 12.92 if v / 255.0 <= 0.04045 else ((v / 255.0 + 0.055) / 1.055) ** 2.4
    return '(SpecifiedColor=(R=%.6f,G=%.6f,B=%.6f,A=1.000000),ColorUseRule=UseColor_Specified)' % tuple(f(v) for v in c)


def result_screen():
    g = Graph(RESULT, 'RefreshView')
    if any(is_call(n, 'Set Brush from Texture') for n in g.e.list_all_nodes()):
        log('Result: RefreshView already shows the portrait')
        return
    cast = find(g, lambda n: n.get_class().get_name() == 'K2Node_DynamicCast' and 'PlayerState' in title(n))
    ps = [x for x in cast.list_output_pins() if str(x.get_pin_name()).startswith('As')][0]
    after = next_of(cast)
    then(cast).break_pin_links()
    wt = g.toint(g.get('SelectedWizardType', PS, ps))
    sw = g.switch_int(wt, [0, 1, 2, 3])
    link(then(cast), sw['in'])
    for i, key in enumerate(KEYS):
        n = g.call('/Script/UMG.Image.SetBrushFromTexture', self=g.get('ResultPortrait'),
                   Texture='/Game/UI/Portraits/T_Wizard_%s.T_Wizard_%s' % (key, key), bMatchSize=False)
        link(sw[i], ex(n))
        link(then(n), ex(after))
    link(sw['default'], ex(after))
    log('Result: RefreshView sets ResultPortrait from SelectedWizardType')
    # the title's colour per result
    for text_, colour in (('A MAGICAL DRAW!', (140, 96, 214)), ('VICTORY!', (232, 128, 24)), ('DEFEAT', (88, 104, 150))):
        st = find(g, lambda n: is_call(n, 'SetText (Text)') and text_ in pin_value(n, 'InText'))
        nxt = next_of(st)
        then(st).break_pin_links()
        col = g.call('/Script/UMG.TextBlock.SetColorAndOpacity', self=g.get('ResultTitle'), InColorAndOpacity=slate(colour))
        link(then(st), ex(col))
        link(then(col), ex(nxt))
        log('Result: "%s" coloured %s (pin %s)' % (text_, colour, pin_value(col, 'InColorAndOpacity')[:60]))


def run():
    try:
        paths = [RESULT] + [B.SPELLS[e] for e in ('Fire', 'Ice', 'Wind', 'Lightning')]
        for p in paths:
            backup(p)
        log('backed up %d Blueprints' % len(paths))
        # every node first, then one compile per Blueprint (compiling between node edits has
        # crashed this editor before)
        for el in ('Fire', 'Ice', 'Lightning'):
            secondary_hit(el)
            secondary_scale(el)
        wind_redirect()
        result_screen()
        for p in paths:
            g = None
            B.compile_bp(p, True)
            log('compiled + saved %s' % p.rsplit('/', 1)[-1])
        REPORT['passed'] = True
        log('done')
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        (OUT / 'r14-wire.json').write_text(json.dumps(REPORT, indent=1, ensure_ascii=False), encoding='utf-8')
        u.log_error(traceback.format_exc())


run()
