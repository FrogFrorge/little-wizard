"""Round 14: the menu screens made bright, in the style of the user's illustration.

The player found the menus dim (a later polish had turned them all navy).  Now:
- cream paper backdrop with soft element glows (T_UI_Backdrop), white cards with warm
  outlines, gold primary buttons, white secondary buttons, dark plum text
- main menu: the title on the left, the four wizards from the illustration on the right
- wizard select: each card shows the wizard's illustration on a glow in their colour,
  the English name, the Chinese name and title, traits and the CURRENT ultimate (the old
  cards still described the pre-round-11 ultimates)
- result: a big portrait (which wizard: set by r14_wire.py's RefreshView change)
- the other menu screens (mode, maps, options, map reference, practice) the same theme
Widget trees are edited through their live objects (find_object(WidgetTree, name)).

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r14_ui.py
"""
import json
import shutil
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'round14'
BACKUP = ROOT / 'round14-before-assets'
FLOW = '/Game/UI/Flow/'
ART = '/Game/UI/Art/'
PORTRAIT = '/Game/UI/Portraits/T_Wizard_'
SCREENS = ['WBP_WizardMain', 'WBP_WizardMode', 'WBP_MapSelect', 'WBP_WizardSelect', 'WBP_WizardResult',
           'WBP_WizardOptions', 'WBP_MapReference', 'WBP_PracticeMenu']
SYS = u.get_default_object(u.SystemLibrary)
EAL = u.EditorAssetLibrary
L = u.BlueprintEditorLibrary
REPORT = {'steps': []}

# ---- the palette (sRGB 0..255, alpha 0..1)
INK = (43, 33, 64)
TEXT = (70, 60, 92)
MUTED = (122, 110, 140)
GOLD_T = (176, 112, 26)
RULE = (226, 210, 186)
PANEL = (255, 255, 255, 0.92)
PANEL_LINE = (234, 222, 204)
PRIMARY, PRIMARY_H, PRIMARY_P, PRIMARY_LABEL = (255, 181, 71), (255, 202, 112), (238, 148, 38), (74, 42, 8)
SEC, SEC_LINE, SEC_H, SEC_H_LINE, SEC_P = (255, 255, 255, 0.96), (214, 200, 234), (247, 242, 255), (176, 154, 222), (234, 226, 250)
# element: strong, pastel, dark (text)
EL = {'Fire': ((242, 100, 58), (255, 230, 218), (190, 66, 30)), 'Ice': ((78, 155, 234), (222, 236, 255), (42, 108, 190)),
      'Wind': ((63, 180, 124), (220, 246, 232), (30, 128, 84)), 'Lightning': ((154, 107, 232), (238, 230, 255), (112, 68, 196))}
WIZ = {'Fire': ('Blaise', 'BLAISE', 'The Blazing Mage', '+10% max health.\nUltimates come more often when hurt.',
                'ULTIMATE · BLAZE CANNON', 'One giant orb blasts straight ahead.'),
       'Ice': ('Neve', 'NEVE', 'Heart of Deep Frost', 'Enemy shots slow down near her.\nHold jump to hover in midair.',
               'ULTIMATE · FROST RING', 'Charge, then burst a ring of orbs.'),
       'Wind': ('Gale', 'GALE', 'The Fleeting Shadow', '+15% move speed and shot speed.',
                'ULTIMATE · SHADOW DASH', 'Turn into an orb and dash through foes.'),
       'Lightning': ('Volta', 'VOLTA', 'Rondo of Currents', 'Blinks to reposition (30 s).\nCanceling enemy shots deals damage.',
                     'ULTIMATE · SKY STORM', 'Call a storm down onto your aim.')}
PRIMARY_BUTTONS = ('PlayButton', 'ContinueButton', 'RestartButton')


def log(s):
    print('R14 ' + s)
    REPORT['steps'].append(s)
    (OUT / 'r14-ui.json').write_text(json.dumps(REPORT, indent=1, ensure_ascii=False), encoding='utf-8')


def backup(path):
    src = Path(u.Paths.project_content_dir()).resolve() / (path.removeprefix('/Game/') + '.uasset')
    dst = BACKUP / src.relative_to(Path(u.Paths.project_content_dir()).resolve())
    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


# ---------------------------------------------------------------- brushes / colours
def lin(c):
    def ch(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return u.LinearColor(ch(c[0]), ch(c[1]), ch(c[2]), c[3] if len(c) > 3 else 1.0)


def sc(c):
    return u.SlateColor(specified_color=lin(c))


def mixc(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def rbox(fill, r=18, outline=None, width=0.0):
    return u.SlateBrush(tint_color=sc(fill), draw_as=u.SlateBrushDrawType.ROUNDED_BOX,
                        outline_settings=u.SlateBrushOutlineSettings(corner_radii=u.Vector4(r, r, r, r), color=sc(outline or fill),
                                                                     width=float(width), rounding_type=u.SlateBrushRoundingType.FIXED_RADIUS))


def use_texture(w, path):
    """Show a texture on an Image or Border (ImageSize is a DeprecateSlateVector2D, which
    Python cannot build, so the widget's own SetBrushFromTexture fills the brush in)."""
    tex = u.load_asset(path)
    assert tex, path
    if isinstance(w, u.Image):
        w.set_brush_from_texture(tex, True)
        b = w.get_editor_property('brush')
    else:
        w.set_brush_from_texture(tex)
        b = w.get_editor_property('background')
    b.set_editor_property('draw_as', u.SlateBrushDrawType.IMAGE)
    b.set_editor_property('tint_color', sc((255, 255, 255)))
    w.set_brush(b)


# ---------------------------------------------------------------- widgets
def widgets(bp):
    t = u.find_object(bp, 'WidgetTree')
    root = u.find_object(t, 'RootCanvas')
    out = []

    def walk(w):
        out.append(w)
        if isinstance(w, u.PanelWidget):
            for c in w.get_all_children():
                walk(c)
        elif isinstance(w, u.ContentWidget) and w.get_content():
            walk(w.get_content())
    walk(root)
    return t, {w.get_name(): w for w in out}


def add(t, klass, name, parent, variable=False):
    o = u.find_object(t, name)
    if o is None:
        o = u.new_object(klass, t, name)
        parent.add_child(o)
    if variable:
        SYS.call_method('SetBoolPropertyByName', (o, 'bIsVariable', True))
    return o


def at(w, x, y, wd, ht, z=None):
    s = w.slot
    s.set_position(u.Vector2D(x, y))
    s.set_size(u.Vector2D(wd, ht))
    if z is not None:
        s.set_z_order(z)


def text(w, color=None, size=None, bold=None, center=None, value=None, shadow=None):
    if value is not None:
        w.set_text(value)
    if color is not None:
        w.set_color_and_opacity(sc(color))
    if size is not None or bold is not None:
        f = w.get_editor_property('font')
        if size is not None:
            f.set_editor_property('size', size)
        if bold is not None:
            f.set_editor_property('typeface_font_name', 'Bold' if bold else 'Regular')
        w.set_font(f)
    if center is not None:
        w.set_editor_property('justification', u.TextJustify.CENTER if center else u.TextJustify.LEFT)
    if shadow is not None:
        off, col = shadow
        w.set_shadow_offset(u.Vector2D(*off))
        w.set_shadow_color_and_opacity(lin(col))


def style(b, normal, hovered, pressed, disabled=None):
    st = b.get_editor_property('widget_style')
    st.set_editor_property('normal', normal)
    st.set_editor_property('hovered', hovered)
    st.set_editor_property('pressed', pressed)
    st.set_editor_property('disabled', disabled or rbox((235, 230, 240, 0.8), 18))
    b.set_style(st)


def primary(b, r=22):
    style(b, rbox(PRIMARY, r, (226, 140, 36), 2), rbox(PRIMARY_H, r, (238, 160, 52), 3), rbox(PRIMARY_P, r, (200, 118, 20), 3))


def secondary(b, r=18):
    style(b, rbox(SEC, r, SEC_LINE, 2), rbox(SEC_H, r, SEC_H_LINE, 3), rbox(SEC_P, r, SEC_H_LINE, 3))


def card(b, line=PANEL_LINE, hover_line=(255, 181, 71), tint=(255, 247, 236), r=26):
    style(b, rbox((255, 255, 255, 0.94), r, line, 3), rbox(tint, r, hover_line, 5), rbox(mixc(tint, (220, 200, 170), 0.15), r, hover_line, 5))


def label_in(b, lookup, size=24, bold=True, color=INK):
    """The label of a button: centred vertically in the button."""
    lab = lookup.get(b.get_name() + 'Label')
    if lab is None:
        return
    sz = b.slot.get_size()
    h = size * 2.0
    at(lab, 0, (sz.y - h) / 2 + 1, sz.x, h)
    text(lab, color, size, bold, True)


# ---------------------------------------------------------------- the common theme
MUTED_PARTS = ('Hint', 'Desc', 'Rules', 'HostNote', 'Stats', 'Footer')
TEXT_PARTS = ('Sub', 'Detail', 'Traits', 'InfoText')


def theme(name, t, lookup):
    for wn, w in lookup.items():
        if wn == 'Backdrop':
            use_texture(w, ART + 'T_UI_Backdrop')
            continue
        if isinstance(w, u.Border):
            if wn.startswith('Bubble'):
                continue
            if 'Rule' in wn:
                w.set_brush(rbox(RULE, 1))
            else:
                w.set_brush(rbox(PANEL, 18, PANEL_LINE, 2))
        elif isinstance(w, u.Button):
            if wn in PRIMARY_BUTTONS:
                primary(w)
                label_in(w, lookup, 26, True, PRIMARY_LABEL)
            elif any(k in wn for k in ('VolumeDown', 'VolumeUp', 'SensitivityDown', 'SensitivityUp')):
                secondary(w, 14)
                label_in(w, lookup, 26, True, INK)
            elif lookup.get(wn.replace('Button', '') + 'Preview') or wn in ('RandomButton', 'LastStandButton', 'TimedButton'):
                card(w)
            elif name != 'WBP_WizardSelect' or wn == 'BackButton':
                secondary(w)
                label_in(w, lookup, 22, True, INK)
        elif isinstance(w, u.TextBlock):
            if wn == 'Brand':
                text(w, GOLD_T, 17, True)
            elif wn in ('Title',):
                text(w, INK, None, True)
            elif wn.endswith('Value'):
                text(w, GOLD_T, 30, True)
            elif wn.endswith('Label') or wn.endswith('Name') or wn.endswith('Title') or wn.endswith('Icon'):
                text(w, INK, None, True)
            elif any(k in wn for k in MUTED_PARTS):
                text(w, MUTED)
            elif any(k in wn for k in TEXT_PARTS):
                text(w, TEXT)
            else:
                text(w, INK)


# ---------------------------------------------------------------- per screen
def main_menu(t, lk):
    c = lk['ContentCanvas']
    text(lk['Eyebrow'], GOLD_T, 20, True, False, 'FOUR ELEMENTS · ONE ARENA')
    at(lk['Eyebrow'], 112, 168, 760, 40)
    text(lk['Title'], INK, 100, True, False, 'LITTLE\nWIZARD', ((0, 6), (255, 196, 110, 0.95)))
    lk['Title'].set_editor_property('line_height_percentage', 0.82)
    at(lk['Title'], 100, 204, 860, 270)
    sub = add(t, u.TextBlock, 'Subtitle', c)
    # round 15: no Chinese under the English title (each language is complete on its own;
    # r15_lang.py translates the title itself)
    text(sub, (222, 98, 46), 40, True, False, '')
    sub.set_visibility(u.SlateVisibility.COLLAPSED)
    at(sub, 112, 478, 720, 64)
    for b, y, h, size in (('PlayButton', 576, 92, 30), ('OptionsButton', 686, 72, 24), ('MapReferenceButton', 770, 72, 24),
                          ('QuitButton', 854, 72, 24)):
        at(lk[b], 110, y, 520, h)
        label_in(lk[b], lk, size, True, PRIMARY_LABEL if b == 'PlayButton' else INK)
    for el in EL:
        lk['Wizard' + el].set_visibility(u.SlateVisibility.COLLAPSED)
    art = add(t, u.Image, 'MainLineup', c)
    use_texture(art, ART + 'T_UI_MainLineup')
    art.set_visibility(u.SlateVisibility.HIT_TEST_INVISIBLE)
    at(art, 700, 318, 1180, 642, -1)
    text(lk['Footer'], MUTED, 18, False, True, 'ELEMENTAL DUELS')


def select_screen(t, lk):
    text(lk['Title'], INK, 54, True, True, 'CHOOSE YOUR WIZARD')
    at(lk['Title'], 180, 126, 1560, 90)
    text(lk['Hint'], MUTED, 22, False, True, 'Pick a wizard for this duel. Every wizard can cast all four magics (keys 1-4).')
    at(lk['Hint'], 180, 214, 1560, 44)
    for i, el in enumerate(EL):
        strong, pastel, dark = EL[el]
        key, name, sub, traits, ult, desc = WIZ[el]
        b = lk[el + 'Button']
        at(b, 160 + i * 405, 268, 385, 714)
        style(b, rbox((255, 255, 255, 0.95), 26, mixc(strong, (255, 255, 255), 0.45), 3),
              rbox(pastel, 26, strong, 5), rbox(mixc(pastel, strong, 0.18), 26, dark, 5))
        cv = lk[el + 'Card']
        glow = add(t, u.Image, el + 'Glow', cv)
        use_texture(glow, ART + 'T_UI_CardGlow_' + el)
        glow.set_visibility(u.SlateVisibility.HIT_TEST_INVISIBLE)
        at(glow, 12, 12, 361, 400, -1)
        lk[el + 'Badge'].set_brush(rbox(pastel, 17, strong, 2))
        at(lk[el + 'Badge'], 18, 18, 140, 34, 1)
        text(lk[el + 'Element'], dark, 14, True, True)
        at(lk[el + 'Element'], 18, 23, 140, 26, 2)
        p = lk[el + 'Portrait']
        use_texture(p, PORTRAIT + key)
        at(p, 62, 18, 260, 410, 0)
        text(lk[el + 'Name'], INK, 32, True, True, name)
        at(lk[el + 'Name'], 20, 432, 345, 46)
        st = add(t, u.TextBlock, el + 'Subtitle', cv)
        st.set_visibility(u.SlateVisibility.HIT_TEST_INVISIBLE)
        text(st, dark, 18, True, True, sub)
        at(st, 20, 476, 345, 30)
        text(lk[el + 'Traits'], TEXT, 16, False, True, traits)
        at(lk[el + 'Traits'], 18, 516, 349, 72)
        text(lk[el + 'UltimateTitle'], dark, 16, True, True, ult)
        at(lk[el + 'UltimateTitle'], 20, 596, 345, 28)
        text(lk[el + 'UltimateDesc'], MUTED, 15, False, True, desc)
        at(lk[el + 'UltimateDesc'], 18, 622, 349, 48)
        text(lk[el + 'Action'], INK, 15, True, True, 'SELECT  >')
        at(lk[el + 'Action'], 20, 676, 345, 30)
    secondary(lk['BackButton'])
    at(lk['BackButton'], 80, 1004, 210, 56)
    label_in(lk['BackButton'], lk, 22, True, INK)


def mode_screen(t, lk):
    for b, el in (('LastStandButton', 'Fire'), ('TimedButton', 'Ice')):
        strong, pastel, dark = EL[el]
        card(lk[b])
        lk[b + 'Stamp'].set_brush(rbox(pastel, 62, strong, 3))
        at(lk[b + 'Stamp'], 220, 18, 124, 124)
        text(lk[b + 'Icon'], dark, 34 if b == 'LastStandButton' else 28, True, True)
        at(lk[b + 'Icon'], 205, 50, 155, 60)
        text(lk[b + 'Title'], INK, 35, True, True)
        at(lk[b + 'Title'], 25, 160, 515, 55)
        text(lk[b + 'Sub'], TEXT, 23, False, True)
        text(lk[b + 'Rules'], MUTED, 21, False, True)


def map_screen(t, lk):
    for wn, w in lk.items():
        if wn.endswith('Name') and isinstance(w, u.TextBlock):
            text(w, INK, 23, True)
        if wn.endswith('Desc') and isinstance(w, u.TextBlock):
            text(w, MUTED, 16, False)
    if 'RandomButtonLabel' in lk:
        text(lk['RandomButtonLabel'], INK, 30, True, True)
        at(lk['RandomButtonLabel'], 10, 110, 510, 60)
    if 'Info' in lk:
        lk['Info'].set_brush(rbox(PANEL, 18, PANEL_LINE, 3))
        text(lk['InfoTitle'], GOLD_T, 24, True)
        text(lk['InfoText'], TEXT, 21, False)


def result_screen(t, lk):
    c = lk['ContentCanvas']
    lk['ResultCard'].set_brush(rbox((255, 255, 255, 0.94), 40, PANEL_LINE, 3))
    at(lk['ResultCard'], 700, 170, 1040, 760)
    por = add(t, u.Image, 'ResultPortrait', c, variable=True)
    use_texture(por, PORTRAIT + 'Blaise')
    por.set_visibility(u.SlateVisibility.HIT_TEST_INVISIBLE)
    at(por, 170, 140, 540, 852, 2)
    text(lk['ResultKicker'], GOLD_T, 20, True, True, 'MATCH RESULT')
    at(lk['ResultKicker'], 740, 222, 960, 40)
    text(lk['ResultTitle'], INK, 86, True, True)
    at(lk['ResultTitle'], 720, 270, 1000, 130)
    text(lk['ResultDetail'], TEXT, 26, False, True)
    at(lk['ResultDetail'], 760, 412, 920, 84)
    text(lk['ResultStats'], MUTED, 24, False, True)
    at(lk['ResultStats'], 760, 502, 920, 44)
    at(lk['RestartButton'], 940, 588, 560, 92)
    label_in(lk['RestartButton'], lk, 30, True, PRIMARY_LABEL)
    text(lk['HostNote'], MUTED, 19, False, True)
    at(lk['HostNote'], 760, 698, 920, 40)
    at(lk['QuitButton'], 1040, 782, 360, 66)
    label_in(lk['QuitButton'], lk, 22, True, INK)


PER = {'WBP_WizardMain': main_menu, 'WBP_WizardSelect': select_screen, 'WBP_WizardMode': mode_screen,
       'WBP_MapSelect': map_screen, 'WBP_MapReference': map_screen, 'WBP_WizardResult': result_screen}


def map_previews():
    """r14_map_previews.py: the arena pictures on light paper, over the old navy ones."""
    src = sorted((OUT / 'map_previews').glob('T_Map_*.png'))
    keep = Path(u.Paths.project_dir()).resolve() / 'SourceArt' / 'R14'
    keep.mkdir(parents=True, exist_ok=True)
    tasks = []
    for f in src:
        backup(FLOW + 'Previews/' + f.stem)
        shutil.copy2(f, keep / f.name)
        t = u.AssetImportTask()
        t.filename = str(keep / f.name)
        t.destination_path = FLOW + 'Previews'
        t.destination_name = f.stem
        t.automated = True
        t.replace_existing = True
        t.save = True
        tasks.append(t)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    log('map previews: %d replaced' % len(src))


def run():
    try:
        map_previews()
        for n in SCREENS:
            backup(FLOW + n)
        log('backed up the screens to %s' % BACKUP)
        for n in SCREENS:
            bp = u.load_asset(FLOW + n)
            t, lk = widgets(bp)
            theme(n, t, lk)
            if n in PER:
                PER[n](t, lk)
            assert L.compile_blueprint(bp), n
            assert EAL.save_loaded_asset(bp, False), n
            log('%s: %d widgets restyled' % (n, len(lk)))
        REPORT['passed'] = True
        log('done')
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        (OUT / 'r14-ui.json').write_text(json.dumps(REPORT, indent=1, ensure_ascii=False), encoding='utf-8')
        u.log_error(traceback.format_exc())


if __name__ == '__main__':
    run()
