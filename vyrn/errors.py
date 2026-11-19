class VyrnError(Exception):
    """Erreur de compilation localisée (ligne/colonne commencent à 1)."""

    def __init__(self, msg, line=0, col=0):
        super().__init__(msg)
        self.msg = msg
        self.line = line
        self.col = col

    def format(self, filename="<source>", src=None):
        out = f"{filename}:{self.line}:{self.col}: erreur: {self.msg}"
        if src is not None and self.line > 0:
            lines = src.splitlines()
            if self.line <= len(lines):
                text = lines[self.line - 1]
                out += f"\n  {self.line:>4} | {text}\n       | {' ' * max(0, self.col - 1)}^"
        return out

    def to_dict(self):
        return {"message": self.msg, "line": self.line, "col": self.col}
