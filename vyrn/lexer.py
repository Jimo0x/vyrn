"""Lexer Vyrn : transforme le source en jetons, avec gestion de l'indentation."""
from dataclasses import dataclass

from .errors import VyrnError

KEYWORDS = {
    "fn", "let", "var", "if", "elif", "else", "while", "for", "in", "return",
    "break", "continue", "struct", "true", "false", "and", "or", "not",
    "extern", "cinclude", "pass",
}

OPERATORS = [
    "->", "..", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=",
    "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "[", "]", ",", ":", ".",
]

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'"}


@dataclass
class Token:
    kind: str   # NAME, INT, FLOAT, STRING, KW, OP, NEWLINE, INDENT, DEDENT, EOF
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"{self.kind}({self.value!r})@{self.line}:{self.col}"


def tokenize(src: str):
    toks = []
    indents = [0]
    depth = 0  # profondeur de parenthèses : les sauts de ligne y sont ignorés
    lines = src.replace("\r\n", "\n").replace("\t", "    ").split("\n")

    for ln, text in enumerate(lines, start=1):
        i = 0
        n = len(text)
        if depth == 0:
            stripped = text.lstrip(" ")
            if stripped == "" or stripped.startswith("#"):
                continue
            ind = n - len(stripped)
            if ind > indents[-1]:
                indents.append(ind)
                toks.append(Token("INDENT", "", ln, 1))
            else:
                while ind < indents[-1]:
                    indents.pop()
                    toks.append(Token("DEDENT", "", ln, 1))
                if ind != indents[-1]:
                    raise VyrnError("indentation incohérente", ln, ind + 1)
            i = ind

        while i < n:
            c = text[i]
            col = i + 1
            if c == " ":
                i += 1
                continue
            if c == "#":
                break
            if c.isdigit():
                j = i
                while j < n and (text[j].isdigit() or text[j] == "_"):
                    j += 1
                is_float = False
                if j + 1 < n and text[j] == "." and text[j + 1].isdigit():
                    is_float = True
                    j += 1
                    while j < n and (text[j].isdigit() or text[j] == "_"):
                        j += 1
                if j < n and text[j] in "eE":
                    k = j + 1
                    if k < n and text[k] in "+-":
                        k += 1
                    if k < n and text[k].isdigit():
                        is_float = True
                        j = k
                        while j < n and text[j].isdigit():
                            j += 1
                toks.append(Token("FLOAT" if is_float else "INT", text[i:j].replace("_", ""), ln, col))
                i = j
                continue
            if c.isalpha() or c == "_":
                j = i
                while j < n and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                word = text[i:j]
                toks.append(Token("KW" if word in KEYWORDS else "NAME", word, ln, col))
                i = j
                continue
            if c in "\"'":
                q = c
                j = i + 1
                out = []
                while True:
                    if j >= n:
                        raise VyrnError("chaîne non terminée", ln, col)
                    ch = text[j]
                    if ch == q:
                        j += 1
                        break
                    if ch == "\\":
                        if j + 1 >= n:
                            raise VyrnError("échappement incomplet", ln, j + 1)
                        e = text[j + 1]
                        if e not in ESCAPES:
                            raise VyrnError(f"échappement inconnu '\\{e}'", ln, j + 1)
                        out.append(ESCAPES[e])
                        j += 2
                        continue
                    out.append(ch)
                    j += 1
                toks.append(Token("STRING", "".join(out), ln, col))
                i = j
                continue
            for op in OPERATORS:
                if text.startswith(op, i):
                    if op in "([":
                        depth += 1
                    elif op in ")]":
                        depth = max(0, depth - 1)
                    toks.append(Token("OP", op, ln, col))
                    i += len(op)
                    break
            else:
                raise VyrnError(f"caractère inattendu '{c}'", ln, col)

        if depth == 0:
            toks.append(Token("NEWLINE", "", ln, n + 1))

    last = len(lines)
    while len(indents) > 1:
        indents.pop()
        toks.append(Token("DEDENT", "", last, 1))
    toks.append(Token("EOF", "", last, 1))
    return toks
