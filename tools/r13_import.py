"""Round 13: bring the new sound, music and cut-in cards into the game.

- every WAV of audio-r13/sfx and audio-r13/music replaces the asset of the same name
  under /Game/Audio/Wizard/<SFX|UI|Music> (the Blueprints keep pointing at them);
  new ones: UltStart_<Wizard> (SFX) and UltCutIn (UI)
- per sound: volume, looping, sound class, concurrency and attenuation by its kind
- the four cut-in cards -> /Game/UI/UltCutIn/T_UltCutIn_<Wizard> (UI texture, no mips)
- the sources are kept in the project (SourceAudio/Wizard/R13, SourceArt/R13), the
  assets they replace are copied first to round13-before-assets/

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r13_import.py
"""
import json
import shutil
import traceback
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / 'round13'
OUT.mkdir(parents=True, exist_ok=True)
BACKUP = ROOT / 'round13-before-assets'
BASE = '/Game/Audio/Wizard'
at = u.AssetToolsHelpers.get_asset_tools()
EAL = u.EditorAssetLibrary
REPORT = {'steps': []}

# by kind: (volume, attenuation, concurrency, priority)
KIND = {'ultimate': (1.0, 'ATT_Ultimate', 'CON_Ultimate', 2.5), 'cast': (0.85, 'ATT_Magic', 'CON_Cast', 1.2),
        'impact': (0.9, 'ATT_Magic', 'CON_Impact', 1.3), 'movement': (0.7, 'ATT_Movement', 'CON_Movement', 0.4),
        'loop': (0.8, 'ATT_Magic', 'CON_Loop', 1.0), 'ui': (0.8, None, 'CON_UI', 2.0), 'music': (0.5, None, 'CON_Music', 3.0)}


def log(s):
    print('R13 ' + s)
    REPORT['steps'].append(s)
    (OUT / 'r13-import.json').write_text(json.dumps(REPORT, indent=1, ensure_ascii=False), encoding='utf-8')


def backup(path):
    src = Path(u.Paths.project_content_dir()).resolve() / (path.removeprefix('/Game/') + '.uasset')
    dst = BACKUP / src.relative_to(Path(u.Paths.project_content_dir()).resolve())
    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return 1
    return 0


def mix(name):
    return u.load_asset('%s/Mix/%s' % (BASE, name))


def import_files(rows, src_dir, keep_dir, dest_of):
    keep_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for r in rows:
        f = keep_dir / (r['name'] + r.get('ext', '.wav'))
        shutil.copy2(src_dir / f.name, f)
        t = u.AssetImportTask()
        t.filename = str(f)
        t.destination_path = dest_of(r)
        t.destination_name = r['name']
        t.automated = True
        t.replace_existing = True
        t.save = True
        tasks.append(t)
    at.import_asset_tasks(tasks)


def main():
    try:
        proj = Path(u.Paths.project_dir()).resolve()
        sfx = json.loads((ROOT / 'audio-r13' / 'sfx-manifest.json').read_text(encoding='utf-8'))
        music = json.loads((ROOT / 'audio-r13' / 'music-manifest.json').read_text(encoding='utf-8'))
        for r in music:
            r['kind'] = 'music'
        rows = sfx + music
        n = sum(backup('%s/%s/%s' % (BASE, r['group'], r['name'])) for r in rows)
        for p in ('/Game/BluePrint/Gamemode/BP_WizardMatchHUD', '/Game/ThirdPerson/Blueprints/BP_WizardCharacter',
                  '/Game/BluePrint/Magic/Ultimates/BP_UltimateCast'):
            n += backup(p)
        log('backed up %d assets to %s' % (n, BACKUP))

        # ---- audio
        keep = proj / 'SourceAudio' / 'Wizard' / 'R13'
        import_files([r for r in rows if r['group'] != 'Music'], ROOT / 'audio-r13' / 'sfx', keep, lambda r: '%s/%s' % (BASE, r['group']))
        import_files([r for r in rows if r['group'] == 'Music'], ROOT / 'audio-r13' / 'music', keep, lambda r: '%s/Music' % BASE)
        classes = {'SFX': mix('SC_WizardSFX'), 'UI': mix('SC_WizardUI'), 'Music': mix('SC_WizardMusic')}
        for r in rows:
            p = '%s/%s/%s' % (BASE, r['group'], r['name'])
            w = u.load_asset(p)
            assert isinstance(w, u.SoundWave), p
            vol, att, con, pri = KIND[r['kind']]
            # round 14: a sound's own 'volume' in the manifest scales its kind's volume
            # (SpellReady 0.3, SuperReady 0.6), so re-running this import keeps them quiet
            props = {'volume': vol * r.get('volume', 1.0), 'looping': bool(r.get('loop') or r['kind'] == 'music'),
                     'sound_class_object': classes[r['group']], 'priority': pri,
                     'concurrency_set': {mix(con)}, 'override_concurrency': False, 'compression_quality': 85,
                     'comment': r['origin'] + '; Little Wizard round 13 (2026-10-16)'}
            w.set_editor_properties(props)
            w.set_editor_property('attenuation_settings', mix(att) if att else None)
            EAL.save_loaded_asset(w, False)
        log('audio: %d sounds (%d new names), %d music loops' % (
            len(sfx), sum(1 for r in sfx if r['name'].startswith('Ult')), len(music)))

        # ---- the cut-in cards
        cards = sorted((ROOT / 'output' / 'round13' / 'cutin').glob('T_UltCutIn_*.png'))
        keep_art = proj / 'SourceArt' / 'R13'
        import_files([{'name': c.stem, 'ext': '.png'} for c in cards], cards[0].parent, keep_art, lambda r: '/Game/UI/UltCutIn')
        for c in cards:
            p = '/Game/UI/UltCutIn/' + c.stem
            t = u.load_asset(p)
            assert isinstance(t, u.Texture2D), p
            t.set_editor_properties({'compression_settings': u.TextureCompressionSettings.TC_EDITOR_ICON,
                                     'lod_group': u.TextureGroup.TEXTUREGROUP_UI,
                                     'mip_gen_settings': u.TextureMipGenSettings.TMGS_NO_MIPMAPS,
                                     'srgb': True, 'never_stream': True})
            EAL.save_loaded_asset(t, False)
        log('cut-in cards: %s' % ', '.join(c.stem for c in cards))
        REPORT['passed'] = True
        log('done')
    except Exception:
        REPORT['passed'] = False
        REPORT['error'] = traceback.format_exc()
        (OUT / 'r13-import.json').write_text(json.dumps(REPORT, indent=1, ensure_ascii=False), encoding='utf-8')
        u.log_error(traceback.format_exc())


main()
