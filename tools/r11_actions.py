"""Round 11: key the characters' own actions (r11_actions_pose.py) into
AnimSequences on Quinn's skeleton: /Game/Characters/WizardActions/Round11/A_R11_<Name>.

UnrealEditor-Cmd <uproject> -run=pythonscript -script=r11_actions.py
"""
import unreal as u
import json
import sys
import traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import importlib
import r11_actions_pose as A
importlib.reload(A)
EAL = u.EditorAssetLibrary
SRC = '/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle'
FOLDER = '/Game/Characters/WizardActions/Round11'
out = {}
try:
    assert A.STAFF, 'run r11_staff_frame.py first (output/round11/staff-frame.json)'
    for name in A.ACTIONS:
        path = FOLDER + '/A_R11_' + name
        anim = u.load_asset(path) if EAL.does_asset_exist(path) else EAL.duplicate_asset(SRC, path)
        assert anim, path
        anim.set_editor_properties({'enable_root_motion': False, 'force_root_lock': True})
        dur, frames = A.action_frames(name, 30)
        n = len(frames)
        ctl = anim.get_editor_property('controller')
        ctl.open_bracket('Round 11 action ' + name, False)
        ctl.set_frame_rate(u.FrameRate(numerator=30, denominator=1), False)
        ctl.set_number_of_frames(u.FrameNumber(n - 1), False)
        for bone in A.BASE:
            ctl.set_bone_track_keys(bone, [u.Vector(*f[bone]['p']) for f in frames], [u.Quat(*f[bone]['q']) for f in frames],
                                    [u.Vector(1, 1, 1)] * n, False)
        ctl.close_bracket(False)
        assert EAL.save_loaded_asset(anim, False), path
        out[name] = dict(path=path, seconds=round(anim.get_play_length(), 3), frames=n)
        print('R11 action', name, out[name])
    out['passed'] = True
except Exception:
    out['passed'] = False
    out['error'] = traceback.format_exc()
    u.log_error(traceback.format_exc())
(ROOT / 'output/round11/r11-actions.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
print('R11_ACTIONS_DONE', out.get('passed'))
