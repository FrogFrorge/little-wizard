"""Round 15: does the language option work in the game?

1. options screen: the language buttons' OnClicked (broadcast, as a click does) step the
   controller's Language by exactly one (Up, Down) and the screen's texts follow
2. the choice is saved: Language is read back by LoadWizardSettings from the save slot
3. in the arena, Chinese chosen: the ultimate cut-in is the Chinese card (HighResShot)
At the end the language is set back to English and saved (the player's own settings file).

UnrealEditor <uproject> -RenderOffscreen -ExecCmds="py r15_lang_test.py"
"""
import json
import time
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'round15'
SHOTS = OUT / 'test'
SHOTS.mkdir(parents=True, exist_ok=True)
RES = OUT / 'r15-lang-test.json'
ls = u.get_editor_subsystem(u.LevelEditorSubsystem)
sysobj = u.get_default_object(u.SystemLibrary)
ctx = dict(stage='wait', at=time.monotonic(), start=time.monotonic(), log=[], checks={}, f=0)


def note(s):
    ctx['log'].append('%.1f %s' % (time.monotonic() - ctx['start'], s))
    RES.write_text(json.dumps({'log': ctx['log'], 'checks': ctx['checks']}, indent=1, ensure_ascii=False), encoding='utf-8')


def finish():
    note('finish')
    try:
        u.unregister_slate_post_tick_callback(ctx['handle'])
    except Exception:
        pass
    ls.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def lang(pc):
    return int(pc.get_editor_property('Language'))


def widget_text(wd, name):
    try:
        return str(wd.get_editor_property(name).get_text())
    except Exception as e:
        return 'ERR %s' % e


def tick(dt):
    try:
        ws = u.EditorLevelLibrary.get_pie_worlds(True)
        if not ws:
            return
        w = ws[0]
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc:
            return
        el = time.monotonic() - ctx['at']
        st = ctx['stage']
        if st == 'wait':
            if el > 5:
                sysobj.call_method('SetIntPropertyByName', (pc, 'Language', 0))
                pc.call_method('ShowOptions')
                ctx.update(stage='options', at=time.monotonic())
            return
        if st == 'options':
            if el > 1.0:
                wd = pc.get_editor_property('MenuWidget')
                up, down = wd.get_editor_property('LanguageUpButton'), wd.get_editor_property('LanguageDownButton')
                l0 = lang(pc)
                up.on_clicked.broadcast()
                l1 = lang(pc)
                ctx['checks']['one click Up: 0 -> 1'] = (l0, l1, l1 == 1)
                down.on_clicked.broadcast()
                l2 = lang(pc)
                ctx['checks']['one click Down: 1 -> 0'] = (l1, l2, l2 == 0)
                for _ in range(2):
                    up.on_clicked.broadcast()
                ctx['checks']['two clicks Up: 0 -> 2 (Japanese)'] = lang(pc) == 2
                ctx['wd'] = wd
                ctx.update(stage='options_text', at=time.monotonic())
            return
        if st == 'options_text':
            if el > 0.5:
                wd = ctx['wd']
                t = widget_text(wd, 'Title')
                v = widget_text(wd, 'LanguageValue')
                ctx['checks']['options screen now Japanese'] = (t, v, t == 'オプション' and v == '日本語')
                # round 16: the font follows the language, and comes back for English
                # (round 17: English / French in Tinos; every text block, runtime-set ones too)
                def font_of(name):
                    fo = wd.get_editor_property(name).get_editor_property('font').get_editor_property('font_object')
                    return fo.get_name() if fo else None
                def fonts():
                    return tuple(font_of(n) for n in ('Title', 'LanguageValue'))
                ja_font = fonts()
                up, down = wd.get_editor_property('LanguageUpButton'), wd.get_editor_property('LanguageDownButton')
                down.on_clicked.broadcast()
                zh_font = fonts()
                down.on_clicked.broadcast()
                en_font = fonts()
                want = (('F_Wizard_JA',) * 2, ('F_Wizard_ZH',) * 2, ('F_Wizard_Latin',) * 2)
                ctx['checks']['fonts JA -> ZH -> EN (Title, LanguageValue)'] = (ja_font, zh_font, en_font,
                                                                               (ja_font, zh_font, en_font) == want)
                for _ in range(2):
                    up.on_clicked.broadcast()
                # saved?  forget it in memory, load from the slot
                sysobj.call_method('SetIntPropertyByName', (pc, 'Language', 0))
                pc.call_method('LoadWizardSettings')
                ctx['checks']['saved and loaded back (2)'] = lang(pc) == 2
                # Chinese for the arena test
                sysobj.call_method('SetIntPropertyByName', (pc, 'Language', 1))
                pc.call_method('SaveWizardSettings')
                pc.call_method('CloseWizardMenu')
                sysobj.call_method('K2_SetTimer', (pc, 'ExploreGeometric', .1, False, 0, 0))
                ctx.update(stage='enter', at=time.monotonic())
                note('options checks done; entering the arena')
            return
        if st == 'enter':
            if el > 8:
                pawn = u.GameplayStatics.get_player_pawn(w, 0)
                ctx['checks']['language kept after travel (1)'] = lang(pc) == 1
                u.SystemLibrary.execute_console_command(w, 'r.AntiAliasingMethod 1')
                pawn.call_method('PlayWizardAction', (4,))        # Blaise's ultimate wind-up
                ctx.update(stage='cutin', at=time.monotonic(), f=0)
            return
        if st == 'cutin':
            ctx['f'] += 1
            if ctx['f'] in (12, 24):
                p = SHOTS / ('cutin_zh_%02d.png' % ctx['f'])
                u.SystemLibrary.execute_console_command(w, 'HighResShot 1280x720 filename=%s' % p.as_posix())
            if ctx['f'] == 30:
                hud = pc.get_hud()
                try:
                    tex = hud.get_editor_property('CutInTex')
                    ctx['checks']['HUD card is the Chinese one'] = (tex.get_name() if tex else None,
                                                                     bool(tex) and tex.get_name().endswith('_ZH'))
                except Exception as e:
                    ctx['checks']['HUD card'] = 'ERR %s' % e
            if ctx['f'] == 60:
                # back to English for the player, saved
                sysobj.call_method('SetIntPropertyByName', (pc, 'Language', 0))
                pc.call_method('SaveWizardSettings')
                pc.call_method('LoadWizardSettings')
                ctx['checks']['restored to English and saved'] = lang(pc) == 0
                ctx.update(stage='end', at=time.monotonic())
            return
        if st == 'end' and el > 1:
            finish()
    except Exception:
        import traceback
        note('ERROR ' + traceback.format_exc())
        finish()


try:
    ctx['handle'] = u.register_slate_post_tick_callback(tick)
    ls.editor_request_begin_play()
    note('begin play requested')
except Exception:
    import traceback
    note('ERROR ' + traceback.format_exc())
    u.SystemLibrary.quit_editor()
