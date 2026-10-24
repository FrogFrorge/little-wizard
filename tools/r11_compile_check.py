"""Compile every game Blueprint; list nodes with errors / warnings (round 11 check)."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
import r11_bp
importlib.reload(r11_bp)
from r11_bp import *          # noqa

ar = u.AssetRegistryHelpers.get_asset_registry()
res = {}
for root in ['/Game/BluePrint', '/Game/ThirdPerson', '/Game/UI', '/Game/VFX', '/Game/Characters/LittleWizardsV5', '/Game/Maps/WizardWorlds']:
    for ad in ar.get_assets_by_path(root, True):
        if str(ad.asset_class_path.asset_name) not in ('Blueprint', 'WidgetBlueprint', 'AnimBlueprint'):
            continue
        p = str(ad.package_name)
        b = u.load_asset(p)
        ok = L.compile_blueprint(b)
        bad = {}
        for gn in L.list_graph_names(b):
            ge = E.get_graph_editor_by_name(b, str(gn))
            if not ge:
                continue
            errs = [str(n.get_node_title()) + ': ' + str(n.get_editor_property('error_msg') if hasattr(n, 'get_editor_property') else '')
                    for n in ge.list_nodes_with_errors()]
            warns = [str(n.get_node_title()) for n in ge.list_nodes_with_warnings()]
            if errs or warns:
                bad[str(gn)] = {'errors': errs, 'warnings': warns}
        res[p] = {'compiled': bool(ok), 'issues': bad}
(OUT / 'r11-compile-check.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
print('R11_COMPILE_CHECK', sum(1 for v in res.values() if v['issues']), 'with issues of', len(res))
