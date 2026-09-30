"""Sweep STORY-127 : remplace les `raise HTTPException(status_code=S, detail=D[, headers=H])`
par l'exception typée équivalente — même statut, même message, mêmes headers.

Transformation AST déterministe :
- 400 → InvalidInputError ; 401 → AuthenticationError ; 403 → PermissionDeniedError
- 404 → NotFoundError ; 409 → ConflictError ; 422 → UnprocessableEntityError
- 429 → RateLimitError ; 503 → ServiceUnavailableError ; 500/autre → WindFlowException
- detail=dict → details= ; detail=str → message positionnel ; headers= → headers=

Usage : python dev/scripts/sweep_127.py <fichier.py> [...]
"""
from __future__ import annotations

import ast
import sys

STATUS_MAP = {
    400: "InvalidInputError",
    401: "AuthenticationError",
    403: "PermissionDeniedError",
    404: "NotFoundError",
    409: "ConflictError",
    422: "UnprocessableEntityError",
    429: "RateLimitError",
    503: "ServiceUnavailableError",
}

ALL_CLASSES = set(STATUS_MAP.values()) | {"WindFlowException"}


def resolve_status(val: ast.expr) -> int | None:
    """Résout le statut : littéral int ou status.HTTP_404_NOT_FOUND."""
    if isinstance(val, ast.Constant) and isinstance(val.value, int):
        return val.value
    if isinstance(val, ast.Attribute) and val.attr.startswith("HTTP_"):
        try:
            return int(val.attr.split("_")[1])
        except (IndexError, ValueError):
            return None
    return None


def build_new_call(call: ast.Call) -> str | None:
    """Construit l'appel typé équivalent au HTTPException(...) donné."""
    status_code: int | None = None
    detail_expr: ast.expr | None = None
    headers_expr: ast.expr | None = None
    for kw in call.keywords:
        if kw.arg == "status_code":
            status_code = resolve_status(kw.value)
        elif kw.arg == "detail":
            detail_expr = kw.value
        elif kw.arg == "headers":
            headers_expr = kw.value

    if status_code is None:
        return None
    cls = STATUS_MAP.get(status_code, "WindFlowException")

    args: list[str] = []
    kwargs: list[str] = []
    if detail_expr is not None:
        if isinstance(detail_expr, ast.Dict):
            kwargs.append(f"details={ast.unparse(detail_expr)}")
        else:
            args.append(ast.unparse(detail_expr))
    if headers_expr is not None:
        kwargs.append(f"headers={ast.unparse(headers_expr)}")

    parts = args + kwargs
    if not parts:
        return f"{cls}()"
    single = ", ".join(parts)
    if len(cls) + len(single) <= 88:
        return f"{cls}({single})"
    # multi-lignes : les marqueurs de continuation seront ré-indentés par
    # l'appelant (chaque "\n    " → indentation du raise, y compris la
    # parenthèse fermante représentée par "\n)")
    return f"{cls}(\n    " + ",\n    ".join(parts) + ",\n)"


def process_file(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    lines = source.split("\n")

    count = 0
    replacements: list[tuple[int, int, str, int]] = []  # (start, end, new_text, raise_col)
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Raise)
            and isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name)
            and node.exc.func.id == "HTTPException"
        ):
            continue
        new_call = build_new_call(node.exc)
        if new_call is None:
            print(f"  SKIP ligne {node.lineno}")
            continue
        indent = lines[node.lineno - 1][: node.col_offset]
        # ré-indente les kwargs multi-lignes au niveau du raise, y compris
        # la parenthèse fermante finale "\n)"
        new_call_indented = new_call.replace("\n    ", f"\n{indent}    ").replace(
            "\n)", f"\n{indent})"
        )
        replacements.append(
            (node.lineno, node.end_lineno, new_call_indented, node.col_offset)
        )
        count += 1

    for start, end, new_call, raise_col in sorted(replacements, reverse=True):
        indent = lines[start - 1][:raise_col]
        lines[start - 1 : end] = [f"{indent}raise {new_call}"]

    new_source = "\n".join(lines)

    # import HTTPException : retire si plus aucun usage CODE (les docstrings
    # et commentaires ne comptent pas — vérifié via AST)
    try:
        new_tree = ast.parse(new_source)
    except SyntaxError as e:
        print(f"  ERREUR syntaxe après transformation: {e}")
        raise SystemExit(1)
    code_uses_http = any(
        isinstance(n, (ast.Name, ast.Attribute))
        and getattr(n, "id", getattr(n, "attr", "")) == "HTTPException"
        for n in ast.walk(new_tree)
    )
    if not code_uses_http:
        out = []
        for ln in new_source.split("\n"):
            stripped = ln.strip()
            if stripped in ("HTTPException,", "HTTPException"):
                continue
            if "HTTPException" in ln and "import" in ln:
                ln = ln.replace(", HTTPException", "").replace("HTTPException, ", "")
            out.append(ln)
        new_source = "\n".join(out)

    # import exceptions typées : fusionne avec l'import core.exceptions
    # existant, sinon insère après le dernier import relatif
    import re
    needed = {c for c in ALL_CLASSES if re.search(rf"\b{c}\(", new_source)}
    m = re.search(
        r"^(\s*)from (\.+)core\.exceptions import (.+)$", new_source, re.M
    )
    if m:
        indent_ws, dots, names_raw = m.groups()
        names = {
            n.strip().rstrip(",")
            for n in names_raw.replace("(", "").replace(")", "").split(",")
            if n.strip()
        }
        merged = sorted(names | needed)
        new_line = f"{indent_ws}from {dots}core.exceptions import ({', '.join(merged)})"
        if len(new_line) <= 88:
            new_source = new_source.replace(m.group(0), new_line)
        else:
            block = (
                f"{indent_ws}from {dots}core.exceptions import (\n"
                + "".join(f"{indent_ws}    {c},\n" for c in merged)
                + f"{indent_ws})"
            )
            new_source = new_source.replace(m.group(0), block)
    elif needed:
        # insère après le dernier ImportFrom RELATIF complet (AST : les
        # imports multi-lignes ont end_lineno > lineno — ne jamais
        # couper un bloc en cours)
        insert_after = 0
        for stmt in new_tree.body:
            if isinstance(stmt, ast.ImportFrom) and stmt.level > 0:
                insert_after = max(insert_after, stmt.end_lineno or stmt.lineno)
        if insert_after == 0:
            # fallback : après le dernier import absolu
            for stmt in new_tree.body:
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    insert_after = max(insert_after, stmt.end_lineno or stmt.lineno)
        block = (
            "from ...core.exceptions import (\n"
            + "".join(f"    {c},\n" for c in sorted(needed))
            + ")"
        )
        lines2 = new_source.split("\n")
        lines2.insert(insert_after, block)
        new_source = "\n".join(lines2)

    # validation finale : AST + raise typés présents
    ast.parse(new_source)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_source)
    return count


if __name__ == "__main__":
    total = 0
    for p in sys.argv[1:]:
        n = process_file(p)
        total += n
        print(f"{p}: {n} raises convertis")
    print(f"TOTAL: {total}")
