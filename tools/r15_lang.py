"""Round 15: the language option (English / 繁體中文 / 日本語 / Français).

Each language is complete on its own (round 14 had mixed Chinese into the English menus).

How it works
- BP_ThirdPersonPlayerController.Language (0 EN, 1 ZH, 2 JA, 3 FR), saved with the other
  options (SG_WizardSettings.Language); LanguageUp / LanguageDown cycle it and save.
- BFL_WizardText.Pick(Lang, EN, ZH, JA, FR) / PickS (strings): the text of a language.
- every screen (the 8 menus, the in-game overlay, the player HUD):
    ApplyLanguage  - AppliedLanguage = the owning player's Language; every text block set
                     from r15_texts.TEXTS through Pick
    CheckLanguage  - on Tick: if the player's Language changed, ApplyLanguage again (so
                     the options screen and the in-game HUD follow a change at once)
    Event Construct -> ApplyLanguage
  and the texts their own graphs set at runtime (results, the status line, spell states,
  the blink countdown) come from Pick / PickS with AppliedLanguage (r15_texts.RUNTIME).
- the options screen gets a LANGUAGE row  < English >  (the rows are re-spaced to fit 6).
- the main menu: the title itself is translated; the Chinese line under it is gone.
- BP_WizardMatchHUD.StartUltCutIn picks the cut-in card of the player's language
  (T_UltCutIn_<Key> English, _ZH, _JA, _FR; r15_cutin_art.py).

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r15_lang.py   env R15_STAGE=assets | graphs
"""
import json
import re
import os
import shutil
import sys
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import r11_bp as BP  # noqa: E402
from r11_bp import Graph, pin, link, then, ex, result, value, chain, fresh, declare, load, cp, I  # noqa: E402
import r14_ui as UI  # noqa: E402
from r15_texts import TEXTS, RUNTIME, LANGS  # noqa: E402

OUT = ROOT / 'output' / 'round15'
OUT.mkdir(parents=True, exist_ok=True)
BACKUP = ROOT / 'round15-before-assets'
STAGE = os.environ.get('R15_STAGE', 'assets')
RPT = OUT / ('r15-lang-%s.json' % STAGE)
REPORT = {'steps': []}
EAL = u.EditorAssetLibrary
L = u.BlueprintEditorLibrary
SYS = u.get_default_object(u.SystemLibrary)
at = u.AssetToolsHelpers.get_asset_tools()

PC = BP.PC
SG = '/Game/UI/Settings/SG_WizardSettings'
HUD = '/Game/BluePrint/Gamemode/BP_WizardMatchHUD'
BFL = '/Game/UI/Localization/BFL_WizardText'
FLOW = '/Game/UI/Flow/'
WIDGETS = {n: FLOW + n for n in ('WBP_WizardMain', 'WBP_WizardMode', 'WBP_MapSelect', 'WBP_WizardSelect', 'WBP_WizardResult',
                                 'WBP_WizardOptions', 'WBP_MapReference', 'WBP_PracticeMenu', 'WBP_WizardOverlay')}
WIDGETS['WBP_PlayerHUD'] = '/Game/UI/WBP_PlayerHUD'
KEYS = ['Blaise', 'Neve', 'Gale', 'Volta']
T = BP.typ('text')
S = BP.typ('string')


def log(s):
    print('R15 ' + str(s))
    REPORT['steps'].append(str(s))
    RPT.write_text(json.dumps(REPORT, indent=1, ensure_ascii=False), encoding='utf-8')


def backup(path):
    src = Path(u.Paths.project_content_dir()).resolve() / (path.removeprefix('/Game/') + '.uasset')
    dst = BACKUP / src.relative_to(Path(u.Paths.project_content_dir()).resolve())
    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def tree_widgets(bp):
    """Every widget of a widget blueprint's designer tree, by name (any root)."""
    prefix = bp.get_path_name() + ':WidgetTree.'
    return {w.get_name(): w for w in u.ObjectIterator(u.Widget) if w.get_path_name().startswith(prefix)}


def make_variable(w):
    SYS.call_method('SetBoolPropertyByName', (w, 'bIsVariable', True))


def title(n):
    return str(n.get_node_title()).split('\n')[0].strip()


# ================================================================== stage 1: assets
def make_bfl():
    if not EAL.does_asset_exist(BFL):
        if hasattr(u, 'BlueprintFunctionLibraryFactory'):
            f = u.BlueprintFunctionLibraryFactory()
        else:
            f = u.BlueprintFactory()
            f.set_editor_property('parent_class', u.BlueprintFunctionLibrary)
            f.set_editor_property('blueprint_type', u.BlueprintType.BPTYPE_FUNCTION_LIBRARY)
        b = at.create_asset('BFL_WizardText', BFL.rsplit('/', 1)[0], u.Blueprint, f)
        assert b, BFL
        BP.ASSETS[BFL] = b
    for name, ty in (('Pick', T), ('PickS', S)):
        g = fresh(BFL, name, [('Lang', I), ('EN', ty), ('ZH', ty), ('JA', ty), ('FR', ty)], [('Out', ty)], pure=True)
        sw = g.switch_int(g.inp('Lang'), [1, 2, 3])
        link(g.entry(), sw['in'])
        r0 = [n for n in g.e.list_all_nodes() if n.get_class().get_name() == 'K2Node_FunctionResult'][0]
        link(sw['default'], ex(r0))
        value(pin(r0, 'Out'), g.inp('EN'))
        for case, lang in ((1, 'ZH'), (2, 'JA'), (3, 'FR')):
            r = g.place(g.e.add_return_node())
            link(sw[case], ex(r))
            value(pin(r, 'Out'), g.inp(lang))
        BP.layout(g)
    BP.compile_bp(BFL, True)
    log('BFL_WizardText: Pick (text) and PickS (string)')


def settings_language():
    declare(SG, 'Language', I, '0')
    BP.compile_bp(SG, True)
    declare(PC, 'Language', I, '0')
    BP.compile_bp(PC, False)
    for name, step in (('LanguageUp', 1), ('LanguageDown', 3)):
        g = fresh(PC, name)
        v = g.math('Percent_IntInt', A=g.math('Add_IntInt', A=g.get('Language'), B=step), B=4)
        chain(g.entry(), g.set('Language', v), g.fn('SaveWizardSettings'))
        BP.layout(g)
    # save: SettingsRef.Language = Language, just before SaveGameToSlot
    g = Graph(PC, 'SaveWizardSettings')
    if not any(title(n) == 'Set Language' for n in g.e.list_all_nodes()):
        save = next(n for n in g.e.list_all_nodes() if title(n) == 'SaveGameToSlot')
        src = list(ex(save).list_connected_pins())
        ex(save).break_pin_links()
        s = g.set('Language', g.get('Language'), SG, g.get('SettingsRef'))
        for p in src:
            link(p, ex(s))
        link(then(s), ex(save))
    # load: Language = SettingsRef.Language before both ApplyWizardSettings calls
    g = Graph(PC, 'LoadWizardSettings')
    if not any(title(n) == 'Set Language' for n in g.e.list_all_nodes()):
        for ap in [n for n in g.e.list_all_nodes() if title(n) == 'ApplyWizardSettings']:
            src = list(ex(ap).list_connected_pins())
            ex(ap).break_pin_links()
            s = g.set('Language', g.get('Language', SG, g.get('SettingsRef')))
            for p in src:
                link(p, ex(s))
            link(then(s), ex(ap))
    BP.compile_bp(PC, True)
    log('settings: Language on the controller and in the save game; LanguageUp / LanguageDown')


def options_row(bp, lk):
    """A LANGUAGE row like the volume rows, and the six rows re-spaced."""
    t = u.find_object(bp, 'WidgetTree')
    c = lk['ContentCanvas']
    if 'LanguageRow' not in lk:
        row = UI.add(t, u.Border, 'LanguageRow', c)
        row.set_brush(UI.rbox(UI.PANEL, 18, UI.PANEL_LINE, 2))
        row.set_visibility(u.SlateVisibility.HIT_TEST_INVISIBLE)
        for n in ('LanguageTitle', 'LanguageHint', 'LanguageValue'):
            tb = UI.add(t, u.TextBlock, n, c)
            tb.set_visibility(u.SlateVisibility.HIT_TEST_INVISIBLE)
        style = lk['MasterVolumeUpButton'].get_editor_property('widget_style')
        for side, ch in (('Down', '<'), ('Up', '>')):
            b = UI.add(t, u.Button, 'Language%sButton' % side, c, variable=True)
            b.set_style(style)
            b.set_background_color(u.LinearColor(1, 1, 1, 1))
            cv = UI.add(t, u.CanvasPanel, 'Language%sButtonContent' % side, b)
            lab = UI.add(t, u.TextBlock, 'Language%sButtonLabel' % side, cv)
            lab.set_text(ch)
            lab.set_visibility(u.SlateVisibility.HIT_TEST_INVISIBLE)
        lk = tree_widgets(bp)
    for i, r in enumerate(['MasterVolume', 'MusicVolume', 'EffectsVolume', 'InterfaceVolume', 'MouseSensitivity', 'Language']):
        y = 286 + 104 * i
        UI.at(lk[r + 'Row'], 290, y, 1340, 94)
        UI.at(lk[r + 'Title'], 320, y + 10, 700, 36)
        UI.text(lk[r + 'Title'], UI.INK, 23, True)
        UI.at(lk[r + 'Hint'], 320, y + 50, 700, 30)
        UI.text(lk[r + 'Hint'], UI.MUTED, 17, False)
        UI.at(lk[r + 'DownButton'], 1070, y + 12, 80, 70)
        UI.at(lk[r + 'UpButton'], 1390, y + 12, 80, 70)
        UI.at(lk[r + 'Value'], 1158, y + 20, 224, 54)
        UI.text(lk[r + 'Value'], UI.GOLD_T, 26 if r == 'Language' else 30, True, True)
        for side in ('Down', 'Up'):
            UI.label_in(lk[r + side + 'Button'], lk, 26, True, UI.INK)
    UI.secondary(lk['LanguageDownButton'], 14)
    UI.secondary(lk['LanguageUpButton'], 14)
    return lk


def main_menu_layout(lk):
    lk['Subtitle'].set_text('')
    lk['Subtitle'].set_visibility(u.SlateVisibility.COLLAPSED)
    UI.at(lk['Eyebrow'], 112, 198, 760, 40)
    UI.at(lk['Title'], 100, 234, 860, 290)
    for b, y, h, size in (('PlayButton', 592, 92, 30), ('OptionsButton', 702, 72, 24), ('MapReferenceButton', 786, 72, 24),
                          ('QuitButton', 870, 72, 24)):
        UI.at(lk[b], 110, y, 520, h)
        UI.label_in(lk[b], lk, size, True, UI.PRIMARY_LABEL if b == 'PlayButton' else UI.INK)


def widgets_assets():
    for short, path in WIDGETS.items():
        bp = load(path)
        lk = tree_widgets(bp)
        if short == 'WBP_WizardOptions':
            lk = options_row(bp, lk)
        if short == 'WBP_WizardMain':
            main_menu_layout(lk)
        n = 0
        for name, tx in TEXTS[short].items():
            if name not in lk:
                log('%s: no text block %s' % (short, name))
                continue
            make_variable(lk[name])
            lk[name].set_text(tx[0])               # the designer shows English
            n += 1
        # round 17: every text block is a variable (ApplyLanguage sets its font) and the
        # designer font is the English one, Tinos
        latin = u.load_asset(LATIN_FONT.split('.')[0])
        for w in lk.values():
            if isinstance(w, u.TextBlock):
                make_variable(w)
                fi = w.get_editor_property('font')
                fi.set_editor_property('font_object', latin)
                w.set_font(fi)
        declare(path, 'AppliedLanguage', I, '-1')
        BP.compile_bp(path, True)
        log('%s: %d text blocks made variables (English in the designer)' % (short, n))


def import_cards():
    src = sorted((OUT / 'cutin').glob('T_UltCutIn_*.png'))
    keep = Path(u.Paths.project_dir()).resolve() / 'SourceArt' / 'R15'
    keep.mkdir(parents=True, exist_ok=True)
    tasks = []
    for f in src:
        backup('/Game/UI/UltCutIn/' + f.stem)
        shutil.copy2(f, keep / f.name)
        tk = u.AssetImportTask()
        tk.filename = str(keep / f.name)
        tk.destination_path = '/Game/UI/UltCutIn'
        tk.destination_name = f.stem
        tk.automated = True
        tk.replace_existing = True
        tk.save = True
        tasks.append(tk)
    at.import_asset_tasks(tasks)
    for f in src:
        tex = u.load_asset('/Game/UI/UltCutIn/' + f.stem)
        tex.set_editor_properties({'compression_settings': u.TextureCompressionSettings.TC_EDITOR_ICON,
                                   'lod_group': u.TextureGroup.TEXTUREGROUP_UI,
                                   'mip_gen_settings': u.TextureMipGenSettings.TMGS_NO_MIPMAPS,
                                   'srgb': True, 'never_stream': True})
        EAL.save_loaded_asset(tex, False)
    declare(HUD, 'CutInLanguage', I, '0')
    BP.compile_bp(HUD, True)
    log('cut-in cards: %d imported (English, ZH, JA, FR)' % len(src))


# ================================================================== stage 2: graphs
def pick(g, texts, string=False):
    n = g.call(cp(BFL) + ('.PickS' if string else '.Pick'), Lang=g.get('AppliedLanguage'),
               EN=texts[0], ZH=texts[1], JA=texts[2], FR=texts[3])
    return pin(n, 'Out', True)


def owner_language(g):
    """(cast node, the controller's Language pin): GetOwningPlayer -> cast to our controller."""
    owner = result(g.call('/Script/UMG.Widget.GetOwningPlayer'))
    castn, pcp = g.cast(owner, PC, u.PlayerController)
    return castn, g.get('Language', PC, pcp)


FONT_OBJECT = re.compile(r'FontObject="[^"]*"')
# the fonts per language (r16_fonts.py): round 16 Chinese 楷體 (LXGW WenKai TC) and Japanese
# Noto Sans JP; round 17 Tinos (Times New Roman shapes) for English and French and for the
# Latin letters / digits of the Chinese menus.  Every text block of a screen follows the
# language, also the ones only their graphs fill in (results, stats, countdown, values).
LATIN_FONT = '/Game/UI/Fonts/F_Wizard_Latin.F_Wizard_Latin'
LANG_FONTS = {0: LATIN_FONT, 1: '/Game/UI/Fonts/F_Wizard_ZH.F_Wizard_ZH', 2: '/Game/UI/Fonts/F_Wizard_JA.F_Wizard_JA'}


def font_literals(path, names=None):
    """{text block: {0: Latin, 1: ZH, 2: JA}} as struct text for SetFont pins: the designer's
    size, weight and spacing, only the font object differs.  All text blocks of the screen."""
    lk = tree_widgets(load(path))
    out = {}
    for n, w in sorted(lk.items()):
        if not isinstance(w, u.TextBlock):
            continue
        base = w.get_editor_property('font').export_text()
        out[n] = {li: FONT_OBJECT.sub('FontObject="/Script/Engine.Font\'%s\'"' % font, base) for li, font in LANG_FONTS.items()}
    return out


def build_apply(short, path):
    g = fresh(path, 'ApplyLanguage')
    castn, lang = owner_language(g)
    link(g.entry(), ex(castn))
    s1 = g.set('AppliedLanguage', lang)
    link(pin(castn, 'then', True), ex(s1))
    s0 = g.set('AppliedLanguage', 0)
    link(pin(castn, 'CastFailed', True), ex(s0))
    # the fonts first: one SetFont chain per font (Chinese, Japanese, the designer's for the rest)
    fonts = font_literals(path)
    sw = g.switch_int(g.get('AppliedLanguage'), [1, 2])
    link(then(s1), sw['in'])
    link(then(s0), sw['in'])
    prev = []
    for case, li in ((1, 1), (2, 2), ('default', 0)):
        last = sw[case]
        for name, lits in fonts.items():
            sf = g.call('/Script/UMG.TextBlock.SetFont', self=g.get(name), InFontInfo=lits[li])
            link(last, ex(sf))
            last = then(sf)
        prev.append(last)
    for name, tx in TEXTS[short].items():
        st = g.call('/Script/UMG.TextBlock.SetText', self=g.get(name), InText=pick(g, tx))
        for p in prev:
            link(p, ex(st))
        prev = [then(st)]
    BP.layout(g)
    # CheckLanguage: apply again when the player's Language differs from the applied one
    g = fresh(path, 'CheckLanguage')
    castn, lang = owner_language(g)
    link(g.entry(), ex(castn))
    b1 = g.branch(g.math('NotEqual_IntInt', A=lang, B=g.get('AppliedLanguage')))
    link(pin(castn, 'then', True), ex(b1))
    link(pin(b1, 'then', True), ex(g.fn('ApplyLanguage')))
    b0 = g.branch(g.math('Less_IntInt', A=g.get('AppliedLanguage'), B=0))
    link(pin(castn, 'CastFailed', True), ex(b0))
    link(pin(b0, 'then', True), ex(g.fn('ApplyLanguage')))
    BP.layout(g)


def event_node(g, short_name, menu):
    for n in g.e.list_all_nodes():
        if n.get_class().get_name() == 'K2Node_Event' and title(n) == 'Event ' + short_name:
            return n
    n = g.e.create_node_from_name(menu, u.Vector2D(0, 0), [])
    assert n, menu
    return g.place(n)


def insert_first(ev, call):
    out = pin(ev, 'then', True)
    targets = list(out.list_connected_pins())
    out.break_pin_links()
    link(out, ex(call))
    for tp in targets:
        link(then(call), tp)


def hooks(path):
    g = Graph(path)
    names = [title(n) for n in g.e.list_all_nodes()]
    if 'Apply Language' in names or 'ApplyLanguage' in names:
        return 'already'
    insert_first(event_node(g, 'Construct', 'AddEvent|UserInterface|EventConstruct'), g.fn('ApplyLanguage'))
    insert_first(event_node(g, 'Tick', 'AddEvent|UserInterface|EventTick'), g.fn('CheckLanguage'))
    return 'construct + tick'


def runtime_texts():
    done = {}
    for short, graph, ntitle, pname, en, tx in RUNTIME:
        g = Graph(WIDGETS[short], graph)
        is_text = ntitle.startswith('SetText')
        hits = already = 0
        for n in list(g.e.list_all_nodes()):
            if title(n).replace(' ', '') != ntitle.replace(' ', ''):
                continue
            p = n.find_input_pin(pname)
            if not p.is_valid():
                continue
            if p.list_connected_pins():
                # a re-run: already fed by Pick / PickS
                if any('Pick' in title(q.get_owning_node()) for q in p.list_connected_pins()):
                    already += 1
                continue
            v = str(p.get_pin_value())
            if (is_text and v.endswith('"%s")' % en)) or (not is_text and v == en) or (is_text and v == en):
                link(pick(g, tx, string=not is_text), p)
                hits += 1
        done['%s.%s %r' % (short, graph, en)] = hits + already
    log('runtime texts: ' + json.dumps(done, ensure_ascii=False))
    missing = [k for k, v in done.items() if v == 0]
    assert not missing, missing


def options_handlers():
    path = WIDGETS['WBP_WizardOptions']
    for side in ('Down', 'Up'):
        g = fresh(path, 'HandleLanguage%sButton' % side)
        owner = result(g.call('/Script/UMG.Widget.GetOwningPlayer'))
        castn, pcp = g.cast(owner, PC, u.PlayerController)
        call = g.call(cp(PC) + '.Language' + side, self=pcp)
        chain(g.entry(), castn)
        link(pin(castn, 'then', True), ex(call))
        link(then(call), ex(g.fn('CheckLanguage')))
        BP.layout(g)


def options_bindings():
    path = WIDGETS['WBP_WizardOptions']
    g = Graph(path)
    ev = next(n for n in g.e.list_all_nodes() if n.get_class().get_name() == 'K2Node_Event' and 'Initialized' in title(n).replace(' ', ''))
    # a re-run must not bind the buttons twice (one click would then step two languages)
    if any(n.get_class().get_name() == 'K2Node_VariableGet' and 'LanguageDownButton' in title(n).replace(' ', '') for n in g.e.list_all_nodes()):
        log('options: language buttons already bound')
        return
    end = pin(ev, 'then', True)
    while end.list_connected_pins():
        end = then(end.list_connected_pins()[0].get_owning_node())
    for side in ('Down', 'Up'):
        bind = g.node('Button|Event|BindEventtoOnClicked')
        value(bind.find_self_pin(), g.get('Language%sButton' % side))
        de = g.node('EventDispatchers|CreateEvent')
        link(pin(de, 'OutputDelegate', True), pin(bind, 'Delegate'))
        L.set_create_delegate_function(de, 'HandleLanguage%sButton' % side)
        link(end, ex(bind))
        end = then(bind)


def hud_cutin():
    g = fresh(HUD, 'StartUltCutIn', [('Wizard', I)])
    pcn = g.call('/Script/Engine.HUD.GetOwningPlayerController')
    castn, pcp = g.cast(result(pcn), PC, u.PlayerController)
    link(g.entry(), ex(castn))
    s1 = g.set('CutInLanguage', g.get('Language', PC, pcp))
    link(pin(castn, 'then', True), ex(s1))
    s0 = g.set('CutInLanguage', 0)
    link(pin(castn, 'CastFailed', True), ex(s0))
    swl = g.switch_int(g.get('CutInLanguage'), [0, 1, 2, 3])
    link(then(s1), swl['in'])
    link(then(s0), swl['in'])
    for li, lang in enumerate(LANGS):
        sww = g.switch_int(g.inp('Wizard'), [0, 1, 2, 3])
        link(swl[li], sww['in'])
        if li == 0:
            link(swl['default'], sww['in'])
        suf = '' if lang == 'EN' else '_' + lang
        for d, key in enumerate(KEYS):
            s = g.set('CutInTex', '/Game/UI/UltCutIn/T_UltCutIn_%s%s.T_UltCutIn_%s%s' % (key, suf, key, suf))
            link(sww[d], ex(s))
            link(then(s), ex(g.set('CutInStart', g.now())))
    BP.layout(g)
    log('HUD: StartUltCutIn picks the card of the player\'s language')


def run():
    try:
        for p in list(WIDGETS.values()) + [PC, SG, HUD]:
            backup(p)
        if STAGE == 'assets':
            make_bfl()
            settings_language()
            widgets_assets()
            import_cards()
        else:
            for short, path in WIDGETS.items():
                build_apply(short, path)
                log('%s: ApplyLanguage (%d texts) + CheckLanguage, hooks: %s' % (short, len(TEXTS[short]), hooks(path)))
            runtime_texts()
            options_handlers()
            hud_cutin()
            for path in WIDGETS.values():
                BP.compile_bp(path, False)
            options_bindings()
            for path in list(WIDGETS.values()) + [HUD]:
                BP.compile_bp(path, True)
            log('compiled + saved %d widgets and the HUD' % len(WIDGETS))
        REPORT['passed'] = True
        log('done')
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        RPT.write_text(json.dumps(REPORT, indent=1, ensure_ascii=False), encoding='utf-8')
        u.log_error(traceback.format_exc())


run()
