"""Round 11: character traits belong to the character (not to the spell, not to practice).

- wind boy: moves 1.2x and his spells fly 1.3x (was 1.1 / 1.1)
- practice: F1-F4 switch the character (fire boy, ice girl, wind boy, lightning girl);
  the practice pawn no longer gets every character's blink + hover: each character
  keeps its own (lightning girl blinks, ice girl hovers); practice still has the short
  cooldowns and G for a charged ultimate
- the practice hint shows the new keys

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r11_traits.py
"""
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
import r11_bp
importlib.reload(r11_bp)
from r11_bp import *          # noqa

RPT = 'r11-traits.json'
OVERLAY = '/Game/UI/Flow/WBP_WizardOverlay'
WIND_MOVE, WIND_SPELL = 1.2, 1.3


def wind_traits():
    g = Graph(CH, 'InitializeWizardTraits')
    changed = []
    for n in g.e.list_all_nodes():
        if n.get_class().get_name() != 'K2Node_VariableSet':
            continue
        for var, new in (('MoveSpeedMultiplier', WIND_MOVE), ('ProjectileSpeedMultiplier', WIND_SPELL)):
            p = n.find_input_pin(var)
            if not p.is_valid() or p.list_connected_pins():
                continue
            v = float(p.get_pin_value() or 0)
            if abs(v - 1.0) > 1e-4:            # the wind branch (the others set 1.0)
                value(p, '%.6f' % new)
                changed.append((var, v, new))
    assert len(changed) == 2, changed
    compile_bp(CH, False)
    log('wind traits %s' % changed, RPT)


def own_traits():
    """Blink and hover gates: 'WizardType == X OR PracticePawn' -> 'WizardType == X'."""
    g = Graph(CH)
    fixed = 0
    for n in list(g.e.list_all_nodes()):
        if n.get_class().get_name() != 'K2Node_VariableGet' or str(n.get_node_title()) != 'Get PracticePawn':
            continue
        outp = pin(n, 'PracticePawn', True)
        for q in list(outp.list_connected_pins()):
            owner = q.get_owning_node()
            if owner.get_class().get_name() == 'K2Node_CommutativeAssociativeBinaryOperator' and str(owner.get_node_title()).startswith('OR'):
                outp.break_single_pin_link(q)
                value(q, False)
                fixed += 1
        if not list(outp.list_connected_pins()):
            g.e.remove_nodes([n])
    log('practice gates removed: %d' % fixed, RPT)
    compile_bp(CH, True)


def practice_keys():
    names = [str(x) for x in L.list_graph_names(load(PC))]
    g = fresh(PC, 'PracticeWizardKeys')
    gsn = result(g.call('/Script/Engine.GameplayStatics.GetGameState'))
    ca, st = g.cast(gsn, GS, u.GameStateBase)
    chain(g.entry(), ca)
    prac = g.branch(g.get('PracticeMode', GS, st))
    link(then(ca), ex(prac))
    prev = pin(prac, 'then', True)
    for k in range(4):
        key = g.call('/Script/Engine.PlayerController.WasInputKeyJustPressed', Key='F%d' % (k + 1))
        br = g.branch(result(key))
        link(prev, ex(br))
        psn = g.place(g.e.add_get_member_variable_node('PlayerState', '/Script/Engine.Controller'))
        pc_, ps = g.cast(pin(psn, 'PlayerState', True), PS, u.PlayerState)
        sel = g.set('SelectedWizardType', 'NewEnumerator%d' % k, PS, ps)
        pawn = result(g.call('/Script/Engine.Controller.K2_GetPawn'))
        cc, w = g.cast(pawn, CH, u.Pawn)
        sync = g.call(cp(CH) + '.SyncWizardTypeFromPlayerState', self=w)
        full = g.set('Health', g.get('MaxHealth', CH, w), CH, w)
        chain(pin(br, 'then', True), pc_, sel, cc, sync, full)
        prev = pin(br, 'else', True)
    layout(g)
    compile_bp(PC, False)
    g = Graph(PC, 'PracticeControls')
    if not any('PracticeWizardKeys' in str(n.get_node_title()).replace(' ', '') for n in g.e.list_all_nodes()):
        first = list(g.entry().list_connected_pins())
        g.entry().break_pin_links()
        call = g.fn('PracticeWizardKeys')
        link(g.entry(), ex(call))
        for q in first:
            link(then(call), q)
    layout(g)
    compile_bp(PC, True)
    log('practice F1-F4 keys', RPT)


def practice_hint():
    g = Graph(OVERLAY, 'EventGraph') if False else None
    b = load(OVERLAY)
    done = 0
    for gn in L.list_graph_names(b):
        ge = E.get_graph_editor_by_name(b, str(gn))
        if not ge:
            continue
        for n in ge.list_all_nodes():
            p = n.find_input_pin('InText')
            if p.is_valid() and 'PRACTICE / G: SUPER' in str(p.get_pin_value()):
                value(p, 'NSLOCTEXT("", "R11PracticeHint", "PRACTICE / G: SUPER / F1-F4: WIZARD")')
                done += 1
    assert done >= 1, 'practice hint not found'
    compile_bp(OVERLAY, True)
    log('practice hint updated (%d)' % done, RPT)


def main():
    try:
        for p in [CH, PC, OVERLAY]:
            backup(p)
        wind_traits()
        own_traits()
        practice_keys()
        practice_hint()
        REPORT['passed'] = True
        log('done', RPT)
        print('R11_TRAITS_DONE')
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        (OUT / RPT).write_text(json.dumps(REPORT, indent=1, default=str), encoding='utf-8')
        u.log_error(traceback.format_exc())


main()
