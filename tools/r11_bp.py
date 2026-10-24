"""Round 11 Blueprint editing helpers (UE 5.8 editor Python: BlueprintGraphEditor).

Used by the r11_*.py scripts (character vs magic, ultimates by character x magic,
character traits, cute VFX wiring).  exec()'d or imported inside Unreal.
"""
import unreal as u
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/round11'
OUT.mkdir(parents=True, exist_ok=True)
BACKUP = ROOT / 'round11-before-assets'
L = u.BlueprintEditorLibrary
E = u.BlueprintGraphEditor
EAL = u.EditorAssetLibrary
SYS = u.get_default_object(u.SystemLibrary)
SUB = u.get_engine_subsystem(u.SubobjectDataSubsystem)
SLIB = u.SubobjectDataBlueprintFunctionLibrary

CH = '/Game/ThirdPerson/Blueprints/BP_WizardCharacter'
PC = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController'
CAST = '/Game/BluePrint/Magic/Ultimates/BP_UltimateCast'
ORB = '/Game/BluePrint/Magic/Ultimates/BP_UltimateOrb'
TELE = '/Game/BluePrint/Magic/Ultimates/Telegraphs/BP_UltimateTelegraph'
GS = '/Game/BluePrint/Gamemode/BP_WizardMatchState'
PS = '/Game/BluePrint/Character/BP_WizardPlayerState'
SPELLS = {el: '/Game/BluePrint/Magic/%sball/BP_%sball' % (el, el) for el in ['Fire', 'Ice', 'Wind', 'Lightning']}

ASSETS = {}
REPORT = {'steps': []}


def log(msg, report=None):
    print('R11 ' + str(msg))
    REPORT['steps'].append(str(msg))
    if report:
        (OUT / report).write_text(json.dumps(REPORT, indent=1, default=str), encoding='utf-8')


def load(p):
    if p not in ASSETS:
        ASSETS[p] = u.load_asset(p)
    assert ASSETS[p], p
    return ASSETS[p]


def cls(p):
    return load(p).generated_class()


def cp(p):
    return cls(p).get_path_name()


def typ(n):
    return L.get_basic_type_by_name(n)


def obj(c):
    return L.get_object_reference_type(c)


def struct(s):
    return L.get_struct_type(s.static_struct())


def arr(t):
    return L.get_array_type(t)


R, I, B = typ('real'), typ('int'), typ('bool')
V = struct(u.Vector)
ROT = struct(u.Rotator)
HIT = struct(u.HitResult)


def backup(p):
    """Copy an asset's files once (round 11 'before' state)."""
    BACKUP.mkdir(exist_ok=True)
    src = Path(u.Paths.project_content_dir()).resolve() / p.removeprefix('/Game/')
    for ext in ('.uasset', '.uexp'):
        f = src.with_suffix(ext)
        d = BACKUP / (f.name)
        if f.exists() and not d.exists():
            shutil.copy2(f, d)


def compile_bp(p, save=True):
    b = load(p)
    assert L.compile_blueprint(b), 'Compile failed: ' + p
    if save:
        assert EAL.save_loaded_asset(b, False), p


# ------------------------------------------------------------------ pins
def pin(n, name, out=False):
    p = n.find_output_pin(name) if out else n.find_input_pin(name)
    assert p.is_valid(), (n.get_node_title(), name, [str(x.get_pin_name()) for x in n.list_all_pins()])
    return p


def link(a, b):
    assert a.is_valid() and b.is_valid()
    assert a.try_create_connection(b), (a.get_owning_node().get_node_title(), str(a.get_pin_name()),
                                        b.get_owning_node().get_node_title(), str(b.get_pin_name()))


def value(p, v):
    if isinstance(v, u.BlueprintGraphPin):
        link(v, p)
    elif isinstance(v, (tuple, list)):
        assert p.set_pin_value(','.join('%g' % x for x in v)), (p.get_pin_name(), v)
    else:
        assert p.set_pin_value(str(v).lower() if isinstance(v, bool) else str(v)), (str(p.get_pin_name()), v)


def result(n):
    p = n.find_output_pin('ReturnValue')
    return p if p.is_valid() else n.find_result_pin()


def then(n):
    for p in n.list_output_pins():
        if str(p.get_pin_name()) in ('then', 'Completed'):
            return p
    return u.BlueprintGraphPin()


def ex(n):
    for p in n.list_input_pins():
        if str(p.get_pin_name()).lower() in ('execute', 'exec', 'in', 'do'):
            return p
    raise AssertionError(('No execute pin', n.get_node_title(), [str(p.get_pin_name()) for p in n.list_all_pins()]))


def chain(start, *nodes):
    """Exec-link start -> nodes...; returns the last 'then' pin."""
    p = start
    for n in nodes:
        if n is None:
            continue
        link(p, ex(n))
        p = then(n)
    return p


def is_exec(p):
    try:
        return str(p.get_pin_type_display_string()).lower().startswith('exec')
    except Exception:
        return False


# ------------------------------------------------------------------ graph
class Graph:
    def __init__(self, p, name='EventGraph', create=False):
        self.p, self.name, self.i = p, name, 0
        self.e = E.create_and_edit_function_graph(load(p), name) if create else E.get_graph_editor_by_name(load(p), name)
        assert self.e, (p, name)

    def place(self, n):
        assert n, (self.p, self.name, self.i)
        n.set_node_pos(u.IntPoint((self.i % 8) * 330, (self.i // 8) * 260))
        self.i += 1
        return n

    def call(me, path, **args):
        dbg = os.environ.get('R11_DEBUG')
        if dbg:
            print('R11 call', path)
        raw = me.e.add_call_function_node(path)
        if not raw and path.startswith('/Game/'):
            # a function made in this run: compile once so the class knows it
            owner = path.split('.')[0]
            for k, b in ASSETS.items():
                if b and b.generated_class() and b.generated_class().get_path_name().split('.')[0] == owner:
                    L.compile_blueprint(b)
            raw = me.e.add_call_function_node(path)
        n = me.place(raw)
        assert n, path
        # links first: wildcard / operator pins take literals only after their type is known
        for k, v in sorted(args.items(), key=lambda kv: 0 if isinstance(kv[1], u.BlueprintGraphPin) else 1):
            if dbg:
                print('R11   pin', k)
            value(pin(n, k), v)
        return n

    def fn(self, name, **args):
        return self.call(cp(self.p) + '.' + name, **args)

    def math(self, name, **args):
        return result(self.call('/Script/Engine.KismetMathLibrary.' + name, **args))

    def sysc(self, name, **args):
        return self.call('/Script/Engine.KismetSystemLibrary.' + name, **args)

    def get(self, name, p=None, target=None):
        n = self.place(self.e.add_get_member_variable_node(name, cp(p) if p else ''))
        assert n, name
        if target is not None:
            value(n.find_self_pin(), target)
        return pin(n, name, True)

    def set(self, name, v, p=None, target=None):
        n = self.place(self.e.add_set_member_variable_node(name, cp(p) if p else ''))
        assert n, name
        value(pin(n, name), v)
        if target is not None:
            value(n.find_self_pin(), target)
        return n

    def branch(self, cond):
        n = self.place(self.e.add_branch_node())
        value(n.find_condition_pin(), cond)
        return n

    def node(self, menu):
        n = self.e.create_node_from_name(menu, u.Vector2D(0, 0), [])
        assert n, menu
        return self.place(n)

    def seq(self, outs=2):
        n = self.node('Utilities|FlowControl|Sequence')
        for _ in range(outs - 2):
            self.e.add_node_pin(n)
        return n

    def seq_out(self, n, i):
        return pin(n, 'then_%d' % i, True)

    def cast(self, src, p, base=u.Actor):
        n = self.e.create_node_from_name('Utilities|Casting|CastTo' + base.static_class().get_name(), u.Vector2D(), [])
        assert n, ('cast', p)
        assert self.e.retarget_node_class(n, base, cls(p))
        self.place(n)
        value(pin(n, 'Object'), src)
        outs = [x for x in n.list_output_pins() if str(x.get_pin_name()).startswith('As')]
        assert len(outs) == 1
        return n, outs[0]

    def foreach(self, array):
        n = self.place(self.e.add_macro_node('/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop'))
        value(pin(n, 'Array'), array)
        return n

    def forloop(self, first, last):
        n = self.place(self.e.add_macro_node('/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForLoop'))
        value(pin(n, 'FirstIndex'), first)
        value(pin(n, 'LastIndex'), last)
        return n

    def isvalid_macro(self, objp):
        n = self.place(self.e.add_macro_node('/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:IsValid'))
        value(pin(n, 'InputObject'), objp)
        return n

    def event(self, name):
        return self.place(self.e.add_custom_event_node(name))

    def native_event(self, name):
        n = self.e.find_event_node(name)
        if not n:
            n = self.e.create_node_from_name('AddEvent|Event' + {'ReceiveBeginPlay': 'BeginPlay', 'ReceiveTick': 'Tick',
                                                                  'ReceiveDestroyed': 'Destroyed'}[name], u.Vector2D(), [])
        return self.place(n)

    def entry(self):
        return self.e.find_graph_entry_pin()

    def inp(self, n):
        return pin(self.entry().get_owning_node(), n, True)

    def ret(self, **args):
        free = [n for n in self.e.list_all_nodes() if n.get_class().get_name() == 'K2Node_FunctionResult'
                and not ex(n).list_connected_pins()]
        n = self.place(free[0] if free else self.e.add_return_node())
        for k, v in args.items():
            value(pin(n, k), v)
        return n

    def selfref(self):
        n = self.node('Variables|Getareferencetoself')
        return pin(n, 'self', True)

    # ---- small math sugar
    def vec(self, x, y=None, z=None):
        # a pin alone is already a vector; with y / z it is the X of a new one (round 12:
        # returning it here made vec(sx, sy, 1) a uniform sx scale -- the 52 m lane square)
        if isinstance(x, u.BlueprintGraphPin) and y is None and z is None:
            return x
        if isinstance(x, (tuple, list)):
            x, y, z = x
        return self.math('MakeVector', X=x, Y=y, Z=z)

    def vadd(self, a, b):
        return self.math('Add_VectorVector', A=self.vec(a), B=self.vec(b))

    def vsub(self, a, b):
        return self.math('Subtract_VectorVector', A=self.vec(a), B=self.vec(b))

    def vmul(self, a, s):
        # vector * MakeVector(s, s, s): the promotable 'vector * float' node reads a
        # literal float as a vector (zero) in this engine version
        return self.math('Multiply_VectorVector', A=self.vec(a), B=self.math('MakeVector', X=s, Y=s, Z=s))

    def fmul(self, a, b):
        return self.math('Multiply_DoubleDouble', A=a, B=b)

    def fadd(self, a, b):
        return self.math('Add_DoubleDouble', A=a, B=b)

    def fsub(self, a, b):
        return self.math('Subtract_DoubleDouble', A=a, B=b)

    def ieq(self, a, b):
        return self.math('EqualEqual_IntInt', A=a, B=b)

    def AND(self, *xs):
        n = self.call('/Script/Engine.KismetMathLibrary.BooleanAND', A=xs[0], B=xs[1])
        for k, x in enumerate(xs[2:]):
            assert self.e.add_node_pin(n)
            value(pin(n, chr(ord('C') + k)), x)
        return result(n)

    def OR(self, *xs):
        n = self.call('/Script/Engine.KismetMathLibrary.BooleanOR', A=xs[0], B=xs[1])
        for k, x in enumerate(xs[2:]):
            assert self.e.add_node_pin(n)
            value(pin(n, chr(ord('C') + k)), x)
        return result(n)

    def NOT(self, a):
        return self.math('Not_PreBool', A=a)

    def selectf(self, a, b, pick_a):
        return self.math('SelectFloat', A=a, B=b, bPickA=pick_a)

    def selectv(self, a, b, pick_a):
        return self.math('SelectVector', A=self.vec(a), B=self.vec(b), bPickA=pick_a)

    def loc(self, actor=None):
        return result(self.call('/Script/Engine.Actor.K2_GetActorLocation', **({'self': actor} if actor is not None else {})))

    def now(self):
        return result(self.call('/Script/Engine.GameplayStatics.GetTimeSeconds'))

    def authority(self):
        return result(self.call('/Script/Engine.Actor.HasAuthority'))

    def valid(self, o):
        return result(self.call('/Script/Engine.KismetSystemLibrary.IsValid', Object=o))

    def toint(self, byte):
        return self.math('Conv_ByteToInt', InByte=byte)

    def tofloat(self, i):
        return self.math('Conv_IntToDouble', InInt=i)

    def switch_int(self, sel, cases):
        """A ladder of branches on an int: returns {case: exec pin}, plus 'default'."""
        outs = {}
        prev = None
        first = None
        for c in cases:
            b = self.branch(self.ieq(sel, c))
            if prev is None:
                first = b
            else:
                link(pin(prev, 'else', True), ex(b))
            outs[c] = pin(b, 'then', True)
            prev = b
        outs['default'] = pin(prev, 'else', True)
        outs['in'] = ex(first)
        return outs


def per_element(g, elem, make, cases=(0, 1, 2, 3)):
    """Branch ladder on an int pin; make(e) -> (first_node, last_exec_pin) or None.
    Returns (input exec pin, [last exec pins])."""
    sw = g.switch_int(elem, list(cases))
    lasts = []
    for e in cases:
        r = make(e)
        if r is None:
            lasts.append(sw[e])
            continue
        first, last = r
        link(sw[e], ex(first))
        lasts.append(last)
    return sw['in'], lasts


def fresh(p, name, inputs=(), outputs=(), pure=False):
    """Empty (or create) a function graph with the given signature."""
    b = load(p)
    names = [str(x) for x in L.list_graph_names(b)]
    if name in names:
        g = Graph(p, name)
        g.e.remove_nodes([n for n in g.e.list_all_nodes() if n.get_class().get_name() not in ('K2Node_FunctionEntry', 'K2Node_FunctionResult')])
        entry = g.entry().get_owning_node()
        have = {str(q.get_pin_name()) for q in entry.list_output_pins()}
        want = [k for k, t in inputs]
        for k in list(have):
            if k not in want and k != 'then':
                g.e.remove_graph_input_parameter(k)
        for k, t in inputs:
            if k not in have:
                g.e.add_graph_input_parameter(k, t)
        rets = [n for n in g.e.list_all_nodes() if n.get_class().get_name() == 'K2Node_FunctionResult']
        rhave = {str(q.get_pin_name()) for r in rets for q in r.list_input_pins()} if rets else set()
        for k, t in outputs:
            if k not in rhave:
                g.e.add_graph_output_parameter(k, t)
        # result nodes hold the outputs: keep one, unhooked
        rets = [n for n in g.e.list_all_nodes() if n.get_class().get_name() == 'K2Node_FunctionResult']
        for r in rets:
            for p in r.list_input_pins():
                p.break_pin_links()
        if len(rets) > 1:
            g.e.remove_nodes(rets[1:])
        return g
    g = Graph(p, name, True)
    for k, t in inputs:
        g.e.add_graph_input_parameter(k, t)
    for k, t in outputs:
        g.e.add_graph_output_parameter(k, t)
    if pure:
        g.e.set_is_pure_function(True)
    return g


def declare(p, name, t, default='', rep=None):
    """Member variable (kept if it exists).  rep: None, 'rep', 'notify'."""
    b = load(p)
    if name not in [str(x) for x in L.list_member_variable_names(b, False)]:
        assert E.get_graph_editor_by_name(b, 'EventGraph').add_member_variable(name, t, str(default)), (p, name)
    if rep == 'rep':
        L.set_blueprint_variable_replication(b, name, u.BlueprintVariableReplication.REPLICATED)
    elif rep == 'notify':
        L.set_blueprint_variable_replication(b, name, u.BlueprintVariableReplication.REP_NOTIFY)


def set_event_net(ev, kind):
    """kind: 'server' (reliable), 'multicast' (reliable), 'multicast_u' (unreliable).
    FunctionFlags is not visible to Python: set it through the console SET command."""
    flags = {'server': 0x2000C0, 'multicast': 0x40C0, 'multicast_u': 0x4040}[kind]
    u.SystemLibrary.execute_console_command(None, 'SET %s FunctionFlags %d' % (ev.get_path_name(), flags))


def find_event(g, name):
    for n in g.e.list_all_nodes():
        if n.get_class().get_name() in ('K2Node_CustomEvent', 'K2Node_Event') and str(n.get_node_title()).split('\n')[0].strip() == name:
            return n
    return None


def remove_tree(g, nodes):
    """Remove nodes and the pure (non-exec) nodes feeding only them."""
    todo = list(nodes)
    gone = set()
    while todo:
        n = todo.pop()
        if n.get_name() in gone:
            continue
        feeders = []
        for p in n.list_input_pins():
            for q in p.list_connected_pins():
                f = q.get_owning_node()
                if not any(is_exec(x) for x in f.list_all_pins()):
                    feeders.append(f)
        g.e.remove_nodes([n])
        gone.add(n.get_name())
        for f in feeders:
            # only if nothing else reads it
            still = any(q.list_connected_pins() for q in f.list_output_pins())
            if not still:
                todo.append(f)


def layout(g):
    """Readable layout: exec nodes left-to-right along their flow, data nodes
    stacked below the node that reads them."""
    nodes = list(g.e.list_all_nodes())
    byname = {n.get_name(): n for n in nodes}
    execn = [n for n in nodes if any(is_exec(p) for p in n.list_all_pins())]
    col = {}
    roots = [n for n in execn if not any(is_exec(p) and p.list_connected_pins() for p in n.list_input_pins())]
    row = 0
    rows = {}
    for r in roots:
        stack = [(r, 0)]
        while stack:
            n, c = stack.pop()
            if n.get_name() in col:
                continue
            col[n.get_name()] = c
            rows[n.get_name()] = row
            outs = [q.get_owning_node() for p in n.list_output_pins() if is_exec(p) for q in p.list_connected_pins()]
            for k, m in enumerate(reversed(outs)):
                stack.append((m, c + 1))
        row += 1
    for n in execn:
        if n.get_name() not in col:
            col[n.get_name()] = 0
            rows[n.get_name()] = row
            row += 1
    used = {}
    for n in execn:
        c, r = col[n.get_name()], rows[n.get_name()]
        k = used.get((c, r), 0)
        used[(c, r)] = k + 1
        n.set_node_pos(u.IntPoint(c * 420, r * 900 + k * 300))
    # data nodes: below their first consumer
    placed = {n.get_name() for n in execn}
    below = {}
    for n in nodes:
        if n.get_name() in placed:
            continue
        cons = [q.get_owning_node() for p in n.list_output_pins() for q in p.list_connected_pins()]
        host = next((c for c in cons if c.get_name() in placed), cons[0] if cons else None)
        if host is None:
            n.set_node_pos(u.IntPoint(-600, 0))
            continue
        hp = host.get_node_pos()
        k = below.get(host.get_name(), 0)
        below[host.get_name()] = k + 1
        n.set_node_pos(u.IntPoint(hp.x - 60 - 40 * (k % 3), hp.y + 200 + 130 * k))


# ------------------------------------------------------------------ components
def components(p):
    b = load(p)
    out = {}
    for h in SUB.k2_gather_subobject_data_for_blueprint(b):
        d = SUB.k2_find_subobject_data_from_handle(h)
        out[str(SLIB.get_variable_name(d))] = (h, SLIB.get_object(d))
    return out


def add_component(p, name, klass, parent='DefaultSceneRoot'):
    """Add a component (kept if it exists); returns the template."""
    cs = components(p)
    if name in cs:
        return cs[name][1]
    if parent in cs:
        parent_h = cs[parent][0]
    else:
        scene = [h for k, (h, o) in cs.items() if isinstance(o, u.SceneComponent)]
        parent_h = scene[0] if scene else next(iter(cs.values()))[0]
    h, why = SUB.add_new_subobject(u.AddNewSubobjectParams(parent_handle=parent_h, new_class=klass, blueprint_context=load(p)))
    assert SLIB.is_handle_valid(h), str(why)
    assert SUB.rename_subobject(h, u.Text(name))
    return SLIB.get_object(SUB.k2_find_subobject_data_from_handle(h))


def comp_template(p, name):
    return components(p)[name][1]
