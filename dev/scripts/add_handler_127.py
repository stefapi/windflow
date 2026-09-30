"""Ajoute l'enregistrement du handler WindFlowException aux apps de test
minimales des tests docker (STORY-127 — divergence documentée : les routers
lèvent désormais des exceptions typées ; l'app de test doit porter le même
handler que app.main pour les convertir en réponses HTTP).

- ajoute les imports module-level (une seule fois) ;
- insère après chaque `X = FastAPI()` :
  `X.add_exception_handler(WindFlowException, windflow_exception_handler)`.
"""
import re
import sys

IMPORTS = (
    "from app.core.exceptions import WindFlowException\n"
    "from app.middleware.error_handler import windflow_exception_handler\n"
)

CALL = "{var}.add_exception_handler(WindFlowException, windflow_exception_handler)"


def process(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    out = []
    count = 0
    for ln in lines:
        out.append(ln)
        m = re.match(r"^(\s*)(\w+) = FastAPI\(\)\n$", ln)
        if not m:
            continue
        indent, var = m.groups()
        out.append(
            f"{indent}# STORY-127 : exceptions typées → handler global requis\n"
            f"{indent}{CALL.format(var=var)}\n"
        )
        count += 1

    if count and IMPORTS not in "".join(out):
        # insère les imports après le dernier import module-level existant
        insert_at = 0
        for i, ln in enumerate(out):
            if ln.startswith(("import ", "from ")) and not ln.startswith(("    ", "\t")):
                insert_at = i + 1
        out.insert(insert_at, IMPORTS)

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)
    return count


if __name__ == "__main__":
    total = 0
    for p in sys.argv[1:]:
        n = process(p)
        total += n
        print(f"{p}: {n} apps")
    print(f"TOTAL: {total}")
