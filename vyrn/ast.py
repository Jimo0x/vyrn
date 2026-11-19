"""Nœuds de l'arbre syntaxique Vyrn."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Node:
    line: int
    col: int


# ---- types écrits dans le source ----
@dataclass
class TypeRef(Node):
    name: str
    args: list = field(default_factory=list)


# ---- déclarations ----
@dataclass
class Param(Node):
    name: str
    type: TypeRef


@dataclass
class FnDecl(Node):
    name: str
    params: list
    ret: Optional[TypeRef]
    body: list
    extern: bool = False


@dataclass
class StructDecl(Node):
    name: str
    fields: list  # list[Param]


@dataclass
class CInclude(Node):
    header: str


@dataclass
class Program:
    items: list


# ---- instructions ----
@dataclass
class Let(Node):
    name: str
    mutable: bool
    type: Optional[TypeRef]
    value: Any


@dataclass
class Assign(Node):
    target: Any
    op: str
    value: Any


@dataclass
class If(Node):
    branches: list  # [(cond, body)]
    orelse: Optional[list]


@dataclass
class While(Node):
    cond: Any
    body: list


@dataclass
class ForRange(Node):
    var: str
    start: Any
    end: Any
    body: list


@dataclass
class ForEach(Node):
    var: str
    iterable: Any
    body: list


@dataclass
class Return(Node):
    value: Any


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


@dataclass
class Pass(Node):
    pass


@dataclass
class ExprStmt(Node):
    expr: Any


# ---- expressions (le vérificateur remplit .ty) ----
@dataclass
class Expr(Node):
    def __post_init__(self):
        self.ty = None


@dataclass
class IntLit(Expr):
    value: int


@dataclass
class FloatLit(Expr):
    value: float


@dataclass
class StrLit(Expr):
    value: str


@dataclass
class BoolLit(Expr):
    value: bool


@dataclass
class Name(Expr):
    name: str


@dataclass
class Binary(Expr):
    op: str
    left: Any
    right: Any


@dataclass
class Unary(Expr):
    op: str
    operand: Any


@dataclass
class Call(Expr):
    func: str
    args: list


@dataclass
class MethodCall(Expr):
    obj: Any
    method: str
    args: list


@dataclass
class Field(Expr):
    obj: Any
    name: str


@dataclass
class Index(Expr):
    obj: Any
    index: Any


@dataclass
class ListLit(Expr):
    elems: list
