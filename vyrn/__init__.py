"""Vyrn — un langage à la syntaxe de Python, compilé en C natif."""
__version__ = "0.1.0"

from .compiler import CompileFailed, build, diagnostics, to_c  # noqa: E402,F401
