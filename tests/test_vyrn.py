import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vyrn import CompileFailed, build, diagnostics  # noqa: E402
from vyrn.compiler import exe_name  # noqa: E402


def run(src, stdin=""):
    src = textwrap.dedent(src)
    with tempfile.TemporaryDirectory() as tmp:
        exe = build(src, exe_name(os.path.join(tmp, "p")), "-O0")
        r = subprocess.run([exe], input=stdin, capture_output=True, text=True, timeout=20)
        return r.returncode, r.stdout, r.stderr


def errors(src):
    return [e.msg for e in diagnostics(textwrap.dedent(src))]


class Programs(unittest.TestCase):
    def out(self, src, expected, stdin=""):
        code, out, err = run(src, stdin)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, textwrap.dedent(expected).lstrip("\n"))

    def test_hello(self):
        self.out('fn main():\n    print("bonjour", 42, 1.5, true)\n', "bonjour 42 1.5 true\n")

    def test_arith(self):
        self.out("""
            fn main():
                print(7 / 2, 7 % 3, 7.0 / 2, 2 + 3 * 4, -(4 - 10))
                print(1 + 2.5, min(3, 9), max(2.0, 1), abs(-5), pow(2, 10))
        """, "3 1 3.5 14 6\n3.5 3 2.0 5 1024.0\n")

    def test_control_flow(self):
        self.out("""
            fn classe(n: int) -> str:
                if n < 0:
                    return "neg"
                elif n == 0:
                    return "zero"
                else:
                    return "pos"

            fn main():
                print(classe(-3), classe(0), classe(8))
                var i = 0
                while true:
                    i += 1
                    if i == 3: continue
                    if i > 5: break
                    print(i)
        """, "neg zero pos\n1\n2\n4\n5\n")

    def test_lists(self):
        self.out("""
            fn main():
                var xs = [3, 1, 2]
                xs.push(10)
                xs[0] = 7
                xs[1] += 5
                print(xs, len(xs), xs[-1])
                print(xs.pop(), xs.contains(2), xs.index_of(6))
                xs.insert(0, 99)
                xs.reverse()
                let first = xs.remove_at(0)
                print(xs, first)
                let grid: list[list[int]] = [[1, 2], [3]]
                grid[1].push(4)
                print(grid)
                let fs = [1, 2.5]
                print(fs)
                let names = ["a", "b"]
                print(names)
        """, "[7, 6, 2, 10] 4 10\n10 true 1\n[6, 7, 99] 2\n[[1, 2], [3, 4]]\n[1.0, 2.5]\n[\"a\", \"b\"]\n")

    def test_strings(self):
        self.out("""
            fn main():
                let s = "  Vyrn Rocks  ".trim()
                print(s.upper(), s.lower(), len(s), s[0], s[-1])
                print(s.contains("Ro"), s.starts_with("Vy"), s.ends_with("x"), s.find("R"))
                print(s.slice(0, 4), s.replace("Rocks", "rules"), "ab" * 3)
                print("a,b,c".split(","), "abc" < "abd", "x" == "x")
                for c in "hé":
                    pass
                print(str(12) + str(true) + str(0.5), int("42") + 1, float("2.5"))
        """, "VYRN ROCKS vyrn rocks 10 V s\ntrue true false 5\nVyrn Vyrn rules ababab\n[\"a\", \"b\", \"c\"] true true\n12true0.5 43 2.5\n")

    def test_structs(self):
        self.out("""
            struct Compte:
                nom: str
                solde: float
                ops: list[float]

            fn deposer(c: Compte, m: float):
                c.solde += m
                c.ops.push(m)

            fn main():
                let c = Compte("Jimo", 0, [])
                deposer(c, 50)
                deposer(c, 25.5)
                print(c.nom, c.solde, c.ops)
                print(c)
        """, "Jimo 75.5 [50.0, 25.5]\nCompte(nom=\"Jimo\", solde=75.5, ops=[50.0, 25.5])\n")

    def test_recursion_and_main_int(self):
        code, out, _ = run("""
            fn fact(n: int) -> int:
                if n <= 1: return 1
                return n * fact(n - 1)

            fn main() -> int:
                print(fact(20))
                return 3
        """)
        self.assertEqual((code, out), (3, "2432902008176640000\n"))

    def test_input(self):
        self.out("""
            fn main():
                let nom = input("nom ? ")
                print("salut", nom)
        """, "nom ? salut Ada\n", stdin="Ada\n")

    def test_c_interop(self):
        self.out("""
            cinclude "stdlib.h"
            extern fn atoi(s: str) -> int

            fn main():
                print(atoi("123") * 2, sqrt(16), floor(2.7))
        """, "246 4.0 2.0\n")

    def test_runtime_errors(self):
        code, _, err = run("fn main():\n    let xs = [1]\n    print(xs[5])\n")
        self.assertEqual(code, 1)
        self.assertIn("ligne 3", err)
        self.assertIn("hors limites", err)
        code, _, err = run("fn main():\n    let z = 0\n    print(1 / z)\n")
        self.assertIn("division par zero", err)
        code, _, err = run('fn main():\n    assert(1 > 2, "maths")\n')
        self.assertIn("maths", err)


class Errors(unittest.TestCase):
    def has(self, src, fragment):
        msgs = errors(src)
        self.assertTrue(any(fragment in m for m in msgs), msgs)

    def test_missing_main(self):
        self.has("fn f():\n    pass\n", "main")

    def test_type_mismatch(self):
        self.has('fn main():\n    let x: int = "a"\n', "attendu int")

    def test_immutable(self):
        self.has("fn main():\n    let x = 1\n    x = 2\n", "immuable")

    def test_unknown_name(self):
        self.has("fn main():\n    print(y)\n", "nom inconnu 'y'")

    def test_bad_condition(self):
        self.has("fn main():\n    if 1:\n        pass\n", "bool")

    def test_wrong_arity(self):
        self.has("fn f(a: int) -> int:\n    return a\nfn main():\n    f(1, 2)\n", "attend 1 argument")

    def test_syntax_error_position(self):
        errs = diagnostics("fn main(:\n    pass\n")
        self.assertEqual((errs[0].line, errs[0].col), (1, 9))

    def test_multiple_errors_collected(self):
        self.assertGreaterEqual(len(errors("fn main():\n    print(a)\n    print(b)\n")), 2)

    def test_compile_failed(self):
        with self.assertRaises(CompileFailed):
            build("fn main():\n    print(x)\n", "/tmp/never")


class Examples(unittest.TestCase):
    def test_examples_compile(self):
        root = os.path.join(os.path.dirname(__file__), "..", "examples")
        for name in sorted(os.listdir(root)):
            if name.endswith(".vy"):
                with self.subTest(name), open(os.path.join(root, name), encoding="utf-8") as f:
                    self.assertEqual(diagnostics(f.read()), [])


if __name__ == "__main__":
    unittest.main()
