"""Vérification de types et résolution des noms.

Types internes :
  'int' 'float' 'bool' 'str' 'void'  |  ('list', T)  |  ('struct', nom)
"""
from . import ast as A
from .errors import VyrnError

PRIMS = {"int", "float", "bool", "str", "void"}
NUMERIC = {"int", "float"}

# fonctions mathématiques intégrées (float -> float), mappées sur <math.h>
MATH1 = {"sqrt", "sin", "cos", "tan", "floor", "ceil", "exp", "log", "fabs"}
BUILTINS = {"print", "println", "len", "str", "int", "float", "input", "assert",
            "exit", "abs", "min", "max", "pow", "rand_int", "clock"} | MATH1

LIST_METHODS = {"push", "pop", "clear", "insert", "remove_at", "contains", "index_of", "copy", "reverse"}
STR_METHODS = {"upper", "lower", "contains", "starts_with", "ends_with", "find",
               "slice", "trim", "split", "replace", "repeat"}


def type_name(t):
    if isinstance(t, tuple):
        if t[0] == "list":
            return f"list[{type_name(t[1])}]"
        return t[1]
    return t


class Checker:
    def __init__(self, program):
        self.program = program
        self.structs = {}      # nom -> [(champ, type)]
        self.funcs = {}        # nom -> (params, ret, extern)
        self.includes = []
        self.list_types = set()
        self.errors = []
        self.scopes = []
        self.current_ret = None
        self.loop_depth = 0

    def err(self, msg, node):
        raise VyrnError(msg, node.line, node.col)

    # ---- types ----
    def resolve(self, tr):
        if tr is None:
            return "void"
        if tr.name == "list":
            if len(tr.args) != 1:
                self.err("list attend un type d'élément : list[T]", tr)
            t = ("list", self.resolve(tr.args[0]))
            if t[1] == "void":
                self.err("list[void] n'a pas de sens", tr)
            self.list_types.add(t)
            return t
        if tr.args:
            self.err(f"le type '{tr.name}' ne prend pas de paramètre", tr)
        if tr.name in PRIMS:
            return tr.name
        if tr.name in self.structs:
            return ("struct", tr.name)
        self.err(f"type inconnu '{tr.name}'", tr)

    def note_type(self, t):
        if isinstance(t, tuple) and t[0] == "list":
            self.list_types.add(t)
            self.note_type(t[1])

    # ---- portée ----
    def push(self):
        self.scopes.append({})

    def pop(self):
        self.scopes.pop()

    def declare(self, name, ty, mutable, node):
        if name in self.scopes[-1]:
            self.err(f"'{name}' est déjà déclaré dans ce bloc", node)
        self.scopes[-1][name] = (ty, mutable)

    def lookup(self, name, node):
        for s in reversed(self.scopes):
            if name in s:
                return s[name]
        self.err(f"nom inconnu '{name}'", node)

    # ---- passe principale ----
    def check(self):
        items = self.program.items
        for it in items:
            if isinstance(it, A.CInclude):
                self.includes.append(it.header)
            elif isinstance(it, A.StructDecl):
                if it.name in self.structs or it.name in PRIMS:
                    self.errors.append(VyrnError(f"struct '{it.name}' déjà définie", it.line, it.col))
                self.structs[it.name] = []
        for it in items:
            try:
                if isinstance(it, A.StructDecl):
                    seen = set()
                    for f in it.fields:
                        if f.name in seen:
                            self.err(f"champ '{f.name}' dupliqué", f)
                        seen.add(f.name)
                        self.structs[it.name].append((f.name, self.resolve(f.type)))
            except VyrnError as e:
                self.errors.append(e)
        for it in items:
            try:
                if isinstance(it, A.FnDecl):
                    if it.name in self.funcs or it.name in BUILTINS or it.name in self.structs:
                        self.err(f"'{it.name}' est déjà défini", it)
                    params = [(p.name, self.resolve(p.type)) for p in it.params]
                    self.funcs[it.name] = (params, self.resolve(it.ret), it.extern)
            except VyrnError as e:
                self.errors.append(e)
        if "main" not in self.funcs:
            self.errors.append(VyrnError("fonction 'main' introuvable : ajoute `fn main():`", 1, 1))
        else:
            params, ret, _ = self.funcs["main"]
            if params or ret not in ("void", "int"):
                self.errors.append(VyrnError("main doit être `fn main()` ou `fn main() -> int`", 1, 1))
        for it in items:
            if isinstance(it, A.FnDecl) and not it.extern and it.name in self.funcs:
                self.check_fn(it)
        return self.errors

    def check_fn(self, fn):
        params, ret, _ = self.funcs[fn.name]
        self.current_ret = ret
        self.scopes = [{}]
        for (pname, pty), p in zip(params, fn.params):
            try:
                self.declare(pname, pty, True, p)
            except VyrnError as e:
                self.errors.append(e)
        self.block(fn.body, new_scope=False)

    def block(self, stmts, new_scope=True):
        if new_scope:
            self.push()
        for s in stmts:
            try:
                self.stmt(s)
            except VyrnError as e:
                self.errors.append(e)
        if new_scope:
            self.pop()

    def assignable(self, src, dst):
        return src == dst or (src == "int" and dst == "float")

    def coerce(self, expr, dst, node, what):
        if not self.assignable(expr.ty, dst):
            self.err(f"{what} : attendu {type_name(dst)}, trouvé {type_name(expr.ty)}", node)

    # ---- instructions ----
    def stmt(self, s):
        if isinstance(s, A.Let):
            declared = self.resolve(s.type) if s.type else None
            self.expr(s.value, expected=declared)
            ty = declared or s.value.ty
            if ty == "void":
                self.err("impossible de stocker une valeur void", s)
            if declared:
                self.coerce(s.value, declared, s, f"valeur de '{s.name}'")
            self.declare(s.name, ty, s.mutable, s)
            s.resolved_type = ty
        elif isinstance(s, A.Assign):
            t = s.target
            if isinstance(t, A.Name):
                ty, mutable = self.lookup(t.name, t)
                if not mutable:
                    self.err(f"'{t.name}' est déclaré avec let (immuable) ; utilise var", t)
                t.ty = ty
            else:
                self.expr(t)
            self.expr(s.value, expected=t.ty)
            if s.op == "=":
                self.coerce(s.value, t.ty, s, "affectation")
            else:
                op = s.op[0]
                rt = self.binary_type(op, t.ty, s.value.ty, s)
                if not self.assignable(rt, t.ty):
                    self.err(f"'{s.op}' produirait {type_name(rt)} dans une variable {type_name(t.ty)}", s)
        elif isinstance(s, A.If):
            for cond, body in s.branches:
                self.expr(cond)
                if cond.ty != "bool":
                    self.err(f"la condition doit être bool, trouvé {type_name(cond.ty)}", cond)
                self.block(body)
            if s.orelse:
                self.block(s.orelse)
        elif isinstance(s, A.While):
            self.expr(s.cond)
            if s.cond.ty != "bool":
                self.err(f"la condition doit être bool, trouvé {type_name(s.cond.ty)}", s.cond)
            self.loop(s.body)
        elif isinstance(s, A.ForRange):
            for e in (s.start, s.end):
                self.expr(e)
                if e.ty != "int":
                    self.err("les bornes d'un intervalle doivent être int", e)
            self.push()
            self.declare(s.var, "int", False, s)
            self.loop(s.body)
            self.pop()
        elif isinstance(s, A.ForEach):
            self.expr(s.iterable)
            it = s.iterable.ty
            if isinstance(it, tuple) and it[0] == "list":
                elem = it[1]
            elif it == "str":
                elem = "str"
            else:
                self.err(f"impossible d'itérer sur {type_name(it)}", s.iterable)
            s.elem_type = elem
            self.push()
            self.declare(s.var, elem, False, s)
            self.loop(s.body)
            self.pop()
        elif isinstance(s, A.Return):
            if s.value is None:
                if self.current_ret != "void":
                    self.err(f"return doit renvoyer une valeur {type_name(self.current_ret)}", s)
            else:
                if self.current_ret == "void":
                    self.err("cette fonction ne renvoie rien (pas de -> type)", s)
                self.expr(s.value, expected=self.current_ret)
                self.coerce(s.value, self.current_ret, s, "valeur de retour")
        elif isinstance(s, (A.Break, A.Continue)):
            if self.loop_depth == 0:
                self.err("break/continue hors d'une boucle", s)
        elif isinstance(s, A.ExprStmt):
            self.expr(s.expr)
        elif isinstance(s, A.Pass):
            pass

    def loop(self, body):
        self.loop_depth += 1
        self.block(body)
        self.loop_depth -= 1

    # ---- expressions ----
    def binary_type(self, op, lt, rt, node):
        if op in ("and", "or"):
            if lt != "bool" or rt != "bool":
                self.err(f"'{op}' attend deux bool", node)
            return "bool"
        if op in ("==", "!="):
            if lt in NUMERIC and rt in NUMERIC:
                return "bool"
            if lt != rt or isinstance(lt, tuple):
                self.err(f"impossible de comparer {type_name(lt)} et {type_name(rt)}", node)
            return "bool"
        if op in ("<", "<=", ">", ">="):
            if (lt in NUMERIC and rt in NUMERIC) or (lt == rt == "str"):
                return "bool"
            self.err(f"impossible d'ordonner {type_name(lt)} et {type_name(rt)}", node)
        if op == "+" and lt == rt == "str":
            return "str"
        if op == "*" and lt == "str" and rt == "int":
            return "str"
        if op == "%":
            if lt == rt == "int":
                return "int"
            self.err("'%' attend deux int", node)
        if op in ("+", "-", "*", "/"):
            if lt in NUMERIC and rt in NUMERIC:
                return "float" if "float" in (lt, rt) else "int"
        self.err(f"opérateur '{op}' invalide entre {type_name(lt)} et {type_name(rt)}", node)

    def expr(self, e, expected=None):
        e.ty = self._expr(e, expected)
        self.note_type(e.ty)
        return e.ty

    def _expr(self, e, expected):
        if isinstance(e, A.IntLit):
            if not -(2 ** 63) <= e.value < 2 ** 63:
                self.err("entier trop grand pour int (64 bits)", e)
            return "int"
        if isinstance(e, A.FloatLit):
            return "float"
        if isinstance(e, A.StrLit):
            return "str"
        if isinstance(e, A.BoolLit):
            return "bool"
        if isinstance(e, A.Name):
            return self.lookup(e.name, e)[0]
        if isinstance(e, A.Unary):
            t = self.expr(e.operand)
            if e.op == "not":
                if t != "bool":
                    self.err("'not' attend un bool", e)
                return "bool"
            if t not in NUMERIC:
                self.err(f"'-' attend un nombre, trouvé {type_name(t)}", e)
            return t
        if isinstance(e, A.Binary):
            lt = self.expr(e.left)
            rt = self.expr(e.right)
            return self.binary_type(e.op, lt, rt, e)
        if isinstance(e, A.ListLit):
            if not e.elems:
                if isinstance(expected, tuple) and expected[0] == "list":
                    return expected
                self.err("liste vide : précise le type, ex. `let xs: list[int] = []`", e)
            want = expected[1] if isinstance(expected, tuple) and expected[0] == "list" else None
            first = self.expr(e.elems[0], expected=want)
            elem = want or first
            if elem == "int" and any(self.expr(x) == "float" for x in e.elems[1:]):
                elem = "float"
            for x in e.elems:
                if x.ty is None:
                    self.expr(x, expected=elem)
                self.coerce(x, elem, x, "élément de liste")
            return ("list", elem)
        if isinstance(e, A.Field):
            ot = self.expr(e.obj)
            if not (isinstance(ot, tuple) and ot[0] == "struct"):
                self.err(f"{type_name(ot)} n'a pas de champ '{e.name}'", e)
            for fname, fty in self.structs[ot[1]]:
                if fname == e.name:
                    return fty
            self.err(f"la struct {ot[1]} n'a pas de champ '{e.name}'", e)
        if isinstance(e, A.Index):
            ot = self.expr(e.obj)
            if self.expr(e.index) != "int":
                self.err("l'indice doit être int", e.index)
            if isinstance(ot, tuple) and ot[0] == "list":
                return ot[1]
            if ot == "str":
                return "str"
            self.err(f"impossible d'indexer {type_name(ot)}", e)
        if isinstance(e, A.MethodCall):
            return self.method(e)
        if isinstance(e, A.Call):
            return self.call(e, expected)
        self.err("expression non supportée", e)

    def args_types(self, e):
        return [self.expr(a) for a in e.args]

    def arity(self, e, n):
        if len(e.args) != n:
            self.err(f"'{e.func if isinstance(e, A.Call) else e.method}' attend {n} argument(s), reçu {len(e.args)}", e)

    def method(self, e):
        ot = self.expr(e.obj)
        m = e.method
        if isinstance(ot, tuple) and ot[0] == "list":
            elem = ot[1]
            sig = {
                "push": ([elem], "void"), "pop": ([], elem), "clear": ([], "void"),
                "insert": (["int", elem], "void"), "remove_at": (["int"], elem),
                "contains": ([elem], "bool"), "index_of": ([elem], "int"),
                "copy": ([], ot), "reverse": ([], "void"),
            }
            if m not in sig:
                self.err(f"list n'a pas de méthode '{m}' (disponibles : {', '.join(sorted(LIST_METHODS))})", e)
            if m in ("contains", "index_of") and isinstance(elem, tuple):
                self.err(f"'{m}' n'est disponible que pour les listes de valeurs simples", e)
        elif ot == "str":
            sig = {
                "upper": ([], "str"), "lower": ([], "str"), "trim": ([], "str"),
                "contains": (["str"], "bool"), "starts_with": (["str"], "bool"),
                "ends_with": (["str"], "bool"), "find": (["str"], "int"),
                "slice": (["int", "int"], "str"), "split": (["str"], ("list", "str")),
                "replace": (["str", "str"], "str"), "repeat": (["int"], "str"),
            }
            if m not in sig:
                self.err(f"str n'a pas de méthode '{m}' (disponibles : {', '.join(sorted(STR_METHODS))})", e)
        else:
            self.err(f"{type_name(ot)} n'a pas de méthode '{m}'", e)
        params, ret = sig[m]
        self.arity(e, len(params))
        for a, p in zip(e.args, params):
            self.expr(a, expected=p)
            self.coerce(a, p, a, f"argument de {m}")
        return ret

    def call(self, e, expected):
        f = e.func
        if f in self.structs:
            fields = self.structs[f]
            if len(e.args) != len(fields):
                self.err(f"{f}(...) attend {len(fields)} champ(s), reçu {len(e.args)}", e)
            for a, (fname, fty) in zip(e.args, fields):
                self.expr(a, expected=fty)
                self.coerce(a, fty, a, f"champ '{fname}'")
            return ("struct", f)
        if f in self.funcs:
            params, ret, _ = self.funcs[f]
            if len(e.args) != len(params):
                self.err(f"'{f}' attend {len(params)} argument(s), reçu {len(e.args)}", e)
            for a, (pname, pty) in zip(e.args, params):
                self.expr(a, expected=pty)
                self.coerce(a, pty, a, f"argument '{pname}' de {f}")
            return ret
        if f in ("print", "println"):
            for a in e.args:
                if self.expr(a) == "void":
                    self.err("impossible d'afficher une valeur void", a)
            return "void"
        if f == "len":
            self.arity(e, 1)
            t = self.expr(e.args[0])
            if not (t == "str" or (isinstance(t, tuple) and t[0] == "list")):
                self.err(f"len() attend str ou list, trouvé {type_name(t)}", e)
            return "int"
        if f == "str":
            self.arity(e, 1)
            if self.expr(e.args[0]) == "void":
                self.err("str() d'une valeur void", e)
            return "str"
        if f in ("int", "float"):
            self.arity(e, 1)
            t = self.expr(e.args[0])
            if t not in ("int", "float", "str", "bool"):
                self.err(f"{f}() ne convertit pas {type_name(t)}", e)
            return f
        if f == "input":
            if len(e.args) > 1:
                self.err("input() prend au plus un message", e)
            for a in e.args:
                if self.expr(a) != "str":
                    self.err("le message de input() doit être str", a)
            return "str"
        if f == "assert":
            if len(e.args) not in (1, 2):
                self.err("assert(condition) ou assert(condition, message)", e)
            if self.expr(e.args[0]) != "bool":
                self.err("assert attend un bool", e.args[0])
            if len(e.args) == 2 and self.expr(e.args[1]) != "str":
                self.err("le message d'assert doit être str", e.args[1])
            return "void"
        if f == "exit":
            self.arity(e, 1)
            if self.expr(e.args[0]) != "int":
                self.err("exit attend un int", e)
            return "void"
        if f == "abs":
            self.arity(e, 1)
            t = self.expr(e.args[0])
            if t not in NUMERIC:
                self.err("abs attend un nombre", e)
            return t
        if f in ("min", "max"):
            self.arity(e, 2)
            a, b = self.args_types(e)
            if a not in NUMERIC or b not in NUMERIC:
                self.err(f"{f} attend deux nombres", e)
            return "float" if "float" in (a, b) else "int"
        if f == "pow":
            self.arity(e, 2)
            for a in e.args:
                if self.expr(a) not in NUMERIC:
                    self.err("pow attend des nombres", a)
            return "float"
        if f == "rand_int":
            self.arity(e, 2)
            for a in e.args:
                if self.expr(a) != "int":
                    self.err("rand_int(min, max) attend deux int", a)
            return "int"
        if f == "clock":
            self.arity(e, 0)
            return "float"
        if f in MATH1:
            self.arity(e, 1)
            if self.expr(e.args[0]) not in NUMERIC:
                self.err(f"{f} attend un nombre", e)
            return "float"
        self.err(f"fonction inconnue '{f}'", e)


def check(program):
    c = Checker(program)
    errors = c.check()
    return c, errors
