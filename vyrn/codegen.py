"""Génération de code C à partir d'un AST vérifié."""
from . import ast as A
from .checker import MATH1
from .runtime import PRELUDE

PRIM_C = {"int": "int64_t", "float": "double", "bool": "bool", "str": "vy_str", "void": "void"}


def mangle(t):
    if isinstance(t, tuple):
        return ("list_" + mangle(t[1])) if t[0] == "list" else t[1]
    return t


def ctype(t):
    if isinstance(t, tuple):
        return ("L_" if t[0] == "list" else "S_") + (mangle(t[1]) if t[0] == "list" else t[1]) + "*"
    return PRIM_C[t]


def cname(t):
    """Nom de base C du type (sans étoile) pour les structs et listes."""
    return ctype(t)[:-1]


def default_value(t):
    return {"int": "0", "float": "0.0", "bool": "false", "str": '""'}.get(t, "NULL")


def tostr(t):
    if isinstance(t, tuple):
        return "TS_" + cname(t)
    return f"vy_str_of_{t}"


def repr_fn(t):
    return "vy_repr_str" if t == "str" else tostr(t)


def c_string(s):
    out = []
    for b in s.encode("utf-8"):
        c = chr(b)
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        elif 32 <= b < 127 and c != "?":
            out.append(c)
        else:
            out.append(f"\\{b:03o}")
    return '"' + "".join(out) + '"'


class CodeGen:
    def __init__(self, checker):
        self.c = checker
        self.out = []
        self.ind = 0
        self.tmp = 0
        # split() renvoie list[str] : toujours disponible
        checker.list_types.add(("list", "str"))

    def w(self, line=""):
        self.out.append("    " * self.ind + line)

    def fresh(self, base):
        self.tmp += 1
        return f"_{base}{self.tmp}"

    # ---- programme ----
    def generate(self, program):
        self.out.append(PRELUDE.strip())
        for h in self.c.includes:
            self.w(f"#include <{h}>" if not h.startswith('"') else f"#include {h}")
        self.w()
        lists = sorted(self.c.list_types, key=lambda t: self.depth(t))
        structs = list(self.c.structs.items())

        for name, _ in structs:
            self.w(f"typedef struct S_{name} S_{name};")
        for t in lists:
            self.w(f"typedef struct {cname(t)} {cname(t)};")
        self.w()
        for name, fields in structs:
            self.w(f"struct S_{name} {{")
            for f, ft in fields:
                self.w(f"    {ctype(ft)} f_{f};")
            if not fields:
                self.w("    char _unused;")
            self.w("};")
        for t in lists:
            self.w(f"struct {cname(t)} {{ int64_t len, cap; {ctype(t[1])}* data; }};")
        self.w()
        for name, _ in structs:
            self.w(f"static vy_str TS_S_{name}(S_{name}* v);")
        for t in lists:
            self.w(f"static vy_str TS_{cname(t)}({ctype(t)} v);")
        self.w()
        for name, fields in structs:
            self.emit_struct(name, fields)
        for t in lists:
            self.emit_list(t)
        self.emit_split()

        fns = [it for it in program.items if isinstance(it, A.FnDecl) and not it.extern]
        for f in fns:
            self.w(self.signature(f) + ";")
        self.w()
        for f in fns:
            self.emit_fn(f)

        _, main_ret, _ = self.c.funcs["main"]
        self.w("int main(int argc, char** argv) {")
        self.w("    (void)argc; (void)argv;")
        self.w("    srand((unsigned)time(NULL));")
        self.w("    setvbuf(stdout, NULL, _IOLBF, 0);")
        if main_ret == "int":
            self.w("    return (int)vy_main();")
        else:
            self.w("    vy_main();")
            self.w("    return 0;")
        self.w("}")
        return "\n".join(self.out) + "\n"

    def depth(self, t):
        return 1 + self.depth(t[1]) if isinstance(t, tuple) and t[0] == "list" else 0

    def emit_struct(self, name, fields):
        params = ", ".join(f"{ctype(ft)} a_{f}" for f, ft in fields) or "void"
        self.w(f"static S_{name}* S_{name}_new({params}) {{")
        self.w(f"    S_{name}* s = (S_{name}*)vy_alloc(sizeof(S_{name}));")
        for f, _ in fields:
            self.w(f"    s->f_{f} = a_{f};")
        self.w("    return s;")
        self.w("}")
        self.w(f"static vy_str TS_S_{name}(S_{name}* v) {{")
        self.w("    vy_buf b = {0};")
        self.w(f'    vy_buf_add(&b, "{name}(");')
        for i, (f, ft) in enumerate(fields):
            sep = ", " if i else ""
            self.w(f'    vy_buf_add(&b, "{sep}{f}=");')
            self.w(f"    vy_buf_add(&b, {repr_fn(ft)}(v->f_{f}));")
        self.w('    vy_buf_add(&b, ")");')
        self.w("    return vy_buf_done(&b);")
        self.w("}")
        self.w()

    def emit_list(self, t):
        L = cname(t)
        T = ctype(t[1])
        e = t[1]
        lines = f"""
static {L}* {L}_new(void) {{
    {L}* l = ({L}*)vy_alloc(sizeof({L}));
    l->len = 0; l->cap = 0; l->data = NULL;
    return l;
}}
static void {L}_push({L}* l, {T} v) {{
    if (l->len == l->cap) {{
        l->cap = l->cap ? l->cap * 2 : 8;
        l->data = ({T}*)vy_realloc(l->data, sizeof({T}) * (size_t)l->cap);
    }}
    l->data[l->len++] = v;
}}
static int64_t {L}_idx({L}* l, int64_t i, int line) {{
    if (i < 0) i += l->len;
    if (i < 0 || i >= l->len) vy_panic("indice de liste hors limites", line);
    return i;
}}
static {T} {L}_get({L}* l, int64_t i, int line) {{ return l->data[{L}_idx(l, i, line)]; }}
static void {L}_set({L}* l, int64_t i, {T} v, int line) {{ l->data[{L}_idx(l, i, line)] = v; }}
static {T} {L}_pop({L}* l, int line) {{
    if (l->len == 0) vy_panic("pop sur une liste vide", line);
    return l->data[--l->len];
}}
static void {L}_clear({L}* l) {{ l->len = 0; }}
static void {L}_insert({L}* l, int64_t i, {T} v, int line) {{
    if (i < 0) i += l->len;
    if (i < 0 || i > l->len) vy_panic("insert : indice hors limites", line);
    {L}_push(l, v);
    memmove(l->data + i + 1, l->data + i, sizeof({T}) * (size_t)(l->len - 1 - i));
    l->data[i] = v;
}}
static {T} {L}_remove_at({L}* l, int64_t i, int line) {{
    i = {L}_idx(l, i, line);
    {T} v = l->data[i];
    memmove(l->data + i, l->data + i + 1, sizeof({T}) * (size_t)(l->len - 1 - i));
    l->len--;
    return v;
}}
static {L}* {L}_from(int64_t n, {T}* items) {{
    {L}* r = {L}_new();
    for (int64_t i = 0; i < n; i++) {L}_push(r, items[i]);
    return r;
}}
static {L}* {L}_copy({L}* l) {{
    {L}* r = {L}_new();
    for (int64_t i = 0; i < l->len; i++) {L}_push(r, l->data[i]);
    return r;
}}
static void {L}_reverse({L}* l) {{
    for (int64_t i = 0, j = l->len - 1; i < j; i++, j--) {{
        {T} t = l->data[i]; l->data[i] = l->data[j]; l->data[j] = t;
    }}
}}
static vy_str TS_{L}({L}* l) {{
    vy_buf b = {{0}};
    vy_buf_add(&b, "[");
    for (int64_t i = 0; i < l->len; i++) {{
        if (i) vy_buf_add(&b, ", ");
        vy_buf_add(&b, {repr_fn(e)}(l->data[i]));
    }}
    vy_buf_add(&b, "]");
    return vy_buf_done(&b);
}}"""
        if not isinstance(e, tuple):
            eq = "vy_str_eq(l->data[i], v)" if e == "str" else "l->data[i] == v"
            lines += f"""
static int64_t {L}_index_of({L}* l, {T} v) {{
    for (int64_t i = 0; i < l->len; i++) if ({eq}) return i;
    return -1;
}}
static bool {L}_contains({L}* l, {T} v) {{ return {L}_index_of(l, v) >= 0; }}"""
        for ln in lines.strip("\n").split("\n"):
            self.w(ln)
        self.w()

    def emit_split(self):
        for ln in r"""
static L_str* vy_s_split(vy_str s, vy_str sep, int line) {
    L_str* r = L_str_new();
    size_t k = strlen(sep);
    if (k == 0) vy_panic("split : separateur vide", line);
    const char* p;
    while ((p = strstr(s, sep))) {
        L_str_push(r, vy_strndup(s, (size_t)(p - s)));
        s = p + k;
    }
    L_str_push(r, vy_strdup(s));
    return r;
}""".strip("\n").split("\n"):
            self.w(ln)
        self.w()

    def signature(self, f):
        params, ret, _ = self.c.funcs[f.name]
        ps = ", ".join(f"{ctype(t)} v_{n}" for n, t in params) or "void"
        return f"static {ctype(ret)} vy_{f.name}({ps})"

    def emit_fn(self, f):
        _, ret, _ = self.c.funcs[f.name]
        self.w(self.signature(f) + " {")
        self.ind += 1
        for s in f.body:
            self.stmt(s)
        if ret != "void":
            self.w(f'vy_panic("fin de \'{f.name}\' atteinte sans return", {f.line});')
            self.w(f"return {default_value(ret)};")
        self.ind -= 1
        self.w("}")
        self.w()

    # ---- instructions ----
    def body(self, stmts):
        self.ind += 1
        for s in stmts:
            self.stmt(s)
        self.ind -= 1

    def stmt(self, s):
        if isinstance(s, A.Let):
            self.w(f"{ctype(s.resolved_type)} v_{s.name} = {self.expr(s.value)};")
        elif isinstance(s, A.Assign):
            self.assign(s)
        elif isinstance(s, A.If):
            for i, (cond, body) in enumerate(s.branches):
                kw = "if" if i == 0 else "} else if"
                self.w(f"{kw} ({self.expr(cond)}) {{")
                self.body(body)
            if s.orelse:
                self.w("} else {")
                self.body(s.orelse)
            self.w("}")
        elif isinstance(s, A.While):
            self.w(f"while ({self.expr(s.cond)}) {{")
            self.body(s.body)
            self.w("}")
        elif isinstance(s, A.ForRange):
            end = self.fresh("end")
            self.w(f"for (int64_t v_{s.var} = {self.expr(s.start)}, {end} = {self.expr(s.end)}; v_{s.var} < {end}; v_{s.var}++) {{")
            self.body(s.body)
            self.w("}")
        elif isinstance(s, A.ForEach):
            it, k = self.fresh("it"), self.fresh("k")
            ity = s.iterable.ty
            self.w("{")
            self.ind += 1
            self.w(f"{ctype(ity)} {it} = {self.expr(s.iterable)};")
            if ity == "str":
                self.w(f"for (int64_t {k} = 0; {it}[{k}]; {k}++) {{")
                self.w(f"    vy_str v_{s.var} = vy_strndup({it} + {k}, 1);")
            else:
                self.w(f"for (int64_t {k} = 0; {k} < {it}->len; {k}++) {{")
                self.w(f"    {ctype(s.elem_type)} v_{s.var} = {it}->data[{k}];")
            self.body(s.body)
            self.w("}")
            self.ind -= 1
            self.w("}")
        elif isinstance(s, A.Return):
            self.w("return;" if s.value is None else f"return {self.expr(s.value)};")
        elif isinstance(s, A.Break):
            self.w("break;")
        elif isinstance(s, A.Continue):
            self.w("continue;")
        elif isinstance(s, A.ExprStmt):
            self.w(f"{self.expr(s.expr)};")
        elif isinstance(s, A.Pass):
            self.w(";")

    def assign(self, s):
        t = s.target
        val = self.expr(s.value)
        op = None if s.op == "=" else s.op[0]

        def combine(cur):
            return val if op is None else self.binop(op, cur, t.ty, val, s.value.ty, s.line)

        if isinstance(t, A.Name):
            self.w(f"v_{t.name} = {combine('v_' + t.name)};")
        elif isinstance(t, A.Field):
            o = self.fresh("o")
            self.w(f"{{ {ctype(t.obj.ty)} {o} = {self.expr(t.obj)}; {o}->f_{t.name} = {combine(f'{o}->f_{t.name}')}; }}")
        elif isinstance(t, A.Index):
            L = cname(t.obj.ty)
            o, i = self.fresh("o"), self.fresh("i")
            cur = f"{L}_get({o}, {i}, {s.line})"
            self.w(f"{{ {ctype(t.obj.ty)} {o} = {self.expr(t.obj)}; int64_t {i} = {self.expr(t.index)}; "
                   f"{L}_set({o}, {i}, {combine(cur)}, {s.line}); }}")

    # ---- expressions ----
    def binop(self, op, l, lt, r, rt, line):
        if op == "and":
            return f"({l} && {r})"
        if op == "or":
            return f"({l} || {r})"
        if lt == "str" and rt == "str":
            if op == "+":
                return f"vy_str_concat({l}, {r})"
            if op == "==":
                return f"vy_str_eq({l}, {r})"
            if op == "!=":
                return f"(!vy_str_eq({l}, {r}))"
            return f"(strcmp({l}, {r}) {op} 0)"
        if lt == "str" and op == "*":
            return f"vy_s_repeat({l}, {r})"
        if op == "/" and lt == rt == "int":
            return f"vy_idiv({l}, {r}, {line})"
        if op == "%":
            return f"vy_imod({l}, {r}, {line})"
        if op == "/":
            return f"((double)({l}) / (double)({r}))"
        return f"({l} {op} {r})"

    def expr(self, e):
        if isinstance(e, A.IntLit):
            return f"INT64_C({e.value})"
        if isinstance(e, A.FloatLit):
            return repr(e.value)
        if isinstance(e, A.StrLit):
            return c_string(e.value)
        if isinstance(e, A.BoolLit):
            return "true" if e.value else "false"
        if isinstance(e, A.Name):
            return f"v_{e.name}"
        if isinstance(e, A.Unary):
            o = self.expr(e.operand)
            return f"(!{o})" if e.op == "not" else f"(-{o})"
        if isinstance(e, A.Binary):
            return self.binop(e.op, self.expr(e.left), e.left.ty, self.expr(e.right), e.right.ty, e.line)
        if isinstance(e, A.ListLit):
            L = cname(e.ty)
            if not e.elems:
                return f"{L}_new()"
            items = ", ".join(self.expr(x) for x in e.elems)
            return f"{L}_from({len(e.elems)}, ({ctype(e.ty[1])}[]){{{items}}})"
        if isinstance(e, A.Field):
            return f"({self.expr(e.obj)})->f_{e.name}"
        if isinstance(e, A.Index):
            if e.obj.ty == "str":
                return f"vy_str_index({self.expr(e.obj)}, {self.expr(e.index)}, {e.line})"
            return f"{cname(e.obj.ty)}_get({self.expr(e.obj)}, {self.expr(e.index)}, {e.line})"
        if isinstance(e, A.MethodCall):
            return self.method(e)
        if isinstance(e, A.Call):
            return self.call(e)
        raise NotImplementedError(type(e).__name__)

    def method(self, e):
        o = self.expr(e.obj)
        args = [self.expr(a) for a in e.args]
        m = e.method
        if e.obj.ty == "str":
            if m == "split":
                return f"vy_s_split({o}, {args[0]}, {e.line})"
            if m == "replace":
                return f"vy_s_replace({o}, {args[0]}, {args[1]}, {e.line})"
            return f"vy_s_{m}({', '.join([o] + args)})"
        L = cname(e.obj.ty)
        if m in ("pop", "insert", "remove_at"):
            args.append(str(e.line))
        return f"{L}_{m}({', '.join([o] + args)})"

    def call(self, e):
        f = e.func
        args = [self.expr(a) for a in e.args]
        tys = [a.ty for a in e.args]
        if f in self.c.structs:
            return f"S_{f}_new({', '.join(args)})"
        if f in self.c.funcs:
            _, _, extern = self.c.funcs[f]
            return f"{f if extern else 'vy_' + f}({', '.join(args)})"
        if f in ("print", "println"):
            parts = [f"{tostr(t)}({a})" for a, t in zip(args, tys)]
            return f"vy_print({len(parts)}{''.join(', ' + p for p in parts)})"
        if f == "len":
            return f"((int64_t)strlen({args[0]}))" if tys[0] == "str" else f"(({args[0]})->len)"
        if f == "str":
            return f"{tostr(tys[0])}({args[0]})"
        if f == "int":
            if tys[0] == "str":
                return f"vy_str_to_int({args[0]}, {e.line})"
            return f"((int64_t)({args[0]}))"
        if f == "float":
            if tys[0] == "str":
                return f"vy_str_to_float({args[0]}, {e.line})"
            return f"((double)({args[0]}))"
        if f == "input":
            return f"vy_input({args[0] if args else chr(34) * 2})"
        if f == "assert":
            msg = args[1] if len(args) > 1 else c_string("condition fausse")
            return f"vy_assert({args[0]}, {msg}, {e.line})"
        if f == "exit":
            return f"exit((int)({args[0]}))"
        if f == "abs":
            return f"vy_iabs({args[0]})" if tys[0] == "int" else f"fabs({args[0]})"
        if f in ("min", "max"):
            if tys == ["int", "int"]:
                return f"vy_i{f}({args[0]}, {args[1]})"
            return f"f{f}((double)({args[0]}), (double)({args[1]}))"
        if f == "pow":
            return f"pow((double)({args[0]}), (double)({args[1]}))"
        if f == "rand_int":
            return f"vy_rand_int({args[0]}, {args[1]}, {e.line})"
        if f == "clock":
            return "vy_clock()"
        if f in MATH1:
            return f"{f}((double)({args[0]}))"
        raise NotImplementedError(f)


def generate(checker, program):
    return CodeGen(checker).generate(program)
