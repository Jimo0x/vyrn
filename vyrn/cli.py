"""Interface en ligne de commande : vyrn run|build|emit-c|check."""
import argparse
import json
import os
import subprocess
import sys
import tempfile

from . import __version__
from .compiler import CompileFailed, build, diagnostics, exe_name, to_c

RED = "\033[31m" if sys.stderr.isatty() else ""
RESET = "\033[0m" if sys.stderr.isatty() else ""


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def report(errors, path, src):
    for e in errors:
        print(RED + e.format(path, src) + RESET, file=sys.stderr)
    print(f"{len(errors)} erreur(s).", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(prog="vyrn", description="Compilateur du langage Vyrn")
    p.add_argument("--version", action="version", version=f"vyrn {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="compiler et exécuter")
    r.add_argument("file")
    r.add_argument("args", nargs=argparse.REMAINDER)
    b = sub.add_parser("build", help="compiler en exécutable natif")
    b.add_argument("file")
    b.add_argument("-o", "--output")
    b.add_argument("--debug", action="store_true", help="compiler sans optimisation")
    e = sub.add_parser("emit-c", help="afficher le C généré")
    e.add_argument("file")
    c = sub.add_parser("check", help="vérifier sans compiler")
    c.add_argument("file")
    c.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    try:
        src = read(a.file)
    except OSError as err:
        print(f"vyrn: impossible de lire {a.file} : {err.strerror}", file=sys.stderr)
        return 2

    if a.cmd == "check":
        errors = diagnostics(src)
        if a.json:
            print(json.dumps([x.to_dict() for x in errors], ensure_ascii=False))
        elif errors:
            report(errors, a.file, src)
        else:
            print("ok")
        return 1 if errors else 0

    try:
        if a.cmd == "emit-c":
            sys.stdout.write(to_c(src))
            return 0
        if a.cmd == "build":
            out = a.output or exe_name(os.path.splitext(a.file)[0])
            build(src, out, "-O0" if a.debug else "-O2")
            print(f"compilé -> {out}")
            return 0
        with tempfile.TemporaryDirectory(prefix="vyrn-run-") as tmp:
            exe = build(src, exe_name(os.path.join(tmp, "prog")))
            return subprocess.call([exe] + a.args)
    except CompileFailed as err:
        report(err.errors, a.file, src)
        return 1
    except RuntimeError as err:
        print(RED + str(err) + RESET, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
