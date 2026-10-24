"""Round 16: the Chinese (霞鶩文楷 TC, a 楷體) and Japanese (Noto Sans JP) fonts in Unreal.

Full editor (importing a font file needs Slate; the commandlet asserts):
UnrealEditor <uproject> -RenderOffscreen -ExecCmds="py r16_fonts.py"

- the four font files (r16_fonts_prepare.py) -> font faces /Game/UI/Fonts/FF_*
  (sources and the OFL licence texts kept in the project: SourceArt/Fonts)
- two composite fonts, Latin from Roboto (as the English menus) and the CJK characters
  (punctuation, kana, ideographs, full-width forms) from the language's own font:
    F_Wizard_ZH  CJK -> LXGW WenKai TC  ("Regular" Regular, "Bold" Medium)
    F_Wizard_JA  CJK -> Noto Sans JP    ("Regular" Regular, "Bold" Bold)
  Their typeface names match Roboto's ("Regular" / "Bold"), so a text block keeps its weight
  when r15_lang's ApplyLanguage swaps the font object for the language.
UFont's composite font is not open to Python attribute by attribute; it is set whole
through CompositeFont.import_text (the format Unreal itself exports).
"""
import json
import shutil
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'output' / 'round16' / 'fonts'
OUT = ROOT / 'output' / 'round16'
RES = OUT / 'r16-fonts.json'
DEST = '/Game/UI/Fonts'
FACES = {'FF_WenKaiTC_Regular': 'LXGWWenKaiTC-Regular.ttf', 'FF_WenKaiTC_Medium': 'LXGWWenKaiTC-Medium.ttf',
         'FF_NotoSansJP_Regular': 'NotoSansJP-Regular.ttf', 'FF_NotoSansJP_Bold': 'NotoSansJP-Bold.ttf',
         'FF_Tinos_Regular': 'Tinos-Regular.ttf', 'FF_Tinos_Bold': 'Tinos-Bold.ttf'}
ROBOTO = ('/Engine/EngineFonts/Faces/RobotoRegular.RobotoRegular', '/Engine/EngineFonts/Faces/RobotoBold.RobotoBold')
# font: (Latin regular, Latin bold, CJK regular, CJK bold); None = a face of this project.
# Round 17: English / French in Tinos (Times New Roman shapes), and Tinos for the Latin
# letters and digits of the Chinese menus too (楷體 + Times); Japanese keeps Roboto's Latin.
FONTS = {'F_Wizard_Latin': ('FF_Tinos_Regular', 'FF_Tinos_Bold', None, None),
         'F_Wizard_ZH': ('FF_Tinos_Regular', 'FF_Tinos_Bold', 'FF_WenKaiTC_Regular', 'FF_WenKaiTC_Medium'),
         'F_Wizard_JA': (ROBOTO[0], ROBOTO[1], 'FF_NotoSansJP_Regular', 'FF_NotoSansJP_Bold')}
# CJK symbols & punctuation, kana, bopomofo, CJK strokes / enclosed / compatibility, ext A,
# unified ideographs, compatibility ideographs, vertical forms, full-width forms, ext B+
CJK = [(0x2E80, 0x2FDF), (0x3000, 0x33FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
       (0xFE30, 0xFE4F), (0xFF00, 0xFFEF), (0x20000, 0x2FFFF)]
res = {'steps': []}


def log(s):
    res['steps'].append(s)
    RES.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')


def face_ref(path):
    return '(FontFaceAsset="/Script/Engine.FontFace\'%s\'")' % path


def composite(latin_regular, latin_bold, regular_face, bold_face):
    eng = '/Engine/EngineFonts/Faces/'
    default = '(Fonts=((Name="Regular",Font=%s),(Name="Bold",Font=%s)))' % (face_ref(latin_regular), face_ref(latin_bold))
    fallback = '(Typeface=(Fonts=((Name="Regular",Font=%s))),ScalingFactor=1.000000)' % face_ref(eng + 'DroidSansFallback.DroidSansFallback')
    ranges = ','.join('(LowerBound=(Type=Inclusive,Value=%d),UpperBound=(Type=Inclusive,Value=%d))' % r for r in CJK)
    sub = '((Typeface=(Fonts=((Name="Regular",Font=%s),(Name="Bold",Font=%s))),ScalingFactor=1.000000,CharacterRanges=(%s),Cultures=""))' % (
        face_ref(regular_face), face_ref(bold_face), ranges) if regular_face else '()'
    return '(DefaultTypeface=%s,FallbackTypeface=%s,SubTypefaces=%s,bEnableAscentDescentOverride=True)' % (default, fallback, sub)


def main():
    at = u.AssetToolsHelpers.get_asset_tools()
    keep = Path(u.Paths.project_dir()).resolve() / 'SourceArt' / 'Fonts'
    keep.mkdir(parents=True, exist_ok=True)
    for f in list(FACES.values()) + ['LXGWWenKaiTC-OFL.txt', 'NotoSansJP-OFL.txt', 'Tinos-OFL.txt']:
        shutil.copy2(SRC / f, keep / f)
    log('sources + OFL licences kept in %s' % keep)
    tasks = []
    for name, f in FACES.items():
        t = u.AssetImportTask()
        t.filename = str(keep / f)
        t.destination_path = DEST
        t.destination_name = name
        t.automated = True
        t.replace_existing = True
        t.save = True
        tasks.append(t)
    at.import_asset_tasks(tasks)
    faces = {}
    for name in FACES:
        fa = u.load_asset('%s/%s' % (DEST, name))
        assert isinstance(fa, u.FontFace), name
        faces[name] = fa.get_path_name()
    log('font faces: %s' % ', '.join(faces))
    face = lambda k: faces.get(k, k) if k else None
    for fname, (lreg, lbold, reg, bold) in FONTS.items():
        path = '%s/%s' % (DEST, fname)
        font = u.load_asset(path) if u.EditorAssetLibrary.does_asset_exist(path) else at.create_asset(fname, DEST, u.Font, u.FontFactory())
        cf = u.CompositeFont()
        cf.import_text(composite(face(lreg), face(lbold), face(reg), face(bold)))
        font.set_editor_property('composite_font', cf)
        back = font.get_editor_property('composite_font').export_text()
        assert face(lreg) in back and (reg is None or (face(reg) in back and 'CharacterRanges' in back)), back[:400]
        u.EditorAssetLibrary.save_loaded_asset(font, False)
        log('%s: Latin %s / %s, CJK %s / %s (%d ranges); cache %s' % (fname, lreg.rsplit('/', 1)[-1], lbold.rsplit('/', 1)[-1], reg, bold,
                                                                    back.count('LowerBound'), font.get_editor_property('font_cache_type')))
    res['passed'] = True
    log('done')


try:
    main()
except Exception:
    res['passed'] = False
    res['error'] = traceback.format_exc()
    RES.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
finally:
    u.SystemLibrary.quit_editor()
