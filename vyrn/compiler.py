"""Pipeline complet : source -> C -> exécutable natif."""
import os
import shutil
import subprocess
import sys
import tempfile

from .checker import check
from .codegen import generate
from .errors import VyrnError
from .parser import parse


class CompileFailed(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(e.msg for e in errors))
        self.errors = errors


def diagnostics(src):
    """Renvoie la liste des erreurs (vide si le programme est valide)."""
    try:
        program = parse(src)
    except VyrnError as e:
        return [e]
    _, errors = check(program)
    return sorted(errors, key=lambda e: (e.line, e.col))


def to_c(src):
    try:
        program = parse(src)
    except VyrnError as e:
        raise CompileFailed([e])
    checker, errors = check(program)
    if errors:
        raise CompileFailed(sorted(errors, key=lambda e: (e.line, e.col)))
    return generate(checker, program)


def find_cc():
    env = os.environ.get("VYRN_CC")
    if env:
        return env
    for cc in ("cc", "gcc", "clang"):
        if shutil.which(cc):
            return cc
    raise RuntimeError("aucun compilateur C trouvé (installe gcc ou clang, ou définis VYRN_CC)")


def build(src, output, opt="-O2"):
    c_code = to_c(src)
    with tempfile.TemporaryDirectory(prefix="vyrn-") as tmp:
        c_path = os.path.join(tmp, "prog.c")
        with open(c_path, "w", encoding="utf-8") as f:
            f.write(c_code)
        cmd = [find_cc(), opt, "-std=c11", "-w", c_path, "-o", output, "-lm"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("le compilateur C a échoué :\n" + r.stderr)
    return output


def exe_name(base):
    return base + (".exe" if sys.platform == "win32" else "")
