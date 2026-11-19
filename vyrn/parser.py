"""Parser récursif descendant pour Vyrn."""
from . import ast as A
from .errors import VyrnError
from .lexer import tokenize

COMPARE = {"==", "!=", "<", "<=", ">", ">="}
ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%="}


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    # ---- utilitaires ----
    @property
    def tok(self):
        return self.toks[self.pos]

    def peek(self, k=1):
        return self.toks[min(self.pos + k, len(self.toks) - 1)]

    def at(self, kind, value=None):
        t = self.tok
        return t.kind == kind and (value is None or t.value == value)

    def at_op(self, value):
        return self.at("OP", value)

    def at_kw(self, value):
        return self.at("KW", value)

    def advance(self):
        t = self.tok
        self.pos += 1
        return t

    def expect(self, kind, value=None, what=None):
        if not self.at(kind, value):
            t = self.tok
            want = what or (f"'{value}'" if value else kind.lower())
            got = t.value or t.kind.lower()
            raise VyrnError(f"attendu {want}, trouvé '{got}'", t.line, t.col)
        return self.advance()

    def name(self, what="un identifiant"):
        return self.expect("NAME", what=what)

    # ---- programme ----
    def program(self):
        items = []
        while not self.at("EOF"):
            if self.at("NEWLINE"):
                self.advance()
                continue
            items.append(self.item())
        return A.Program(items)

    def item(self):
        t = self.tok
        if self.at_kw("fn"):
            return self.fn_decl()
        if self.at_kw("extern"):
            self.advance()
            f = self.fn_signature(t)
            f.extern = True
            self.expect("NEWLINE", what="fin de ligne")
            return f
        if self.at_kw("struct"):
            return self.struct_decl()
        if self.at_kw("cinclude"):
            self.advance()
            h = self.expect("STRING", what="un nom d'en-tête entre guillemets")
            self.expect("NEWLINE", what="fin de ligne")
            return A.CInclude(t.line, t.col, h.value)
        raise VyrnError(f"déclaration attendue (fn, struct, extern, cinclude), trouvé '{t.value or t.kind.lower()}'", t.line, t.col)

    def fn_signature(self, start):
        self.expect("KW", "fn")
        name = self.name("un nom de fonction").value
        self.expect("OP", "(")
        params = []
        while not self.at_op(")"):
            p = self.name("un nom de paramètre")
            self.expect("OP", ":")
            params.append(A.Param(p.line, p.col, p.value, self.type_ref()))
            if not self.at_op(")"):
                self.expect("OP", ",")
        self.expect("OP", ")")
        ret = None
        if self.at_op("->"):
            self.advance()
            ret = self.type_ref()
        return A.FnDecl(start.line, start.col, name, params, ret, [])

    def fn_decl(self):
        f = self.fn_signature(self.tok)
        f.body = self.block()
        return f

    def struct_decl(self):
        t = self.advance()
        name = self.name("un nom de struct").value
        self.expect("OP", ":")
        self.expect("NEWLINE", what="fin de ligne")
        self.expect("INDENT", what="un bloc indenté")
        fields = []
        while not self.at("DEDENT"):
            if self.at("NEWLINE"):
                self.advance()
                continue
            if self.at_kw("pass"):
                self.advance()
                self.expect("NEWLINE", what="fin de ligne")
                continue
            f = self.name("un nom de champ")
            self.expect("OP", ":")
            fields.append(A.Param(f.line, f.col, f.value, self.type_ref()))
            self.expect("NEWLINE", what="fin de ligne")
        self.advance()
        return A.StructDecl(t.line, t.col, name, fields)

    def type_ref(self):
        t = self.name("un type")
        args = []
        if self.at_op("["):
            self.advance()
            args.append(self.type_ref())
            while self.at_op(","):
                self.advance()
                args.append(self.type_ref())
            self.expect("OP", "]")
        return A.TypeRef(t.line, t.col, t.value, args)

    # ---- blocs et instructions ----
    def block(self):
        self.expect("OP", ":")
        if not self.at("NEWLINE"):  # bloc sur une ligne : `if x: return 1`
            return [self.simple_stmt()]
        self.advance()
        self.expect("INDENT", what="un bloc indenté")
        body = []
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.at("NEWLINE"):
                self.advance()
                continue
            body.append(self.statement())
        self.advance()
        return body

    def statement(self):
        t = self.tok
        if self.at_kw("if"):
            return self.if_stmt()
        if self.at_kw("while"):
            self.advance()
            cond = self.expr()
            return A.While(t.line, t.col, cond, self.block())
        if self.at_kw("for"):
            self.advance()
            var = self.name("une variable de boucle").value
            self.expect("KW", "in")
            first = self.expr()
            if self.at_op(".."):
                self.advance()
                end = self.expr()
                return A.ForRange(t.line, t.col, var, first, end, self.block())
            return A.ForEach(t.line, t.col, var, first, self.block())
        return self.simple_stmt()

    def simple_stmt(self):
        s = self.small_stmt()
        self.expect("NEWLINE", what="fin de ligne")
        return s

    def small_stmt(self):
        t = self.tok
        if self.at_kw("let") or self.at_kw("var"):
            mutable = self.advance().value == "var"
            name = self.name("un nom de variable").value
            ty = None
            if self.at_op(":"):
                self.advance()
                ty = self.type_ref()
            self.expect("OP", "=")
            return A.Let(t.line, t.col, name, mutable, ty, self.expr())
        if self.at_kw("return"):
            self.advance()
            val = None if self.at("NEWLINE") else self.expr()
            return A.Return(t.line, t.col, val)
        if self.at_kw("break"):
            self.advance()
            return A.Break(t.line, t.col)
        if self.at_kw("continue"):
            self.advance()
            return A.Continue(t.line, t.col)
        if self.at_kw("pass"):
            self.advance()
            return A.Pass(t.line, t.col)
        e = self.expr()
        if self.tok.kind == "OP" and self.tok.value in ASSIGN_OPS:
            op = self.advance().value
            if not isinstance(e, (A.Name, A.Field, A.Index)):
                raise VyrnError("cible d'affectation invalide", e.line, e.col)
            return A.Assign(t.line, t.col, e, op, self.expr())
        return A.ExprStmt(t.line, t.col, e)

    def if_stmt(self):
        t = self.advance()
        branches = [(self.expr(), self.block())]
        orelse = None
        while self.at_kw("elif"):
            self.advance()
            branches.append((self.expr(), self.block()))
        if self.at_kw("else"):
            self.advance()
            orelse = self.block()
        return A.If(t.line, t.col, branches, orelse)

    # ---- expressions ----
    def expr(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.at_kw("or"):
            t = self.advance()
            left = A.Binary(t.line, t.col, "or", left, self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.at_kw("and"):
            t = self.advance()
            left = A.Binary(t.line, t.col, "and", left, self.not_expr())
        return left

    def not_expr(self):
        if self.at_kw("not"):
            t = self.advance()
            return A.Unary(t.line, t.col, "not", self.not_expr())
        return self.comparison()

    def comparison(self):
        left = self.additive()
        if self.tok.kind == "OP" and self.tok.value in COMPARE:
            t = self.advance()
            left = A.Binary(t.line, t.col, t.value, left, self.additive())
            if self.tok.kind == "OP" and self.tok.value in COMPARE:
                raise VyrnError("comparaisons enchaînées non supportées, utilise 'and'", self.tok.line, self.tok.col)
        return left

    def additive(self):
        left = self.term()
        while self.tok.kind == "OP" and self.tok.value in ("+", "-"):
            t = self.advance()
            left = A.Binary(t.line, t.col, t.value, left, self.term())
        return left

    def term(self):
        left = self.unary()
        while self.tok.kind == "OP" and self.tok.value in ("*", "/", "%"):
            t = self.advance()
            left = A.Binary(t.line, t.col, t.value, left, self.unary())
        return left

    def unary(self):
        if self.at_op("-"):
            t = self.advance()
            return A.Unary(t.line, t.col, "-", self.unary())
        return self.postfix()

    def args(self):
        self.expect("OP", "(")
        out = []
        while not self.at_op(")"):
            out.append(self.expr())
            if not self.at_op(")"):
                self.expect("OP", ",")
        self.expect("OP", ")")
        return out

    def postfix(self):
        e = self.primary()
        while True:
            if self.at_op("."):
                self.advance()
                n = self.name("un nom de champ ou de méthode")
                if self.at_op("("):
                    e = A.MethodCall(n.line, n.col, e, n.value, self.args())
                else:
                    e = A.Field(n.line, n.col, e, n.value)
            elif self.at_op("["):
                t = self.advance()
                idx = self.expr()
                self.expect("OP", "]")
                e = A.Index(t.line, t.col, e, idx)
            else:
                return e

    def primary(self):
        t = self.tok
        if t.kind == "INT":
            self.advance()
            return A.IntLit(t.line, t.col, int(t.value))
        if t.kind == "FLOAT":
            self.advance()
            return A.FloatLit(t.line, t.col, float(t.value))
        if t.kind == "STRING":
            self.advance()
            return A.StrLit(t.line, t.col, t.value)
        if self.at_kw("true") or self.at_kw("false"):
            self.advance()
            return A.BoolLit(t.line, t.col, t.value == "true")
        if t.kind == "NAME":
            self.advance()
            if self.at_op("("):
                return A.Call(t.line, t.col, t.value, self.args())
            return A.Name(t.line, t.col, t.value)
        if self.at_op("("):
            self.advance()
            e = self.expr()
            self.expect("OP", ")")
            return e
        if self.at_op("["):
            self.advance()
            elems = []
            while not self.at_op("]"):
                elems.append(self.expr())
                if not self.at_op("]"):
                    self.expect("OP", ",")
            self.expect("OP", "]")
            return A.ListLit(t.line, t.col, elems)
        raise VyrnError(f"expression attendue, trouvé '{t.value or t.kind.lower()}'", t.line, t.col)


def parse(src: str) -> A.Program:
    return Parser(tokenize(src)).program()
